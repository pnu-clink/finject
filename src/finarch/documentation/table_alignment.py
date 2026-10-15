"""Center table text, right-align numbers, and left-align marked model names."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


def cell_alignment(cell):
    """Return the alignment for a whole cell, not for digits inside a name."""
    if cell.get('data-model-name') == 'true':
        return 'left'
    if cell.name == 'th':
        return 'center'
    if cell.get('data-numeric-placeholder') == 'true':
        return 'right'
    text = cell.get_text(' ', strip=True)
    # A value may include a unit, a denominator, a change, or an interval.
    text = re.sub(r'\s+(?:tokens?|hours?|GPU-hours?|ms|seconds?)$', '', text)
    numeric = bool(re.search(r'\d', text) and re.fullmatch(
        r'[\d\s.,+\-−–/%‰()\[\]→±×*†]+',
        re.sub(r'(?<=\d)[eE](?=[+\-]?\d)', '', text),
    ))
    return 'right' if numeric else 'center'


def align_table_cells(doc):
    """Apply the same policy to saved Draft HTML and the editor's saved cells."""
    for table in doc.find_all('table'):
        for cell in table.find_all(['td', 'th']):
            align = cell_alignment(cell)
            cell['data-cell-align'] = align
            style = re.sub(r'(?:^|;)\s*text-align\s*:[^;]*', '', cell.get('style', ''), flags=re.I).strip(' ;')
            cell['style'] = (style + ';' if style else '') + 'text-align:' + align
    return doc


def align_html_tables(content):
    """Change only table markup, preserving the surrounding prose and figures."""
    return re.sub(
        r'<table\b[^>]*>.*?</table>',
        lambda match: str(align_table_cells(BeautifulSoup(match[0], 'html.parser'))),
        content,
        flags=re.S | re.I,
    )
