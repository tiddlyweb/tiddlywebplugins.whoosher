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


def test_boolean():
    """
    We expect a default AND but can do OR.
    """

    store.put(Bag('mybag'))

    tiddlera = Tiddler('a', 'mybag')
    tiddlera.tags = ['one', '@two']
    store.put(tiddlera)

    tiddlerb = Tiddler('b', 'mybag')
    tiddlerb.tags = ['@two', 'three']
    store.put(tiddlerb)

    tiddlerc = Tiddler('c', 'mybag')
    tiddlerc.tags = ['three', 'four']
    store.put(tiddlerc)

    tiddlers = list(search(config, 'tags:one'))
    assert len(tiddlers) == 1

    tiddlers = list(search(config, 'tags:@two'))
    assert len(tiddlers) == 2

    tiddlers = list(search(config, 'tags:one tags:@two'))
    assert len(tiddlers) == 1

    tiddlers = list(search(config, 'tags:one tags:four'))
    assert len(tiddlers) == 0

    tiddlers = list(search(config, 'tags:one OR tags:four'))
    assert len(tiddlers) == 2
