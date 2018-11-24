#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from setuptools import setup, find_packages
import os
import io
import sys


if sys.version_info < (3, 5):
    raise RuntimeError('fixbibtex requires Python 3.5+')


here = os.path.abspath(os.path.dirname(__file__))


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(os.path.join(here, filename), encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md')

setup(
    name='fixbibtex',
    version='0.1',
    url='https://github.com/jaimergp/fixbibtex',
    license='MIT',
    author='Jaime Rodríguez-Guerra',
    author_email='jaime.rogue@gmail.com',
    description='Use the Crossref API to fix BibTex Entries',
    long_description=long_description,
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Development Status :: 2 - Pre-Alpha',
        'Natural Language :: English',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
    ],
    install_requires='pybtex habanero tqdm'.split(),
    python_requires=">=3.5",
    entry_points='''
        [console_scripts]
        fixbibtex=fixbibtex:cli
        '''
    ,
)
