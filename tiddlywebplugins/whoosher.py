"""
Whoosh based index/search system for TiddlyWeb.

whoosher is a plugin for tiddlyweb. To use, update
tiddlywebconfig.py to include 'tiddlywebplugins.whoosher'
in system_plugins and twanager_plugins:

    config = {
            'twanager_plugins': ['tiddlywebplugins.whoosher'],
            'system_plugins': ['tiddlywebplugins.whoosher'],
    }

Use 'twanager wreindex' to establish an index for an existing
store. For very large stores it is necessary to index in chunks,
do this by providing an optional prefix. If the tiddlers to be
indexed do not start with prefix, they will not be indexed. For
example 'twanager wreindex a' will index all tiddlers whose
title starts with 'a' (case sensitive!).

Over time the index files will be get lumpy. To optimize them,
you may run 'twanager woptimize'. This will lock the index so it
is best to do while the instance server is off.

By default the index is located in a directory called 'indexdir'
off the main instance directory. This may be changed by setting

        'wsearch.indexdir': 'indexdir',

to an absolute or relative path.

Whoosh uses a schema to describe the structure of the index. whoosher
has a reasonable default for this in its static variable SEARCH_DEFAULTS.
That default does not index fields. If there are tiddlers fields that need
to be indexed for a particular installation or application, wsearch.schema
and wsearch.default_fields can be set. _Read the code_ to understand how
these can be used.
"""
import os

import logging
import time

from traceback import format_exc

from whoosh.index import exists_in, create_in, open_dir
from whoosh.fields import Schema, ID, KEYWORD, TEXT
from whoosh.qparser import MultifieldParser, QueryParser
from whoosh.store import LockError
from whoosh.qparser.common import QueryParserError

from tiddlywebplugins.utils import get_store

from tiddlyweb.filters import FilterIndexRefused
from tiddlyweb.manage import make_command
from tiddlyweb.util import binary_tiddler
from tiddlyweb.store import NoTiddlerError
from tiddlyweb.web.http import HTTP400

import tiddlyweb.web.handler.search

from tiddlyweb.model.tiddler import Tiddler

from tiddlyweb.store import HOOKS

IGNORE_PARAMS = []

SEARCH_DEFAULTS = {
        'wsearch.schema': {'title': TEXT,
            'id': ID(stored=True, unique=True),
            'ftitle': ID,
            'bag': TEXT,
            'fbag': ID,
            'text': TEXT,
            'modified': ID,
            'modifier': ID,
            'created': ID,
            'tags': KEYWORD(scorable=True, lowercase=True),
            'field_1': TEXT,
            'field_2': TEXT},
        'wsearch.indexdir': 'indexdir',
        'wsearch.default_fields': ['text', 'title'],
        }


def init(config):
    if __name__ not in config.get('beanstalk.listeners', []):
        # tiddler_change handles both put and deleted tiddlers
        HOOKS['tiddler']['put'].append(_tiddler_change_handler)
        HOOKS['tiddler']['delete'].append(_tiddler_change_handler)

    @make_command()
    def wsearch(args):
        """Search the whoosh index for provided terms."""
        query = ' '.join(args)
        ids = search(config, query)
        for result in ids:
            bag, title = result['id'].split(':', 1)
            print "%s:%s" % (bag, title)

    @make_command()
    def wreindex(args):
        """Rebuild the entire whoosh index."""
        try:
            prefix = args[0]
        except IndexError:
            prefix = None
        store = get_store(config)
        schema = config.get('wsearch.schema',
                SEARCH_DEFAULTS['wsearch.schema'])
        if __name__ in config.get('beanstalk.listeners', []):
            _reindex_async(config)
        else:
            for bag in store.list_bags():
                bag = store.get(bag)
                writer = get_writer(config)
                if writer:
                    try:
                        try:
                            tiddlers = bag.get_tiddlers()
                        except AttributeError:
                            tiddlers = store.list_bag_tiddlers(bag)
                        for tiddler in tiddlers:
                            if prefix and not tiddler.title.startswith(prefix):
                                continue
                            tiddler = store.get(tiddler)
                            index_tiddler(tiddler, schema, writer)
                        writer.commit()
                    except:
                        logging.debug('whoosher: exception while indexing: %s',
                                format_exc())
                        writer.cancel()
                else:
                    logging.debug('whoosher: unable to get writer '
                            '(locked) for %s', bag.name)

    @make_command()
    def woptimize(args):
        """Optimize the index by collapsing files."""
        index = get_index(config)
        index.optimize()


