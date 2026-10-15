"""Render a source-grounded, publication-style PNG of one saved dataset run."""

import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = (Path(__file__).resolve().parent / '../../../../..').resolve()
RUN = ROOT / 'reports/run/20260917-002'
REVIEW = ROOT / 'reports/run/20260920-002-failure-review'
OUTPUT = REVIEW / 'pipeline-figure'
ASSET = ROOT / 'paper/asset'
PREPARED = ROOT / 'data/prepared/finance-reasoning/full-20260917-v2/selection-manifest.json'
SCALE = 2
WIDTH, HEIGHT = 4600, 1530
INK = '#23292e'
MUTED = '#56616a'
RULE = '#59636a'
HAIR = '#a3aeb5'
PAPER = '#f8fafb'
WHITE = '#ffffff'
SOFT = '#eef2f4'
GOOD = '#edf5f1'
BAD = '#f8f0ed'
WAIT = '#f8f5ed'

SERIF = '/System/Library/Fonts/Supplemental/Times New Roman.ttf'
SERIF_BOLD = '/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf'
SANS = '/System/Library/Fonts/Supplemental/Arial.ttf'
SANS_BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

TYPE_ORDER = [
    ('IC_VALUE_01_BEFORE', 'IC-v1', 'Value conflict · before'),
    ('IC_VALUE_01_AFTER', 'IC-v2', 'Value conflict · after'),
    ('IC_SOURCE_A_ONLY', 'IC-s1', 'Source on original claim'),
    ('IC_SOURCE_B_ONLY', 'IC-s2', 'Source on added claim'),
    ('IC_RELATION_01', 'IC-r', 'Relation conflict'),
    ('EA_01', 'EA-v1', 'First input deletion'),
    ('EA_02', 'EA-v2', 'Second input deletion'),
]


