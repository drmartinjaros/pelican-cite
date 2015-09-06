# -*- coding: utf-8 -*-
"""
pelican-cite
==============

A Pelican plugin that provices a BibTeX-style reference system within
pelican sites. 

Based on teh Pelican BibTeX plugin written by Vlad Niculae <vlad@vene.ro>
"""

import logging
import re

try:
    from pybtex.database.input.bibtex import Parser
    from pybtex.database.output.bibtex import Writer
    from pybtex.database import BibliographyData, PybtexError
    from pybtex.backends import html
    from pybtex.style.formatting import plain
    pyb_imported = True
except ImportError:
    pyb_imported = False

from pelican import signals

__version__ = '0.0.1'

JUMP_BACK = '<a href="#ref-{0}-{1}" title="Jump back to reference {1}">{2}</a>'
CITE_RE = re.compile("\[@@?\s*(\w.*?)\s*\]")

logger = logging.getLogger(__name__)
global_bib = None
style = plain.Style()
backend = html.Backend()

def get_bib_file(article):
    """
    If a bibliography file is specified for this article/page, parse
    it and return the parsed object.
    """
    if 'publications_src' in article.metadata:
        refs_file = article.metadata['publications_src']
        try:
            local_bib = Parser().parse_file(refs_file)
            return local_bib
        except PybtexError as e:
            logger.warn('`pelican_bibtex` failed to parse file %s: %s' % (
                refs_file,
                str(e)))
            return global_bib
    else:
        return global_bib


def process_content(article):
    """
    Substitute the citations and add a bibliography for an article or
    page, using the local bib file if specified or the global one otherwise.
    """
    data = get_bib_file(article)
    if not data:
        return
    content = article._content

    # Scan post to figure out what citations are needed
    cite_count = {}
    replace_count = {}
    for citation in CITE_RE.findall(content):
        if citation in cite_count:
            cite_count[citation] = 1
            replace_count[citation] = 1
        else:
            cite_count[citation] += 1

    # Get formatted entries for the appropriate bibliographic entries
    cited = []    
    for key in data.entries.keys():
        if key in cite_count: cited.append(data.entries[key])
    formatted_entries = style.format_entries(cited)

    # Get the data for the required citations and append to content
    labels = {}
    content += '<h3>Bibliography</h3>\n'
    for formatted_entry in formatted_entries:
        key = formatted_entry.key
        ref_id = key.replace(' ','')
        label = ("<a href='#" + ref_id + "' id='#ref-" + ref_id + "-{0}'>"
                + formatted_entry.label + "</a>")
        text = ("<p id='" + ref_id + "'>"
               + formatted_entry.text.render(html_backend))
        for i in range(cite_count[key]):
            if i == 0:
                text += JUMP_BACK.format(ref_id,1,'↩ 1')
            else:
                text += ', ' + JUMP_BACK.format(ref_id,i+1,i+1)
        text += '</p>'
        content += text + '\n'
        labels[key] = label

    # Replace citations in article/page
    def replace_cites(match):
        label = match.group(1)
        if label in labels:
            # TODO: Add ability to change style of label depending on @ or @@
            return labels[label]
        else:
            logger.warn('No BibTeX entry found for label "{}"'.format(label))
            return match.group(0)
    
    CITE_RE.sub(replace_cites,content)
    article._content = content
    

def add_citations(generators):
    if not pyb_loaded:
        logger.warn('`pelican-cite` failed to load dependency `pybtex`')
        return

    if 'PUBLICATIONS_SRC' in generator.settings:
        refs_file = generator.settings['PUBLICATIONS_SRC']
        try:
            global_bib = Parser().parse_file(refs_file)
        except PybtexError as e:
            logger.warn('`pelican_bibtex` failed to parse file %s: %s' % (
                refs_file,
                str(e)))

    # Process the articles and pages
    for generator in generators:
        if isinstance(generator, ArticlesGenerator):
            for article in generator.articles:
                process_content(article)
        elif isinstance(generator, PagesGenerator):
            for page in generator.pages:
                process_content(page)


def register():
    signals.all_generators_finalized.connect(add_citations)