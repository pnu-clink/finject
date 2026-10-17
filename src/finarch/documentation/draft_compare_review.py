"""Save paragraph review choices and apply them to both Korean manuscripts."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup, Comment

from finarch.documentation.draft_compare import (
    comparison_data, paragraph_text, proposal_revision,
)


class ComparisonConflict(ValueError):
    """The proposal or its source changed after the browser loaded it."""


def _read_proposal(repository, sid):
    for path in (repository.directory / 'compare').glob('*-ko.json'):
        proposal = json.loads(path.read_text())
        if proposal['section_id'] == sid:
            return path, proposal
    raise KeyError(sid)


def _check_version(proposal, payload):
    if payload.get('proposal_revision') != proposal_revision(proposal):
        raise ComparisonConflict('Other options or tweaks are saved first, so please update and bring the latest comparison.')


def _normalise_paragraph(raw, block_tag='p'):
    # Reuse the section editor's executable-markup filter.
    from finarch.documentation.draft_editor import clean_html

    if block_tag not in ['p', 'li'] or not isinstance(raw, str) or len(raw) > 100_000:
        raise ValueError('Please check the text of the amendments.')
    document = BeautifulSoup(clean_html(raw), 'html.parser')
    for comment in document.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    if document.select('figure, table, img, h1, h2, h3, h4, ul, ol'):
        raise ValueError('In the modification room, please edit the text of the text.')
    # Enter and pasted paragraph breaks stay inside this one reviewed paragraph.
    for block in list(document.find_all(['p', 'div', 'li'])):
        if block.parent is None:
            continue
        if block.previous_sibling is not None:
            block.insert_before(document.new_tag('br'))
        block.unwrap()
    paragraph = document.new_tag(block_tag)
    for node in list(document.contents):
        paragraph.append(node.extract())
    if not paragraph_text(str(paragraph)):
        raise ValueError('You can\'t save empty documents.')
    return str(paragraph)


def save_decision(repository, payload):
    """Save a choice/edit only in compare JSON; do not write the manuscripts."""
    with repository.lock:
        path, proposal = _read_proposal(repository, payload.get('section_id'))
        _check_version(proposal, payload)
        paragraph = next(
            (item for item in proposal['paragraphs'] if item['id'] == payload.get('paragraph_id')),
            None,
        )
        if paragraph is None:
            raise KeyError(payload.get('paragraph_id'))
        decision = payload.get('decision')
        if decision not in ['original', 'accept', 'edited', 'remove']:
            raise ValueError('Please select one of the original retaining/adopting/correcting/removing options.')
        if decision == 'edited':
            paragraph['edited_html'] = _normalise_paragraph(
                payload.get('edited_html', paragraph.get('edited_html', paragraph['revised_html'])),
                paragraph.get('block_tag', 'p'),
            )
        paragraph['decision'] = decision
        saved_at = dt.datetime.now().astimezone().isoformat()
        paragraph['reviewed_at'] = saved_at
        repository.atomic_write(path, json.dumps(proposal, ensure_ascii=False, indent=2) + '\n')
        return {
            'comparison': comparison_data(repository.directory, repository.read(), proposal['section_id']),
            'saved_at': saved_at,
        }


def _replace_markdown_section(repository, markdown, sections, sid, body, *, compressed=False):
    section = next(item for item in sections if item['id'] == sid)
    heading = ('### ' if section['level'] else '## ') + section['ko']
    if not compressed:
        start, _, end = repository.markdown_bounds(markdown, sections, sid)
        return markdown[:start] + heading + '\n\n' + body + '\n\n' + markdown[end:]
    headings = list(re.finditer(r'(?m)^#{2,3} ([^\n]+)\s*$', markdown))
    match_index = next(
        (index for index, match in enumerate(headings) if match.group(1).strip() == section['ko']),
        None,
    )
    if match_index is not None:
        start = headings[match_index].start()
        end = headings[match_index + 1].start() if match_index + 1 < len(headings) else len(markdown)
    else:
        # Register only this reviewed section, in the same order as the Draft.
        section_index = next(index for index, item in enumerate(sections) if item['id'] == sid)
        following = {item['ko'] for item in sections[section_index + 1:]}
        start = next(
            (match.start() for match in headings if match.group(1).strip() in following),
            len(markdown),
        )
        end = start
    prefix = markdown[:start]
    if prefix and not prefix.endswith('\n\n'):
        prefix = prefix.rstrip() + '\n\n'
    return prefix + heading + '\n\n' + body + '\n\n' + markdown[end:]


def apply_decisions(repository, payload):
    """Commit reviewed paragraphs, Markdown copies and previews as one operation."""
    from finarch.documentation.draft_editor import EMBEDDED

    with repository.lock:
        proposal_path, proposal = _read_proposal(repository, payload.get('section_id'))
        _check_version(proposal, payload)
        source_before = repository.source.read_text()
        sections = json.loads(source_before)
        current = {section['id']: section for section in sections}
        sources = proposal.get('source_sections_sha256') or {
            proposal['section_id']: proposal['source_section_sha256']
        }
        for sid, digest in sources.items():
            if hashlib.sha256(current[sid]['kohtml'].encode()).hexdigest() != digest:
                raise ComparisonConflict('The draft rule cannot be changed and applied, so please update the comparison to the current rule.')

        groups = {}
        for paragraph in proposal['paragraphs']:
            groups.setdefault(paragraph.get('section_id', proposal['section_id']), []).append(paragraph)
        changed_sections = []
        for sid, paragraphs in groups.items():
            section = current[sid]
            document = BeautifulSoup(section['kohtml'], 'html.parser')
            # Keep analysis paragraphs and contribution list items in their
            # existing containers and document order.
            available = [node for node in document.descendants
                         if getattr(node, 'name', None) in ['p', 'li']
                         or isinstance(node, Comment) and str(node).startswith('draft-compare-removed:')]
            next_position = 0
            for paragraph in paragraphs:
                block_tag = paragraph.get('block_tag', 'p')
                if block_tag not in ['p', 'li']:
                    raise ValueError('Please check the format of the ladder: ' + paragraph['label'])
                expected = paragraph.get('applied_html', paragraph['original_html'])
                marker = 'draft-compare-removed:' + hashlib.sha256(paragraph['id'].encode()).hexdigest()
                expected = marker if expected == '' else str(BeautifulSoup(expected, 'html.parser').find(block_tag))
                index = next(
                    (i for i in range(next_position, len(available)) if str(available[i]) == expected),
                    None,
                )
                if index is None:
                    raise ComparisonConflict('The position of the ladder can\'t be changed and applied: ' + paragraph['label'])
                decision = paragraph.get('decision', 'original')
                if decision == 'remove':
                    available[index].replace_with(Comment(marker))
                    paragraph['applied_html'] = ''
                    paragraph['applied_decision'] = decision
                    next_position = index + 1
                    continue
                if decision == 'original':
                    selected = paragraph['original_html']
                elif decision == 'accept':
                    selected = paragraph['revised_html']
                elif decision == 'edited':
                    if not paragraph.get('edited_html'):
                        raise ValueError('First, save the correction chart: ' + paragraph['label'])
                    selected = paragraph['edited_html']
                else:
                    raise ValueError('Please check the status of the adoption of the document.')
                replacement = BeautifulSoup(selected, 'html.parser')
                children = [node for node in replacement.contents if getattr(node, 'name', None)]
                if len(children) != 1 or children[0].name != block_tag:
                    raise ValueError('Please check the format of the ladder: ' + paragraph['label'])
                available[index].replace_with(children[0])
                paragraph['applied_html'] = str(children[0])
                paragraph['applied_decision'] = decision
                next_position = index + 1
            updated = str(document)
            # BeautifulSoup may normalize surrounding whitespace. No reviewed
            # content change means no manuscript rewrite is needed.
            old_document = str(BeautifulSoup(section['kohtml'], 'html.parser'))
            if updated != old_document:
                section['kohtml'] = updated
                section['state'] = 'revised'
                changed_sections.append(sid)

        markdown_before = repository.markdown.read_text()
        compressed_path = repository.directory / 'Draft compression.md'
        compressed_before = compressed_path.read_text() if compressed_path.exists() else '# Draft compression\n\n'
        markdown_after, compressed_after = markdown_before, compressed_before
        for sid in groups:
            _, body_start, end = repository.markdown_bounds(markdown_before, json.loads(source_before), sid)
            body = repository.markdown_body(current[sid]['kohtml'], markdown_before[body_start:end])
            if sid in changed_sections:
                markdown_after = _replace_markdown_section(repository, markdown_after, sections, sid, body)
            compressed_after = _replace_markdown_section(
                repository, compressed_after, sections, sid, body, compressed=True,
            )
        applied_at = dt.datetime.now().astimezone().isoformat()
        proposal['applied_at'] = applied_at
        proposal['source_sections_sha256'] = {
            sid: hashlib.sha256(current[sid]['kohtml'].encode()).hexdigest() for sid in sources
        }
        if proposal['section_id'] in proposal['source_sections_sha256']:
            proposal['source_section_sha256'] = proposal['source_sections_sha256'][proposal['section_id']]
        before = {proposal_path: proposal_path.read_text()}
        updates = {proposal_path: json.dumps(proposal, ensure_ascii=False, indent=2) + '\n'}
        if changed_sections:
            before[repository.source] = source_before
            updates[repository.source] = json.dumps(sections, ensure_ascii=False, indent=2) + '\n'
            before[repository.markdown] = markdown_before
            updates[repository.markdown] = markdown_after
            embedded = json.dumps(sections, ensure_ascii=False).replace('</script', '<\\/script')
            for path in repository.previews:
                before[path] = path.read_text()
                if len(EMBEDDED.findall(before[path])) != 1:
                    raise ValueError('I can\'t find the source code in the draft HTML.')
                updates[path] = EMBEDDED.sub(lambda m: m[1] + embedded + m[3], before[path], count=1)
        if compressed_after != compressed_before:
            before[compressed_path] = compressed_before if compressed_path.exists() else None
            updates[compressed_path] = compressed_after
        for path, content in before.items():
            if (path.read_text() if path.exists() else None) != content:
                raise ComparisonConflict('The application file has been changed, so please call the latest information and apply it again.')
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = repository.directory / 'backup/editor' / (stamp + '-compare-apply')
        backup.mkdir(parents=True, exist_ok=False)
        for path, content in before.items():
            if content is not None:
                (backup / path.name).write_text(content)
        written = []
        try:
            for path, content in updates.items():
                repository.atomic_write(path, content)
                written.append(path)
        except Exception:
            for path in reversed(written):
                if path.read_text() == updates[path]:
                    if before[path] is None:
                        path.unlink()
                    else:
                        repository.atomic_write(path, before[path])
            raise
        return {
            'comparison': comparison_data(repository.directory, sections, proposal['section_id']),
            'applied_at': applied_at,
            'changed_sections': changed_sections,
            'compressed_changed': compressed_after != compressed_before,
        }