def load(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def collect():
    selection, selection_hash = load(PREPARED)
    review, review_hash = load(REVIEW / 'failure-review.json')
    generation, generation_hash = load(RUN / 'phase-reports/generation/data.json')
    preparation, preparation_hash = load(RUN / 'phase-reports/preparation/data.json')
    source_results_hash = hashlib.sha256((RUN / 'RESULTS.md').read_bytes()).hexdigest()

    raw = selection['totals']['total']
    selected = selection['totals']['selected']
    input_excluded = sum(selection['totals'][key] for key in ('empty_context', 'boolean_answer', 'duplicate_qc'))
    by_difficulty = [
        dict(name=name.removeprefix('finance-').title(), **selection['counts'][name])
        for name in ('finance-easy', 'finance-medium', 'finance-hard')
    ]
    for row in by_difficulty:
        row['excluded'] = row['total'] - row['selected']
    assert raw == 2238 and selected == 2050 and input_excluded == 188
    assert len(selection['exclusions']) == input_excluded
    assert sum(row['total'] for row in by_difficulty) == raw
    assert sum(row['selected'] for row in by_difficulty) == selected

    prep_stops = collections.Counter()
    gen_stops = collections.Counter()
    for row in review['rows']:
        if row['phase'] == 'Preparation':
            prep_stops[row['evidence']['run']['stopped_at']] += 1
        else:
            saved = json.loads((ROOT / row['refs'][0]).read_text())
            gen_stops[saved['restart']] += 1
    assert dict(prep_stops) == {'02-review': 90, '03-calculation': 33, '04-graph': 2, '05-verification': 87}
    assert dict(gen_stops) == {'01-perturbation': 745, '02-generate-text': 525, '03-validation': 397}
    assert len(preparation['errors']) == sum(prep_stops.values()) == 212

    types = {row['category']: row for row in review['generation_types']}
    assert set(types) == {code for code, _, _ in TYPE_ORDER}
    for row in types.values():
        assert row['total'] == 1838 and sum(row[key] for key in ('PASS', 'FAIL', 'NOT_EVALUATED', 'NOT_RUN')) == 1838
    totals = {key: sum(row[key] for row in types.values()) for key in ('PASS', 'FAIL', 'NOT_EVALUATED', 'NOT_RUN')}
    assert totals == {'PASS': 11199, 'FAIL': 1664, 'NOT_EVALUATED': 3, 'NOT_RUN': 0}
    assert sum(totals.values()) == 1838 * 7 == generation['summary'][0]['total'] * 7
    assert len(review['clean_cases']) == 1080 and len(review['nonclean_cases']) == 758
    assert 1080 + 758 == selected - 212 == 1838
    assert sum(gen_stops.values()) == totals['FAIL'] + totals['NOT_EVALUATED'] == 1667
    assert totals['PASS'] - 1080 * 7 == 3639
    # The pinned source files are concatenated in Easy, Medium, Hard order.
    # Resolve each passed original through the saved selection manifest, not
    # through the seven type-level result totals.
    source_bounds = []
    offset = 0
    for row in by_difficulty:
        source_bounds.append((row['name'], offset, offset + row['total']))
        offset += row['total']
    assert offset == raw
    selected_to_difficulty = {}
    for item in selection['ids']:
        raw_index = int(item['raw_id'].removeprefix('finance-test-'))
        matches = [name for name, start, end in source_bounds if start <= raw_index < end]
        assert len(matches) == 1 and item['id'] not in selected_to_difficulty
        selected_to_difficulty[item['id']] = matches[0]
    assert len(selected_to_difficulty) == selected
    assert collections.Counter(selected_to_difficulty.values()) == {
        row['name']: row['selected'] for row in by_difficulty
    }
    assert len(set(review['clean_cases'])) == 1080
    passed_difficulty = collections.Counter(selected_to_difficulty[item_id] for item_id in review['clean_cases'])
    assert sum(passed_difficulty.values()) == 1080
    return dict(
        source_run=RUN.name, raw=raw, selected=selected, input_excluded=input_excluded,
        exclusion_reasons={key: selection['totals'][key] for key in ('empty_context', 'boolean_answer', 'duplicate_qc')},
        by_difficulty=by_difficulty, preparation_failed=212, preparation_passed=1838,
        preparation_final_stops=dict(prep_stops), generation_originals=1838,
        generation_type_results=12866, generation_final_stops=dict(gen_stops),
        types=[dict(code=short, meaning=meaning, **types[code]) for code, short, meaning in TYPE_ORDER],
        type_totals=totals, all_seven_pass=1080,
        all_seven_pass_by_difficulty=[
            {'name': row['name'], 'count': passed_difficulty[row['name']]}
            for row in by_difficulty
        ],
        not_all_seven_pass=758,
        partial_type_pass=3639,
        evidence_sha256={
            str(PREPARED.relative_to(ROOT)): selection_hash,
            str((REVIEW / 'failure-review.json').relative_to(ROOT)): review_hash,
            str((RUN / 'phase-reports/preparation/data.json').relative_to(ROOT)): preparation_hash,
            str((RUN / 'phase-reports/generation/data.json').relative_to(ROOT)): generation_hash,
            str((RUN / 'RESULTS.md').relative_to(ROOT)): source_results_hash,
        },
    )


def render(data):
    """Draw the source-to-seven-types-to-original decision shown in the sketch."""
    canvas = Image.new('RGB', (WIDTH * SCALE, HEIGHT * SCALE), PAPER)
    draw = ImageDraw.Draw(canvas)
    font_cache = {}

    def font(size, family=SANS):
        key = (size, family)
        if key not in font_cache:
            font_cache[key] = ImageFont.truetype(family, round(size * SCALE))
        return font_cache[key]

    def label(x, y, value, size=24, color=INK, family=SANS, anchor='lt'):
        draw.text((round(x * SCALE), round(y * SCALE)), str(value),
                  font=font(size, family), fill=color, anchor=anchor)

    def centered(x, y, value, size=24, color=INK, family=SANS_BOLD):
        label(x, y, value, size, color, family, 'mt')

    def box(x, y, w, h, fill=WHITE, outline=RULE, radius=5, width=2):
        draw.rounded_rectangle(
            (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
            radius=radius * SCALE, fill=fill, outline=outline, width=width * SCALE,
        )

    def line(points, color=RULE, width=2):
        draw.line([(round(x * SCALE), round(y * SCALE)) for x, y in points],
                  fill=color, width=width * SCALE, joint='curve')

    def arrow(x1, x2, y, color=RULE, width=3):
        line([(x1, y), (x2 - 12, y)], color, width)
        draw.polygon(
            [(x2 * SCALE, y * SCALE),
             ((x2 - 15) * SCALE, (y - 9) * SCALE),
             ((x2 - 15) * SCALE, (y + 9) * SCALE)],
            fill=color,
        )

    def elbow_arrow(x1, y1, turn_x, y2, x2):
        line([(x1, y1), (turn_x, y1), (turn_x, y2)], width=3)
        arrow(turn_x, x2, y2)

    def down_arrow(x, y1, y2):
        line([(x, y1), (x, y2 - 12)], width=3)
        draw.polygon(
            [(x * SCALE, y2 * SCALE),
             ((x - 9) * SCALE, (y2 - 15) * SCALE),
             ((x + 9) * SCALE, (y2 - 15) * SCALE)],
            fill=RULE,
        )

    # The main route follows the user's sketch. Lines precede opaque nodes.
    box(30, 150, 4540, 845, fill='#fcfdfd', outline='#6f7a81', radius=14)
    arrow(360, 440, 580)
    arrow(780, 860, 580)
    arrow(1210, 1290, 580)
    down_arrow(610, 665, 745)
    down_arrow(1035, 665, 745)

    line([(1510, 580), (1560, 580), (1560, 300), (1560, 870)], width=3)
    for index in range(7):
        row_y = 300 + 95 * index
        arrow(1560, 1640, row_y)
        arrow(2090, 2210, row_y)
        arrow(2500, 2630, row_y)
        line([(3250, row_y), (3330, row_y)], width=2)
    line([(3330, 300), (3330, 870)], width=3)
    arrow(3330, 3420, 580)
    elbow_arrow(3780, 535, 3840, 470, 3900)
    elbow_arrow(3780, 625, 3840, 720, 3900)

    centered(WIDTH // 2, 22,
             'FinanceReasoning: From Raw Records to Seven-Type Validation',
             65, family=SERIF_BOLD)
    centered(WIDTH // 2, 102,
             'Saved final automatic states · source run 20260917-002',
             24, color=MUTED, family=SANS)
    label(65, 164, 'SOURCE & PREPARATION', 25, family=SANS_BOLD)
    label(1290, 164, 'EXPANSION', 25, family=SANS_BOLD)
    label(1640, 164, 'SEVEN PARALLEL TYPES', 25, family=SANS_BOLD)
    label(2210, 164, 'SHARED CHECKS', 25, family=SANS_BOLD)
    label(2630, 164, 'FINAL TYPE RESULTS', 25, family=SANS_BOLD)
    label(3420, 164, 'REJOIN BY ORIGINAL', 25, family=SANS_BOLD)

    def main_node(x, w, title, value, detail):
        box(x, 495, w, 170)
        label(x + 22, 513, title, 30, family=SERIF_BOLD)
        line([(x + 22, 558), (x + w - 22, 558)], color=HAIR)
        label(x + 22, 572, value, 59, family=SERIF_BOLD)
        label(x + 22, 638, detail, 20, color=MUTED)

    main_node(60, 300, 'Raw sources', '2,238', 'Easy / Medium / Hard')
    main_node(440, 340, 'Input selection', '2,050', 'selected originals')
    main_node(860, 350, 'Preparation', '1,838', 'originals PASS')

    box(60, 745, 300, 140, fill=SOFT, outline=HAIR)
    label(80, 761, 'Raw composition', 24, family=SANS_BOLD)
    label(80, 803, 'Easy 1,000', 23)
    label(80, 837, 'Medium 1,000 · Hard 238', 20)

    box(440, 745, 340, 140, fill=BAD, outline='#a88c81')
    label(460, 761, 'Excluded', 25, family=SANS_BOLD)
    label(460, 793, '188', 49, family=SERIF_BOLD)
    label(580, 823, 'before Preparation', 20, color=MUTED)

    box(860, 745, 350, 140, fill=BAD, outline='#a88c81')
    label(880, 761, 'Preparation FAIL', 25, family=SANS_BOLD)
    label(880, 793, '212', 49, family=SERIF_BOLD)
    label(1000, 823, 'originals', 20, color=MUTED)

    box(1290, 505, 220, 150, fill=SOFT)
    centered(1400, 521, 'Expand', 30, family=SERIF_BOLD)
    centered(1400, 558, '7 types', 49, family=SERIF_BOLD)
    centered(1400, 623, '12,866 candidates', 18, color=MUTED, family=SANS)

    label(1640, 210, 'Each type receives 1,838 originals', 20, color=MUTED)
    label(2630, 210, 'PASS / FAIL / not evaluated after retries', 20, color=MUTED)
    for index, row in enumerate(data['types']):
        y = 258 + 95 * index
        box(1640, y, 450, 84, fill=WHITE, outline=HAIR, radius=3, width=1)
        label(1658, y + 11, row['code'], 30, family=SANS_BOLD)
        label(1948, y + 12, '1,838', 27, family=SERIF_BOLD)
        label(1658, y + 48, row['meaning'], 20, color=MUTED)

    box(2210, 238, 290, 700, fill=SOFT, outline=RULE)
    centered(2355, 438, 'Generation', 31, family=SERIF_BOLD)
    centered(2355, 477, 'checks', 39, family=SERIF_BOLD)
    line([(2240, 534), (2470, 534)], color=HAIR)
    centered(2355, 560, 'structure', 22, color=MUTED, family=SANS)
    centered(2355, 595, 'meaning', 22, color=MUTED, family=SANS)
    centered(2355, 630, 'preservation', 22, color=MUTED, family=SANS)
    centered(2355, 694, '7 types checked', 21, family=SANS_BOLD)

    for index, row in enumerate(data['types']):
        y = 258 + 95 * index
        box(2630, y, 620, 84, fill=WHITE, outline=HAIR, radius=3, width=1)
        label(2646, y + 10, row['code'], 26, family=SANS_BOLD)
        label(2770, y + 10, f"PASS {row['PASS']:,}", 23, color='#31594b')
        label(2952, y + 10, f"FAIL {row['FAIL']:,}", 23, color='#8e5148')
        label(3115, y + 10, f"N/E {row['NOT_EVALUATED']}", 21, color=MUTED)
        label(2646, y + 48, 'final saved type status', 18, color=MUTED)

    box(3420, 485, 360, 190)
    centered(3600, 510, 'Group by', 33, family=SERIF_BOLD)
    centered(3600, 553, 'original ID', 36, family=SERIF_BOLD)
    line([(3450, 608), (3750, 608)], color=HAIR)
    centered(3600, 624, '1,838 original questions', 20, color=MUTED, family=SANS)

    box(3900, 385, 600, 205, fill=GOOD, outline='#6c8b7c')
    label(3924, 405, 'AND  ·  all 7 types PASS', 27, family=SANS_BOLD)
    label(3924, 447, '1,080', 67, family=SERIF_BOLD)
    label(4170, 490, 'originals', 22, color=MUTED)
    line([(3924, 525), (4476, 525)], color=HAIR, width=1)
    difficulty_summary = '  ·  '.join(
        f"{row['name']} {row['count']:,}"
        for row in data['all_seven_pass_by_difficulty']
    )
    label(3924, 540, difficulty_summary, 24, color='#31594b', family=SANS_BOLD)

    box(3900, 635, 600, 170, fill=BAD, outline='#ad8f85')
    label(3924, 655, 'OR  ·  ≥1 type FAIL / N/E', 27, family=SANS_BOLD)
    label(3924, 697, '758', 67, family=SERIF_BOLD)
    label(4140, 740, 'originals', 22, color=MUTED)

    # Compact evidence panels keep denominators separate from the main route.
    line([(55, 1025), (4545, 1025)], color=HAIR, width=2)
    label(60, 1040, 'Counted exits and stage details', 34, family=SERIF_BOLD)
    panels = [
        (60, 1090, 940, 355),
        (1030, 1090, 1090, 355),
        (2150, 1090, 1120, 355),
        (3300, 1090, 1240, 355),
    ]
    for x, y, w, h in panels:
        box(x, y, w, h, outline=HAIR, radius=3, width=1)

    label(82, 1110, 'Source selection', 30, family=SERIF_BOLD)
    label(82, 1160, 'Difficulty', 21, family=SANS_BOLD)
    for x, name in ((360, 'Raw'), (560, 'Selected'), (770, 'Excluded')):
        label(x, 1160, name, 21, family=SANS_BOLD)
    line([(82, 1195), (978, 1195)], color=HAIR)
    for index, row in enumerate(data['by_difficulty']):
        y = 1205 + 54 * index
        label(82, y, row['name'], 24)
        label(360, y, f"{row['total']:,}", 24)
        label(560, y, f"{row['selected']:,}", 24)
        label(770, y, f"{row['excluded']:,}", 24)
    line([(82, 1373), (978, 1373)], color=HAIR)
    label(82, 1385, '188 = empty context 168 + boolean 14 + duplicate 6',
          20, color=MUTED)

    label(1052, 1110, 'Preparation stages', 30, family=SERIF_BOLD)
    prep_rows = [
        ('Source Intake', '—'),
        ('Original Review', '90'),
        ('PoT Authoring & Run', '33'),
        ('Execution & Graph', '2'),
        ('Preparation Checks', '87'),
    ]
    for index, (name, stops) in enumerate(prep_rows):
        y = 1160 + index * 49
        label(1052, y, name, 23)
        label(1940, y, stops, 23, family=SANS_BOLD)
    line([(1052, 1410), (2096, 1410)], color=HAIR)
    label(1052, 1418, '212 final stops; 1,838 originals passed', 19, color=MUTED)

    label(2172, 1110, 'Generation stages', 30, family=SERIF_BOLD)
    gen_rows = [
        ('Perturbation Plan', 745),
        ('Text Realization', 525),
        ('Generation Checks', 397),
    ]
    for index, (name, stops) in enumerate(gen_rows):
        y = 1170 + index * 62
        label(2172, y, name, 24)
        label(3130, y, f"{stops:,}", 24, family=SANS_BOLD)
    line([(2172, 1364), (3248, 1364)], color=HAIR)
    label(2172, 1375, '1,667 type final stops = 1,664 FAIL + 3 N/E', 21)
    label(2172, 1410, 'These counts are type outcomes, not originals.', 19, color=MUTED)

    label(3322, 1110, 'Original-level decision', 30, family=SERIF_BOLD)
    label(3322, 1170, '1,080 all-seven PASS  +  758 partial  =  1,838', 25)
    label(3322, 1222, 'Within the 758 partial originals:', 23, family=SANS_BOLD)
    label(3322, 1262, '3,639 type PASS  ·  1,664 type FAIL  ·  3 N/E', 22)
    line([(3322, 1322), (4518, 1322)], color=HAIR)
    label(3322, 1340, 'AND / OR applies after matching all seven', 21, color=MUTED)
    label(3322, 1373, 'type results to each original question.', 21, color=MUTED)
    label(3322, 1410, 'Saved automatic status only; no human approval.', 19, color=MUTED)

    label(60, 1480,
          'Fig. 1. Final states after bounded retries. Source and Preparation exits count originals; Generation exits count original × type outcomes.',
          21, color=INK)
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    ASSET.mkdir(parents=True,exist_ok=True)
    data=collect()
    image=render(data)
    png=ASSET/'dataset-pipeline-2238-to-1080.png'
    image.save(png,optimize=True)
    digest=hashlib.sha256(png.read_bytes()).hexdigest()
    summary=dict(data,figure_path=str(png.relative_to(ROOT)),figure_png_sha256=digest,width=WIDTH,height=HEIGHT,
                 generated_at=datetime.now(timezone.utc).isoformat(),model_calls=0,
                 scope='Saved automatic outcomes; not a new production run or human semantic judgment.')
    (OUTPUT/'figure-data.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    template=Path(__file__).with_name('pipeline-figure-readme-template.md').read_text()
    (OUTPUT/'README.md').write_text(template)
    log=[dict(event='read_saved_evidence',sources=list(data['evidence_sha256']),model_calls=0),
         dict(event='reconcile_populations',raw=2238,selected=2050,preparation_passed=1838,
              type_results=12866,all_seven_pass=1080,
              all_seven_pass_by_difficulty=data['all_seven_pass_by_difficulty']),
         dict(event='render_png',path=str(png.relative_to(ROOT)),width=WIDTH,height=HEIGHT,sha256=digest)]
    (OUTPUT/'figure-log.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in log))
    print(json.dumps(dict(path=str(png),sha256=digest,width=WIDTH,height=HEIGHT),ensure_ascii=False))


if __name__=='__main__':
    main()
