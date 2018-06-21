#!/usr/bin/env python

"""
BibTeX fixer
------------

Fix your .bib BibTex files automatically

This script will connect to Crossref's API and retrieve
missing details in your bib files.

Set CROSSREF_MAILTO env var to your mail address to
gain access to a priority queue.

It requires `pybtex` and `habanero`:

    pip install pybtex habanero

TODO
.....

- Speed could be greatly enhanced with async programming.
"""

from __future__ import print_function
import os
import sys
from copy import deepcopy
from time import sleep
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, *args, **kwargs):
        return it
from pybtex.database import parse_file as parse_bibfile, Person
from habanero import Crossref
cr = Crossref(mailto=os.environ.get('CROSSREF_MAILTO'))


def fix_bibtex(path):
    bib = parse_bibfile(path)
    newbib = deepcopy(bib)
    for key, entry in tqdm(bib.entries.items(), unit='entry'):
        ref = find_crossref(entry, key)
        if not ref:
            continue
        new_entry = new_entry_from_crossref(ref, entry)
        newbib.entries[key] = new_entry
        sleep(0.1)
    return bib, newbib


def find_crossref(entry, key):
    query = entry.fields['title']
    filters = {}
    if 'issn' in entry.fields:
        filters['issn'] = entry.fields['issn']
    if 'year' in entry.fields:
        filters['from-pub-date'] = entry.fields['year']
    if 'author' in entry.persons:  # add last author to query
        query += ' ' + str(entry.persons['author'][-1])
    try:
        ref = cr.works(query=query, filter=filters)
    except Exception as e:
        print('! Could not fetch', key, 'due to error:', e)
        return
    first = ref['message']['items'][0]
    if first['score'] < 30:
        print('! Warning, low search score for entry with key', key)
    return first


def new_entry_from_crossref(ref, old_entry):
    entry = deepcopy(old_entry)
    if 'container-title' in ref:
        entry.fields['journal'] = ref['container-title'][0]
    if 'issue' in ref:
        entry.fields['number'] = str(ref['issue'])
    if 'page' in ref:
        entry.fields['pages'] = str(ref['page']).replace('-', '--')
    if 'title' in ref:
        entry.fields['title'] = ref['title'][0]
    if 'URL' in ref:
        entry.fields['url'] = ref['URL']
    if 'volume' in ref:
        entry.fields['volume'] = str(ref['volume'])
    if 'issued' in ref:
        entry.fields['year'] = str(ref['issued']['date-parts'][0][0])
    if 'DOI' in ref:
        entry.fields['doi'] = ref['DOI']
    if 'ISSN' in ref:
        entry.fields['issn'] = ref['ISSN'][0]
    persons = {'author': []}
    for author in ref['author']:
        person = Person('{}, {}'.format(author['family'], author['given']))
        persons['author'].append(person)
    entry.persons = persons
    return entry


def main(path):
    oldbib, newbib = fix_bibtex(path)
    basename, ext = os.path.splitext(path)
    oldbib_path = '{}.old{}'.format(basename, ext)
    newbib_path = '{}.new{}'.format(basename, ext)
    oldbib.to_file(oldbib_path)
    newbib.to_file(newbib_path)

    print('Patched file has been rewritten in', newbib_path)
    print('Original file has been rewritten in', oldbib_path)
    print('Use a diff tool to evaluate changes, like:')
    print('   colordiff', oldbib_path, newbib_path)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python fixbibtex.py your.bib')
    main(sys.argv[1])

