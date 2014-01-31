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
    bag = Bag('somewhere')
    module.store.put(bag)


def test_tags():
    tiddler = Tiddler('hi', 'somewhere')
    tiddler.tags = ['alpha', 'beta', 'gamma']
    store.put(tiddler)

    tiddler = Tiddler('hi2', 'somewhere')
    tiddler.tags = ['alpha', 'gamma']
    store.put(tiddler)

    tiddlers1 = list(search(config, 'tags:beta'))
    tiddlers2 = list(search(config, 'tag:beta'))

    assert tiddlers1 == tiddlers2
    assert len(tiddlers1) == len(tiddlers2)
    assert len(tiddlers1) == 1

    tiddlers1 = list(search(config, 'tags:alpha'))
    tiddlers2 = list(search(config, 'tag:alpha'))

    assert tiddlers1 == tiddlers2
    assert len(tiddlers1) == len(tiddlers2)
    assert len(tiddlers1) == 2

    tiddlers1 = list(search(config, 'tags:beta OR tags:gamma'))
    tiddlers2 = list(search(config, 'tag:beta OR tag:gamma'))
    tiddlers3 = list(search(config, 'tag:beta OR tags:gamma'))

    assert tiddlers1 == tiddlers2
    assert tiddlers2 == tiddlers3
    assert len(tiddlers1) == len(tiddlers2)
    assert len(tiddlers2) == len(tiddlers3)
    assert len(tiddlers1) == 2

    tiddlers1 = list(search(config, 'tags:beta AND tags:gamma'))
    tiddlers2 = list(search(config, 'tag:beta AND tag:gamma'))
    tiddlers3 = list(search(config, 'tag:beta AND tags:gamma'))

    assert tiddlers1 == tiddlers2
    assert tiddlers2 == tiddlers3
    assert len(tiddlers1) == len(tiddlers2)
    assert len(tiddlers2) == len(tiddlers3)
    assert len(tiddlers1) == 1
