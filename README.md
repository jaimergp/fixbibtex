# BibTex fixer with Crossref API

Use the Crossref API to fix BibTex Entries.

# Installation

This script is still in a very early stage of development, but can be potentially useful in some cases. Definitely NOT for production! As a result, there is no PyPI entry (yet), but can be installed with `pip` via its repo URL:

```
pip install https://github.com/jaimergp/fixbibtex/archive/v0.1.zip
```

I will be tagging new releases as more features and fixes are added. There will be breaking changes, so do not trust the (pseudo)API until we reach `v1.0`.

## Requirements

`pip` will handle them, but in case you want to install them manually, `fixbibtex`  relies on:

- Python 3.5+. Needed for `async` features.
- `pybtex`: BibTeX parser and writer.
- `habanero`: CrossRef API.
- `tqdm`: Progress bar.


# Usage

After installation, a `fixbibtex` command will be available. Run it like this:

```
$> fixbibtex <your_references>.bib
```

Two `*.bib` files will be generated:

- `<your_references>.new.bib`: A new BibTeX database including the fixes.
- `<your_references>.old.bib`: A copy your original file with the same format rules as `*.new.bib` so you can `diff` them and compare changes easily.

I recommend using `code --diff *.old.bib *.new.bib` for a better experience, but you can use `colordiff` and similar tools as well.

## About CrossRef API usage

The excellent [CrossRef]() project offers it API free of charge for everybody, without keys, tokens, OAuth... It is truly mind-blowing! Such a good service must be respected, so please do not try to modify the code to overcome the limitations imposed. CrossRef devs are very nice, and if you voluntarily include your email address in the requests, they will grant you access to a priority queue. That way, if you accidentally misuse the service, they can notify you about the mistake.

Set an environment variable `CROSSREF_MAILTO` to a valid email address to use this feature with `fixbibtex`.

# How does it work?

`fixbibtex` will parse your `*.bib` file with `PybTeX`. Then, it will iterate over the entries performing the following checks:

1. Collect all the `article` entries, excluding pre-prints. We are not trying to amend books, chapters and other resources for now. (This will change in the future, though).
2. For each article, query CrossRef with the authors' last names and the article title, filtering by ISSN and publication date if available. If successful, update the original BibTeX entry with result.
3. Compare the original title with the updated title. If the similarity is below 0.75 and the DOI of the article is available, fallback to a DOI query to try to fix it.
4. If the DOI-provided title has a similarity above 0.75, update the entry with the new data. A green notice will be printed. If not, trust the original data in step 2, cross fingers and let the user figure it out. A red warning will be printed in that case.

The resulting entries will be written with PybTex in a new file, as explained above.

# A word of caution and next steps

IMPORTANT: In its current state, `fixbibtex` is far from perfect, so please review the changes it introduces before blindly applying the fixes in your LaTeX projects!

There are several ways it can be improved, though. Help is appreciated! Some ideas:

- Improve the search heuristics.
    + Decide which fields are more robust to guide the queries
    + Cross validate the searches with CrossRef alternatives (not sure if there are any)
- Better string distance function to measures similarity
- Handle italics, superscript and subscripts
- Code cleanup, especially the async stuff
    + Disclaimer: This was hacked together out of despair in the week before submitting my thesis, so it has not received the care it needs! :)
- GUI. Not sure if this will add value. Maybe it can be plugged in existing solutions, like Mendeley and so on.