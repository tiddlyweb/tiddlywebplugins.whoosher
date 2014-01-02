
import shutil

from tiddlyweb.config import config
from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler

from tiddlywebplugins.whoosher import init, search

from tiddlywebplugins.utils import get_store


def setup_module(module):
    try:
        shutil.rmtree('store')
    except:
        pass
    try:
        shutil.rmtree('indexdir')
    except:
        pass

    init(config)
    module.store = get_store(config)


def test_search_quoted_phrase():
    bag = Bag('bag1')
    store.put(bag)
    tiddler1 = Tiddler('tiddler1', 'bag1')
    tiddler1.text = 'There are five monkeys in this house'
    tiddler1.tags = ['oh', 'hai', 'you', 'five chimps']
    store.put(tiddler1)

    tiddlers = list(search(config, '"five monkeys"'))
    assert len(tiddlers) == 1

def test_search_unicode():
    bag = Bag(u'\u24b6')
    store.put(bag)
    tiddler1 = Tiddler(u'\u24b6', bag.name)
    tiddler1.text = u'oh \u24b6ss'
    store.put(tiddler1)

    tiddlers = list(search(config, u'\u24b6ss'))
    assert len(tiddlers) == 1
