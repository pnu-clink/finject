"""Stage the authorized Korean evidence-centered manuscript from frozen saved results.

Reads the current review snapshot and the 20261008 response snapshot. It does not
change evaluation data or invoke models. --apply publishes the reviewed staged
Korean sections to the existing Draft, editor source, and compressed manuscript.
"""
from __future__ import annotations
import argparse
import base64
import collections
import copy
import datetime
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from finarch.documentation.draft_editor import DraftRepository, EMBEDDED

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'reports/run/20261003-paper-revision-draft'
WORK = ROOT / 'paper/asset/.build/v2-evidence-draft'
BUILD = WORK / 'build'
ASSETS = ROOT / 'paper/asset/figures/v2'
MODELS = ['Luna', 'Haiku', 'Qwen3-8B', 'Qwen3-14B', 'Qwen3.8-27B']
SUMMARY = ROOT / 'reports/analysis/20261008-finject-1354/summary.json'
RESPONSES = SUMMARY.with_name('responses.jsonl')
SNAPSHOT = BUILD / 'paper-review-before.json'

def h(text): return html.escape(str(text))
def p(text, id=None): return f'<p'+(f' id="{id}"' if id else '')+f'>{text}</p>'
def ref(id, label): return f'<a href="#{id}">{label}</a>'
def cite(id, name): return ref('ref-'+id, '('+name+')')
def section_ref(id, label): return ref(id, label)
def table(id, caption, headers, rows, wide=False):
    return f'<table id="{id}" data-table-number="0" data-caption-position="bottom" data-layout="{"two-column" if wide else "one-column"}" style="width:100%;min-width:0;table-layout:auto;"><caption>Table 0: {caption}</caption><thead><tr>'+''.join('<th>'+str(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def img(id, name, caption, wide=False):
    path = WORK / 'output' / (name+'.png')
    src='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    return f'<figure id="{id}" data-figure-number="0" data-layout="{"two-column" if wide else "one-column"}" data-figure-file="paper/asset/figures/v2/{name}.pdf" data-pdf-placement="top"><img src="{src}" alt="{h(caption)}"/><figcaption>Figure 0: {caption}</figcaption></figure>'
def math(tex, id=None):
    # MathML carries both a native accessible rendering and the exact TeX source.
    import subprocess
    result=subprocess.run(['pandoc','-f','markdown','-t','html5','--mathml'],input='$$\n'+tex+'\n$$',text=True,capture_output=True,check=True).stdout
    return '<div class="equation"'+(f' id="{id}"' if id else '')+'>'+result+'</div>'

def source_pairs():
    types=['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY']
    responses={}
    with RESPONSES.open() as file:
        for line in file:
            r=json.loads(line)
            if r.get('model_label') not in MODELS or r['variant'] not in types: continue
            key=(r['model_label'],r['prompt_condition'],r['reasoning'],r['final_id'],r['variant'])
            if key in responses: raise ValueError('Duplicate response key: '+str(key))
            if r['target_status']!='VALID': cat='X'
            elif r['action']=='A': cat='A'
            elif r['action']=='N' and r['original_reference_match'] is True: cat='M'
            elif r['action']=='N' and r['original_reference_match'] is False: cat='W'
            else: cat='X'
            responses[key]=cat
    ids=[f'id-{i:04}' for i in range(1,1355)]
    out=[]
    for model in MODELS:
        for g in ['unguided','guided']:
            for r in ['off','on']:
                for pair,(before,after) in enumerate([(types[0],types[2]),(types[1],types[3])],1):
                    counts=collections.Counter()
                    excluded=collections.Counter()
                    for fid in ids:
                        a=responses.get((model,g,r,fid,before),'X');b=responses.get((model,g,r,fid,after),'X')
                        if 'X' in (a,b): excluded[f'{a}->{b}']+=1
                        else: counts[a+'->'+b]+=1
                    n=sum(counts.values());assert n+sum(excluded.values())==1354
                    cb={c:sum(v for k,v in counts.items() if k.startswith(c)) for c in 'MWA'}
                    ca={c:sum(v for k,v in counts.items() if k.endswith(c)) for c in 'MWA'}
                    out.append(dict(model=model,G=g,R=r,pair=pair,n=n,planned=1354,excluded=dict(excluded),before=cb,after=ca,transitions=dict(counts),delta_pp={c:100*(ca[c]-cb[c])/n if n else None for c in 'MWA'}))
    return out

def build():
    sections=json.loads(SNAPSHOT.read_text()); previous=copy.deepcopy(sections)
    by={s['id']:s for s in sections}
    assets={}
    for s in sections:
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        for t in doc.find_all(['figure','table'],id=True): assets[t['id']]=str(t)
    summary=json.loads(SUMMARY.read_text())
    q={(r['model'],r['G'],r['R']):r for r in summary['rq1'] if r['model'] in MODELS}
    pairs=source_pairs()
    evidence=dict(source=str(RESPONSES.relative_to(ROOT)),sha256=hashlib.sha256(RESPONSES.read_bytes()).hexdigest(),new_model_calls=0,scope='paired valid output categories; original_reference_match reused unchanged',pairs=pairs)
    (BUILD/'source-attribution-results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    def put(sid,body,title=None):
        s=by[sid];s['kohtml']=body;s['oldko']='';s['state']='revised'
        if title is not None:s['ko']=title
    def asset(id):return assets[id]
    gr='G<sup>+</sup>R<sup>+</sup>'
    gm='G<sup>−</sup>'
    a3ref=ref('fig:revision-2','Figure 3')
    tab3=ref('tab:v2-support','Table 3')
    tab4=ref('tab:v2-reasoning','Table 4')
    tab5=ref('tab:v2-guidance','Table 5')
    tab6=ref('tab:v2-source','Table 6')
    app32=section_ref('s11-pipeline-2','Appendix 3.2')
    app42=section_ref('s11-nasu','Appendix 4.2')
    app44=section_ref('s11-pipeline-4','Appendix 4.4')
    put('abstract',p('In finance, the model\'s numerical answers and assignments must both be justified on a given basis. It is difficult to trust a response if the model does not have the necessary basis or if it does not match the explanation even if it presents the reason. We propose a reusable method of construction, evaluation and analysis using FInject, which controls the basis conditions and evaluates the assignment. 1,354and variants 9,478And the two evaluators\' match rates for the candidates in the first round are: 98.98%Cohen\'s κ is 0.619The reasoning and citation basis of five models was determined to be LLM, so that the reasoning and presentation of the reasoning alone did not guarantee the support of the answer. Reasoning and the submission of submissions increased, but the submission response remained. The weight of the original statistical answers that match or disagree with the original statements of the sources was also varied. FInject provides a basis for evaluating whether the reasoning supports the explanation and final judgment, beyond the answer or the statistical answer.'))
    intro=img('fig:abstention-intro','Figure1-v2-evidence','The numeric-answer justifies the rationale in the same question and the abstention.0217It\'s a summary of the table, and it\'s not the actual model output. 34 + 11 = 45And it\'s not just the Apple. 2017If you remove the year value, you can\'t confirm the sum in the remaining context. '+app32+'is presented in')
    intro+=p('The large language model used in financial decision-making (LLM) must provide not only answers, but also a basis for justifying those answers. The financial knowledge and computational ability of the model is necessary to interpret the report, but it cannot replace the value of a particular company or institution without verifying the context. If the necessary value is missing or the basis conflicts, the model should be able to explain and govern the situation on the basis of that. '+cite('realfin','Dai et al., 2026')+'.')
    intro+=p('An LLM may justify a wrong answer with a plausible explanation, and the explanation presented may not reflect the actual process of judgment. '+cite('unfaithful-cot','Turpin et al., 2023')+'So the numerical answer is, <strong>numeric-answer</strong>And the governor. <strong>abstention</strong> In all of them, the context is based on<strong>evidence</strong>(The model is described in the following table.)<strong>reason</strong>The reason here refers to the explanation presented by the model and not to the internal reasoning itself.')
    intro+=p('For example, the share of sales of two companies 34%and 11%Let\'s put it together. 45%If you can\'t remove one of the essential values and restore it to the rest of the context, you can justify the authority on the same question.'+ref('fig:abstention-intro','Figure 1')+'On the contrary, if you answer as a figure based on the missing value or explain that there is no recoverable basis, even a reasoned answer fails to support the basis.')
    intro+=p('The existing financial QA is a document-based statistical calculation that evaluates the '+cite('finqa','Chen et al., 2021')+' '+cite('tatqa','Zhu et al., 2021')+'Recent research has also examined the lack of essential conditions and the reasons for the authorization. '+cite('realfin','Dai et al., 2026')+'.FInject controls the computational basis of the same question by linking the originals to the seven variants, and evaluates the reasoning, usage basis presented by the model and the completeness of the final answer together.')
    intro+=p('FInject is a set of originals selected from FinanceReasoning and TAT-QA. 1,354and variants 9,478It consists of an independent Python root and a calculation graph that tracks the basis for the change and its calculation effect, and a human reviewer checks the complexity of the variation. Through an input adapter, the production process can be reused in other numerical QA as well. '+ref('fig:pipeline-full','Figure A1')+'is presented in')
    intro+=p('We analyze the proportion of responses based on reasoning, changes in the authority guidelines, and changes in the source sign. In the experiment, the reasoning and reasoning were requested, but the sub-supported response was left, and the distribution of responses and authority was changed if the source was added, while maintaining the statistical content. This shows the need to evaluate the reasoning that justifies the results along with the results of the response.')
    put('s1',intro)
    put('s2',p('Comparing the method of production of financial statements QA with the basis-regulation assessment. '+section_ref('s11-related','Appendix 2')+'is presented in'))
    put('s2-1',p('FinQA provides a question and answer program for financial reporting. '+cite('finqa','Chen et al., 2021')+'TAT-QA is a mathematical theory that combines tables and statements. '+cite('tatqa','Zhu et al., 2021')+'FinanceReasoning includes financial functions and Python solutions. '+cite('finance_reasoning','Tang et al., 2025')+'FinChain verifies the solution in an executable calculation step. '+cite('finchain','Xie et al., 2026')+'These data provide a basis for numerical accuracy and calculation.')+p('FInject tracks the basis needed for the calculation and applies the same questions to the collision, source, and acceptance conditions. It connects verified originals with variations, calculation effects and change locations, so that when the basis conditions change, the model\'s numerical answers can be compared with the input.'+ref('table-s11-full-tables-1','Table A1')+').'))
    put('s2-2',p('RealFin assesses the identification of missing essential terms in the financial statements and the refusal of improper answers. '+cite('realfin','Dai et al., 2026')+'RefusalBench distinguishes between search and private categories of rights. '+cite('refusalbench','Muhamed et al., 2026')+'AgentAbstain compares the agent\'s situation with the one that requires execution and supervision. '+cite('agentabstain','Liu et al., 2026')+'Non-financial QA also has research on knowledge conflicts and lack of evidence.'+ref('table-s11-comparisons-2','Table A4')+').')+p('Therefore, requiring reasons or grounds is not the distinctive feature of FInject itself. FInject controls the grounds connected to the numerical calculation, determining whether the cited grounds and calculations support the final numeric-answer or abstention.'+ref('table-s11-full-tables-2','Table A2')+').'))
    put('s3',p('Financial calculations use the same value in multiple steps, so we have to track the impact of changes in the input basis on the final answer. '+ref('fig:revision-1','Figure 2')+'The process of preparing the original and generating and verifying the transformation.')+p('<strong>Notation.</strong> <i>Q</i>And the question is, <i>C</i>It\'s the original context. <i>C</i><sub>0</sub> = <i>C</i>and, <i>C</i><sub>1</sub>, …, <i>C</i><sub>7</sub> '+a3ref+'It\'s the seven-dimensional context defined by the <i>Ans</i>The model returned the data set to the source, which is the exact answer to the number of copies provided by the source dataset. <code>answer</code>And all the variations are the same. <i>Q</i>is used.','notation-common'))
    put('s3-1',p('FinanceReasoning '+cite('finance_reasoning','Tang et al., 2025')+'And TAT-QA is '+cite('tatqa','Zhu et al., 2021')+'In the numerical answer, select the case that provides the correct answer and remove the overlay. '+ref('notation-common','Notation')+'The question, the context, the source, the correct answer.')+p('<strong>Independent sets and calculation graphs.</strong> LLM composes Python solutions in question and context without looking at the correct answer. The execution values are contrasted with the source solutions according to the required unit and precision, and the input values, mean values, and dependencies of the solution are recorded in a directional non-cycle graph (DAG). The graph connects the base position of the number and the values that are transmitted to the next calculation. LLM and the person use this connection to examine the change object and the calculation effect.'+section_ref('s11-pipeline-1','Appendix 3.1')+').')+asset('fig:revision-1'))
    put('s3-2',p('Every copy is a copy. '+a3ref+'It makes seven contexts. <strong>IC-v</strong>The same collision number is added to the front f) or back b) while maintaining the original claim. <strong>IC-s1</strong>So the original claim of IC-v, f, <strong>IC-s2</strong>The IC-v,b source is attached to the additional claims of IC-v and maintains the parent\'s number and placement. <strong>IC-r</strong>Add a relation that conflicts with the specified value. <strong>ER1·ER2</strong>Each of the different essential input bases is deleted from the original.')+img('fig:revision-2','Figure3-v2-seven-variants','The seven fundamental variations applying to the same question.0217The tables and actual changes were summarized in sentences. Green represents the addition of a conflict, red represents the source tag, and the cancellation line represents the deletion. The source phrases of IC-s1 and IC-s2 were shortened and the entire original and storage type corresponded to the '+app32+'is presented in',True)+p('After verifying that the answer applied to the conflict figure-relationship method varies with the original, the LLM represents the change in context. ER also preserves the possibility of restoring the answer to the remaining basis after deletion. '+app32+'is recorded in'))
    put('s3-3',p('<strong>Calculation and context.</strong> It contrasts Python execution and graphs, and checks that the generated context maintains query and non-variant information while implementing the planned collision-switching. It also verifies that the item, time, and phase match.')+p('<strong>IC.</strong> If you can\'t justify a numerical answer with two uncountable arguments, <code>CONFLICT</code>The collision value itself does not disappear by adding the source surface.')+p('<strong>ER.</strong> The remaining basis for the answer can be restored even after deletion. The fact that the footage used in the production has been discontinued does not render the entire case unanswered. '+section_ref('s11-validation','Appendix 3.3')+'is presented in'))
    put('s3-4',p('The two reviewers compare the original context, change position and calculation graph in the test tool to determine whether the intended variation is implemented and additional errors are made. <strong>98.98%</strong>And the integration of Cohen\'s <strong>κ = 0.619</strong>The randomness of the approval bias is 97.31%And they were disagreeable. 111of 96The first occurred in IC-r. The two reviewers selected only the set of cases that approved all seven variations and the original. <strong>1,354items</strong>Come on, change it up. <strong>9,478items</strong>The test tools and the judging statistics '+section_ref('s11-annotation','Appendix 3.4')+'is presented in'))
    put('s4',p('We evaluate why the model presented and whether the citation basis supports the final response. We separate the response collection, the basis support judgment, the comparison of the corresponding response, and do not confirm the basis support by merely statistical correctness.'))
    fields=table('table-s4-1-1','The field in TargetOutput. The actual storage field and the corresponding classification values are '+section_ref('s11-pipeline-3','Appendix 4.1')+'.',['The field.','Meaning'],[['<code>answer</code>','The number of replies or sub-requests returned by the model'],['<code>classification</code>','The situation returned by the model'],['<code>reason</code>','The model\'s explanation'],['<code>evidence</code>','The context of the citation that links to the explanation']])
    put('s4-1',p('<strong>Notation.</strong> <i>G</i><sup>+</sup>/<i>G</i><sup>−</sup>The provision/re-creation of guidance on the regulatory standards, <i>R</i><sup>+</sup>/<i>R</i><sup>−</sup>The reasoning setting is activated/inactivated. <i>g</i>and <i>r</i>The derivative of a function is a + or −. <strong>TargetLLM</strong>It\'s a model that\'s being evaluated. <strong>TargetOutput</strong> '+ref('table-s4-1-1','Table 1')+'Includes four fields of. Common input symbols are '+ref('notation-common','3Notation of the chapter')+'Following.','notation-call')+fields+math(r'\operatorname{TargetLLM}(Q,C_i\mid G^g,R^r)\rightarrow\operatorname{TargetOutput}(\text{answer},\text{classification},\text{reason},\text{evidence}),','eq:target-call')+math(r'i\in\{0,\ldots,7\},\qquad g,r\in\{+,-\}.')+p('Each call has the same question and the same answer. <strong>A single context</strong>The original and seven variations are evaluated separately, with no source answer, output code, calculation graph, and review judgments. Under all conditions, reason and evidence are required, and the actual prompt and model-by-model settings are used to determine the results. '+section_ref('s11-prompts','Appendix P')+'and '+section_ref('s11-experimental-settings','Appendix 6')+'is presented in'),'4.1 Target Model Response Collection')
    put('s4-2',p('<strong>Notation.</strong> <strong>N</strong>The numeric-answer, <strong>A</strong>is abstention, <strong>S</strong>and <strong>U</strong>The two criteria are supported and unsupported respectively. <strong>NS·NU·AS·AU</strong>It\'s called NASU response classification.'+ref('table-s4-2-1','Table 2')+').','notation-nasu')+table('table-s4-2-1','Combining response form and base support.',['Response','Supported','Unsupported'],[['Numeric-answer','NS','NU'],['Abstention','AS','AU']])+p('<strong>Supported.</strong> The given evidence supports the model\'s reason and final answer together. In NS, the cited value, relationship, and calculation must justify the number submitted. In AS, the described conflict, nearness deficiency must not actually determine the answer. Correct answer consistency, conflict declaration, citation existence alone do not determine.')+p('LLM judgments contrast responses with entries. If a minor is identified among the application criteria, it is classified as U, and the judgments are divided into four categories if there is no uncertainty or response-checking. Information deficiency does not require citation of a phrase that does not exist, but reviews the relationship between the essential conditions described and the remaining basis. Detailed judgments and actual cases are used to determine the extent to which the information is available. '+app42+'is presented in'))
    put('s4-3',p('<strong>Notation.</strong> And then the NS-NU-AS-AU rate is '+ref('notation-nasu','4.2section classification')+'The answer is yes. <strong><i>T</i></strong>The model and G/R settings are calculated by the number of plan responses of IC-v, f·IC-v, b·IC-r·ER1·ER2. 1,354 × 5 = <strong>6,770</strong>It\'s not accurate. <i>T</i>IC-s is compared separately to the parent IC-v.','notation-metrics')+p('<strong>The support rate.</strong> The numeric-answer calculates the NS/(NS+NU) and the abstention calculates the AS/(AS+AU). The provided weight for the entire case is reported as NS/T and AS/T. The first is the proportion of the basis supported by the basis of the corresponding response, and the latter is the weight of the basis for the response of the entire plan case. '+section_ref('s11-metrics','Appendix 4.3')+'is presented in'))
    put('s4-4',p('<strong>RQ1. How much are numeric-answer and abstention supported when the basis conditions change?</strong> Comparing model-specific support rates and weighting against plan phrases from five basic variations.')+p('<strong>RQ2. How do the guidelines and reasoning settings change the supported response?</strong> In the same model-problem, G or R is fixed and different conditions are compared. In ER, the reasoning is based on the newly NS-converted response and the relationship of inverse probability, while in IC, the underlying governance changes are analyzed.')+p('<strong>RQ3: How do the numerical answers and the assignment differ depending on which source you attach to the claim?</strong> IC-v,f→IC-s1 and IC-v→IC-S2 are connected respectively. Calculates the weight change of the numeric-answer, dissonant numeric-an answer, abstention, corresponding to the original answer in the same corresponding pair with valid responses on both sides. Numerical dissonance is the adoption of a specific conflict value, and not all of the sub-parts are considered CONFLICT. '+app44+'is presented in'))
    put('s5',p('Luna, Haiku, Qwen3-8B, Qwen3-14B, Qwen3.8-27BThe storage response was collected into a final FInject case set. Each model applies four G/R conditions to the original and seven variations.6.1 Sol/low. The text is a key comparison, '+section_ref('s11-pooled-results','Appendix 5')+'In some cases, it presents the total result and the range of losses.'))
    support=[];gain=[];icrows=[];variantrows=[]
    agg=collections.defaultdict(collections.Counter)
    for r in summary['aggregates']:
        if r['model'] in MODELS:
            agg[r['model'],r['G'],r['R'],r['variant']].update({k:r[k] for k in ['planned','NS','NU','AS','AU','D','F']})
    for model in MODELS:
        r=q[model,'ON','ON'];support.append([model,f'{100*r["N"]:.1f}',f'{100*r["A"]:.1f}',f'{100*r["resolved"]/r["planned"]:.1f}'])
        b=q[model,'OFF','OFF'];a=q[model,'OFF','ON'];gain.append([model,f'{100*(a["NS"]-b["NS"])/6770:+.1f}',f'{100*(a["AS"]-b["AS"])/6770:+.1f}'])
        rates=[]
        for G,R in [('OFF','OFF'),('OFF','ON'),('ON','OFF'),('ON','ON')]:
            c=sum((agg[model,G,R,v] for v in ['IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_RELATION_01']),collections.Counter());assert c['planned']==4062
            rates.append(f'{100*c["AS"]/4062:.1f}')
        icrows.append([model,*rates])
        for v,label in [('IC_VALUE_01_BEFORE','IC-v,f'),('IC_VALUE_01_AFTER','IC-v,b'),('IC_RELATION_01','IC-r'),('EA_01','ER1'),('EA_02','ER2')]:
            a=agg[model,'ON','ON',v];assert a['planned']==1354
            variantrows.append([model,label,*[f'{a[k]:,}' for k in ['NS','NU','AS','AU','D','F']]])
    put('s5-1',p('I used both the guidance and reasoning of the authority. '+gr+'In this case, the support rate of numeric-answer is model-to-model. 14.8–77.8%And the support rate for abstention is 85.8–98.9%It was.'+tab3+'Both respondents requested that they submit reasons and citation, but the sub-appointed verdict remained.')+table('tab:v2-support',gr+'The completion of the judgment is the answer/T of the four NASU categories. '+ref('tab:finject-rq1','Table A23')+'.',['Model','Numeric-answer support rate','Abstention support rate','Judgment completed.'],support)+p('The number is similar to the original correct answer, but the submitted basis-based calculation may not justify its value, and the responses to find the collision may also mix with the calculation error. On the contrary, the numeric-answer that restores the missing value from the ER to the remaining basis may be Supported. '+app42+'E, the variance classification is the '+ref('tab:v2-variant-counts','Table A0')+'is presented in')+p('<strong>Finding 1Submission of reasons and citations does not guarantee evidence support.</strong> In FInject, both numeric-answer and abstention showed sub-supported responses. Not only the form of the response, but also the basis, calculation, statement, and completeness of the final judgment should be evaluated to distinguish these differences.'),'5.1 RQ1: Based answers and authorization')
    put('s5-2',p('<strong>Set up the reasoning.</strong> I don\'t have any authority. '+gm+'And if you turn on the reasoning, all the models have increased NS/T, and the increase in width was greater than AS/T.'+tab4+'The answer to the newly renamed NS 92.4–95.7%The NS transition was more pronounced in the phrase with the reversible flag, but this linkage alone cannot determine whether the model used the actual reversible process'+ref('table-s11-results-rq2-1','Table A25')+').')+table('tab:v2-reasoning',gm+'From R<sup>−</sup>→R<sup>+</sup>The total dry and the original answer rate is '+ref('tab:reasoning-gains-full','Table A24')+'.',['Model','Δ NS/T','Δ AS/T'],gain)+p('<strong>Link to the governance guide.</strong> In the collision transformation, '+gr+'The AS weight of all models was the highest, but'+tab5+'In the actual model-by-model setting, Qwen\'s R transformation changes the sampling setting as well, so it is not interpreted as a reasoning-only effect.'+section_ref('s11-experimental-settings','Appendix 6')+').')+table('tab:v2-guidance','The denominator of the AS weight of the collision variation is set to three IC types per set. 4,062items and includes miscalculation and mischecking. '+ref('table-s11-results-rq2-2','Table A26')+'.',['Model','G−R−','G−R+','G+R−','G+R+'],icrows)+p('<strong>Finding 2.Reasoning setting and improved correspondence of different ground conditions that are not jurisdictional.</strong> The new NS following Reasoning appeared mainly in the base removal clause, and in the conflict the AS proportion of settings that provided guidance and reasoning together was highest. However, even improved settings remained unsupported responses, and the provision of settings alone did not guarantee evidence-appropriate judgments.'),'5.2 RQ2: Guidance; Reasoning and supporting evidence')
    mainpairs=[]
    for model in MODELS:
        ps=[r for r in pairs if r['model']==model and r['G']=='guided' and r['R']=='on'];p1,p2=ps
        mainpairs.append([model,f'{p1["delta_pp"]["M"]:+.1f}',f'{p2["delta_pp"]["W"]:+.1f}'])
    put('s5-3',p('IC-s1 gives a source to the back-origin claim, and IC-s2 gives a source for the back-overlying claim. '+gr+'In all five models, the original correct correspondence weight of IC-s1 and the inconsistency weight of IC‐s2 increased'+tab6+'Both types of responses decreased the weight of the regulation.')+table('tab:v2-source',gr+'The source additional post-change (%) is the same as the valid corresponding pair denominator. The original match/dismatch is a stored numerical comparison and distinguishes the basis supporting the judgment. '+ref('tab:v2-source-outcomes','Table A0')+'.',['Model','IC-s1<br/>Increase in matching','IC-s2<br/>Increased original inconsistency'],mainpairs)+p('This change is consistent with the tendency of numerical responses to move towards the source\'s claim. However, the inconsistency also includes other calculation errors, so it does not mean the exact adoption rate of additional numbers. Other G/R conditions also have changes in the opposite direction, and the source phrase added does not interpret the basis itself as being more true.'+section_ref('s11-results-rq4','Appendix 5.4')+').')+p('<strong>Finding 3The distribution of responses varies only with the source information attached to the evidence.</strong> Although the relationship between numbers and calculations is maintained, the correspondence with the original answer varies depending on which of the original or additional claims the source is attached to. Therefore, a basis-based assessment should consider how the basis is presented along with the numerical content.'),'5.3 RQ3: Change in the source and response')
    put('s5-4','');by['s5-4']['hidden_ko']=True
    put('conclusion',p('We proposed FInject, which evaluates whether evidence supports the reason and numeric-answer or abstention of a model in the QA of financial statements. In the experiment, requiring reasoning and reasoning and authority guidance, there was a sub-supported response, and the distribution of statistical responses and powers varied by source indicators alone. When evaluating the financial model\'s response, it is necessary to verify not only the final results, but also the consistency of the reasons and explanations that justify the results.')+'<ul><li><strong>The way we make tracing the evidence.</strong> It connects independent Python puzzles, calculation graphs, controlled changes and human review, and reuses the procedure for other numerical QA as an input adapter.</li><li><strong>A data set that controls the base conditions.</strong> Original 1,354items and seven variations. 9,478Connect the items and compare the model responses to the collision, source, and impact.</li><li><strong>Reusable evaluation and analysis methods.</strong> Determine the response and the evidence support of the jurisdiction, and compare the response response that changed the setting-source conditions.</li></ul>','6. Conclusion')
    # Preserve all original result tables and move detailed main-text graphics to appendices.
    appendix_assets={
        's11-pipeline-2':['fig:perturbation-dag'],
        's11-nasu':['fig:arv-fav-cases'],
        's11-results-rq1':['table-s5-1-1','fig:abstention-support-share'],
        's11-results-rq2':['table-s5-2-original-reasoning','table-s5-2-1','table-s5-2-guidance-reasoning','fig:nasu-gr-bars','fig:gr-fixed-lines'],
        's11-results-rq3':['table-s5-3-1'],
        's11-results-rq4':['table-s5-4-1'],
    }
    # Discover the actual NS/AS figure ID rather than depending on a historical name.
    nsas=BeautifulSoup(next(s for s in previous if s['id']=='s4-2')['kohtml'],'html.parser').find('figure')
    appendix_assets['s11-nasu']=[nsas['id']]
    for sid,ids in appendix_assets.items():
        by[sid]['kohtml']+=''.join(asset(id) for id in ids)
        by[sid]['oldko']=''
    ex=json.loads((BUILD/'example.json').read_text())
    exact='<h4>The originals and the change of position of the sentence-shaped picture</h4>'+p('Figure of the head 1·Figure 3The final <code>id-0217</code>The source is FinanceReasoning-embedded <code>CodeTAT-QA-test-24</code>In the diagram, the value of the original table is summarized as a sentence. The data below are the criteria for actual input. The image\'s verified by an analyst is a summary of the added long source phrase and does not guarantee external verification facts.')+p('<strong>Question.</strong> '+h(ex['original']['question']))+'<pre>'+h(ex['original']['context'])+'</pre>'
    vmap={v['type']:v for v in ex['variants']}
    ordered=[('C1','IC-v,f','IC_VALUE_01_BEFORE'),('C2','IC-v,b','IC_VALUE_01_AFTER'),('C3','IC-s1 (IC-s,f)','IC_SOURCE_A_ONLY'),('C4','IC-s2 (IC-s,b)','IC_SOURCE_B_ONLY'),('C5','IC-r','IC_RELATION_01'),('C6','ER1','EA_01'),('C7','ER2','EA_02')]
    rows=[]
    for ci,label,typ in ordered:
        v=vmap[typ]; patches=v['metadata']['edit_provenance']['steps'][-1]['patches']
        edit=' '.join(x['text'].strip() if x['text'].strip() else 'Deleted: '+x['before'] for x in patches)
        rows.append([ci,label,'<code>'+typ+'</code>',h(edit)])
    exact+=table('tab:v2-variant-map','The symbol-type of the image and the actual stored changes. C3/C4 adds the last source patch to the context of C1/C2 respectively.',['The context.','The mark name.','Type of storage','Changes to the original'],rows,True)
    exact+=p('C1/C2 is Apple. 34%and 37.4%And it\'s just different in order, and Huawei is. 11%And the question remains. C3 is the back-end Apple 34%E, the C4 is the back of the Apple add-on 37.4%Both conditions are attached to the back argument, so comparing each child to the parent does not interpret the difference between the two children as a pure position effect.')
    exact+=p('The C6 is Apple\'s 2017The year value 34But the C7 is Huawei\'s 2017The year value 11The weight of the other year is 2017There is no relationship determining the year value, and no aggregate or additional conditions are given. Therefore the aggregate of this example is not determined solely after deletion. Supported responses for explanation show the nature of this context, and do not represent the impossibility of all ERs to answer or actual model judgments.')
    by['s11-pipeline-2']['kohtml']=exact+by['s11-pipeline-2']['kohtml']
    by['s11-validation']['kohtml']+=p('<strong>The uncertain scope of the reverse review.</strong> The full man-made estimate of whether ER\'s missing values can be restored in the remaining context has not yet been confirmed. The Supported assessment of production approvals and responses does not replace the independent case-by-case answer probability gold. The NS/AS statistics of the chapter are based on the saved response estimate, and the inverse flag is used only for the correlation analysis of the recorded subset.')
    by['s11-pipeline-3']['kohtml']=p('<strong>The paper tag and the storage field.</strong> TargetOutput is the <code>reason</code>The raw response is <code>explanation</code>It refers to. <code>answer</code>The output of the model, <i>Ans</i>The source is the correct answer. <code>answer=null</code>It\'s not like the classification field is empty, which is a rule. <code>ANSWERABLE</code>and <code>ABSTAIN</code>Including Unguided. <code>classification=null</code>The existing raw response is preserved as agreed. The text classification is numerical and authoritative. <code>answer</code>is categorized by')+by['s11-pipeline-3']['kohtml']
    by['s11-nasu']['kohtml']=p('<strong>Notation.</strong> <i>y</i>is the model response. <code>Numeric(y)</code>and <code>Abstain(y)</code>Silver means numerical answers and governance. <strong>FAV</strong>(Final Answer Validity) is the total response, <strong>ARV</strong>(Abstention Reason Validity) is a validity judgment of a jurisdictional reason. The two judgments each return Supported, Unsupported, and Undetermined. The following NS·AS is the response set and in the statistics uses that dry.')+math(r'\begin{aligned}\mathrm{NS}&=\{y\mid\operatorname{Numeric}(y)\land\operatorname{FAV}(y)=\mathrm{Supported}\},\\\mathrm{AS}&=\{y\mid\operatorname{Abstain}(y)\land\operatorname{ARV}(y)=\mathrm{Supported}\land\operatorname{FAV}(y)=\mathrm{Supported}\}.\end{aligned}','eq:app-nasu')+p('Supported/Unsupported of this chapter is a summary of the detailed judgments below. It does not change the judgement criteria or mixed judgments stored to simplify the term. The ARV of numerical answers does not apply, and the jurisdiction must meet both judgments AS.')+by['s11-nasu']['kohtml']
    # Replace the over-broad paired-analysis prose with exactly the available analysis.
    keep_tables=''.join(asset(id) for id in ['table-s4-4-1','table-s11-pipeline-4-1'])
    put('s11-pipeline-4',p('<strong>Setup comparison.</strong> The same model and final source ID; variation type are based on G/R configuration. NS/T·AS/T uses the same scheduling number including uncertainty; mischecking. The change reports the difference in the ratio before the reversal as %p.')+asset('table-s4-4-1')+p('<strong>The response category of the source comparison.</strong> Model G/R condition, maximum source ID, and then the <code>IC_VALUE_01_BEFORE</code>and <code>IC_SOURCE_A_ONLY</code>, <code>IC_VALUE_01_AFTER</code>and <code>IC_SOURCE_B_ONLY</code>I\'m connecting them. <code>target_status=VALID</code>Each type of plan pair includes only pairs that can determine the response category on both sides. 1,354items and valid counterparts. <i>n</i>The three categories of weight between parents and children are the same. <i>n</i>Calculate the denominator.')+p('The numerical response is stored in the <code>original_reference_match</code>The right to tell the difference between true and false is the original match. <code>action=A</code>It does not introduce any new anti-up-group rule or conflict-candidate comparison. Whether or not the review of the judgment LLM is completed is not an inclusion condition for this output category comparison, so the Supported maintenance rate and denominator below may differ.')+p('The original inconsistency does not imply that the input value has been adopted exactly, and the assignment does not mean only CONFLICT. A separate reason-evidence analysis is needed as to whether which claims were used for actual calculations and how the source was interpreted.')+p('<strong>Supplement: Original response group and Supported retention rate.</strong> The group comparison and the maintenance of the previous AS, based on the original correct answer matching, are preserved as supplemental analysis. The group comparisons use the group (NS+AS)/(NS+NU+AS+AU) of each group. The AS maintenance rate is the percentage of both NASUs remaining AS of the existing AS in the confirmed corresponding pair, and N/A in the absence of the original AS. AS→NS is not calculated as a basis support failure.')+asset('table-s11-pipeline-4-1'))
    by['s11-results-rq1']['kohtml']+=table('tab:v2-variant-counts',gr+'The number of rows in each row is the number of rounds in each row. 1,354D is undefined, F is unchecked and unchecked, and is classified into four categories.',['Model','Variant','NS','NU','AS','AU','D','F'],variantrows,True)
    by['s11-results-rq1']['kohtml']=p('The support rate per response form includes only those responses that the judgment has confirmed in the denominator, while NS/T·AS/T leaves the uncertainty and unverification on the plan denominator. The support rate of the jurisdiction may be low even if the AS/T is high, so it distinguishes between the two indicators.')+by['s11-results-rq1']['kohtml']
    by['s11-results-rq3']['ko']='Appendix 5.3Supplement: The success of the original grass and the adaptation of the original.'
    by['s11-results-rq3']['kohtml']=p('The original correct answer provides a comparison of support rates of consistent groups and inconsistent groups as a complementary result. This group comparison is a phrase-intersectional association and does not imply a correlation.')+by['s11-results-rq3']['kohtml']
    pairrows=[]
    for r in pairs:
        condition=('G+' if r['G']=='guided' else 'G−')+('R+' if r['R']=='on' else 'R−')
        fmt=lambda c:f'{r["before"][c]:,} → {r["after"][c]:,}'
        pairrows.append([r['model'],condition,'IC-s'+str(r['pair']),f'{r["n"]:,}',str(1354-r['n']),fmt('M'),fmt('W'),fmt('A')])
    source_table=table('tab:v2-source-outcomes','The numbers IC-v→IC-s are the same corresponding pair after the source. Each of the three categories after the addition is n, and the ratio is each of the preceding three categories/n. Except for both, neither of the two is a plan pair that has not received a valid response category.',['Model','G/R','Type of source','n','Reject','Original match','Original inconsistency','Abstention'],pairrows,True)
    by['s11-results-rq4']['ko']='Appendix 5.4RQ3: Change in source and response'
    by['s11-results-rq4']['kohtml']=p('The source compares IC-s1 to the back original claim and IC-s2 to the back additional claim with each parent. The original match/disagreement authority determines by the stored model output, and does not replace whether or not supported. '+gr+'Unlike the common tendency of the other settings, reverse directional changes occur. For example, in Luna\'s G+R−, the original consistency weight of IC-s1 is the same as the original consistent weight of the IC-s1. 3.77%P decreased.')+source_table+'<h4>Supplement: Maintaining a valid authority</h4>'+by['s11-results-rq4']['kohtml']
    # Qualify the related-work distinction without modifying the original comparison tables.
    by['s11-full-tables']['kohtml']=p('Compares the production and evaluation scope of a financial dataset. FInject tracks the change location of the basis used in the calculations and connects the source and transformation. RealFin evaluates the identification of missing conditions, so it does not classify it as a study dealing only with whether or not it is authorized. It does not claim the originality of reasoning and approximation evaluation by the selected characteristics of the comparison table alone.')+by['s11-full-tables']['kohtml']
    by['s11-comparisons']['kohtml']=p('Non-financial QA is active in research on conflict, neighborhood tribes, and sovereign property. RefusalBench distinguishes between sovereign wealth detection and private category. '+cite('refusalbench','Muhamed et al., 2026')+'.FInject\'s scope is based on the change in basis and response complexity assessment associated with financial statistics calculations.')+by['s11-comparisons']['kohtml']
    put('s8',p('FInject deals with financial statements QA using controlled base changes, and does not represent financial advice or the actual transaction work as a whole. Synthetic collision, source, and solution may differ from actual document errors. Calculation graphs are dependent relationships of the follicles used in production and do not include all possible recovery paths.')+p('Whether or not a response is supported depends on LLM judgement. A person\'s verification of a dataset creation does not independently guarantee the accuracy of a response judgment, nor is a person\'s review of the ER\'s total inverse probability uncertain. Unsupported is not all interpreted as a response to hallucination, inappropriate authority, or unanswerable cases.')+p('The reason presented by the model can differ from the internal reasoning process. R setup comparisons also include model-by-model sampling changes, with the gap and mis-examination range varying by model; conditions. The number of source experiments does not confirm the adoption of specific claims merely by match-disagreement, and does not consider the source statement as a real reliability improvement. Both source conditions add a label to the backward claims, so they cannot completely separate the effect of the source and location.'))
    refs=by['references']['kohtml']
    refs+='<div class="reference" id="ref-unfaithful-cot"><p>Miles Turpin, Julian Michael, Ethan Perez, and Samuel R. Bowman. 2023. <a href="https://proceedings.neurips.cc/paper_files/paper/2023/hash/ed3fea9033a80fea1376299fa7863f4a-Abstract-Conference.html">Language Models Don’t Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting</a>. Advances in Neural Information Processing Systems 36.</p></div>'
    refs+='<div class="reference" id="ref-refusalbench"><p>Aashiq Muhamed, Leonardo F. R. Ribeiro, Markus Dreyer, Virginia Smith, and Mona T. Diab. 2026. <a href="https://aclanthology.org/2026.eacl-long.321/">RefusalBench: Generative Evaluation of Selective Refusal in Grounded Language Models</a>. Proceedings of EACL (Volume 1: Long Papers), pages 6811–6856.</p></div>'
    put('references',refs)
    # Bring inherited appendix prose into the v2 scope without altering its data.
    by['abstract']['kohtml']=by['abstract']['kohtml'].replace('\uae08\uc735\uc5d0\uc11c \ubaa8\ub378\uc758 \uc218\uce58 \ub2f5\ubcc0\uacfc \uae30\uad8c\uc740','In finance, the numerical answers and the submissions of the large-scale language model of LLM are')
    by['abstract']['kohtml']=by['abstract']['kohtml'].replace('\ub610\ud55c \ucd9c\ucc98\ub97c \ubd99\uc774\ub294 \uc8fc\uc7a5\uc5d0 \ub530\ub77c','Provided that the authority provides guidance and reasoning together, the source is based on the claim that the source is a')
    by['s1']['kohtml']=by['s1']['kohtml'].replace('\uac19\uc740 \uc9c8\ubb38\uc5d0\uc11c \uadfc\uac70\uac00 \uc815\ub2f9\ud654\ud558\ub294 numeric-answer\uc640 abstention.','In the same question, the numeric-answer justifies the basis and the abstention. Supported means that the basis supports the explanation and the final answer together.')
    doc=BeautifulSoup(by['s1']['kohtml'],'html.parser')
    figure=doc.find('figure').extract()
    paragraphs=doc.find_all('p',recursive=False)
    paragraphs[1].replace_with(BeautifulSoup(p('An LLM may justify a wrong answer with a plausible explanation, and the explanation presented may not reflect the actual process of judgment. '+cite('unfaithful-cot','Turpin et al., 2023')+'Therefore, it is necessary to verify that the given evidence supports the explanation and the final judgment.'),'html.parser'))
    notation=BeautifulSoup(p('<strong>Notation.</strong> <strong>evidence</strong>The context of the citation, <strong>reason</strong>The numerical answer to the model is <strong>numeric-answer</strong>The grant. <strong>abstention</strong>If the evidence supports the explanation and the final answer, <strong>Supported</strong>All. Reason does not mean the internal reasoning of the model itself.','notation-response'),'html.parser')
    paras=doc.find_all('p',recursive=False)
    paras[1].insert_after(notation)
    doc.find(id='notation-response').insert_after(figure)
    by['s1']['kohtml']=str(doc)
    by['s11-pipeline-2']['kohtml']=by['s11-pipeline-2']['kohtml'].replace('\ubcf8\ubb38\uc758 <a href="#fig:perturbation-dag">','Down here. <a href="#fig:perturbation-dag">')
    doc=BeautifulSoup(by['s11-pipeline-3']['kohtml'],'html.parser')
    for node in doc.find_all('p'):
        t=node.get_text(' ',strip=True)
        if t.startswith('TargetOutput\uc758 \ud56d\ubaa9.'):
            node.replace_with(BeautifulSoup(p('<strong>The rule of the markings of the example.</strong> In the example of the response saved below, you can see only four fields. <code>ANSWERABLE</code>The illustration is a picture of Isaiah. <code>NOT_APPLICABLE</code>It doesn\'t convert all the classifications of the actual execution into three domain categories, and whether the number is a response or not, the domain is a variable. <code>answer</code>is determined by'),'html.parser'))
        elif t.startswith('NOT_APPLICABLE\uc758 \uad6c\ubcc4.'):
            node.replace_with(BeautifulSoup(p('<strong>The distinction between NOT_APPLICABLE.</strong> In the example, this value is a sign that does not apply a power assignment to a numerical response. The ARV of the response judgment is the same string, but this is a separate judgment field. '+app42+'is presented in'),'html.parser'))
    by['s11-pipeline-3']['kohtml']=str(doc)
    by['s11-evaluation']['kohtml']=table('table-s11-pipeline-3-1','The actual execution classification value. G− does not require classification, and the values below are the model\'s self-report.',['The value.','Meaning'],[['<code>ANSWERABLE</code>','G+: Judging that a single-digit answer is justified.'],['<code>CONFLICT</code>','G+: There are conflicting claims and no solutions.'],['<code>INSUFFICIENT_EVIDENCE</code>','G+: No value needed; no correlation; no restoration'],['<code>UNRESOLVED</code>','G+: The ambiguity of the interpretation changes the result.'],['<code>ABSTAIN</code>','G+: We couldn\'t confirm a specific input error, but we couldn\'t finish or verify the release.'],['<code>null</code>','G−: Classification sub-clause.']],True)
    pooled=BeautifulSoup(by['s11-pooled-results']['kohtml'],'html.parser')
    for node in pooled.find_all('p'):
        if 'RQ3' in node.get_text() or 'RQ4' in node.get_text():
            node.replace_with(BeautifulSoup(p('The basic support rate is the plan response of five variations 6,770The dryers and denominators of NS-AS are '+ref('notation-metrics','Notation of the title')+'D is undefined, F is unchecked. Sources compare each type of plan 1,354We use the valid corresponding pair of pairs. '+section_ref('s11-results-rq4','Appendix 5.4')+'The output range comparison and the supplemented supported maintenance rates may vary depending on the inclusion conditions and denominator may also vary.'),'html.parser'))
    by['s11-pooled-results']['kohtml']=str(pooled)
    # Number the Korean assets by their actual display order. English content is preserved.
    numbers={};oldlabels={};main={'table':0,'figure':0};app={'table':0,'figure':0}
    for s in sections:
        if s.get('hidden_ko'): continue
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        for t in doc.find_all(['table','figure'],id=True):
            kind=t.name;prefix='Table' if kind=='table' else 'Figure';cap=t.find('caption' if kind=='table' else 'figcaption')
            is_app=s['id'].startswith('s11');counter=app if is_app else main;counter[kind]+=1
            number=('A' if is_app else '')+str(counter[kind]);numbers[t['id']]=prefix+' '+number
            t['data-'+kind+'-number']=number
            if cap:
                if 'data-'+kind+'-number' in cap.attrs:cap['data-'+kind+'-number']=number
                text=cap.get_text(' ',strip=True);match=re.match(r'(?:Table|Figure)\s+A?\d+',text)
                if match:oldlabels[match[0]]=numbers[t['id']]
                # Preserve caption markup and links.
                for node in cap.find_all(string=True):
                    if re.match(r'^\s*(?:Table|Figure)\s+A?\d+',str(node)):
                        node.replace_with(re.sub(r'^\s*(?:Table|Figure)\s+A?\d+',numbers[t['id']],str(node),count=1));break
            if not is_app and not (kind=='figure' and t['id']=='fig:revision-2'):t['data-layout']='one-column'
        s['kohtml']=str(doc)
    numbers['tab:inverse-association']=numbers['table-s11-results-rq2-1']
    titles={s['id']:s['ko'] for s in sections}
    for s in sections:
        doc=BeautifulSoup(s['kohtml'],'html.parser')
        if s['id']=='s1':
            cap=doc.find('figure',id='fig:abstention-intro').find('figcaption')
            cap.clear();cap.append(BeautifulSoup('Figure 1: Examples of justifying numeric-answer and abstention.0217The original and deleted position is the default default. '+app32+'.','html.parser'))
        if s['id']=='s3-2':
            cap=doc.find('figure',id='fig:revision-2').find('figcaption')
            cap.clear();cap.append(BeautifulSoup('Figure 3The seven fundamental variations represented by the sentence:0217Green: Added conflict, pink: source tag, cancellation line: deleted. Summary of the source and source statements and source '+app32+'.','html.parser'))
        for a in doc.select('a[href^="#"]'):
            dest=a['href'][1:]
            if dest in numbers:
                a.string=re.sub(r'(?:Table|Figure)\s+A?\d+|\bA\d+\b',lambda m:numbers[dest].split()[-1] if m[0].startswith('A') else numbers[dest],a.get_text(),count=1)
        if s['id']=='s11-results-rq4':
            for node in doc.find_all(string=True):
                if 'Table 8\uc758 \uc804\uccb4 \ubc84\uc804' in str(node):
                    node.replace_with(str(node).replace('Table 8\uc758 \uc804\uccb4 \ubc84\uc804','Table A38Full version of'))
        if s['id']=='s11-prompts':
            for node in doc.find_all(string=True):
                if '\uac1c\uc815 NOT_APPLICABLE \uaddc\uc57d\uacfc \uad6c\ubd84\ud55c\ub2e4' in str(node):
                    node.replace_with(str(node).replace('\uc544\ub798 \uc800\uc7a5 \uc6d0\ubb38\uc740 ANSWERABLE / ABSTAIN / classification=null\uc744 \uc720\uc9c0\ud558\uba70 \uac1c\uc815 NOT_APPLICABLE \uaddc\uc57d\uacfc \uad6c\ubd84\ud55c\ub2e4.','The following rule maintains the ANSWERABLE / ABSTAIN / classification=null used in actual execution. The storage field explanation corresponds to the reason of the article.'))
        if s['id']=='s11-pooled-results':
            for node in doc.find_all(string=True):
                if '\uc774\uc804 classification \uacc4\uc57d\uc744 \uc720\uc9c0\ud55c\ub2e4' in str(node):
                    node.replace_with(str(node).replace('\uc800\uc7a5 \uc2e4\ud589\uc5d0\ub294 \ud3c9\uac00 \ubd80\ub85d\uc5d0\uc11c \uc124\uba85\ud55c \uc774\uc804 classification \uacc4\uc57d\uc744 \uc720\uc9c0\ud55c\ub2e4. \uc774 \uc7ac\uc9d1\uacc4\uac00 \uc218\uc815\ub41c \uc218\uc9d1 \uacc4\uc57d\uacfc\uc758 \uc815\ud569\uc131\uc774\ub098 \ub3c5\ub9bd\uc801\uc778 \ub2f5\ubcc0 \uac00\ub2a5\uc131 gold\ub97c \ud655\uc815\ud558\uc9c0\ub294 \uc54a\ub294\ub2e4.','Using the classification and explanation fields of the storage execution as they are, the explanation corresponds to the reason of the text. The answer support judgment and the independent answer probability gold distinguish.'))
        s['kohtml']=str(doc)
    # Check preservation of English, original detailed tables, and every anchor.
    assert all(s['enhtml']==o['enhtml'] and s['en']==o['en'] for s,o in zip(sections,previous))
    visible=[s for s in sections if not s.get('hidden_ko')]
    ids={s['id'] for s in visible};dupes=[]
    for s in visible:
        for t in BeautifulSoup(s['kohtml'],'html.parser').find_all(id=True):
            if t['id'] in ids:dupes.append(t['id'])
            ids.add(t['id'])
    broken=[]
    for s in visible:
        for a in BeautifulSoup(s['kohtml'],'html.parser').select('a[href^="#"]'):
            if a['href'][1:] not in ids:broken.append([s['id'],a['href'],a.get_text()])
    assert not dupes,dupes
    # Historical links are repaired in the final editorial pass, never silently dropped.
    for old in ['table-s5-1-1','table-s5-2-original-reasoning','table-s5-2-1','table-s5-2-guidance-reasoning','table-s5-3-1','table-s5-4-1']:
        new=next(BeautifulSoup(s['kohtml'],'html.parser').find('table',id=old) for s in sections if BeautifulSoup(s['kohtml'],'html.parser').find('table',id=old))
        before=BeautifulSoup(assets[old],'html.parser').find('table')
        assert [[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])] for tr in new.find_all('tr')]==[[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])] for tr in before.find_all('tr')],old
    (BUILD/'paper-review-v2-ko.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2)+'\n')
    report=dict(main_assets=main,appendix_assets=app,broken_links=broken,duplicate_ids=dupes,English_unchanged=True,preserved_original_result_tables=6,notation_ids=['notation-common','notation-call','notation-nasu','notation-metrics'],source_pair_rows=len(pairs),asset_numbers=numbers)
    (BUILD/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='asset_numbers'},ensure_ascii=False))
    return sections

