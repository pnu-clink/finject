"""Check that review choices commit only the intended Korean paragraphs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from finarch.documentation.draft_compare import comparison_data, compressed_document
from finarch.documentation.draft_compare_review import (
    ComparisonConflict, apply_decisions, save_decision,
)
from finarch.documentation.draft_editor import DraftRepository


class DraftReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = DraftRepository(self.root, self.root / 'previews')
        self.directory = self.repository.directory
        (self.directory / 'compare').mkdir(parents=True)
        (self.root / 'previews').mkdir()
        self.sections = [
            {'id': 's1', 'ko': '1. Introduction', 'level': 0, 'state': 'revised',
             'en': '1. Introduction', 'enhtml': '<p>English stays intact.</p>',
             'kohtml': '<figure id="figure-one"><figcaption>\uadf8\ub9bc \ucea1\uc158</figcaption></figure>'
                       '<p>\uc6d0\ubcf8 \uccab \ubb38\ub2e8 <a href="#reference">[1]</a></p>'
                       '<table id="table-one"><tr><td>\ud45c \ub0b4\uc6a9</td></tr></table>'
                       '<p>\uc6d0\ubcf8 \ub458\uc9f8 \ubb38\ub2e8</p><p>\uc6d0\ubcf8 \uc14b\uc9f8 \ubb38\ub2e8</p>'
                       '<math display="block"><mi>Q</mi></math>'},
            {'id': 's2', 'ko': '2. Related Works', 'level': 0, 'state': 'revised',
             'en': '2. Related Works', 'enhtml': '<p>Other English.</p>',
             'kohtml': '<p>\ub2e4\ub978 \ub2e8\uc6d0\uc758 \ubcf8\ubb38</p>'},
        ]
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False, indent=2) + '\n')
        markdown = '# Draft\n\n'
        for section in self.sections:
            markdown += '## ' + section['ko'] + '\n\n' + section['kohtml'] + '\n\n'
        self.repository.markdown.write_text(markdown)
        self.compressed = self.directory / 'draft \uc555\ucd95.md'
        self.compressed.write_text(markdown)
        for path in self.repository.previews:
            path.write_text('<html><script id="document-data" type="application/json">'
                            + json.dumps(self.sections, ensure_ascii=False) + '</script></html>')
        originals = BeautifulSoup(self.sections[0]['kohtml'], 'html.parser').find_all('p', recursive=False)
        self.proposal = {
            'version': 1, 'section_id': 's1', 'title': '1. Introduction',
            'source_section_sha256': hashlib.sha256(self.sections[0]['kohtml'].encode()).hexdigest(),
            'section_ids': ['s1', 's2'],
            'paragraphs': [
                {'id': 'p1', 'label': '\uccab \ubb38\ub2e8', 'original_html': str(originals[0]),
                 'revised_html': '<p>\ucd95\uc57d \uccab \ubb38\ub2e8 <a href="#reference">[1]</a></p>'},
                {'id': 'p2', 'label': '\ub458\uc9f8 \ubb38\ub2e8', 'original_html': str(originals[1]),
                 'revised_html': '<p>\ucd95\uc57d \ub458\uc9f8 \ubb38\ub2e8</p>'},
                {'id': 'p3', 'label': '\uc14b\uc9f8 \ubb38\ub2e8', 'original_html': str(originals[2]),
                 'revised_html': '<p>\ucd95\uc57d \uc14b\uc9f8 \ubb38\ub2e8</p>'},
            ],
        }
        self.proposal_path = self.directory / 'compare/introduction-ko.json'
        self.proposal_path.write_text(json.dumps(self.proposal, ensure_ascii=False, indent=2) + '\n')

    def data(self):
        return comparison_data(self.directory, self.repository.read(), 's1')

    def choose(self, paragraph, decision, edited_html=None):
        payload = {'section_id': 's1', 'proposal_revision': self.data()['proposal_revision'],
                   'paragraph_id': paragraph, 'decision': decision}
        if edited_html is not None:
            payload['edited_html'] = edited_html
        return save_decision(self.repository, payload)

    def apply(self):
        return apply_decisions(self.repository, {
            'section_id': 's1', 'proposal_revision': self.data()['proposal_revision'],
        })

    def manuscript_bytes(self):
        return {path: path.read_bytes() for path in [
            self.repository.source, self.repository.markdown, self.compressed, *self.repository.previews,
        ]}

    def test_default_is_original_and_choices_do_not_write_manuscripts(self):
        before = self.manuscript_bytes()
        self.assertEqual(self.data()['decisions'], {'original': 3, 'accept': 0, 'edited': 0, 'remove': 0})
        self.assertFalse(self.data()['pending_application'])
        self.choose('p2', 'accept')
        self.choose('p3', 'edited', '<p>\uc800\uc7a5\ud55c \uc218\uc815\ubb38</p>')
        self.assertEqual(self.manuscript_bytes(), before)
        self.assertEqual(self.data()['decisions'], {'original': 1, 'accept': 1, 'edited': 1, 'remove': 0})

    def test_english_only_section_does_not_break_korean_editor_save(self):
        from finarch.documentation.draft_editor import revision
        hidden = {'id': 's1-old', 'ko': '\uc774\uc804 \uc808', 'level': 1, 'state': 'settled',
                  'en': 'Old English section', 'enhtml': '<p>English is retained.</p>',
                  'kohtml': '', 'hidden_ko': True}
        current = [self.sections[0], hidden, self.sections[1]]
        self.repository.source.write_text(json.dumps(current, ensure_ascii=False))
        self.assertEqual([s['id'] for s in self.repository.index()], ['s1', 's2'])
        result = self.repository.save('s2', {'revision': revision(current[2]),
                                            'title': current[2]['ko'], 'html': '<p>\uc218\uc815 \ud6c4</p>'})
        self.assertTrue(result['changed'])
        self.assertIn('\uc218\uc815 \ud6c4', self.repository.markdown.read_text())
        self.assertEqual(self.repository.read()[1]['enhtml'], hidden['enhtml'])

    def test_markdown_keeps_table_caption_and_reference_anchor(self):
        table = '<table id="tab:v2-support" data-layout="one-column"><caption>Table 3: \uc9c0\uc6d0\uc728</caption><thead><tr><th>\ubaa8\ub378</th><th>\uc9c0\uc6d0\uc728</th></tr></thead><tbody><tr><td>Luna</td><td>77.8</td></tr></tbody></table>'
        body = self.repository.markdown_body('<p><a href="#tab:v2-support">Table 3</a></p>' + table, '')
        saved = BeautifulSoup(body, 'html.parser').find('table', id='tab:v2-support')
        self.assertIsNotNone(saved)
        self.assertEqual(saved.caption.get_text(), 'Table 3: \uc9c0\uc6d0\uc728')
        self.assertEqual(saved['data-layout'], 'one-column')

    def test_markdown_keeps_notation_and_prompt_heading_anchors(self):
        body = self.repository.markdown_body('<p id="notation-common">Q\ub294 \uc9c8\ubb38\uc774\ub2e4.</p><h3 id="prompts-analysis">Appendix P.5</h3><p>\ud310\uc815 \ud504\ub86c\ud504\ud2b8</p>', '')
        doc = BeautifulSoup(body, 'html.parser')
        self.assertIsNotNone(doc.find(id='notation-common'))
        self.assertIsNotNone(doc.find(id='prompts-analysis'))

    def test_compressed_appendix_keeps_internal_headings_in_its_section(self):
        self.compressed.write_text('# Draft\n\n## 1. Introduction\n\n\ubcf8\ubb38\n\n### \ub0b4\ubd80 \uc124\uba85\n\n\ubcf4\ucda9 \uc124\uba85\n\n## 2. Related Works\n\n\ub2e4\uc74c \uc808\n')
        result = compressed_document(self.directory, self.sections, self.root)
        self.assertEqual([s['id'] for s in result['sections']], ['s1', 's2'])
        self.assertIn('\ub0b4\ubd80 \uc124\uba85', result['sections'][0]['html'])
        self.assertIn('\ubcf4\ucda9 \uc124\uba85', result['sections'][0]['html'])

    def test_apply_mixed_choices_preserves_other_content_and_both_previews(self):
        self.choose('p1', 'accept')
        self.choose('p3', 'edited', '<p>\uc218\uc815\ud55c \ubb38\uc7a5 <strong>\uac15\uc870</strong></p>')
        result = self.apply()
        self.assertEqual(result['changed_sections'], ['s1'])
        current = self.repository.read()
        document = BeautifulSoup(current[0]['kohtml'], 'html.parser')
        paragraphs = document.find_all('p', recursive=False)
        self.assertEqual(str(paragraphs[0]), self.proposal['paragraphs'][0]['revised_html'])
        self.assertEqual(str(paragraphs[1]), self.proposal['paragraphs'][1]['original_html'])
        self.assertEqual(paragraphs[2].get_text(), '\uc218\uc815\ud55c \ubb38\uc7a5 \uac15\uc870')
        self.assertIsNotNone(document.find('figure', id='figure-one'))
        self.assertIsNotNone(document.find('table', id='table-one'))
        self.assertIsNotNone(document.math)
        self.assertEqual(current[0]['enhtml'], self.sections[0]['enhtml'])
        self.assertEqual(current[1], self.sections[1])
        for path in [self.repository.markdown, self.compressed]:
            content = path.read_text()
            self.assertIn('\ucd95\uc57d \uccab \ubb38\ub2e8', content)
            self.assertIn('\uc6d0\ubcf8 \ub458\uc9f8 \ubb38\ub2e8', content)
            self.assertIn('\uc218\uc815\ud55c \ubb38\uc7a5', content)
            self.assertIn('\ub2e4\ub978 \ub2e8\uc6d0\uc758 \ubcf8\ubb38', content)
        for path in self.repository.previews:
            embedded = BeautifulSoup(path.read_text(), 'html.parser').script.get_text()
            self.assertEqual(json.loads(embedded), current)
        self.assertFalse(result['comparison']['pending_application'])
        self.assertFalse(result['comparison']['source_changed'])

    def test_nested_analysis_paragraph_stays_inside_its_topic(self):
        original = self.proposal['paragraphs'][1]['original_html']
        nested = '<div class="finding-topic"><h3>\ubd84\uc11d \ud56d\ubaa9</h3><div class="finding-subtopic">' + original + '</div></div>'
        self.sections[0]['kohtml'] = self.sections[0]['kohtml'].replace(original, nested)
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False))
        self.proposal['source_section_sha256'] = hashlib.sha256(self.sections[0]['kohtml'].encode()).hexdigest()
        self.proposal_path.write_text(json.dumps(self.proposal, ensure_ascii=False))
        self.choose('p2', 'accept')
        self.apply()
        doc = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual(doc.select_one('.finding-subtopic p').get_text(), '\ucd95\uc57d \ub458\uc9f8 \ubb38\ub2e8')
        self.assertEqual(doc.select_one('.finding-topic h3').get_text(), '\ubd84\uc11d \ud56d\ubaa9')
        self.assertEqual(doc.select_one('#table-one').get_text(), '\ud45c \ub0b4\uc6a9')
        self.choose('p2', 'original')
        self.apply()
        self.assertEqual(self.repository.read(), self.sections)

    def test_reapplying_and_restoring_original_after_adoption(self):
        self.choose('p2', 'accept')
        self.apply()
        adopted = self.manuscript_bytes()
        self.assertEqual(self.apply()['changed_sections'], [])
        self.assertEqual(self.manuscript_bytes(), adopted)
        self.choose('p2', 'original')
        self.assertTrue(self.data()['pending_application'])
        self.apply()
        self.assertEqual(self.repository.read(), self.sections)

    def test_contribution_item_keeps_list_structure_through_review_and_restore(self):
        original = self.proposal['paragraphs'][1]['original_html']
        item = '<li><strong>\uae30\uc5ec.</strong> \uc81c\uc791 \ubc29\ubc95 \uc124\uba85</li>'
        listing = '<ol>' + item + '<li>\ub2e4\ub978 \uae30\uc5ec\ub294 \uc720\uc9c0</li></ol>'
        self.sections[0]['kohtml'] = self.sections[0]['kohtml'].replace(original, listing)
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False))
        self.proposal['source_section_sha256'] = hashlib.sha256(self.sections[0]['kohtml'].encode()).hexdigest()
        self.proposal['paragraphs'][1].update({
            'block_tag': 'li', 'original_html': item,
            'revised_html': '<li><strong>\uae30\uc5ec.</strong> \uc81c\uc791 \ubc29\ubc95</li>',
        })
        self.proposal_path.write_text(json.dumps(self.proposal, ensure_ascii=False))
        self.choose('p2', 'accept')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in document.select('ol > li')],
                         ['\uae30\uc5ec. \uc81c\uc791 \ubc29\ubc95', '\ub2e4\ub978 \uae30\uc5ec\ub294 \uc720\uc9c0'])
        self.choose('p2', 'edited', '<p><strong>\uae30\uc5ec.</strong> \uc218\uc815\ud55c \uc81c\uc791 \ubc29\ubc95</p>')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual(document.select_one('ol > li').get_text(), '\uae30\uc5ec. \uc218\uc815\ud55c \uc81c\uc791 \ubc29\ubc95')
        self.assertIsNone(document.select_one('ol > p'))
        self.choose('p2', 'remove')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in document.select('ol > li')], ['\ub2e4\ub978 \uae30\uc5ec\ub294 \uc720\uc9c0'])
        self.choose('p2', 'original')
        self.apply()
        self.assertEqual(self.repository.read(), self.sections)

    def test_remove_apply_repeat_and_restore(self):
        before = self.manuscript_bytes()
        self.choose('p2', 'remove')
        self.assertEqual(self.manuscript_bytes(), before)
        self.assertEqual(self.data()['decisions']['remove'], 1)
        self.apply()
        self.assertNotIn('\uc6d0\ubcf8 \ub458\uc9f8 \ubb38\ub2e8', self.repository.read()[0]['kohtml'])
        for path in [self.repository.markdown, self.compressed]:
            self.assertNotIn('\uc6d0\ubcf8 \ub458\uc9f8 \ubb38\ub2e8', path.read_text())
        self.assertEqual(self.apply()['changed_sections'], [])
        self.choose('p2', 'original')
        self.apply()
        self.assertEqual(self.repository.read(), self.sections)

    def test_remove_all_then_restore_mixed_choices(self):
        for key in ['p1', 'p2', 'p3']:
            self.choose(key, 'remove')
        self.apply()
        self.assertEqual(self.data()['selected_totals']['count'], 0)
        self.choose('p1', 'accept')
        self.choose('p3', 'edited', '<p>\ub2e4\uc2dc \ub123\uc740 \ubb38\ub2e8</p>')
        self.apply()
        doc = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in doc.find_all('p')], ['\ucd95\uc57d \uccab \ubb38\ub2e8 [1]', '\ub2e4\uc2dc \ub123\uc740 \ubb38\ub2e8'])
        self.assertIsNotNone(doc.find('table', id='table-one'))

    def test_stale_choice_version_is_rejected(self):
        version = self.data()['proposal_revision']
        self.choose('p1', 'accept')
        before = self.manuscript_bytes()
        with self.assertRaises(ComparisonConflict):
            save_decision(self.repository, {'section_id': 's1', 'proposal_revision': version,
                                           'paragraph_id': 'p2', 'decision': 'accept'})
        with self.assertRaises(ComparisonConflict):
            apply_decisions(self.repository, {'section_id': 's1', 'proposal_revision': version})
        self.assertEqual(self.manuscript_bytes(), before)

    def test_changed_source_is_not_overwritten(self):
        self.choose('p1', 'accept')
        current = self.repository.read()
        current[0]['kohtml'] += '<p>\ub2e4\ub978 \ud3b8\uc9d1\uae30\uc5d0\uc11c \ucd94\uac00\ud55c \ubb38\uc7a5</p>'
        self.repository.source.write_text(json.dumps(current, ensure_ascii=False))
        before = self.manuscript_bytes()
        with self.assertRaises(ComparisonConflict):
            self.apply()
        self.assertEqual(self.manuscript_bytes(), before)

    def test_failed_second_manuscript_write_rolls_back_every_written_file(self):
        self.choose('p2', 'accept')
        before = self.manuscript_bytes()
        proposal_before = self.proposal_path.read_bytes()
        real_write = self.repository.atomic_write

        def failing_write(path, content):
            if path == self.compressed:
                raise OSError('simulated disk failure')
            real_write(path, content)

        with patch.object(self.repository, 'atomic_write', side_effect=failing_write):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(self.manuscript_bytes(), before)
        self.assertEqual(self.proposal_path.read_bytes(), proposal_before)

    def test_edited_html_is_one_safe_paragraph_and_keeps_citation_links(self):
        self.choose('p1', 'edited',
                    '<p onclick="evil()">\uccab \uc904 <a href="#reference">[1]</a></p>'
                    '<div>\ub458\uc9f8 \uc904<script>evil()</script></div>')
        paragraph = self.data()['paragraphs'][0]['edited_html']
        document = BeautifulSoup(paragraph, 'html.parser')
        self.assertEqual(len(document.find_all('p')), 1)
        self.assertNotIn('onclick', paragraph)
        self.assertIsNone(document.script)
        self.assertEqual(document.a['href'], '#reference')
        self.assertIn('\ub458\uc9f8 \uc904', document.get_text())
        with self.assertRaises(ValueError):
            self.choose('p1', 'edited', '<p> </p>')

    def test_apply_registers_only_reviewed_missing_section_in_compressed_file(self):
        self.compressed.write_text('# draft \uc555\ucd95\n\n## 2. Related Works\n\n\ub2e4\ub978 \ub2e8\uc6d0\uc758 \ubcf8\ubb38\n')
        self.choose('p2', 'accept')
        self.apply()
        content = self.compressed.read_text()
        self.assertLess(content.index('## 1. Introduction'), content.index('## 2. Related Works'))
        self.assertIn('\ucd95\uc57d \ub458\uc9f8 \ubb38\ub2e8', content)
        self.assertIn('\ub2e4\ub978 \ub2e8\uc6d0\uc758 \ubcf8\ubb38', content)


if __name__ == '__main__':
    unittest.main()
