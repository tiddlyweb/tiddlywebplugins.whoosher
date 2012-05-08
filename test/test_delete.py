
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


def test_search_unique():
    bag = Bag('bag1')
    store.put(bag)
    tiddler1 = Tiddler('tiddler1', 'bag1')
    tiddler1.text = 'catsdogshouses'
    store.put(tiddler1)

    tiddler2 = Tiddler('tiddler2', 'bag1')
    tiddler2.text = 'housesdogscats'
    store.put(tiddler2)

    tiddlers = list(search(config, 'catsdogshouses'))

    assert len(tiddlers) == 1
    assert tiddlers[0]['id'] == 'bag1:tiddler1'

    tiddlers = list(search(config, 'housesdogscats'))
    assert len(tiddlers) == 1
    assert tiddlers[0]['id'] == 'bag1:tiddler2'

    store.delete(tiddler1)

    tiddlers = list(search(config, 'catsdogshouses'))
    assert len(tiddlers) == 0

    tiddlers = list(search(config, 'housesdogscats'))
    assert len(tiddlers) == 1
    assert tiddlers[0]['id'] == 'bag1:tiddler2'

    store.delete(tiddler2)

    tiddlers = list(search(config, 'housesdogscats'))
    assert len(tiddlers) == 0
