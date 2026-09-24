import copy, hashlib, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'task'))
import scenarios, base_scenarios
from schedule_policy import SchedulePolicy, config

class ScheduleTests(unittest.TestCase):
    def test_exact_pack_and_unchanged_business_inputs(self):
        pack=scenarios.suite('all')
        self.assertEqual(len(pack),20)
        self.assertEqual([sum(c['schedule_audit']['template_index']==t for c in pack[4:]) for t in range(4)],[4]*4)
        self.assertEqual(len({c['schedule_audit']['seed'] for c in pack}),20)
        for i,case in enumerate(pack):
            self.assertEqual(case['schedule_audit'],config(i))
            case.pop('schedule_audit');case.pop('name')
            expected=copy.deepcopy((base_scenarios.PUBLIC+base_scenarios.HELDOUT)[i%4]);expected.pop('name')
            self.assertEqual(case,expected)

    def test_permutation_is_deterministic_and_lossless(self):
        queue=[('x','A',{'private':i},str(i)) for i in range(100)]
        policy=SchedulePolicy(config(3))
        result=policy.order_queue(queue,10,{})
        self.assertEqual(result,SchedulePolicy(config(3)).order_queue(queue,10,{}))
        self.assertEqual(set(x[3] for x in result),set(x[3] for x in queue))
        self.assertNotEqual(result,queue)
        renamed=[(src,dst,{'renamed':body['private']},encoded) for src,dst,body,encoded in queue]
        self.assertEqual([x[3] for x in result],[x[3] for x in SchedulePolicy(config(3)).order_queue(renamed,10,{})])

    def test_exact_bounded_fault_windows(self):
        for i in range(20):
            c=config(i);p=SchedulePolicy(c);src,dst=c['link']
            active=[r for r in range(1,114) if p.block_link(r,src,dst)]
            self.assertEqual(active,[c['link_start_round'],c['link_start_round']+1])
            self.assertTrue(set(active).isdisjoint(set(range(22,32))|set(range(60,114))))
            for r in list(range(1,9))+list(range(22,32))+list(range(60,114)):
                self.assertFalse(p.drop_output(r,r,c['output_node'],{'messages':[{}],'replies':[]}))
            for ordinal in range(1,c['output_eligible_ordinal']+1):
                self.assertEqual(p.drop_output(9,ordinal,c['output_node'],{'messages':[{}],'replies':[]}),ordinal==c['output_eligible_ordinal'])
            self.assertFalse(p.drop_output(10,100,c['output_node'],{'messages':[{}],'replies':[]}))

    def test_manifest_cannot_override_faults(self):
        c=config(0);c['output_node']='arbitrary'
        with self.assertRaises(ValueError):SchedulePolicy(c)

    def test_history_contract_and_legacy_remain_exact(self):
        import json
        manifest=json.loads((ROOT/'upstream-source-hashes.json').read_text())['sha256']
        for name in ('history.py','API_CONTRACT.md','reference/immutable_v1.py'):
            self.assertEqual(hashlib.sha256((ROOT/'task'/name).read_bytes()).hexdigest(),manifest['families/reservation/'+name])

if __name__=='__main__':unittest.main()
