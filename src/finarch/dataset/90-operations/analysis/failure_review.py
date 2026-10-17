"""Build an evidence-linked descriptive review without model calls or mutation of inputs."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = (Path(__file__).resolve().parent / '../../../../..').resolve()
SOURCE = ROOT / 'reports/run/20260917-002'
OUTPUT = ROOT / 'reports/run/20260920-002-failure-review'
INPUTS = {}


def read(path):
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def save(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


# Editorial classifications describe saved observations; they do not certify semantic truth.
CAT = {}


def category(key, phase, title, owner, why, supply, fix, example, confidence='Causal classification based on records; improvement effects are misdiagnosed'):
    CAT[key] = dict(id=key, phase=phase, title=title, owner=owner, why=why,
                    supply=supply, fix=fix, example=example, confidence=confidence)


category('P_PERIOD', 'Preparation', 'The company and the data in question are not correct.', 'Original verification and replacement',
         'There\'s no time or company number required in the question, and if you use a different time to get the correct answer, the question itself will change.',
         'You have to provide a table, a table title, a keyword that matches the company and the report in question.',
         'We check the source of the question for a missing document, and then we make the verified copy a separate version, and then save the reason for the change.',
         'test-0022The question is: 2014years, while the table 2004·2003years. 2004What the fuck? 875−848=27It\'s like this storage answer. 2014You can\'t say that\'s the answer.')
category('P_MISSING', 'Preparation', 'The amount, the answer, the condition is missing.', 'Original backup + prepping steps verified',
         'And even if you use the same numbers as you can see, it\'s not the value that the question asks for, and it\'s hard to verify the calculation without adding the necessary values or the necessary conditions.',
         'You have to specify what each number is worth, what range, what the starting value is, how much, and where you want to trade.',
         'First, we compare the list of items needed to be calculated with the items provided, and the missing items are complementary to the source, and not replaced by similar items or correct answers.',
         'test-0029So, I\'m asking you how many shares are allowed to be issued, and the actual number of shares is not the same.')
category('P_MEASURE', 'Preparation', 'It\'s not clear what the price or rate is.', 'Question clarification or review criteria supplement',
         'The table has multiple calculations, but the question is not well defined or the method of comparison is not enough, and the review is stopped, and not all cases are confirmed to be original errors.',
         'For example, it specifies whether the basic dividend is a dividend or a dividend, or a simple difference or a change in the rate.',
         'So we compare two different interpretations, and we first acknowledge that the financial terms alone make sense, and then we supplement the question.',
         'test-0214The basic dividend is: 1.563So, the dividend payout is 1.551But the question is not which.')
category('P_CONVENTION', 'Preparation', 'I haven\'t figured out how far to go with the calculation practice.', 'Priority review criteria supplement; only the necessary conditions are added to the original',
         'The review machine stopped because there were other procedures, like interest rate calculation, average, and subtraction, and the fact that you didn\'t write the procedure in the sentence doesn\'t make the original wrong.',
         'It provides the numerical standard, the method of replication, the method average, the initial value, the method reversal as common guidelines or case conditions.',
         'We set the basic rules and the basis for the application in advance, using a clear standard method of naming, and actually only requiring additional conditions if the competing interpretation changes the outcome.',
         'test-0965The simple average of the per-family rate is: 181.64So the total price of the whole thing is 180.00So you can just figure out what average you want.')
category('P_SCALE', 'Preparation', 'The unit-to-correct vote is not the question.', 'Original, correct answer, verification of metadata + cleaning supplement',
         'You mixed dollars and thousands of dollars, the prime and the percentage, the question number and the answer number, and you compared the numbers, and you compare the values of different meanings.',
         'It\'s a unit of the table, a unit of output, a digit, a base of the correct output.',
         'It converts the values and units together and records the pre-conversion, and instead of changing the questions or the numbers to match the correct answer, it determines which records to correct as the source.',
         'test-0320: 713Thousands of times.42The dollar is 29.946That\'s a million dollars. 30But the answer is, 29,946.')
category('P_TEXT', 'Preparation', 'I couldn\'t fix the broken text and date safely.', 'The rules of purification',
         'The date is either stuck or the punctuation is left as a number, and the current rule protects the numbers, so it can\'t stop the text from breaking or confirm the correct position.',
         'It\'s a pre-breaking code, a clean sentence, and a location matching sign for both sentences.',
         'It distinguishes between the broken letters identified by the source and the actual numbers, the repeated phrases are assigned to the location and surrounding phrases, and all edits are applied at once on a primitive basis.',
         'test-0229: “december 292000The task of separating the shell from the date was treated as a numerical change.0300The reiteration stopped at the correction position of the sentence.')
category('P_VERIFY_UNCERTAIN', 'Preparation', 'The calculations were done, but the review didn\'t confirm the interpretation.', 'Priority replenishment; verification of the original by paragraph',
         'Apart from the calculation, the reviewer couldn\'t confirm the meaning and the order of the question, which is different from the validation judgment that it\'s wrong.',
         'It provides the selected items, the category, the duration, the form and the reasons for their selection, together with the answers that make the alternative interpretation actually work.',
         'First, we re-examine the excessive ambiguity judgments that ignore the sensible direction and financial practices, and the rest are complementary to the question of actual ambiguity.',
         'test-0014: 1The quarter. 60%in 2The quarter. 50%It\'s changed to −.10%The change and decrease in width of p 10%You can only tell p. You don\'t have to think of every case as a lack of data.')
category('P_VERIFY_FAIL', 'Preparation', 'There are some inconsistencies in the analysis of the whole, the explanation, the evaluation.', 'The first step in the calculation and verification process',
         'The reviews in the archive have pointed to problems with calculation, composition, approximation, or explanation. 14Not all of them are validated by calculation errors.',
         'It provides the middle calculation, the original sentence used, the unit and the final inverse rule.',
         'If we correct a wrong calculation, if we force a single rule to be reviewed without a basis, we correct a reviewer, even if the numbers are random, and the unit doesn\'t pass another calculation.',
         'test-0083The index: 100→205The change in the face. 105It\'s a point. 105%So if you\'re going to say, "The numbers are the same", then the amount of questions you ask will vary.')
category('P_GOLD', 'Preparation', 'The calculation and the storage are different.', 'Original answer: Re-certification of the account',
         'The meaning review passed, but the calculation results and the storage correctness stopped, so just passing the meaning review can\'t confirm that the storage correctly.',
         'We need not just the exact numbers, but the base lines, the formulas, the mean, the units, and the inverse rules.',
         'We use the source items to recreate both calculations and find the points where the difference is, to ban numerical adjustments to match the correct answer, and to preserve the existing exclusion status and the original.',
         'test-0349The execution value is: 480.0The answer is, 129.6We have to distinguish between what\'s different and what\'s right.')
category('P_NOANSWER', 'Preparation', 'I didn\'t have the information I needed, so I couldn\'t make a numerical answer.', 'Original backup + early confirmation in the preparation phase',
         'The resulting loop left the answer blank, but the runner stopped because it only received numbers, not just a number reading error.',
         'It gives you the necessary numbers and conditions for the question, and if not, what\'s missing.',
         'It returns the missing information to a separate state before it runs and supplements the data you need from the source. 0Or you don\'t put the correct numbers in temporarily.',
         'test-0324I\'m asking about the tax bill and the tax bill, but the data only shows the remaining unpaid taxes.')
category('P_NUMBER', 'Preparation', 'The program didn\'t get the numbers that people read.', 'Number clearance: Regular supplementation',
         'four, five, three, six months, EUR90The meaning is read, but it didn\'t fit the program that predicted only numbers.',
         'The source items expression, the meaning, the same numerical value, the unit, the source items position, is given as a set.',
         'It complements the number-rules.json and the number register to process the number of characters and the call prefix, leaves the font and the conversion log, and checks the return of the same expression, and this analysis hasn\'t changed the rules.',
         'test-0768So, what\'s the point? 4It was written, but the original was rejected, not a token, but a number.')
category('P_LINK', 'Preparation', 'The source code link information is not correct.', 'Repair, close connection, inspection process',
         'The quote\'s location, the code line, the name of the formula, the input that connects to the calculation, etc. were not correct, so I stopped before I checked the contents.',
         'It provides the same version of the source code and the same function of the question, the quote position, the code line, the value.',
         'After the sentence is cleared, we re-calculate the location and compare it to the actual quotation, and we also distinguish the values that were not included in this calculation from the repeat and condition box, and we divide the generating error and the checker error into the original record.',
         'test-1957The quote position included the end of the sentence, but there was no end in the quote.')
category('P_CODE', 'Preparation', 'The code generated doesn\'t match the execution rules.', 'Generate and execute code',
         'So you just put the subset in a place that requires an integer, like a list position, and you stop the calculation.',
         'It gives us a number value, a value, a quantity, and so on.',
         'We use the numbers to determine if a number is a positive integer, and we don\'t make a total adjustment to the formula for changing the number to a positive intege.',
         'test-1948The observation number was mistakenly passed and stopped in the calculation of the list range.')
category('P_TRANSPORT', 'Preparation', 'I didn\'t get the answer to the end.', 'Execution and incident management',
         'We didn\'t finish the test with a failure to connect or an incomplete response, which is not proof that the data is wrong.',
         'The data content is kept in place, and the request identifier, the completed state, and the call response are preserved.',
         'It separates the communication re-runs and the content-modification re-rums and re-opens safely from the finished stage.', 'Preparation 7The connection failed. 6That\'s it. 1That one.')

category('G_NUM_DUP', 'Generation', 'The same number as the deleted value is left in the preserve list.', 'Transformational planning and numerical testing',
         'The value to delete is repeated over the same editing interval, and you only click once in the number list, so the actual request requires you to save the same number, so if you delete it completely, it can take a number check.',
         'It\'s the same thing that makes a distinction between the whole repeating position and each role, the deleted position and the left position.',
         'Instead of deleting them all just because they\'re the same, we check if they\'re repeating the same thing, and then we tie them to the deleting plan, and the scanner uses the rest of the list of numbers.',
         'test-0012The source is:6% (6 The list of permissible numbers for the request that you saved is %). 6And this one is left, and it\'s in conflict with the purpose of deleting both expressions.',
         'The statistic is the number of candidates that are left on the list of deleted objects, and even if the same number is different, they\'re not all confirmed for the same cause.')
category('G_NUM', 'Generation', 'It\'s not the same as the actual editing results.', 'Editing planning, creativity and testing',
         'Not only if you put in a new number, but if you\'ve lost a year, a different amount, or if you\'re counting the same number, you don\'t just have to make a number by mistake.',
         'The deleted object and the retained lead are marked by the position of the element, and the number that appears as a character breach is first distinguished.',
         'We compare the actual pre-edit numbers to the figures, and then we separate the difference between the add-on and the sub-add-on, and if the test conditions are wrong, we fix the planning and scanning instead of the generating line.',
         'This is a categorization of the total number of failures. 279The number of deleted objects from the type remaining on the preserve list 40Type the type. 239type.')
category('G_UNCHANGED', 'Generation', 'So if you change the value or the relationship, the final answer doesn\'t change.', 'Modified object selection supplement',
         'The input that doesn\'t affect the answer, 0The resulting value, the same returns, the last inverse, etc. doesn\'t produce the different answers that the current candidate needs, and each cause requires no confirmation.',
         'It gives you how the response after the counter-lift varies and the permissible range when you change each input.',
         'Instead of selecting the first number that appears, we\'re looking for other input and output that affect the answer, and we\'re not pushing it past an exaggerated number that\'s out of range.',
         'Change the value 276Type, change of relationship 32The type stops with the answer unchanged, and the same pre-calculation problem is repeatedly recorded in the source type, and it\'s not the same as the number of cause cases.')
category('G_QUESTION', 'Generation', 'We didn\'t get the numbers in the question to the next level.', 'Interstep data transfer complement',
         'The source of the numbers used in the calculation is the question, and the next step is to get the question string and not be able to locate it, which doesn\'t mean there\'s no question in the original.',
         'We need to get the source-differentiation and correction versions of each of the text, the query, and the numbers together.',
         'It fixes the path that only the text is sent, and it keeps the value of the source of the question to the end, so it doesn\'t mix the position of the text with the question position.',
         'test-0250The failure to save is the missing query source string, not the task of rewriting the question, but the task of verifying the passage between steps.')
category('G_CONTROL', 'Generation', 'So you can\'t just write the condition-by-reverse calculation after you\'ve deleted the value.', 'Calculation representation and analysis support',
         'When there\'s a number, it\'s calculated, but the conditioned and half-representation of the value is lost, and the program doesn\'t support it now, so the work that was trying to create the data shortage is within the scope of the program support.',
         'It gives results that vary depending on the flow of computation and the conditions that left the deleted input with an unknown value.',
         'It\'s complementary to the calculation of the parameters, including the default values, and it doesn\'t validate the fact that the program isn\'t running as an unanswered problem.',
         'test-0003Two types of deletion have stopped at this stage. The current implementation will explicitly stop if there is a mismatched input to the condition-reverse calculation.')
category('G_DEP', 'Generation', 'The front-end created collision phrases failed to pass', 'Fix the front step + reboot',
         'The type that\'s going to be the source must first have a verified collision phrase, and if there\'s no front step or failure, then the next step stops.',
         'Provides a text of the front or rear collision passing through the same case as the execution and its judgment records.',
         'It solves the cause of the associated value change type failure before you rearrange the source phrase. The subsequent stop does not count backwards for any original error.',
         'No confirmed collision record, blocked records. 116No items and no forwarding phrase. 12I tied the items up.')
category('G_INQUESTION', 'Generation', 'If you delete it from the text, the same number remains in the question.', 'Objective selection: correctly actually the addition of the',
         'The question is fixed and the text is deleted, and the question has the same number, and the deleted candidate is blocked, and the current comparison is overlapping, so it doesn\'t even guarantee the same thing.',
         'It gives all the positions and values a role that points to the same fact in the main subject.',
         'Instead of a simple number match, we check that it\'s the same thing, and then we select another element that\'s not in the question. If the actual element is fixed in the question, it can\'t be used as a text-delete.',
         '109The type is blocked by this condition, and not all of these numbers are valid for exposure.')
category('G_SECOND', 'Generation', 'And the second time, I couldn\'t find the clearing entry.', 'Check the list of input types',
         'Now, there\'s only one input that\'s registered in the array, and it requires the type that deletes the second input, which doesn\'t necessarily mean that there\'s one value in the entire array.',
         'It gives you a list of inputs you actually need to answer and the location of each input.',
         'If there\'s a missing essential input, it complements the extraction, and instead of creating a second input that doesn\'t exist if there\'s actually only one problem, it separately determines the type of application.',
         'test-0001There\'s no second deletion object, it stopped before it was created, and the rewrite procedure won\'t work.')
category('G_INTENT', 'Generation', 'I changed the sentence, but I didn\'t get the problem I wanted.', 'Transformational planning and problem-creating complement',
         'The deleted values are left elsewhere, or the object, time, and source of the conflict are rejected in the review, as opposed to the plan.',
         'Specifies the amount of the company, the duration, the category, the recurring position, the relevant aggregate, the other pool path, the claim attached to the source.',
         'The deletion investigates the repetition of the same fact and the path to restore the answer, to see if the value conflict is two claims about the same object, or if the source only holds to one claim that is specified.',
         'test-0004The second type of deletion: table 99I erased the remainder, but I repeated the remainder. 2008The year-end amount is explained 99I\'m left with it.')
category('G_READ', 'Generation', 'After deleting, adding, or missing, the phrase or tag is broken.', 'Line boundary and editing method',
         'You can just delete the number position or put the sentence in the wrong place, and the grammatical and punctuation structure is broken.',
         'It provides the boundaries of the sentence and the marking cells to edit and the surrounding context to maintain.',
         'The tables edit the cells, the tables erase the amount, then the phrases are minimized, and the phrasing that\'s broken from the beginning is checked and the phrase that\'s broke is checked.',
         'test-0009The second type of deletion: the remaining . left the sentence unfinished as the amount of the . left.')
category('G_EXTRA', 'Generation', 'It\'s changed to the point where it shouldn\'t be changed.', 'Edit scope and verification',
         'It\'s hard to compare just one type of change in value, value, and condition other than the goal.',
         'It\'s a part of the sentence that you can change and the part that you can keep.',
         'We narrow down the correction range and compare the post-editing, and we don\'t rewrite the entire unrelated sentence.', 'In the stored meaning test, 24The type is left with this.')
category('G_FORMAT', 'Generation', 'The final sentence left the designation or the editing format.', 'Generate formatting and check rules',
         'It didn\'t meet the formal requirements of internal names, parentheses, source parentheses and correction positions, and we have to distinguish whether we\'ve gotten to the normal parentheses.',
         'The program manages the modification position and the phrases and internal management information that you show to the person in a separate space.',
         'It separates the internal mark from the final text, instead of banning the entire parenthesis, to verify that it\'s actually an internal mark, and then to assemble it in the program if possible.', 'Manufacturing mark inspection 33Now, the test can also capture a general overarching expression, so it doesn\'t just determine the inside exposure.')
category('G_EXEC', 'Generation', 'So the process of calculating the change value is stopped.', 'Variation value range; calculation support supplement',
         'I couldn\'t create a calculation or a calculation link that put the change candidate in. 0 And we can\'t just define it as a cause of division.',
         'It gives a range of permissible values and a specific calculation and input of execution failures.',
         'They pick candidates that satisfy the unit, the crime, the mathematical conditions and leave the actual failure position, not repeat the same failure candidates.', 'Failed to execute the calculation 22Type and answer unconnected input 1type.')
category('G_TRANSPORT', 'Generation', 'The connection is broken or the response is incomplete.', 'Execution and incident management',
         'We didn\'t get a response to the data or the verification, and it\'s not just an issue that can be stopped by improving the way we deliver data.',
         'It preserves the raw response received, whether the original request is completed or not.',
         'It separates the communication failure from the content failure and restarts the call itself. If there\'s no verification response, it doesn\'t process the pass.', 'Connection failure 65Type, imperfect response 8type.')
category('G_STORAGE', 'Generation', 'I\'ve got an earlier file in the storage location.', 'Results storage and recovery method',
         'The file is already in the reuse file, and the new file is not saved, not because of a phrase or a data error.',
         'Provides a storage location for each attempt, a state of ownership of the existing results and a state of completion.',
         'Each attempt uses a unique storage location and reuses the already completed record, and it doesn\'t necessarily overwrite or delete the previous results.',
         'test-0259·0276·0292·1850The change of value type stopped overlapping with the existing reuse.json and storage location.')
category('G_UNKNOWN', 'Generation', 'The review was not completed and the final verdict was not made.', 'Completed review verification + clarification of the subject of the sentence',
         'Three types remained as the final under-review, a mix of records that didn\'t have a review result and indications that the subject and duration of the sentence were unclear, so we don\'t see them as communication failures.',
         'It provides a clear phrase on which item/period the added value refers to and the actual results of the review.',
         'test-0034Check whether the review is complete.0165So what is the length of the test?0867It reviews the sentences and then makes it clear which quarter they are, and preserves the existing undervaluation mark.',
         'test-0867The circle is a list of the four quarks, but the additional phrase just doesn\'t confirm if the same quarks collide as the one we call the quarks.')


REVIEW_GROUPS = {
    'P_PERIOD': '0022 0079 0372 0399 0659 0796 0815 1250 1254 1292 1326 1365 1453 1550 1998 2015',
    'P_MISSING': '0029 0315 0394 0430 0477 0623 0642 0655 0772 0852 1343 1493 1499 1523 1530 1544 1570 1659 1721 1754 1766 1854 1906 1950 2043 2046 2049',
    'P_MEASURE': '0143 0214 0226 0252 0504 0658 0700 0709 0828 0898 1351 1429 1620 1874',
    'P_CONVENTION': '0914 0965 1062 1190 1398 1432 1441 1875 1920 1934 1977 2002',
    'P_SCALE': '0055 0290 0320 0395 0403 0552 0883 1517 1548 1584 1878 1958 2042',
    'P_TEXT': '0063 0229',
}
REVIEW_IDS = {f'test-{i}': group for group, ids in REVIEW_GROUPS.items() for i in ids.split()}


def prep_group(error, evidence):
    code = error['code']
    if code == 'ORIGINAL_REVIEW_NOT_PASSED':
        return REVIEW_IDS[error['case']]
    if code == 'VERIFICATION_FAILED_OR_UNKNOWN':
        findings = evidence.get('verdict', {}).get('findings', [])
        if any(x.get('judgment') == 'FAIL' for x in findings): return 'P_VERIFY_FAIL'
        if any(x.get('judgment') != 'PASS' for x in findings): return 'P_VERIFY_UNCERTAIN'
        if findings: return 'P_GOLD'
        raise ValueError('Missing verification findings')
    if code == 'NUMERIC_ANSWER_REQUIRED': return 'P_NOANSWER'
    if code == 'FACT_NUMERIC_TOKEN_REQUIRED': return 'P_NUMBER'
    if code.startswith('API_'): return 'P_TRANSPORT'
    if code == 'AMBIGUOUS_SOURCE_REVISION_ANCHOR': return 'P_TEXT'
    if code == 'QUESTION_PRECISION_INSTRUCTION_REMOVED_OR_ADDED': return 'P_SCALE'
    if code == '\uc0c1\uc138 \uac80\uc0ac \uc2e4\ud328': return 'P_CODE'
    return 'P_LINK'


GEN_GROUPS = {
    'UNPLANNED_NUMERIC_CONTENT': 'G_NUM', 'FINAL_ANSWER_UNCHANGED': 'G_UNCHANGED',
    'RELATION_ANSWER_UNCHANGED': 'G_UNCHANGED', 'planned_change': 'G_INTENT', 'readability': 'G_READ',
    'FACT_SOURCE_MISSING': 'G_QUESTION', 'GRAPH_CONTROL_FLOW_MISSING_FACTS': 'G_CONTROL',
    'AUDITED_VALUE_DEPENDENCY_REQUIRED': 'G_DEP', 'VALUE_BEFORE_GENERATION_REQUIRED': 'G_DEP',
    'EA_VALUE_PRESENT_IN_QUESTION': 'G_INQUESTION', 'MISSING_SECOND_EA_INPUT': 'G_SECOND',
    'unintended_change': 'G_EXTRA', 'BRANCH_EXECUTION_FAILED': 'G_EXEC',
    'FACT_NOT_CONNECTED_TO_ANSWER': 'G_EXEC', 'API_CONNECTION_FAILED': 'G_TRANSPORT',
    'API_RESPONSE_INCOMPLETE': 'G_TRANSPORT', '\uc0c1\uc138 \uac80\uc0ac \uc2e4\ud328': 'G_UNKNOWN',
    'NOT_EVALUATED': 'G_UNKNOWN',
    **{x: 'G_FORMAT' for x in ['CONSTRUCTION_TAG_IN_CONTEXT','UNAUTHORIZED_PATCH_OR_GRAPH_MAPPING',
       'PARENTHESIZED_SOURCE_REQUIRED','PYTHON_IDENTIFIER_IN_CONTEXT','STANDALONE_SENTENCE_REQUIRED','INSERTION_NEEDS_SEPARATOR']},
}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prep = read(SOURCE / 'phase-reports/preparation/data.json')
    gen = read(SOURCE / 'phase-reports/generation/data.json')
    latest = read(SOURCE / '02-generation/summary.json')['latest']
    rows = []
    sample_refs = {}
    for case in sorted(set(latest) | {e['case'] for e in prep['errors']}):
        folder = SOURCE / '01-preparation' / case
        candidates = list(folder.glob('01-round/01-source/01-receive-input/01-input.json'))
        refs = []
        for path in candidates:
            read(path); refs.append(str(path.relative_to(ROOT)))
        sample_refs[case] = refs
    for error in prep['errors']:
        file = SOURCE / error['source']
        run = read(file)
        evidence = {'run': run}
        refs = [str(file.relative_to(ROOT)), *sample_refs[error['case']]]
        paths = {'review': '02-review/02-LLM-review-original/03-result.json',
                 'verdict': '05-verification/08-record-verdict/01-result.json',
                 'calculation': '03-calculation/02-LLM-generate-code/03-result.json',
                 'execution': '03-calculation/04-execute-python/03-result.json',
                 'sample': '01-source/01-receive-input/01-input.json'}
        for key, relative in paths.items():
            path = file.parent / relative
            if path.exists():
                evidence[key] = read(path); refs.append(str(path.relative_to(ROOT)))
        top = read(SOURCE / '01-preparation' / error['case'] / 'run.json')
        refs.append(str((SOURCE / '01-preparation' / error['case'] / 'run.json').relative_to(ROOT)))
        evidence['recovery'] = top.get('recovery', {})
        group = prep_group(error, evidence)
        rows.append(dict(phase='Preparation', case=error['case'], type='Get the original ready.', status='FAIL',
                         group=group, classification_code=error['code'], refs=refs, evidence=evidence))
    failing = {(e['case'], e['category']): e for e in gen['errors']}
    clean = []
    numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
    for case, variants in latest.items():
        if len(variants) == 7 and all(v['status'] == 'PASS' for v in variants.values()):
            clean.append(case)
        for variant in variants.values():
            if variant['status'] == 'PASS': continue
            error = failing.get((case, variant['label']), {})
            code = error.get('code', variant['status'])
            group = GEN_GROUPS[code]
            file = SOURCE / variant['path'] / 'run.json'
            saved = read(file)
            if code == '\uc0c1\uc138 \uac80\uc0ac \uc2e4\ud328' and str(saved.get('reason', '')).startswith('FileExistsError:'):
                group = 'G_STORAGE'
            refs = [str(file.relative_to(ROOT)), *sample_refs[case]]
            plan = saved.get('plan', {})
            request = plan.get('request', {})
            numeric_collision = False
            if code == 'UNPLANNED_NUMERIC_CONTENT' and request.get('axis') == 'EA':
                target = plan.get('intent', {}).get('target_original', {})
                target_numbers = set(numbers(target.get('text', '')))
                numeric_collision = any(target_numbers & set(numbers(' '.join(slot.get('allowed_numbers', []))))
                                        for slot in request.get('edit_slots', []))
                if numeric_collision: group = 'G_NUM_DUP'
            evidence = dict(reason=saved.get('reason'), recovery=saved.get('recovery', {}),
                            edit_slots=request.get('edit_slots', []), question=request.get('question'),
                            target=plan.get('intent', {}).get('target_original'), numeric_collision_candidate=numeric_collision)
            for relative in ['02-generate-text/01-input.json','02-generate-text/failure.json','03-validation/03-result.json','01-perturbation/failure.json']:
                p = file.parent / relative
                if p.exists():
                    read(p); refs.append(str(p.relative_to(ROOT)))
            rows.append(dict(phase='Generation', case=case, type=variant['label'], status=variant['status'],
                             group=group, classification_code=code, refs=refs, evidence=evidence))
    for relative in ['src/finarch/dataset/02-generation/01-perturbation/generation_plan.py',
                     'src/finarch/dataset/02-generation/02-generate-text/dtt_realize.py',
                     'src/finarch/dataset/shared/calculation/python_graph.py',
                     'src/finarch/dataset/shared/calculation/python_runtime.py']:
        INPUTS[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    for row in rows:
        row['refs'] = list(dict.fromkeys(row['refs']))
    for item in CAT.values():
        chosen = [r for r in rows if r['group'] == item['id']]
        item['count'] = len(chosen)
        item['cases'] = len({r['case'] for r in chosen})
        item['types'] = dict(collections.Counter(r['type'] for r in chosen))
    counts = collections.Counter(r['phase'] for r in rows)
    gen_cases = sorted({r['case'] for r in rows if r['phase'] == 'Generation'})
    assert counts == {'Preparation': 212, 'Generation': 1667}, counts
    assert len(clean) == 1080 and len(gen_cases) == 758
    assert len({(r['phase'], r['case'], r['type']) for r in rows}) == len(rows)
    assert sum(x['count'] for x in CAT.values()) == len(rows)
    summary = dict(kind='FAILURE_CAUSE_REVIEW', title='FinanceReasoning Failure Causes and Progress',
                   preparation_failed=212, generation_nonclean_cases=758, generation_failed=1664,
                   generation_not_evaluated=3, clean_cases=1080, source_run=SOURCE.name)
    payload = dict(summary=summary, categories=list(CAT.values()), rows=rows,
                   generation_types=gen['summary'], nonclean_cases=gen_cases, clean_cases=clean,
                   method='Saved final-state census; editorial categories; saved model judgments are not ground truth; no model calls or production reruns.')
    save('failure-review.json', payload)
    save('summary.json', summary)
    report = report_text(payload)
    (OUTPUT / 'REPORT.md').write_text(report)
    template = Path(__file__).with_name('failure-review-readme-template.md').read_text()
    (OUTPUT / 'README.md').write_text(template.format(source_run=SOURCE.name, report_run=OUTPUT.name))
    save('validation.json', dict(status='PASS', rows=len(rows), preparation=counts['Preparation'],
         generation=counts['Generation'], nonclean_cases=len(gen_cases), clean_cases=len(clean),
         duplicates=0, unclassified=0, evidence_files=len(INPUTS), model_calls=0,
         scope='Counts, classification coverage and evidence availability only; no semantic certification.'))
    save('manifest.json', dict(inputs=[dict(path=p, sha256=h) for p,h in sorted(INPUTS.items())]))
    (OUTPUT / 'analysis-log.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in [
        dict(event='read_saved_evidence', files=len(INPUTS), source_run=SOURCE.name),
        dict(event='reconcile_final_population', preparation_failed=212, generation_failed=1664, generation_not_evaluated=3, clean=1080, nonclean=758),
        dict(event='write_editorial_review', rows=len(rows), categories=len(CAT), model_calls=0, production_changes=0)
    ]) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


def report_text(payload):
    category_counts = collections.Counter(row['group'] for row in payload['rows'])
    generation_types = (
        ('IC_VALUE_01_BEFORE', 'IC-v1', 'Add another value to the front'),
        ('IC_VALUE_01_AFTER', 'IC-v2', 'Add another value claim on the back'),
        ('IC_SOURCE_A_ONLY', 'IC-s1', 'The original claim is attached to the source.'),
        ('IC_SOURCE_B_ONLY', 'IC-s2', 'Additional claims to the source'),
        ('IC_RELATION_01', 'IC-r', 'Adding incompatible relationships'),
        ('EA_01', 'EA-v1', 'Delete the first essential value'),
        ('EA_02', 'EA-v2', 'Delete the second essential value'),
    )
    type_names = {code: name for code, name, _ in generation_types}
    stage_order = {
        'Preparation': {
            '02-review': 'P02 The original review',
            '03-calculation': 'P03 Grass generation and action',
            '04-graph': 'P04 Calculation graph',
            '05-verification': 'P05 Comprehensive verification of the',
        },
        'Generation': {
            '01-perturbation': 'G01 The transformation plan.',
            '02-generate-text': 'G02 Text realization',
            '03-validation': 'G03 Validate final text',
        },
    }
    stages = {phase: collections.defaultdict(list) for phase in stage_order}
    for row in payload['rows']:
        phase = row['phase']
        if phase == 'Preparation':
            stage = row.get('evidence', {}).get('run', {}).get('stopped_at')
        else:
            saved = json.loads((ROOT / row['refs'][0]).read_text())
            stage = saved.get('restart')
        if stage not in stage_order[phase]:
            raise ValueError(f'UNMAPPED_FAILURE_STAGE:{phase}:{row["case"]}:{stage}')
        stages[phase][(stage, row['group'])].append(row)

    def stage_table(phase):
        lines = []
        for stage, label in stage_order[phase].items():
            for category in CAT.values():
                if category['phase'] != phase:
                    continue
                records = stages[phase].get((stage, category['id']), [])
                if not records:
                    continue
                values = [label, category['title'], str(len(records))]
                if phase == 'Generation':
                    counts = collections.Counter(row['type'] for row in records)
                    unknown = set(counts) - set(type_names)
                    if unknown:
                        raise ValueError(f'UNMAPPED_GENERATION_TYPE:{sorted(unknown)}')
                    values.append(' · '.join(
                        f'{type_names[code]} {counts[code]}'
                        for code, _, _ in generation_types if counts[code]))
                    values.append(str(len({row['case'] for row in records})))
                values.append(category['owner'])
                lines.append('|' + '|'.join(values) + '|\n')
        if sum(len(records) for records in stages[phase].values()) != sum(
                row['phase'] == phase for row in payload['rows']):
            raise ValueError('FAILURE_STAGE_COUNT_MISMATCH:' + phase)
        return ''.join(lines)

    text = '''# FinanceReasoning 20260917-002The Causes of Failure and the Way to Improve

The first thing to distinguish between **Problems that don't have the information they need.**and **The problem is that the program doesn't pass or edit the information correctly.**And if you treat both of them with the same data deficiency, it's hard to fix the cause.

## The scope of analysis and how to read

The input of the preparation is 2,050And that's the case. 212Except for the case 1,838The phrase passed and went to Generation. 1,838In a case. 1,080The case passed all seven types. 758The case has failed or been underestimated in more than one category.

The whole Generation's testing unit is **The type of the case**To the right. 1,838 × 7 = 12,866It's a items. 1,080In the case, 1,080 × 7 = 7,560The items type passed. 758In this case, 758 × 7 = 5,306results **Pass 3,639+ failed 1,664+ not evaluated 3items**. That is, 1,664and 3It's not the number of cases, it's the number of type-by-type results. 212The phrase didn't make it into Generation.

Excluded before entry 188The phrase is 212It's not included in the clause. Even if you passed the final after the previous failure, you don't put it back in the final failure number. Clean pass is a stored automated verification criterion, and it doesn't mean that the person has confirmed the correct answer.

The following classification is the elemental preparation for each case, and the origin is the main observation cause for each case x model. Many problems can overlap, and the number of elements per category overlaps. The stored review times are not valid data, but they are not valid. In particular, the custom, consistency, and verifier error claims must be judged according to the original.

## First, we need to change the order.

1. **And it's the part where you move the data.** It's going to pass the text and the question along, and it's going into the original position of the numbers, and it is going to be the sorted version, and it will be the amount of text that's written in the characters.
2. **Before you create, check if you can create each type with this case.** Check to see if the input changes the actual answer, if the second input is erased, if the same thing remains in the question.
3. **It's a plan of what to delete and what to leave behind.** We're going to test all the repetitions of the same fact, and we're going into the editing plan, the field generating, the numerical check using the same list.
4. **It supplements the source code that doesn't have the information you need.** We check the year, company, team, and requirements from the source and leave a version-by-version settings.
5. **It reduces the scope of the review that is too strict or contradictory.** We set the financial standard and the half-year we can allow first, and we don't fix the originals or the calculations just because they're different from the storage answer.
6. **The communication failure is resumed separately.** It doesn't mix with the number of content replenishments, it preserves the results that have already been passed.

This is a proposed improvement, this time it's not changing the production code, the source code, the answer, or calling a new model, so we don't know yet how to pass after the improvement.

## Preparation: Should I change the original, or should I change the layout?

It's not that we need to replace the entire original. The missing information needs to be replenished from the source, but the issues of numerical representation, user position, communication, and transmission can be fixed in the process. What the reviewer doesn't confirm the interpretation doesn't count as a total original error.

The bottom section is where attempts to represent the final state have failed. The actual correction responsibility must be identified along with the right column and the case basis. If the same cause classification occurs in multiple sections, it's divided by the column row.

|Segment|Causes|Number of cases|First place to see your hands.|
|---|---|---:|---|
'''
    text += stage_table('Preparation')
    text += '\nPreparation detail\n'
    for c in CAT.values():
        if c['phase'] == 'Preparation': text += detail(c, category_counts[c['id']])
    text += '''
## Generation: What's stopping you, by seven types?

|type|The type that we're trying to create.|Pass|Fail|Not evaluated|
|---|---|---:|---:|---:|
'''
    type_summaries = {row['category']: row for row in payload['generation_types']}
    if set(type_summaries) != set(type_names):
        raise ValueError('GENERATION_TYPE_SUMMARY_MISMATCH')
    for code, name, meaning in generation_types:
        row = type_summaries[code]
        text += f"|{name}|{meaning}|{row['PASS']}|{row['FAIL']}|{row['NOT_EVALUATED']}|\n"
    text += '''
The type name is the name of this report and the viewer.

If you fail to change values in the same element, you can also block the source type, so you can't interpret all the source type failures as problems in the source phrase itself.

The bottom is the stop position of the attempt representing the final state. `Type of occurrence`And the number of failures and undervalues of the row is the number of failed types.

|Segment|Causes|Failure: Number of types of undervaluation|Type of occurrence|Number of source items|First place to see your hands.|
|---|---|---:|---|---:|---|
'''
    text += stage_table('Generation')
    text += '\n# # Generation detail station\n'
    for c in CAT.values():
        if c['phase'] == 'Generation': text += detail(c, category_counts[c['id']])
    text += '''
## How should the data be provided?

Every single question. **Question: Text → required value and meaning → calculation → allow change → other position of the same fact**It's going to have to go on. 100If you have both this chart and this description sentence, you need to have a sign that both locations have the same revenue. 100Or other items. 100And when you delete it, the wrong content changes.

|What you're going to provide|A small example.|The problem is trying to stop it.|
|---|---|---|
|The meaning and the source of the value|2019A company sales 100One million dollars, the table below. 2rows|Other company, time, group mix|
|To convey the question and the text together|The touch of the question. 5The year also conveyed with the original position|The source of the question|
|The source-verified response is|four → 4The source is preserved.|Number expression refusal: over and over|
|Calculation definitions|The increase is after period--after period, output is %p.|The fractional fractional factor|
|Variable values and scope|The positive amount, the change, the change in the answer.|The answer is either the same or it's not going to work.|
|The location of the same repeated fact|Sales of the ticket 100And the same sales of the headquarters 100|Only one is deleted or preserve rules collide|
|Connected sums. Other computation paths|All 150And other parts 50Deleted by 100The Restoration|You can delete it and get the answer.|
|The passage of the preceding text.|The front and rear collision phrase verification results|No input of the source type|

### Comprehensive detail station

#### Minimum scope for adoption and verification

**Adopted:** The primary question is synchronous transmission, position correlation maintaining, repetitive position management of the same fact, communication failure separation. The verification method is a small local check to see if the representative's primary record is being put without missing.

**Adopted amendments:** The condition of the original question and the modification of the subject selection, clarifying only if it is actually vague and not forcing the original to increase until financial practices are sufficient, must be verified along with the meaning and results of the change.

**The reservation:** The goal is to make all the currently failed cases pass through all seven types. The only cases that actually need one entry should be defined from the meaning of the second type of deletion, and not achieved by putting data together.

**- What is it?** You can just name the error and judge it as a faulty original, change the score to match the correct answer, make the test loose and increase the passing capacity, and you can't verify the quality of the product.

#### The basis and the limits

Article-by-case originals, final judgments, at-time review and settlement results, creation requests and failure records can be verified with a common viewer's base button. The entire file hash is on manifest.json. The category-by-category description describes the observed failure structure and is not the result of independently re-proving the financial correctness of each case.

We checked the source of the query in the current code, we checked the number of numbers when deleted, we checks the condition of the default input, we check the countdown. We didn't assume that the current code was the same as the execution code at the time, but we used it only in the range that corresponded to the request and result that was stored at the time.0012The translation of 6The silver remains in the request itself at the time, so you can verify the code change irrespective of the variable.
'''
    return text


def detail(c, count):
    return f"\n#### {c['title']} ({count}entries)\n\nWhy did you stop? {c['why']}\n\nWhere are you fixing it? {c['owner']}\n\nWhat data should we provide? {c['supply']}\n\nHow do you improve it? {c['fix']}\n\nReal record example: {c['example']}\n\nScope of the judgement: {c['confidence']}\n"


if __name__ == '__main__':
    main()
