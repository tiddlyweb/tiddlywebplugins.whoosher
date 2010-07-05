
from tiddlyweb.config import config
from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler

from tiddlywebplugins.whoosher import init, search


init(config)


def test_search_unique():
    from tiddlyweb.store import Store
    environ = {'tiddlyweb.config': config}
    store = Store(config['server_store'][0], config['server_store'][1], environ)
    environ['tiddlyweb.store'] = store
    bag = Bag('bag1')
    store.put(bag)
    tiddler1 = Tiddler('tiddler1', 'bag1')
    tiddler1.text = 'catsdogshouses'
    store.put(tiddler1)

    tiddler2 = Tiddler('tiddler2', 'bag1')
    tiddler2.text = 'housesdogscats'
    store.put(tiddler2)

    print 'put the stuff'

    tiddlers = list(search(config, 'catsdogshouses'))

    print 'did a search'
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