def apply():
    repo=DraftRepository(ROOT)
    sections=json.loads((BUILD/'paper-review-v2-ko.json').read_text())
    checkpoint=BUILD/'published-master.sha256'
    expected=checkpoint.read_text().strip() if checkpoint.exists() else hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    if hashlib.sha256(repo.source.read_bytes()).hexdigest()!=expected:raise RuntimeError('Draft changed during authoring; merge the latest edits first.')
    before={repo.source:repo.source.read_text(),repo.markdown:repo.markdown.read_text(),RUN/'draft \uc555\ucd95.md':(RUN/'Draft compression.md').read_text()}
    for path in repo.previews:before[path]=path.read_text()
    embedded=json.dumps(sections,ensure_ascii=False).replace('</script','<\\/script')
    updates={repo.source:json.dumps(sections,ensure_ascii=False,indent=2)+'\n'}
    bodies=[]
    for s in sections:
        if s.get('hidden_ko'):continue
        content=BeautifulSoup(s['kohtml'],'html.parser')
        for figure in content.select('figure[data-figure-file]'):
            asset=figure['data-figure-file']
            if asset.startswith('paper/asset/figures/v2/') and figure.img:
                figure.img['src']='../../../'+str(Path(asset).with_suffix('.png'))
        body=repo.markdown_body(str(content),before[repo.markdown])
        bodies.append(('### ' if s['level'] else '## ')+s['ko']+'\n\n'+body+'\n\n')
    updates[repo.markdown]='# FInject · Hanging Draft v2\n\n'+''.join(bodies)
    updates[RUN/'draft \uc555\ucd95.md']='# Draft compression v2\n\n'+''.join(bodies)
    for path in repo.previews:
        content=EMBEDDED.sub(lambda m:m[1]+embedded+m[3],before[path],count=1)
        content=content.replace('Abstract → Appendices · \ucd5c\uc2e0 \ub85c\uceec PDF \uae30\uc900','Changes to the evidence center')
        content=content.replace('\ud604\uc7ac \ub85c\uceec \uc601\ubb38 PDF\uc758 \ubcf8\ubb38, \uadf8\ub9bc·\ud45c\uc640 \ubd80\ub85d\uc744 \ubc18\uc601\ud55c \ud55c·\uc601 Draft\uc785\ub2c8\ub2e4.','Korean is an evidence-based v2 sketch, English and local PDFs are old manuscripts, and before translation and editing updates.')
        content=content.replace('\ub3d9\uc77c\ud55c \uc139\uc158 \uc790\ub8cc\ub85c \ud55c\uad6d\uc5b4·\uc601\ubb38 \ud30c\uc77c\uc744 \ud568\uaed8 \uc0dd\uc131\ud569\ub2c8\ub2e4. \uadf8\ub9bc\uc744 \ud074\ub9ad\ud558\uba74 \ud655\ub300\ud569\ub2c8\ub2e4. \ucc38\uace0\ubb38\ud5cc\uc740 \ucd5c\uc2e0 \ub85c\uceec PDF\uc758 \ucd9c\ub825 \ud56d\ubaa9\uacfc \ud568\uaed8 \uac31\uc2e0\ud569\ub2c8\ub2e4.','The Korean version of the text and the editor use the same font, and you click on the picture and you magnify it. English and PDF are before the translation and editing update.')
        content=content.replace("section.className='paper-section'+(item.level?' subsection':'');","section.className='paper-section'+(item.level?' subsection':'')+(item.hidden_ko?' ko-hidden':'');")
        content=content.replace("a.className=item.level?'sub':'';","a.className=(item.level?'sub':'')+(item.hidden_ko?' ko-hidden':'');")
        content=content.replace('</style>','body[data-lang=ko]:not(.bilingual) .ko-hidden{display:none!important}.notation{border-left:3px solid #087b86;padding-left:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere} .equation{overflow-x:auto} figure[data-layout="two-column"] img{width:100%;max-height:none}\n</style>',1)
        updates[path]=content
    backup=RUN/'backup/editor/v2-evidence-first-draft'
    if backup.exists():backup=backup/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True,exist_ok=True)
    for path,content in before.items():
        if path.read_text()!=content:raise RuntimeError('Concurrent change: '+str(path))
        name=path.name
        (backup/name).write_text(content)
    for path,content in updates.items():repo.atomic_write(path,content)
    checkpoint.write_text(hashlib.sha256(repo.source.read_bytes()).hexdigest()+'\n')
    for file in (WORK/'output').glob('Figure*'):
        if file.suffix in ['.png','.svg','.pdf']:shutil.copy2(file,ASSETS/file.name)
        elif file.name.endswith('-r3.pptx'):shutil.copy2(file,ASSETS/file.name.replace('-r3.pptx','.pptx'))
    print('Published Korean Draft and compressed manuscript; English and PDF unchanged.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    if args.apply:apply()
    else:build()