def whoosh_search(environ):
    """
    Handle incoming /search?q=<query> and
    return the found tiddlers.
    """
    search_query = query_dict_to_search_string(
            environ['tiddlyweb.query']) or ''
    if not search_query:
        raise HTTP400('query string required')
    try:
        results = search(environ['tiddlyweb.config'], search_query)
    except QueryParserError, exc:
        raise HTTP400('malformed query string: %s' % exc)
    tiddlers = []
    for result in results:
        bag, title = result['id'].split(':', 1)
        tiddler = Tiddler(title, bag)
        tiddlers.append(tiddler)
    return tiddlers

tiddlyweb.web.handler.search.get_tiddlers = whoosh_search


def index_query(environ, **kwargs):
    """
    Return a generator of tiddlers that match
    the provided arguments.
    """
    config = environ['tiddlyweb.config']
    store = environ['tiddlyweb.store']
    query_parts = []
    for field, value in kwargs.items():
        if field == 'tag':
            field = 'tags'
        query_parts.append('%s:"%s"' % (field, value))
    query_string = ' '.join(query_parts)

    try:
        schema = config.get('wsearch.schema',
                SEARCH_DEFAULTS['wsearch.schema'])
        searcher = get_searcher(config)
        parser = QueryParser('text', schema=Schema(**schema))
        query = parser.parse(query_string)
        logging.debug('whoosher: filter index query parsed to %s', query)
        results = searcher.search(query)
    except:
        logging.debug('whoosher: exception during index_query: %s',
                format_exc())
        raise FilterIndexRefused

    def tiddler_from_result(result):
        bag, title = result['id'].split(':', 1)
        tiddler = Tiddler(title, bag)
        return store.get(tiddler)

    for result in results:
        yield tiddler_from_result(result)

    searcher.close()
    return


def get_index(config):
    """
    Return the current index object if there is one.
    If not attempt to open the index in wsearch.indexdir.
    If there isn't one in the dir, create one. If there is
    not dir, create the dir.
    """
    index_dir = config.get('wsearch.indexdir',
            SEARCH_DEFAULTS['wsearch.indexdir'])
    if not os.path.isabs(index_dir):
        index_dir = os.path.join(config.get('root_dir', ''), index_dir)

    if exists_in(index_dir):
        # For now don't trap exceptions, as we don't know what they
        # will be and so we want them to raise destructively.
        index = open_dir(index_dir)
    else:
        try:
            os.mkdir(index_dir)
        except OSError:
            pass
        schema = config.get('wsearch.schema',
                SEARCH_DEFAULTS['wsearch.schema'])
        index = create_in(index_dir, Schema(**schema))
    return index


def get_writer(config):
    """
    Return a writer based on config insructions.
    """
    writer = None
    attempts = 0
    limit = config.get('wsearch.lockattempts', 5)
    try:
        while writer == None and attempts < limit:
            attempts += 1
            try:
                writer = get_index(config).writer()
            except LockError:
                time.sleep(.1)
    except:
        logging.debug('whoosher: exception getting writer: %s',
                format_exc())
    return writer


def get_searcher(config):
    """
    Return a searcher based on config instructions.
    """
    return get_index(config).searcher()


def get_parser(config):
    schema = config.get('wsearch.schema', SEARCH_DEFAULTS['wsearch.schema'])
    default_fields = config.get('wsearch.default_fields',
            SEARCH_DEFAULTS['wsearch.default_fields'])
    return MultifieldParser(default_fields, schema=Schema(**schema))


def query_parse(config, query):
    parser = get_parser(config)
    return parser.parse(query)


def search(config, query):
    """
    Perform a search, returning a whoosh result
    set.
    """
    searcher = get_searcher(config)
    limit = config.get('wsearch.results_limit', 51)
    query = query_parse(config, unicode(query))
    logging.debug('whoosher: query parsed to %s', query)
    results = searcher.search(query, limit=limit)
    return results


def delete_tiddler(tiddler, writer):
    """
    Delete the named tiddler from the index.
    """
    logging.debug('whoosher: deleting tiddler: %s:%s', tiddler.bag,
            tiddler.title)
    writer.delete_by_term('id', _tiddler_id(tiddler))


def index_tiddler(tiddler, schema, writer):
    """
    Index the given tiddler with the given schema using
    the provided writer.

    The schema dict is read to find attributes and fields
    on the tiddler.
    """
    if binary_tiddler(tiddler):
        return
    logging.debug('whoosher: indexing tiddler: %s:%s', tiddler.bag,
            tiddler.title)
    data = {}
    for key in schema:
        try:
            try:
                value = getattr(tiddler, key)
            except AttributeError:
                value = tiddler.fields[key]
            try:
                data[key] = unicode(value.lower())
            except AttributeError:
                value = ','.join(value)
                data[key] = unicode(value.lower())
        except (KeyError, TypeError), exc:
            pass
        except UnicodeDecodeError, exc:
            pass
    data['id'] = _tiddler_id(tiddler)
    data['ftitle'] = tiddler.title
    data['fbag'] = tiddler.bag
    writer.update_document(**data)


