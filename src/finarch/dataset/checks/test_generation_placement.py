"""Placement contracts independent of historical run fixtures."""
import unittest
source_request = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['source_request']).source_request
value_boundaries = __import__('finarch.dataset.02-generation.01-perturbation.generation_plan', fromlist=['value_boundaries']).value_boundaries
slot = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['slot']).slot
check_response = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['check_response']).check_response

class PlacementChecks(unittest.TestCase):
    def test_relation_cannot_be_inside_or_before_table(self):
        context='Intro.\n| Name | Value |\n| --- | --- |\n| A | 100 |\n| B | 200 |\nEnd.'
        for pos, error in ((context.index('| A'), 'RELATION_INSIDE_TABLE'),
                           (context.index('\n| B'), 'RELATION_INSIDE_TABLE'),
                           (context.index('100'), 'RELATION_INSIDE_TABLE'),
                           (context.index('| Name'), 'RELATION_AFTER_TABLE_REQUIRED')):
            spec=slot(pos,pos,'',['n1'],'RELATION','Insert a relation.',prefix='\n\n',allowed=['2'])
            request={'axis':'IC_RELATION','question':'Which value?','context':context,'edit_slots':[spec]}
            patch={k:spec[k] for k in ('start','end','before','element_ids')}
            with self.assertRaisesRegex(ValueError,error):
                check_response(request,{'patches':[dict(patch,text='\n\nA was twice B.\n')]})

    def test_relation_paragraph_preserves_following_source_text(self):
        context='| Name | Value |\n| --- | --- |\n| A | 100 |\n| B | 200 |\nNext paragraph.'
        pos=context.index('\nNext')
        spec=slot(pos,pos,'',['n1'],'RELATION','Insert a relation.',prefix='\n\n',allowed=['2'])
        request={'axis':'IC_RELATION','question':'Which value?','context':context,'edit_slots':[spec]}
        patch={k:spec[k] for k in ('start','end','before','element_ids')}
        text='\n\nA was twice B.\n'
        observation,_=check_response(request,{'patches':[dict(patch,text=text)]})
        self.assertEqual(observation['context'],context[:pos]+text+context[pos:])
        self.assertIn('200 |\n\nA was twice B.\n\nNext paragraph.',observation['context'])
        with self.assertRaisesRegex(ValueError,'RELATION_PARAGRAPH_SEPARATOR_REQUIRED'):
            check_response(request,{'patches':[dict(patch,text=text.rstrip())]})

    def test_whole_table_boundaries(self):
        context='Intro.\n| Name | Value |\n| --- | --- |\n| A | 100 |\n| B | 200 |\nEnd.'
        start=context.index('100')
        a,b=value_boundaries(context,[start,start+3])
        self.assertEqual(context[a:b],'| Name | Value |\n| --- | --- |\n| A | 100 |\n| B | 200 |')
        for pos in (context.index('| A'),context.index('100')):
            spec=slot(pos,pos,'',['n1'],'VALUE','Insert a sentence.',allowed=['110'])
            request={'axis':'IC_VALUE','question':'Which value?','context':context,'edit_slots':[spec]}
            patch={k:spec[k] for k in ('start','end','before','element_ids')}
            with self.assertRaisesRegex(ValueError,'VALUE_INSIDE_TABLE'):
                check_response(request,{'patches':[dict(patch,text='The value is 110.\n')]})

    def test_source_stays_with_target_in_multi_claim_sentence(self):
        original='Fees were 80000, commissions were 45000, and gains were 30000.'
        text='Fees were 88000. '
        plan={'label':'IC_SOURCE_A_ONLY','request':{'context':original},'intent':{'target_original':{'span':[10,15]},'value_pair':['80000','88000']}}
        base={'status':'PASS','patches':[{'start':0,'end':0,'text':text,'element_ids':['n1']}],'observation':{'context':text+original}}
        request=source_request(plan,base);request['question']='Total?'
        spec=request['edit_slots'][0];patch={k:spec[k] for k in ('start','end','before','element_ids')}
        observation,_=check_response(request,{'patches':[dict(patch,text=' (according to the analyst)')]})
        self.assertIn('Fees were 80000 (according to the analyst), commissions',observation['context'])

    def test_sources_belong_inside_the_assigned_sentence(self):
        original='Revenue is 100.'
        for after in (False,True):
            text=' Revenue is 110.' if after else 'Revenue is 110. '
            start=len(original) if after else 0
            current=original+text if after else text+original
            plan={'label':'IC_SOURCE_B_ONLY' if after else 'IC_SOURCE_A_ONLY','request':{'context':original},'intent':{'target_original':{'span':[11,14]},'value_pair':['100','110']}}
            base={'status':'PASS','patches':[{'start':start,'end':start,'text':text,'element_ids':['n1']}],'observation':{'context':current}}
            request=source_request(plan,base);request['question']='What is revenue?'
            spec=request['edit_slots'][0]
            patch={k:spec[k] for k in ('start','end','before','element_ids')}
            observation,_=check_response(request,{'patches':[dict(patch,text=' (according to the analyst)')]})
            expected='Revenue is 100. Revenue is 110 (according to the analyst).' if after else 'Revenue is 110. Revenue is 100 (according to the analyst).'
            self.assertEqual(observation['context'],expected)
            with self.assertRaisesRegex(ValueError,'PARENTHESIZED_SOURCE_REQUIRED'):
                check_response(request,{'patches':[dict(patch,text=' According to the analyst.')]})

if __name__=='__main__':unittest.main()
