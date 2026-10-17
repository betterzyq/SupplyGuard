"""No external model/DB/LLM calls. Contract checks are not retrieval accuracy."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from packages.authz.rbac import UserContext, can_access_admin
from packages.authz.document_policy import can_access_document
from packages.benchmarks.metrics import graph_path_hit_rate, citation_scores, blocked_accuracy

ROOT=Path(__file__).resolve().parents[2]


def validate():
    path=ROOT/'data/eval/enterprise-v2.json'
    dataset=json.loads(path.read_text())
    rows=[]
    for c in dataset['cases']:
        kind=c['kind']
        if kind=='graph_gold':
            # A schema/gold structural check only, explicitly excluded from scorer pass rate.
            rows.append({'id':c['id'],'kind':kind,'status':'gold_only','paths':len(c['gold_graph_paths'])})
            continue
        if kind=='policy':
            user=UserContext(user_id=UUID(int=1),tenant_id=UUID(int=2),email='contract@example.invalid',department='',roles=[c['role']])
            if c['resource']=='admin':
                allowed=can_access_admin(user)
            else:
                doc=SimpleNamespace(tenant_id=UUID(int=2 if c['scope']=='same_tenant' else 3))
                allowed=can_access_document(user,doc).allowed
            actual='allow' if allowed else 'denied'
            expected=c['expected_decision']
        elif kind=='path_scorer':
            actual=graph_path_hit_rate(c['found'],c['gold'])
            expected=c['expected']
        elif kind=='citation_scorer':
            actual=citation_scores(c['found'],c['gold'])
            expected={'citation_precision':c['precision'],'citation_recall':c['recall']}
        else:
            actual=blocked_accuracy([{'should_be_blocked':True,'decision':c['decision']}])
            expected=c['expected']
        rows.append({'id':c['id'],'kind':kind,'actual':actual,'expected':expected,'status':'passed' if actual==expected else 'failed'})
    evaluated=[r for r in rows if r['status']!='gold_only']
    return {'dataset_version':dataset['dataset_version'],'scorer_version':dataset['scorer_version'],'policy_version':dataset['policy_version'],
        'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'purpose':dataset['purpose'],
        'status':'passed' if all(r['status']=='passed' for r in evaluated) else 'failed',
        'evaluated_contracts':len(evaluated),'gold_only_cases':len(rows)-len(evaluated),'rows':rows,
        'live_retrieval_status':'not_run','historical_scores':'deprecated; no comparison to enterprise-v2 contract results'}