def _tiddler_id(tiddler):
    return '%s:%s' % (tiddler.bag, tiddler.title)


def _tiddler_change_handler(storage, tiddler):
    schema = storage.environ['tiddlyweb.config'].get('wsearch.schema',
            SEARCH_DEFAULTS['wsearch.schema'])
    writer = get_writer(storage.environ['tiddlyweb.config'])
    store = storage.environ.get('tiddlyweb.store',
            get_store(storage.environ['tiddlyweb.config']))
    if writer:
        try:
            try:
                store.get(Tiddler(tiddler.title, tiddler.bag))
                index_tiddler(tiddler, schema, writer)
            except NoTiddlerError:
                delete_tiddler(tiddler, writer)
            writer.commit()
        except:
            logging.debug('whoosher: exception while indexing: %s',
                    format_exc())
            writer.cancel()
    else:
        logging.debug('whoosher: unable to get writer (locked) for %s:%s',
                tiddler.bag, tiddler.title)


def query_dict_to_search_string(query_dict):
    terms = []
    while query_dict:
        keys = query_dict.keys()
        key = keys.pop()
        values = query_dict[key]
        del query_dict[key]
        if key in IGNORE_PARAMS:
            continue

        if key == 'q':
            terms.extend([value for value in values])
        else:
            if key.endswith('_field'):
                prefix = key.rsplit('_', 1)[0]
                value_key = '%s_value' % prefix
                key = values[0].lower().replace(' ', '_')
                try:
                    values = query_dict[value_key]
                    del query_dict[value_key]
                except KeyError:
                    values = []
                if not values:
                    continue
            elif key.endswith('_value'):
                prefix = key.rsplit('_', 1)[0]
                field_key = '%s_field' % prefix
                try:
                    key = query_dict[field_key][0].lower().replace(' ', '_')
                    del query_dict[field_key]
                except KeyError:
                    key = ''
                if not key:
                    continue

            if key == 'avid' and not values[0].isdigit():
                continue

            for value in values:
                if ' ' in key or ' ' in value:
                    terms.append('%s:"%s"' % (key.lower(), value.lower()))
                else:
                    terms.append('%s:%s' % (key.lower(), value.lower()))
    return ' '.join(terms)


def _reindex_async(config):
    from tiddlywebplugins.dispatcher.listener import (DEFAULT_BEANSTALK_HOST,
            DEFAULT_BEANSTALK_PORT, BODY_SEPARATOR)
    import beanstalkc
    beanstalk_host = config.get('beanstalk.host', DEFAULT_BEANSTALK_HOST)
    beanstalk_port = config.get('beanstalk.port', DEFAULT_BEANSTALK_PORT)
    beanstalk = beanstalkc.Connection(host=beanstalk_host,
            port=beanstalk_port)
    username = 'admin'
    beanstalk.use('index')
    store = get_store(config)

    for bag in store.list_bags():
        bag = store.get(bag)
        try:
            tiddlers = bag.get_tiddlers()
        except AttributeError:
            tiddlers = store.list_bag_tiddlers(bag)
        for tiddler in tiddlers:
            tiddler = store.get(tiddler)
            data = BODY_SEPARATOR.join([username, tiddler.bag, tiddler.title,
                str(tiddler.revision)])
            try:
                beanstalk.put(data.encode('UTF-8'))
            except beanstalkc.SocketError, exc:
                logging.error('unable to write to beanstalkd for %s:%s: %s',
                        tiddler.bag, tiddler.title, exc)


try:
    from tiddlywebplugins.dispatcher.listener import Listener as BaseListener

    class Listener(BaseListener):

        TUBE = 'index'
        STORE = None

        def _act(self, job):
            config = self.config
            if not self.STORE:
                self.STORE = get_store(config)
            info = self._unpack(job)
            schema = config.get('wsearch.schema',
                    SEARCH_DEFAULTS['wsearch.schema'])
            tiddler = Tiddler(info['tiddler'], info['bag'])
            writer = get_writer(config)
            if writer:
                try:
                    try:
                        tiddler = self.STORE.get(tiddler)
                        index_tiddler(tiddler, schema, writer)
                    except NoTiddlerError:
                        delete_tiddler(tiddler, writer)
                    writer.commit()
                except:
                    logging.debug('whoosher: exception while indexing: %s',
                            format_exc())
                    writer.cancel()
            else:
                logging.debug('whoosher: unable to get writer (locked)'
                        'for %s:%s', tiddler.bag, tiddler.title)

except ImportError:
    pass
