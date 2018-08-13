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
import argparse
import asyncio
import concurrent.futures
from difflib import SequenceMatcher
from tqdm import tqdm
from pybtex.errors import set_strict_mode
from pybtex.database import parse_file as parse_bibfile, Person
from habanero import Crossref
cr = Crossref(mailto=os.environ.get('CROSSREF_MAILTO'))

MAX_POOL_WORKERS = int(os.environ.get('FIXBIBTEX_WORKERS', '5'))
COLORS = {
    'END': '\33[0m',
    'BOLD': '\33[1m',
    'ITALIC': '\33[3m',
    'URL': '\33[4m',
    'BLINK': '\33[5m',
    'BLINK2': '\33[6m',
    'SELECTED': '\33[7m',

    'BLACK': '\33[30m',
    'RED': '\33[31m',
    'GREEN': '\33[32m',
    'YELLOW': '\33[33m',
    'BLUE': '\33[34m',
    'VIOLET': '\33[35m',
    'BEIGE': '\33[36m',
    'WHITE': '\33[37m',

    'BLACKBG': '\33[40m',
    'REDBG': '\33[41m',
    'GREENBG': '\33[42m',
    'YELLOWBG': '\33[43m',
    'BLUEBG': '\33[44m',
    'VIOLETBG': '\33[45m',
    'BEIGEBG': '\33[46m',
    'WHITEBG': '\33[47m',

    'GREY': '\33[90m',
    'RED2': '\33[91m',
    'GREEN2': '\33[92m',
    'YELLOW2': '\33[93m',
    'BLUE2': '\33[94m',
    'VIOLET2': '\33[95m',
    'BEIGE2': '\33[96m',
    'WHITE2': '\33[97m',

    'GREYBG': '\33[100m',
    'REDBG2': '\33[101m',
    'GREENBG2': '\33[102m',
    'YELLOWBG2': '\33[103m',
    'BLUEBG2': '\33[104m',
    'VIOLETBG2': '\33[105m',
    'BEIGEBG2': '\33[106m',
    'WHITEBG2': '\33[107m',
}


def cprint(*args, color=None, **kwargs):
    if color and color.upper() in COLORS:
        print(COLORS[color.upper()], end='')
        end = kwargs.pop('end', '\n')
        print(*args, end='', **kwargs)
        print(COLORS['END'], end=end)
    else:
        print(*args, **kwargs)


async def fix_bibtex(path):
    bib = parse_bibfile(path)
    futures = []
    loop = asyncio.get_event_loop()
    non_article_keys = []
    pbar = tqdm(leave=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_POOL_WORKERS) as executor:
        for key, entry in bib.entries.items():
            if entry.type != 'article' or 'rxiv.org' in entry.fields.get('url', '') :  # skip books, chapters, etc (for now)
                non_article_keys.append(key)
                continue
            futures.append(loop.run_in_executor(executor, find_crossref, (entry, key, pbar)))
        pbar.total = len(futures)
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
                print('\n! `{}` has low similarity ({:.2f})...'.format(key, new_entry.similarity))
                if doi_in_bibtex:
                    print('  Searching for DOI `{}`...'.format(doi_in_bibtex))
                    fb_ref = find_crossref_doi(doi_in_bibtex)
                    if fb_ref:
                        new_entry_fb = update_entry_from_crossref(fb_ref, entry)
                        similarity = similar(title_in_bibtex, new_entry_fb.fields['title'])
                        if similarity <  0.75:
                            cprint('  Not fixed... :( Similarity with DOI: {:.2f}'.format(similarity), color='red')
                        else:
                            cprint('  Fixed! Similarity with DOI: {:.2f}'.format(similarity), color='green')
                            new_entry = new_entry_fb
                    else:
                        cprint('  Wrong DOI!', color='red')
                else:
                    cprint('  No DOI available for fallback search.', color='red')
            bib.entries[key] = new_entry
        pbar.close()
    if len(bib.entries) != len(futures):
        print('\n! Skipped', len(bib.entries) - len(futures),
              'non-article pieces (book chapters, pre-prints...):\n ',
              '\n  '.join(non_article_keys))
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
    if 'title' in ref and ref['title']:
        entry.similarity  = similar(entry.fields['title'], ref['title'][0])
        entry.fields['title'] = ref['title'][0]
    if 'URL' in ref:
        entry.fields['url'] = ref['URL']
    if 'volume' in ref:
        entry.fields['volume'] = str(ref['volume'])
    if 'published-print' in ref:  # prioritize print vs online
        entry.fields['year'] = str(ref['published-print']['date-parts'][0][0])
    elif 'published-online' in ref:
        entry.fields['year'] = str(ref['published-online']['date-parts'][0][0])
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


def main(path, strict=False):
    set_strict_mode(strict)
    loop = asyncio.get_event_loop()
    newbib = loop.run_until_complete(fix_bibtex(path))
    basename, ext = os.path.splitext(path)
    newbib_path = '{}.new{}'.format(basename, ext)
    newbib.to_file(newbib_path)
    oldbib_path = '{}.old{}'.format(basename, ext)
    parse_bibfile(path).to_file(oldbib_path)

    print('\nPatched file:', newbib_path)
    print('Original file:', oldbib_path)
    print('Use a diff tool to see changes:')
    print('   colordiff', oldbib_path, newbib_path)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', metavar='FILE', help="BibTex file")
    parser.add_argument('--strict', action='store_true', default=False,
                        help='Transforms warnings into errors (off by default).')
    args = parser.parse_args()
    main(args.path, args.strict)


if __name__ == '__main__':
    cli()
