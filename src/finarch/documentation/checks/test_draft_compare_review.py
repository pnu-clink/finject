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
             'kohtml': '<figure id="figure-one"><figcaption>그림 캡션</figcaption></figure>'
                       '<p>원본 첫 문단 <a href="#reference">[1]</a></p>'
                       '<table id="table-one"><tr><td>표 내용</td></tr></table>'
                       '<p>원본 둘째 문단</p><p>원본 셋째 문단</p>'
                       '<math display="block"><mi>Q</mi></math>'},
            {'id': 's2', 'ko': '2. Related Works', 'level': 0, 'state': 'revised',
             'en': '2. Related Works', 'enhtml': '<p>Other English.</p>',
             'kohtml': '<p>다른 단원의 본문</p>'},
        ]
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False, indent=2) + '\n')
        markdown = '# Draft\n\n'
        for section in self.sections:
            markdown += '## ' + section['ko'] + '\n\n' + section['kohtml'] + '\n\n'
        self.repository.markdown.write_text(markdown)
        self.compressed = self.directory / 'draft 압축.md'
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
                {'id': 'p1', 'label': '첫 문단', 'original_html': str(originals[0]),
                 'revised_html': '<p>축약 첫 문단 <a href="#reference">[1]</a></p>'},
                {'id': 'p2', 'label': '둘째 문단', 'original_html': str(originals[1]),
                 'revised_html': '<p>축약 둘째 문단</p>'},
                {'id': 'p3', 'label': '셋째 문단', 'original_html': str(originals[2]),
                 'revised_html': '<p>축약 셋째 문단</p>'},
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
        self.choose('p3', 'edited', '<p>저장한 수정문</p>')
        self.assertEqual(self.manuscript_bytes(), before)
        self.assertEqual(self.data()['decisions'], {'original': 1, 'accept': 1, 'edited': 1, 'remove': 0})

    def test_english_only_section_does_not_break_korean_editor_save(self):
        from finarch.documentation.draft_editor import revision
        hidden = {'id': 's1-old', 'ko': '이전 절', 'level': 1, 'state': 'settled',
                  'en': 'Old English section', 'enhtml': '<p>English is retained.</p>',
                  'kohtml': '', 'hidden_ko': True}
        current = [self.sections[0], hidden, self.sections[1]]
        self.repository.source.write_text(json.dumps(current, ensure_ascii=False))
        self.assertEqual([s['id'] for s in self.repository.index()], ['s1', 's2'])
        result = self.repository.save('s2', {'revision': revision(current[2]),
                                            'title': current[2]['ko'], 'html': '<p>수정 후</p>'})
        self.assertTrue(result['changed'])
        self.assertIn('수정 후', self.repository.markdown.read_text())
        self.assertEqual(self.repository.read()[1]['enhtml'], hidden['enhtml'])

    def test_markdown_keeps_table_caption_and_reference_anchor(self):
        table = '<table id="tab:v2-support" data-layout="one-column"><caption>Table 3: 지원율</caption><thead><tr><th>모델</th><th>지원율</th></tr></thead><tbody><tr><td>Luna</td><td>77.8</td></tr></tbody></table>'
        body = self.repository.markdown_body('<p><a href="#tab:v2-support">Table 3</a></p>' + table, '')
        saved = BeautifulSoup(body, 'html.parser').find('table', id='tab:v2-support')
        self.assertIsNotNone(saved)
        self.assertEqual(saved.caption.get_text(), 'Table 3: 지원율')
        self.assertEqual(saved['data-layout'], 'one-column')

    def test_markdown_keeps_notation_and_prompt_heading_anchors(self):
        body = self.repository.markdown_body('<p id="notation-common">Q는 질문이다.</p><h3 id="prompts-analysis">Appendix P.5</h3><p>판정 프롬프트</p>', '')
        doc = BeautifulSoup(body, 'html.parser')
        self.assertIsNotNone(doc.find(id='notation-common'))
        self.assertIsNotNone(doc.find(id='prompts-analysis'))

    def test_compressed_appendix_keeps_internal_headings_in_its_section(self):
        self.compressed.write_text('# Draft\n\n## 1. Introduction\n\n본문\n\n### 내부 설명\n\n보충 설명\n\n## 2. Related Works\n\n다음 절\n')
        result = compressed_document(self.directory, self.sections, self.root)
        self.assertEqual([s['id'] for s in result['sections']], ['s1', 's2'])
        self.assertIn('내부 설명', result['sections'][0]['html'])
        self.assertIn('보충 설명', result['sections'][0]['html'])

    def test_apply_mixed_choices_preserves_other_content_and_both_previews(self):
        self.choose('p1', 'accept')
        self.choose('p3', 'edited', '<p>수정한 문장 <strong>강조</strong></p>')
        result = self.apply()
        self.assertEqual(result['changed_sections'], ['s1'])
        current = self.repository.read()
        document = BeautifulSoup(current[0]['kohtml'], 'html.parser')
        paragraphs = document.find_all('p', recursive=False)
        self.assertEqual(str(paragraphs[0]), self.proposal['paragraphs'][0]['revised_html'])
        self.assertEqual(str(paragraphs[1]), self.proposal['paragraphs'][1]['original_html'])
        self.assertEqual(paragraphs[2].get_text(), '수정한 문장 강조')
        self.assertIsNotNone(document.find('figure', id='figure-one'))
        self.assertIsNotNone(document.find('table', id='table-one'))
        self.assertIsNotNone(document.math)
        self.assertEqual(current[0]['enhtml'], self.sections[0]['enhtml'])
        self.assertEqual(current[1], self.sections[1])
        for path in [self.repository.markdown, self.compressed]:
            content = path.read_text()
            self.assertIn('축약 첫 문단', content)
            self.assertIn('원본 둘째 문단', content)
            self.assertIn('수정한 문장', content)
            self.assertIn('다른 단원의 본문', content)
        for path in self.repository.previews:
            embedded = BeautifulSoup(path.read_text(), 'html.parser').script.get_text()
            self.assertEqual(json.loads(embedded), current)
        self.assertFalse(result['comparison']['pending_application'])
        self.assertFalse(result['comparison']['source_changed'])

    def test_nested_analysis_paragraph_stays_inside_its_topic(self):
        original = self.proposal['paragraphs'][1]['original_html']
        nested = '<div class="finding-topic"><h3>분석 항목</h3><div class="finding-subtopic">' + original + '</div></div>'
        self.sections[0]['kohtml'] = self.sections[0]['kohtml'].replace(original, nested)
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False))
        self.proposal['source_section_sha256'] = hashlib.sha256(self.sections[0]['kohtml'].encode()).hexdigest()
        self.proposal_path.write_text(json.dumps(self.proposal, ensure_ascii=False))
        self.choose('p2', 'accept')
        self.apply()
        doc = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual(doc.select_one('.finding-subtopic p').get_text(), '축약 둘째 문단')
        self.assertEqual(doc.select_one('.finding-topic h3').get_text(), '분석 항목')
        self.assertEqual(doc.select_one('#table-one').get_text(), '표 내용')
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
        item = '<li><strong>기여.</strong> 제작 방법 설명</li>'
        listing = '<ol>' + item + '<li>다른 기여는 유지</li></ol>'
        self.sections[0]['kohtml'] = self.sections[0]['kohtml'].replace(original, listing)
        self.repository.source.write_text(json.dumps(self.sections, ensure_ascii=False))
        self.proposal['source_section_sha256'] = hashlib.sha256(self.sections[0]['kohtml'].encode()).hexdigest()
        self.proposal['paragraphs'][1].update({
            'block_tag': 'li', 'original_html': item,
            'revised_html': '<li><strong>기여.</strong> 제작 방법</li>',
        })
        self.proposal_path.write_text(json.dumps(self.proposal, ensure_ascii=False))
        self.choose('p2', 'accept')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in document.select('ol > li')],
                         ['기여. 제작 방법', '다른 기여는 유지'])
        self.choose('p2', 'edited', '<p><strong>기여.</strong> 수정한 제작 방법</p>')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual(document.select_one('ol > li').get_text(), '기여. 수정한 제작 방법')
        self.assertIsNone(document.select_one('ol > p'))
        self.choose('p2', 'remove')
        self.apply()
        document = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in document.select('ol > li')], ['다른 기여는 유지'])
        self.choose('p2', 'original')
        self.apply()
        self.assertEqual(self.repository.read(), self.sections)

    def test_remove_apply_repeat_and_restore(self):
        before = self.manuscript_bytes()
        self.choose('p2', 'remove')
        self.assertEqual(self.manuscript_bytes(), before)
        self.assertEqual(self.data()['decisions']['remove'], 1)
        self.apply()
        self.assertNotIn('원본 둘째 문단', self.repository.read()[0]['kohtml'])
        for path in [self.repository.markdown, self.compressed]:
            self.assertNotIn('원본 둘째 문단', path.read_text())
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
        self.choose('p3', 'edited', '<p>다시 넣은 문단</p>')
        self.apply()
        doc = BeautifulSoup(self.repository.read()[0]['kohtml'], 'html.parser')
        self.assertEqual([p.get_text() for p in doc.find_all('p')], ['축약 첫 문단 [1]', '다시 넣은 문단'])
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
        current[0]['kohtml'] += '<p>다른 편집기에서 추가한 문장</p>'
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
                    '<p onclick="evil()">첫 줄 <a href="#reference">[1]</a></p>'
                    '<div>둘째 줄<script>evil()</script></div>')
        paragraph = self.data()['paragraphs'][0]['edited_html']
        document = BeautifulSoup(paragraph, 'html.parser')
        self.assertEqual(len(document.find_all('p')), 1)
        self.assertNotIn('onclick', paragraph)
        self.assertIsNone(document.script)
        self.assertEqual(document.a['href'], '#reference')
        self.assertIn('둘째 줄', document.get_text())
        with self.assertRaises(ValueError):
            self.choose('p1', 'edited', '<p> </p>')

    def test_apply_registers_only_reviewed_missing_section_in_compressed_file(self):
        self.compressed.write_text('# draft 압축\n\n## 2. Related Works\n\n다른 단원의 본문\n')
        self.choose('p2', 'accept')
        self.apply()
        content = self.compressed.read_text()
        self.assertLess(content.index('## 1. Introduction'), content.index('## 2. Related Works'))
        self.assertIn('축약 둘째 문단', content)
        self.assertIn('다른 단원의 본문', content)


if __name__ == '__main__':
    unittest.main()
