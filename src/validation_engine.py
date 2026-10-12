import uuid
from .database import connect, audit

def validate_project(project_id):
    with connect() as con:
        comps=[dict(x) for x in con.execute('SELECT * FROM components WHERE project_id=?',(project_id,))]
        interfaces=[dict(x) for x in con.execute('SELECT * FROM interfaces WHERE project_id=?',(project_id,))]
        deps=[dict(x) for x in con.execute('SELECT * FROM dependencies WHERE project_id=?',(project_id,))]
        docs={x['id']:x['filename'] for x in con.execute('SELECT id,filename FROM documents WHERE project_id=?',(project_id,))}
    names={c['name'] for c in comps}
    findings=[]
    def add(rule,title,description,entity=None,row=None,severity='Medium',action='Review the source and extracted architecture record.'):
        row=row or {}
        findings.append((str(uuid.uuid4()),project_id,rule,title,severity,description,entity,row.get('document_id'),row.get('page'),row.get('evidence',''),action))
    seen={}
    for c in comps:
        key=c.get('entity_id') or c['name']
        if key in seen: add('DUPLICATE_ID','Duplicate component identifier',f"Identifier '{key}' appears more than once.",c['name'],c)
        seen[key]=1
        if not c.get('page') or not c.get('evidence'): add('MISSING_EVIDENCE','Component lacks usable evidence',f"{c['name']} has incomplete source provenance.",c['name'],c,'Low')
    for i in interfaces:
        key=i.get('entity_id') or i['name']
        if key in seen: add('DUPLICATE_ID','Duplicate architecture identifier',f"Identifier '{key}' appears more than once.",i['name'],i)
        seen[key]=1
        for role, endpoint in [('provider',i.get('provider'))]+[('consumer',x) for x in __import__('json').loads(i.get('consumers') or '[]')]:
            if endpoint and endpoint not in names: add('UNKNOWN_ENDPOINT','Unknown interface endpoint',f"Interface {i['name']} names {endpoint} as {role}, but it is absent from the component inventory.",i['name'],i)
        if not i.get('page') or not i.get('evidence'): add('MISSING_EVIDENCE','Interface lacks usable evidence',f"{i['name']} has incomplete source provenance.",i['name'],i,'Low')
        if not i.get('provider') or not i.get('consumers') or not i.get('data'): add('INCOMPLETE_INTERFACE','Incomplete interface definition',f"{i['name']} is missing provider, consumer, or data details. This is a completeness prompt, not a confirmed defect.",i['name'],i,'Low')
    for d in deps:
        for endpoint in [d.get('source'),d.get('target')]:
            if endpoint and endpoint not in names: add('MISSING_COMPONENT_REF','Missing component reference',f"Dependency references {endpoint}, which is absent from the component inventory.",endpoint,d,'Medium')
    with connect() as con:
        con.execute('DELETE FROM findings WHERE project_id=? AND rule_id IN (\'DUPLICATE_ID\',\'MISSING_EVIDENCE\',\'UNKNOWN_ENDPOINT\',\'INCOMPLETE_INTERFACE\',\'MISSING_COMPONENT_REF\') AND status=\'Open\'',(project_id,))
        for f in findings: con.execute('INSERT INTO findings(id,project_id,rule_id,title,severity,description,entity,document_id,page,evidence,action) VALUES(?,?,?,?,?,?,?,?,?,?,?)',f)
    audit(project_id,'validation_run',f'{len(findings)} deterministic findings')
    return len(findings)

def compare_revisions(project_id, old_revision, new_revision):
    with connect() as con:
        oldc=[dict(r) for r in con.execute('SELECT * FROM components WHERE project_id=? AND revision=?',(project_id,old_revision))]
        newc=[dict(r) for r in con.execute('SELECT * FROM components WHERE project_id=? AND revision=?',(project_id,new_revision))]
        oldi=[dict(r) for r in con.execute('SELECT * FROM interfaces WHERE project_id=? AND revision=?',(project_id,old_revision))]
        newi=[dict(r) for r in con.execute('SELECT * FROM interfaces WHERE project_id=? AND revision=?',(project_id,new_revision))]
        oldd=[dict(r) for r in con.execute('SELECT * FROM dependencies WHERE project_id=? AND revision=?',(project_id,old_revision))]
        newd=[dict(r) for r in con.execute('SELECT * FROM dependencies WHERE project_id=? AND revision=?',(project_id,new_revision))]
    result=[]
    for label, a, b, key in [('component',oldc,newc,'name'),('interface',oldi,newi,'name')]:
        am={x[key]:x for x in a}; bm={x[key]:x for x in b}
        for name in bm.keys()-am.keys(): result.append({'category':f'Added {label}','entity':name,'previous':'','new':name,'old_page':None,'new_page':bm[name].get('page')})
        for name in am.keys()-bm.keys(): result.append({'category':f'Removed {label}','entity':name,'previous':name,'new':'','old_page':am[name].get('page'),'new_page':None})
        if label=='interface':
            for name in am.keys()&bm.keys():
                for field in ('provider','consumers','data'):
                    if am[name].get(field)!=bm[name].get(field): result.append({'category':f'Changed interface {field}','entity':name,'previous':str(am[name].get(field)),'new':str(bm[name].get(field)),'old_page':am[name].get('page'),'new_page':bm[name].get('page')})
    for label,a,b in [('dependency',oldd,newd)]:
        aset={(x.get('source'),x.get('target')) for x in a}; bset={(x.get('source'),x.get('target')) for x in b}
        for pair in bset-aset: result.append({'category':'Added dependency','entity':' → '.join(pair),'previous':'','new':' → '.join(pair),'old_page':None,'new_page':None})
        for pair in aset-bset: result.append({'category':'Removed dependency','entity':' → '.join(pair),'previous':' → '.join(pair),'new':'','old_page':None,'new_page':None})
    return result

def impact_candidates(project_id, entity, revision=None):
    with connect() as con:
        q='SELECT source,target FROM dependencies WHERE project_id=?'; args=[project_id]
        if revision: q+=' AND revision=?'; args.append(revision)
        edges=[tuple(r) for r in con.execute(q,args)]
    found=set(); frontier={entity}
    while frontier:
        nxt={src for src,dst in edges if dst in frontier}-found-{entity}
        if not nxt: break
        found |= nxt; frontier=nxt
    return sorted(found)
