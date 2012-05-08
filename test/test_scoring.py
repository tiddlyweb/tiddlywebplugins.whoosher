
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


def test_scoring():
    """title is more imporant than tags is more important than text"""
    store.put(Bag('place'))

    tiddler = Tiddler('test', 'place')
    tiddler.tags = ['apple']
    tiddler.text = 'orange'
    store.put(tiddler)

    tiddler = Tiddler('apple', 'place')
    tiddler.tags = ['orange']
    tiddler.text = 'test'
    store.put(tiddler)

    tiddler = Tiddler('orange', 'place')
    tiddler.tags = ['test']
    tiddler.text = 'apple'
    store.put(tiddler)

    tiddlers = list(search(config, 'test'))

    assert ['test', 'orange', 'apple'] == [tiddler['id'].split(':', 2)[1]
            for tiddler in tiddlers]
