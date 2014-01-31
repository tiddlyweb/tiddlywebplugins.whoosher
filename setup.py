
import os
from setuptools import setup, find_packages

VERSION = '0.9.27'

setup(
        namespace_packages = ['tiddlywebplugins'],
        name = 'tiddlywebplugins.whoosher',
        version = VERSION,
        description = 'A TiddlyWeb plugin that provides an indexed search interface using Whoosh.',
        long_description=open(os.path.join(os.path.dirname(__file__), 'README')).read(),
        author = 'Chris Dent',
        url = 'http://pypi.python.org/pypi/tiddlywebplugins.whoosher',
        packages = find_packages(exclude=['test']),
        author_email = 'cdent@peermore.com',
        platforms = 'Posix; MacOS X; Windows',
        install_requires = ['setuptools',
            'tiddlyweb>=1.4.2',
            'httpexceptor',
            'tiddlywebplugins.utils',
            'Whoosh',
            ],
        zip_safe=False,
        )
