"""Read a paragraph-level revision proposal without changing the paper draft."""
from __future__ import annotations

import hashlib
import json
import base64
import mimetypes
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import unquote

from bs4 import BeautifulSoup


def paragraph_text(content, *, citations=True):
    document = BeautifulSoup(content, 'html.parser')
    for annotation in document.select('annotation, annotation-xml'):
        annotation.decompose()
    if not citations:
        for citation in document.select('.citation'):
            citation.decompose()
    return re.sub(r'\s+', ' ', document.get_text()).strip().rstrip(' ,')


def proposal_revision(proposal):
    """Version the saved proposal and review choices, excluding derived UI data."""
    raw = json.dumps(proposal, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def comparison_data(directory, sections, section_id='s1'):
    """Return the saved original/proposal pairs, counts, and source freshness."""
    proposals = [
        json.loads(path.read_text())
        for path in (directory / 'compare').glob('*-ko.json')
    ]
    order = {section['id']: index for index, section in enumerate(sections)}
    proposals.sort(key=lambda proposal: order[proposal['section_id']])
    data = next((proposal for proposal in proposals if proposal['section_id'] == section_id), None)
    if data is None:
        raise KeyError(section_id)
    data['proposal_revision'] = proposal_revision(data)
    data['comparisons'] = [
        {'section_id': proposal['section_id'], 'title': proposal['title']}
        for proposal in proposals
    ]
    sources = data.get('source_sections_sha256') or {
        data['section_id']: data['source_section_sha256']
    }
    current = {section['id']: section['kohtml'] for section in sections}
    data['source_changed'] = any(
        hashlib.sha256(current[sid].encode()).hexdigest() != digest
        for sid, digest in sources.items()
    )
    data.setdefault('groups', [{'id': data['section_id'], 'title': data['title'], 'level': 0}])
    totals = {'original': 0, 'revised': 0}
    decisions = {'original': 0, 'accept': 0, 'edited': 0, 'remove': 0}
    selected_count = 0
    pending = False
    for paragraph in data['paragraphs']:
        decision = paragraph.setdefault('decision', 'original')
        if decision not in decisions:
            raise ValueError('Please check the status of the adoption of the document.')
        decisions[decision] += 1
        edited = paragraph.get('edited_html', paragraph['revised_html'])
        selected = {
            'original': paragraph['original_html'],
            'accept': paragraph['revised_html'],
            'edited': edited,
            'remove': '',
        }[decision]
        selected_count += len(paragraph_text(selected, citations=False))
        pending = pending or selected != paragraph.get('applied_html', paragraph['original_html'])
        paragraph['edited_count'] = len(paragraph_text(edited, citations=False))
        paragraph['edited_text'] = paragraph_text(edited)
        for version in totals:
            count = len(paragraph_text(paragraph[version + '_html'], citations=False))
            paragraph[version + '_count'] = count
            totals[version] += count
        paragraph['reduction'] = round(
            100 * (1 - paragraph['revised_count'] / paragraph['original_count']), 1
        )
        paragraph['revised_text'] = paragraph_text(paragraph['revised_html'])
    totals['reduction'] = round(100 * (1 - totals['revised'] / totals['original']), 1)
    data['totals'] = totals
    data['decisions'] = decisions
    data['selected_totals'] = {
        'count': selected_count,
        'reduction': round(100 * (1 - selected_count / totals['original']), 1),
    }
    data['pending_application'] = pending
    data['count_basis'] = 'Includes blank letter count/citation number and picture captions excluded'
    return data


def compressed_revision(directory):
    """Identify changes to the separate, editable compressed manuscript."""
    stat = (directory / 'Draft compression.md').stat()
    return f'{stat.st_mtime_ns}:{stat.st_size}'


def compressed_document(directory, sections, root):
    """Render only the sections actually written in draft compression.md"""
    source = directory / 'Draft compression.md'
    markdown = source.read_text()
    rendered = subprocess.run(
        ['pandoc', '-f', 'gfm', '-t', 'html5', '--wrap=none'],
        input=markdown, text=True, capture_output=True, check=True,
    ).stdout
    document = BeautifulSoup(rendered, 'html.parser')
    by_title = {section['ko']: section for section in sections}
    result = []
    active = None
    for node in document.contents:
        if getattr(node, 'name', None) == 'h1':
            continue
        if getattr(node, 'name', None) in ['h2', 'h3']:
            title = node.get_text(' ', strip=True)
            if title not in by_title:
                if active is None:
                    raise ValueError('I couldn\'t find the title of the passage in the original: ' + title)
                active['html'] += str(node)
                continue
            original = by_title[title]
            active = {'id': original['id'], 'title': title, 'level': original['level'], 'html': ''}
            result.append(active)
        elif active is not None:
            active['html'] += str(node)
    if not result:
        raise ValueError('There\'s no one working on the compression file.')

    assets = Path(unicodedata.normalize('NFC', str(root / 'paper/asset'))).resolve()
    for section in result:
        body = BeautifulSoup(section['html'], 'html.parser')
        for image in body.find_all('img', src=True):
            src = image['src']
            if src.startswith(('data:', 'https:', 'http:')):
                continue
            path = Path(unicodedata.normalize('NFC', unquote(src)))
            if not path.is_absolute():
                path = directory / path
            path = Path(unicodedata.normalize('NFC', str(path.resolve())))
            if not path.is_relative_to(assets) or not path.is_file():
                raise ValueError('Please check the drawing path of the compression file: ' + src)
            mime = mimetypes.guess_type(path.name)[0]
            if mime not in ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp', 'image/gif']:
                raise ValueError('It\'s a graphics format that doesn\'t support: ' + path.name)
            image['src'] = 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()
        # Markdown stores each figure image and its caption in adjacent paragraphs.
        for paragraph in list(body.find_all('p', recursive=False)):
            if paragraph.find('img') is None or paragraph.get_text(strip=True):
                continue
            caption = paragraph.find_next_sibling()
            figure = body.new_tag('figure')
            paragraph.replace_with(figure)
            for child in list(paragraph.contents):
                figure.append(child.extract())
            if caption and caption.name == 'p' and re.match(r'^Figure\s+\d', caption.get_text()):
                caption.name = 'figcaption'
                figure.append(caption.extract())
        section['html'] = str(body)
    return {'title': 'Draft compression', 'sections': result, 'revision': compressed_revision(directory)}
