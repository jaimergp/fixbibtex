#!/usr/bin/env python

"""
BibTeX fixer
------------

Fix your .bib BibTex files automatically

This script will connect to Crossref's API and retrieve
missing details in your bib files.

Set CROSSREF_MAILTO env var to your mail address to
gain access to a priority queue.

It requires `pybtex`, `habanero`, and `tqdm`:

    pip install pybtex habanero tqdm

TODO
.....

- String distance comparison to see if the entry matched
  in Crossref is not correct
"""

from __future__ import print_function
import os
import sys
from copy import copy, deepcopy
from time import sleep
import asyncio
import concurrent.futures
from difflib import SequenceMatcher
from tqdm import tqdm
from pybtex.database import parse_file as parse_bibfile, Person
from habanero import Crossref
cr = Crossref(mailto=os.environ.get('CROSSREF_MAILTO'))

MAX_POOL_WORKERS = int(os.environ.get('FIXBIBTEX_WORKERS', '5'))

async def fix_bibtex(path):
    bib = parse_bibfile(path)
    futures = []
    loop = asyncio.get_event_loop()
    pbar = tqdm(total=len(bib.entries), leave=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_POOL_WORKERS) as executor:
        for key, entry in bib.entries.items():
            futures.append(loop.run_in_executor(executor, find_crossref, (entry, key, pbar)))
        for result in await asyncio.gather(*futures):
            if result is None:
                continue
            key, entry, ref = result
            if not ref:
                continue
            doi_in_bibtex = entry.fields.get('doi', '')
            title_in_bibtex = entry.fields.get('title', '')
            new_entry = update_entry_from_crossref(ref, entry)
            if getattr(new_entry, 'similarity', 0) < 0.75:  # Fallback with DOI
                print('! `{}` has low similarity ({:.2f})...'.format(key, new_entry.similarity))
                if doi_in_bibtex:
                    print('  Searching for DOI `{}`...'.format(doi_in_bibtex))
                    fb_ref = find_crossref_doi(doi_in_bibtex)
                    if fb_ref:
                        new_entry_fb = update_entry_from_crossref(fb_ref, entry)
                        similarity = similar(title_in_bibtex, new_entry_fb.fields['title'])
                        if similarity <  0.75:
                            print('  Not fixed... :( Similarity with DOI: {:.2f}'.format(similarity))
                        else:
                            print('  Fixed! Similarity with DOI: {:.2f}'.format(similarity))
                            new_entry = new_entry_fb
                    else:
                        print('  Wrong DOI!')
                else:
                    print('  No DOI available for fallback search.')
            bib.entries[key] = new_entry
        pbar.close()
    return bib


def find_crossref(args):
    sleep(0.1)
    entry, key, pbar = args
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
        pbar.update()
    except Exception as e:
        print('! Could not fetch', key, 'due to error:', e)
        pbar.update()
        return None, None, None
    if ref['message']['items']:
        first = ref['message']['items'][0]
        return key, entry, first


def find_crossref_doi(doi):
    sleep(0.1)
    if not doi:
        return
    try:
        ref = cr.works(ids=doi)
    except Exception as e:
        return
    else:
        if ref['status'] == 'ok' and ref['message']:
            return ref['message']


def update_entry_from_crossref(ref, entry):
    entry = copy(entry)
    if 'container-title' in ref:
        entry.fields['journal'] = ref['container-title'][0]
    if 'issue' in ref:
        entry.fields['number'] = str(ref['issue'])
    if 'page' in ref:
        entry.fields['pages'] = str(ref['page']).replace('-', '--')
    if 'title' in ref:
        entry.similarity  = similar(entry.fields['title'], ref['title'][0])
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
    if 'author' in ref:
        persons = {'author': []}
        for author in ref['author']:
            if 'family' in author:
                authorname = author['family']
                if 'given' in author:
                    authorname += ', ' + author['given']
                person = Person(authorname)
            else:
                # Author is not a person but an organization or similar
                person = Person(author['name'])
            persons['author'].append(person)
        if len(entry.persons.get('author', [])) <= len(persons['author']):
            entry.persons = persons
    entry.relevance = ref.get('score', 100)
    return entry


def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main(path):
    loop = asyncio.get_event_loop()
    newbib = loop.run_until_complete(fix_bibtex(path))
    basename, ext = os.path.splitext(path)
    newbib_path = '{}.new{}'.format(basename, ext)
    newbib.to_file(newbib_path)
    oldbib_path = '{}.old{}'.format(basename, ext)
    parse_bibfile(path).to_file(oldbib_path)

    print('Patched file:', newbib_path)
    print('Original file:', oldbib_path)
    print('Use a diff tool to see changes:')
    print('   colordiff', oldbib_path, newbib_path)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python fixbibtex.py your.bib')
    main(sys.argv[1])
