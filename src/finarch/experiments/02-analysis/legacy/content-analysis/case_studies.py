"""Evidence-linked case notes for the completed exp-003; not population scoring."""
import json
from pathlib import PurePosixPath
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text

CASES = [
('gemini-2.5-flash','8de02d0540cdc6c46b1987792dbb5e04','Type error: the negative sign in front of the call sign',
 'Context 2015Shit. 1,136and 2014Shit. 1,171So if you take it down,35So the answer is -$.35 And the right way to do that is to calculate the million. 35So I read it wrong, and I corrected the abstraction of the odd numbers and then I corrected it to the numerical match.'),
('gemini-2.5-flash','44fed44f1912214d55ec6bc2ba89905a','It\'s a failure of form, but it\'s a match to the correct numbers.',
 'Context 57,299 + 565,609 = 622,908And the exact answer to the source. 622908So the answer is not a string, it\'s a JSON number, and the format failed, so we have to distinguish it from the computational failure, and there\'s a very small limit to the unity response.'),
('gemini-2.5-flash','6f898b79010dffa1f6d3b65e6b3526f7','Instead of a base array, return the string.',
 '2014Shit. 1,171 - 2013Shit. 1,701 = -530The answer and the explanation are the same, but the evidence is returned in a string, and it violates the schematic.'),
('gemini-2.5-flash-lite','2f71f10a3053b293c75755b05b0c4404','You\'re breaking a serial number or a serial number.',
 'The same test.0056From the...530The answer is the same as the answer itself, and you can\'t treat it as a complete error just because it\'s a form error.'),
('gemini-2.5-flash','3d1f2619331bb7e18b8dc05e9f4b53ac','And it\'s not automatically compared because of the age.',
 'The positive fluctuations in the context 13 + 24 + 49 = 86And the answer is, 86So the answer is, 2011and 86So the two numbers that are included together are extracted, so the conservative numerical comparison is left undervalued, which is not an error in answer, but a limit to the extent of the extractor\'s application.'),
('gemini-2.5-flash-lite','f5182838f857cd8b7aeb6208f9918fcb','The source numbers are odd and the answer is odd.',
 'The context Domesticstate is 57299But in the description, 5729.9I read it. 571339So I\'m going to say, "R" is going to be reversed. 1038708So the real sum is 622908The number of errors and the internal inconsistency of the response are the same failures as the content of the response. 622,908But this one case alone does not determine the general effect of the inference setting.'),
('gemini-2.5-flash-lite','170ee87531372539970b51d65ef57629','The result of the calculation is inconsistency in the specified prime numbers.',
 '5.3 / 17.7 = Drugs 0.299435So the three-digit inverse is 0.299So, what\'s the answer? 0.300It\'s different from precision, which is that even if you cite the right two inputs, the final figure is not guaranteed.'),
('gemini-2.5-flash','927bb8b05ec01ad387e3fca870cfc5f1','I explained the collision, but the null form failed.',
 'I\'m going to start with the IC-value-after P1/on. 5.99and additional low-cost 6.589He explained the collision. 8.4-5.99=2.41and 8.4-6.589=1.811 We presented two results, and we didn\'t confirm one, but we broke the string agreement with answer = zero, and we were excluded from the existing UBO detection, which shows that collision recognition and formatting success are separate.'),
('gemini-2.5-flash-lite','96431b1a3d638ac9692188ff1f66e2a3','null response with explanation of lack of evidence',
 'EA-01 In P1/on, the total cost is not provided and the annual balance cannot be calculated, and the answer=null is returned. The intent of the e-book is observed in the description, but is not reflected in the existing answer-only statistics. The e-book has not been independently verified until it can be recovered by other routes, so it is not scaled up to the e-Book fairness judgment.'),
('gemini-2.5-flash','bbb673eec1f95713cec9712a275a51d2','Reboot: output cuts after the column breakdown',
 'The final output shows a broken string of fragments and phrases that start repeating the answer and description. 6031So, what\'s the point of this? 1262Instead of just assuming that the accident was difficult, we record actual power failure and termination.'),
('gemini-2.5-flash-lite','db917fb07245996cc29a9503610e2228','Repeatedly cutting the output.',
 'And then there\'s a massive escape loop behind the evidence string, and then the output is over. 7923So, what\'s the point of this? 253And it\'s MAX_TOKENS. The starting part of the answer is not complete JSON, so it didn\'t recover as normal.'),
]


def build(root):
    if root.name != '20260920-exp-003':
        return
    public={x['item_id']:x for x in rows(root/'01-input/public.jsonl')}
    private={x['item_id']:x for x in rows(root/'01-input/private.jsonl')}
    allrows={m:{x['trial_id']:x for x in rows(root/m/'03-results/results.jsonl')} for m in {x[0] for x in CASES}}
    out=['# Representative response 11The opposite of the case.', '', 'It\'s not random samples for frequency estimation, but it\'s a case of explaining different causes of failure and underestimation, each case being linked to the actual input and raw response, not the whole-value bond.', '']
    for i,(model,trial,title,note) in enumerate(CASES,1):
        row=allrows[model][trial];result=read(root/row['result_path']);response=result.get('response')
        out += [f'## {i}. {title}', '', f"{model} · {row['case']} · {row['variant']} · {row['prompt_condition']}/{row['reasoning']} · {row['status']}", '', note, '',
                f"[JSON output]{row['call_path']}(Raw response){PurePosixPath(row['result_path']).parent}I\x27m not sure what the answer is.{row['result_path']})", '',
                '**Question**: '+public[row['item_id']]['question'],
                '**The original reference answer.**: '+private[row['item_id']]['reference']['reference_answer']+' (Not used as a straightforward answer to a variable problem)', '',
                '```json',json.dumps(response,ensure_ascii=False,indent=2) if response is not None else '(JSON incomplete: see raw response link above)', '```', '',
                '<details><summary>The context that actually conveyed it.</summary>', '', public[row['item_id']]['context'], '', '</details>', '']
    # Markdown only: no HTML disclosure elements.
    out=[x.replace('<details><summary>\uc2e4\uc81c \uc804\ub2ec\ud55c \ucee8\ud14d\uc2a4\ud2b8</summary>','**The context that actually conveyed it.**').replace('</details>','') for x in out]
    write_text(root/'CASE-STUDIES.md','\n'.join(out))
