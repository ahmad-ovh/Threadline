import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.model import ContractError, ConflictError, MissingError, validate_graph, apply_patch, graph_diff, sha, digest
from threadline.store import Store


def graph(project='sample',label='Main'):
    return {'schemaVersion':'1.0','project':{'id':project,'name':'Sample'},'source':{'treeHash':'tree-1','commit':None},
            'nodes':[{'id':'module:src','kind':'module','label':'src','path':'src'},
                     {'id':'file:src/main.py','kind':'file','label':label,'path':'src/main.py','parent':'module:src'}],
            'edges':[{'id':'e1','source':'module:src','target':'file:src/main.py','kind':'contains','evidence':[]}]}

class ContractTests(unittest.TestCase):
    def test_valid_snapshot_is_copied(self):
        g=graph();out=validate_graph(g);out['nodes'].clear();self.assertEqual(len(g['nodes']),2)
    def test_schema_version_rejected(self):
        g=graph();g['schemaVersion']='9';self.assertRaises(ContractError,validate_graph,g)
    def test_duplicate_nodes(self):
        g=graph();g['nodes'].append(g['nodes'][0]);self.assertRaises(ContractError,validate_graph,g)
    def test_duplicate_edges(self):
        g=graph();g['edges'].append(g['edges'][0]);self.assertRaises(ContractError,validate_graph,g)
    def test_dangling_edge(self):
        g=graph();g['edges'][0]['target']='missing';self.assertRaises(ContractError,validate_graph,g)
    def test_parent_cycle(self):
        g=graph();g['nodes'][0]['parent']='file:src/main.py';self.assertRaises(ContractError,validate_graph,g)
    def test_missing_parent(self):
        g=graph();g['nodes'][1]['parent']='absent';self.assertRaises(ContractError,validate_graph,g)
    def test_unsafe_paths(self):
        for path in ('/etc/passwd','../key','C:\\secret','C:/secret','a/../../key','a\x00b'):
            with self.subTest(path=path):
                g=graph();g['nodes'][1]['path']=path;self.assertRaises(ContractError,validate_graph,g)
    def test_evidence_line_and_hash(self):
        for proof in ({'path':'../secret'},{'line':0},{'line':True},{'hash':'bad'},{'status':'certainly true'}):
            with self.subTest(proof=proof):
                g=graph();g['edges'][0]['evidence']=[proof];self.assertRaises(ContractError,validate_graph,g)
    def test_invalid_node_kind(self):
        g=graph();g['nodes'][1]['kind']='execute';self.assertRaises(ContractError,validate_graph,g)
    def test_invalid_relation(self):
        g=graph();g['edges'][0]['kind']='magic';self.assertRaises(ContractError,validate_graph,g)
    def test_nonfinite_data_rejected(self):
        g=graph();g['source']['extra']=float('nan');self.assertRaises(ValueError,validate_graph,g)
    def test_patch_update(self):
        g=graph();n=copy.deepcopy(g['nodes'][1]);n['label']='Updated';result=apply_patch(g,{'upsertNodes':[n]});self.assertEqual(next(x for x in result['nodes'] if x['id']==n['id'])['label'],'Updated')
    def test_patch_dangling_rejected(self):
        self.assertRaises(ContractError,apply_patch,graph(),{'removeNodes':['file:src/main.py']})
    def test_patch_complete_removal(self):
        result=apply_patch(graph(),{'removeNodes':['file:src/main.py'],'removeEdges':['e1']});self.assertEqual(len(result['nodes']),1)
    def test_patch_duplicate_upserts(self):
        n=graph()['nodes'][1];self.assertRaises(ContractError,apply_patch,graph(),{'upsertNodes':[n,n]})
    def test_delta_contains_before_and_after(self):
        d=graph_diff(graph(),graph(label='New'));self.assertEqual(d['nodes']['changed'][0]['before']['label'],'Main');self.assertEqual(d['nodes']['changed'][0]['after']['label'],'New')
    def test_invalid_project_id(self):
        g=graph('../private');self.assertRaises(ContractError,validate_graph,g)

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'store');self.store.register('sample','Sample',mode='published')
    def tearDown(self): self.tmp.cleanup()
    def publish(self,g=None,event='a',expected=0,**kw):
        return self.store.publish(g or graph(),expected=expected,event_id=event,summary='Observed change',**kw)
    def test_initial_revision(self):
        self.assertEqual(self.publish()['revision'],1);self.assertEqual(self.store.head('sample'),1)
    def test_duplicate_request_is_idempotent(self):
        self.publish();r=self.publish();self.assertTrue(r['duplicate']);self.assertEqual(self.store.head('sample'),1)
    def test_reused_id_with_different_content_rejected(self):
        self.publish();self.assertRaises(ConflictError,self.publish,graph(label='Other'))
    def test_stale_parent_rejected(self):
        self.publish();self.assertRaises(ConflictError,self.publish,graph(label='Next'),'b',0)
    def test_noop_does_not_create_revision(self):
        self.publish();r=self.publish(event='b',expected=1);self.assertFalse(r['changed']);self.assertEqual(len(self.store.history('sample')),1)
    def test_noop_request_is_still_idempotent(self):
        self.publish();self.publish(event='b',expected=1);r=self.publish(event='b',expected=1);self.assertTrue(r['duplicate']);self.assertRaises(ConflictError,self.publish,graph(label='New'),'b',1)
    def test_source_capture_timestamp_not_change(self):
        self.publish();g=graph();g['source']['capturedAt']='tomorrow';g['source']['scanStats']={'durationMs':300};self.assertFalse(self.publish(g,event='b',expected=1)['changed'])
    def test_historical_snapshot_immutable(self):
        self.publish();self.publish(graph(label='New'),event='b',expected=1);self.assertEqual(next(n for n in self.store.snapshot('sample',1)['nodes'] if n['kind']=='file')['label'],'Main')
    def test_store_survives_restart(self):
        self.publish();other=Store(self.store.directory);self.assertEqual(other.head('sample'),1);self.assertEqual(other.snapshot('sample')['project']['id'],'sample')
    def test_checkpoint_does_not_modify_graph(self):
        self.publish();before=self.store.snapshot('sample');c=self.store.checkpoint('sample','Feature complete');self.assertEqual(c['revision'],1);self.assertEqual(self.store.snapshot('sample'),before);self.assertEqual(len(self.store.history('sample')),1)
    def test_checkpoints_cover_revisions(self):
        self.publish();self.store.checkpoint('sample','Start');self.publish(graph(label='Second'),event='b',expected=1);self.publish(graph(label='Third'),event='c',expected=2);c=self.store.checkpoint('sample','Done');self.assertEqual((c['start_revision'],c['revision']),(2,3))
    def test_empty_checkpoint_rejected(self): self.assertRaises(ContractError,self.store.checkpoint,'sample','Empty')
    def test_invalid_checkpoint_revision(self):
        self.publish();self.assertRaises(ContractError,self.store.checkpoint,'sample','Future','',100)
    def test_invalid_blob_rolls_back_transaction(self):
        self.assertRaises(ContractError,self.publish,blobs={'bad':'text'});self.assertEqual(self.store.head('sample'),0)
    def test_source_content_at_exact_revision(self):
        g=graph();text='print("one")\n';hv=sha(text.encode());g['nodes'][1]['hash']=hv;self.publish(g,blobs={hv:text})
        g2=copy.deepcopy(g);text2='print("two")\n';hv2=sha(text2.encode());g2['nodes'][1]['hash']=hv2;g2['source']['treeHash']='tree-2';self.publish(g2,event='b',expected=1,blobs={hv2:text2})
        self.assertEqual(self.store.source('sample','src/main.py',1)['text'],text);self.assertEqual(self.store.source('sample','src/main.py',2)['text'],text2)
    def test_source_not_part_of_graph_cannot_be_read(self):
        self.publish();self.assertRaises(MissingError,self.store.source,'sample','../secret')
    def test_two_writers_one_winner(self):
        self.publish();results=[]
        def writer(name):
            try: results.append(self.publish(graph(label=name),event=name,expected=1)['revision'])
            except ConflictError: results.append('conflict')
        ts=[threading.Thread(target=writer,args=(name,)) for name in ('writer-a','writer-b')]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertCountEqual(results,[2,'conflict']);self.assertEqual(self.store.head('sample'),2)
    def test_patch_published_atomically(self):
        self.publish();n=graph()['nodes'][1];n['label']='Patched';r=self.store.publish(None,project_id='sample',patch={'upsertNodes':[n]},expected=1,event_id='b',summary='Patch');self.assertEqual(r['revision'],2)
    def test_export_has_no_source_blobs_or_local_root(self):
        g=graph();text='secret source body';hv=sha(text.encode());g['nodes'][1]['hash']=hv;self.publish(g,blobs={hv:text});data=json.dumps(self.store.export('sample'));self.assertNotIn(text,data);self.assertNotIn(self.tmp.name,data)
    def test_bounded_context_and_query(self):
        self.publish();r=self.store.query('sample',text='Main',limit=1);self.assertEqual(len(r['nodes']),1);self.assertEqual(r['revision'],1)
    def test_pagination(self):
        for i in range(4):self.publish(graph(label=str(i)),event=str(i),expected=i)
        self.assertEqual([e['revision'] for e in self.store.history('sample',2)],[4,3]);self.assertEqual([e['revision'] for e in self.store.history('sample',2,3)],[2,1])
    def test_project_root_collision_rejected(self):
        self.assertRaises(ConflictError,self.store.register,'sample','Different',self.tmp.name)

if __name__=='__main__':unittest.main()
