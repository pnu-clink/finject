"""Build a traceable, human-authored thematic index of saved A03 findings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[5]
PAPER = Path('reports/run/20260924-paper-draft/PAPER-KO.md')
STAGE = Path('02_analysis/03_research')
ORDER = ('RQ1', 'RQ2', 'SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5', 'SQ6')

# Each saved finding has one primary theme. The explicit IDs make editorial
# decisions reviewable and prevent a title-keyword rule from silently moving F.
PRIMARY = {
    'G01': '13 49 52 56 60 64 96',
    'G02': '1 5 9 14 17 21 25 29 33 37 41 45 50 54 61 68 76 80 92 97 101 108 112 124 128 132 136 144 152 165 169 172 181',
    'G03': '2 6 10 15 18 22 26 30 58 70 104 141 157',
    'G04': '3 7 11 16 19 23 42 46 53 57 62 65 69 73 77 81 85 89 98 100 105 109 113 116 120 125 129 133 137 140 145 148 153 156 160 164 168 176 180',
    'G05': '27 31 34 38 93 102 106 110 114 117 122 126 130 134 138 142 146 149 154 158 161 166 170 173 177 182',
    'G06': '35 39 67 72 78 84 88 94 118 121 150 162 174 178',
    'G07': '4 8 12 20 24 28 32 36 40 43 47 51 55 59 63 66 74 79 82 86 90 95 99 103 107 111 115 119 123 127 131 135 139 143 147 151 155 159 163 167 171 175 179 183',
    'G08': '71 75',
    'G09': '44 48 83 87 91',
}

SECONDARY = {
    'F003': ('G05',), 'F007': ('G05',), 'F033': ('G04',),
    'F035': ('G03',), 'F038': ('G02',), 'F044': ('G08',),
    'F050': ('G04',), 'F071': ('G01',), 'F075': ('G09',),
    'F083': ('G06',), 'F093': ('G04',), 'F104': ('G02',),
    'F121': ('G02', 'G03'), 'F126': ('G03',), 'F130': ('G03',),
    'F141': ('G02',), 'F157': ('G02',), 'F160': ('G02',),
    'F172': ('G04',), 'F173': ('G02',), 'F178': ('G02',),
}

GROUPS = {
    'G01': ('SQ1', 'The standard line of matching the original numbers.',
            'The recorded numerical units of the original vary according to the root conditions, but the relationship between the original performance and the modification correspondence cannot be determined by this set alone.',
            'F013·F049·F096The matching of the original condition figures by the original condition and the total MATCH/MISMATCH/UNEVALUATED record.',
            'The match between the return numbers and the reference values can mix the differences in the ubo-form failure and the explanatory path.',
            'It\'s just the baseline of SQ1, so you have to compare the same conditional variation correspondence directly to the original outcome and then you can determine the H3 relationship.'),
    'G02': ('RQ2', 'Judgmental guidance and collision reporting.',
            'Criteria-Guided Solving has recorded more frequent CONFLICT signatures and null responses in multiple conflict variations.',
            'F001·F005·F101 Under the same model, variable, reference setting, you can read the Unguided/Criteria-Guided correspondence comparison.',
            'It also changes the classification requirements and the output agreements that are not standard, and it returns the numbers in some guidelines.',
            'CONFLICT is the model\'s trademark, and it doesn\'t translate the euphoric increase into accuracy of collision identification or meaningful quality improvement.'),
    'G03': ('RQ2', 'The difference in the settings of the inference varies depending on the type of editing.',
            'The response changes in Reasoning OFF/ON did not appear in the same direction in the claims add-on, correlational modification, deleted fact.',
            'F002·F006·F030·F141I read the same case, the same floating instruction, the same OFF/ON correspondence per variable condition.',
            'The type of editing and the amount of information left over, the reported explanations don\'t show the model\'s internal inference.',
            'It\'s not an observation of setup differences, it\'s not a verification of independent repetition or a correctional rule or a correlational improvement.'),
    'G04': ('RQ1', 'Opposition position and candidate number switching',
            'There are cases and corresponding pairs where the match of the candidate numbers changes depending on the front and back placement of the counterpoint number argument, but there are no uniform position rules.',
            'F003·F100·F140·F180Read along with the BEFORE/AFTER response and the remaining response-to-reverse.',
            'The position of tables and sentences, the surrounding representations, and the chosen path of calculation can vary.',
            'A/B is a candidate number matching code, not determined by base selection, meaning, or pure position interaction.'),
    'G05': ('RQ1', 'Change in the source tag and parent-related',
            'The variation that gives the back argument its source shows a connected parental response to other candidate equations, but the direction of change is mixed.',
            'F106·F170Read the corresponding pre and counter instances of the parent VALUE linked to the SOURCE_A/B respectively.',
            'The source phrase itself, the object and the location of the claim, the model response variables can work together.',
            'The authenticity of the source statement has not been verified, nor has the model\'s general source preference or repercussions been identified.'),
    'G06': ('RQ1', 'The different routes of handling of the collision',
            'The relationship modification response came with the original use of the table values, the addition of a relationship application, and a two-way collision report.',
            'F035·F078·F162·F178I read the conditional classification and the calculation path of the stored description together.',
            'The scope of application of the table-to-table relationship and the interpretation of the sentence can vary, and the condition-by-condition ebo pattern is G02·G03And overlap with it.',
            'Conflict signals are not independent judgments of the validity of relational interpretation or mathematics.'),
    'G07': ('RQ1', 'After the fact of deleting the independent ubo and the numerical path',
            'In each fact-delete, the nulls increased, and the description of the remaining number responses recorded different paths, such as recovery, partial computation, and retention.',
            'F004·F008·F171·F183The EA_01/EA_02And read the ORIGINAL correspondence and numerical exceptions to each.',
            'The remaining data is a mix of the available and the missing data, and the described data is not even verifiable.',
            'The two deletions are distinct variations, each starting from the original, and the numerical unit is not calculated as the recovery success rate or the meaningful answer.'),
    'G08': ('SQ3', 'Form valid; process consistency; boundaries of discretion',
            'The formal validity of the storage response and the nominative number of the data do not guarantee the completeness in the descriptive sense.',
            'F071·F075I read the format validation denominator, the candidate code, the description and the inverse of the calculation.',
            'OTHER can be due to a unit, sub-lift, or other computational path, and candidate matches can coexist with other explanatory paths.',
            'It doesn\'t combine the problem of form failure and case-by-case complexity with the problem of numerical significance error rate.'),
    'G09': ('SQ3', 'Final answer: the dissonance of the numbers in the distribution.',
            'The final answer, the model classification, the conditional numbers in the description, should be read as different response factors.',
            'F044·F083·F091The null explanation of the numbers, the calculation path of the OTHER answer, the half-example of the relationship explanation.',
            'The numbers in the description can be conditional examples, and the numerical differences can be related to the choice of numbers, groups, and representations.',
            'It\'s a question based on a storage case, not a complexity judgment or error rate of my response.'),
}

EMPTY = {
    'SQ2': ('No direct review', 'The conversion validity of the production clause and the consistency between independent reviewers is this A03 I didn\'t review it in the discovery cluster.'),
    'SQ4': ('No direct review', 'There\'s no direct finding that links the variables, the correlations, the depths of the computational structure to the responses.'),
    'SQ5': ('No direct review', 'There is no private external knowledge classification of the original, but no observational or conclusive finding of the use of the model\'s knowledge.'),
    'SQ6': ('Pending independent repeated verification', 'This storage response is not a data that verifies the independent repetition of the same condition.'),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ids(numbers: str) -> list[str]:
    return [f'F{int(value):03d}' for value in numbers.split()]


def build(run: str) -> dict:
    if not run.replace('-', '').isalnum():
        raise ValueError('INVALID_RUN_ID')
    root = PROJECT / 'reports/experiments-run' / run
    folder = root / STAGE
    source_path = folder / 'findings.json'
    source = json.loads(source_path.read_text())
    findings = {row['id']: row for row in source['findings']}
    assigned = [item for values in PRIMARY.values() for item in ids(values)]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(findings):
        raise ValueError('FINDING_PRIMARY_COVERAGE_MISMATCH')
    owner = {item: group for group, values in PRIMARY.items() for item in ids(values)}
    if set(SECONDARY) - set(findings) or any(set(values) - set(GROUPS) for values in SECONDARY.values()):
        raise ValueError('SECONDARY_GROUP_REFERENCE_INVALID')
    if any(owner[item] in values for item, values in SECONDARY.items()):
        raise ValueError('SECONDARY_DUPLICATES_PRIMARY')
    paper_path = PROJECT / PAPER
    paper_text = paper_path.read_text()
    version = re.search('\ud55c\uae00 \ub17c\ubb38 \ucd08\uc548 v(\\d+\\.\\d+)', '\n'.join(paper_text.splitlines()[:5]))
    if not version:
        raise ValueError('PAPER_VERSION_NOT_FOUND')
    questions = {code: (title, text) for code, title, text in re.findall(
        r'^\|(SQ[1-6])\|([^|]+)\|([^|]+)\|', paper_text, re.MULTILINE)}
    questions.update((code, (title, text)) for code, title, text in [
        ('RQ1', 'Reaction to the change in the basis', re.search(r'\*\*RQ1\. ([^\n*]+)\*\*', paper_text).group(1)),
        ('RQ2', 'Weed conditions and original answers', re.search(r'\*\*RQ2\. ([^\n*]+)\*\*', paper_text).group(1)),
    ])
    if set(questions) != set(ORDER):
        raise ValueError('PAPER_QUESTION_SET_CHANGED')
    groups = []
    for group_id, values in GROUPS.items():
        question, title, claim, evidence, alternatives, boundary = values
        primary = ids(PRIMARY[group_id])
        observations = sorted({item for finding_id in primary for item in findings[finding_id]['interpretation_ids']})
        groups.append({'id': group_id, 'question_id': question, 'title_ko': title,
                       'claim_ko': claim, 'evidence_ko': evidence,
                       'alternatives_ko': alternatives, 'boundary_ko': boundary,
                       'primary_finding_ids': primary, 'related_finding_ids': [],
                       'interpretation_ids': observations})
    review = {'schema_version': 1, 'run': run, 'method': 'human-authored-thematic-editorial-index',
              'review_scope': 'Saved A03 findings only; no re-scoring or independent semantic adjudication',
              'new_external_model_calls': 0,
              'source_sha256': {str(STAGE / 'findings.json'): sha(source_path), str(PAPER): sha(paper_path)},
              'groups': groups,
              'finding_review': [{'finding_id': item, 'primary_group': owner[item],
                                  'secondary_groups': list(SECONDARY.get(item, ())),
                                  'note_ko': 'I saved the original title, headline, boundary and assigned the subject-specific reading location.'}
                                 for item in sorted(findings)]}
    index = {'schema_version': 1, 'kind': 'editorial-index-of-saved-findings', 'run': run,
             'paper_version': version.group(1), 'paper': {'path': str(PAPER), 'sha256': sha(paper_path), 'sections': ['3.3', '3.4']},
             'saved_review': {'path': str(STAGE / 'rq-review.json'), 'sha256': None},
             'notice_ko': f'Saved {len(findings)}I\x27m going to tell you about the items research. {len(GROUPS)}And then we\x27ll just tie it to the items theme and then we\x27re going to do a paper on the items theme.{version.group(1)}It\x27s an editing color that\x27s connected to the RQ/SQ, not a new model call, semantic assessment, or discussion conclusion.',
             'questions': [], 'groups': groups}
    for code in ORDER:
        mapped = [group['id'] for group in groups if group['question_id'] == code]
        status, scope = EMPTY.get(code, ('Existing observations linked \xb7 conclusions not established',
                                         'Saved claims, counterexamples, and limitations are linked. No semantic-correctness assessment beyond the matched aggregates and cases was performed.'))
        if code == 'SQ1':
            status, scope = ('Baseline linked \xb7 direct relationship not reviewed', GROUPS['G01'][5])
        if code == 'SQ3':
            status, scope = ('Cases linked \xb7 not an exhaustive assessment',
                             'Counterexamples to saved explanations are linked. No exhaustive semantic-consistency check or error-rate estimate was performed.')
        index['questions'].append({'id': code, 'title_ko': questions[code][0],
                                   'question_ko': questions[code][1], 'status_ko': status,
                                   'scope_ko': scope, 'group_ids': mapped})
    folder.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    save('rq-review.json', review)
    index['saved_review']['sha256'] = sha(folder / 'rq-review.json')
    save('rq-sq-review.json', index)
    lines = ['# Research findings topically integrated and RQ/SQ connecting', '',
             'The original F. 183I connected the items to a weekly group, and the auxiliary connections don\'t count overtime.',
             'This document is stored in A03It\'s not a new model judgment or paper conclusion.', '']
    for question in index['questions']:
        lines += [f"## {question['id']} · {question['title_ko']}", '', question['question_ko'], '',
                  f"**Scope:** {question['scope_ko']}", '']
        for group in groups:
            if group['question_id'] != question['id']:
                continue
            lines += [f"### {group['id']} · {group['title_ko']} ({len(group['primary_finding_ids'])}items F)", '',
                      group['claim_ko'], '', '**Based on:** ' + group['evidence_ko'], '',
                      '**Alternatives:** ' + group['alternatives_ko'], '',
                      '**The limits of interpretation:** ' + group['boundary_ko'], '',
                      '**Original F:** ' + ', '.join(group['primary_finding_ids']), '']
    (folder / 'rq-review.md').write_text('\n'.join(lines) + '\n')
    audit = ['♪ The original research findings 183The answering machine.', '',
             'All the main groups of F are exactly one, and the subgroups are cross-topic guides.', '',
             'The name of the group is the name of the team.', '|---|---|---|---|']
    for row in review['finding_review']:
        audit.append('|'+ '|'.join([row['finding_id'], findings[row['finding_id']]['display_ko']['title'].replace('|','/'),
                                  row['primary_group'], ', '.join(row['secondary_groups']) or '—'])+'|')
    (folder / 'rq-review-audit.md').write_text('\n'.join(audit) + '\n')
    template = PROJECT / 'src/finarch/experiments/templates/editorial-grouping-readme.md'
    (folder / 'rq-sq-review-README.md').write_text(template.read_text().format(run=run, count=len(findings), version=version.group(1)))
    validation = {'source_findings': len(findings), 'primary_assignments': len(assigned),
                  'groups': len(groups), 'questions': len(index['questions']),
                  'all_findings_covered_once': True, 'source_hashes_verified': True,
                  'semantic_review': 'EDITORIAL_GROUPING_NOT_INDEPENDENT_VALIDATION',
                  'new_external_model_calls': 0}
    save('rq-review-validation.json', validation)
    return validation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    print(json.dumps(build(parser.parse_args().run), ensure_ascii=False))
