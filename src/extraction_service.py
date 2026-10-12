"""Conservative structured extraction from page chunks; preserves only explicit matches."""
import re, json
from .database import connect, audit

COMPONENT = re.compile(r"\b(?:component|module|software unit)\s*[:#-]?\s+([A-Z][A-Za-z0-9_.-]{1,80})", re.I)
INTERFACE = re.compile(r"\binterface\s*[:#-]?\s+([A-Z][A-Za-z0-9_.-]{1,80})", re.I)
PROVIDER = re.compile(r"\bprovider\s*[:=]\s*([A-Za-z][A-Za-z0-9_.-]*)", re.I)
CONSUMERS = re.compile(r"\bconsumers?\s*[:=]\s*([A-Za-z0-9_., -]+)", re.I)
DATA = re.compile(r"\b(?:signal|data|payload)\s*[:=]\s*([A-Za-z0-9_., -]+)", re.I)
DEP = re.compile(r"\b([A-Z][A-Za-z0-9_.-]+)\s+(?:depends on|uses|calls)\s+([A-Z][A-Za-z0-9_.-]+)", re.I)

def extract_document(document_id, project_id):
    with connect() as con:
        doc=con.execute('SELECT revision FROM documents WHERE id=? AND project_id=?',(document_id,project_id)).fetchone()
        if not doc: raise ValueError('Document is outside the selected project or no longer exists.')
        pages=[dict(r) for r in con.execute('SELECT page,text FROM chunks WHERE document_id=? AND project_id=? ORDER BY page,id',(document_id,project_id))]
        revision=doc['revision']
        con.execute('DELETE FROM components WHERE document_id=?',(document_id,))
        con.execute('DELETE FROM interfaces WHERE document_id=?',(document_id,))
        con.execute('DELETE FROM dependencies WHERE document_id=?',(document_id,))
        comps=set(); interfaces=set(); deps=set()
        for row in pages:
            text=row['text']; page=row['page']
            for m in COMPONENT.finditer(text): comps.add((m.group(1),page,text[:500]))
            for m in INTERFACE.finditer(text):
                name=m.group(1); provider=PROVIDER.search(text); consumers=CONSUMERS.search(text); data=DATA.search(text)
                interfaces.add((name,provider.group(1) if provider else None,consumers.group(1).strip() if consumers else None,data.group(1).strip() if data else None,page,text[:500]))
            for m in DEP.finditer(text): deps.add((m.group(1),m.group(2),page,text[:500]))
        for name,page,evidence in comps:
            con.execute('INSERT INTO components(project_id,document_id,revision,entity_id,name,page,evidence,confidence) VALUES(?,?,?,?,?,?,?,?)',(project_id,document_id,revision,name,name,page,evidence,'pattern_match'))
        for name,provider,consumers,data,page,evidence in interfaces:
            consumer_list=[x.strip() for x in re.split(r'[,;]',consumers) if x.strip()] if consumers else []
            con.execute('INSERT INTO interfaces(project_id,document_id,revision,entity_id,name,provider,consumers,data,page,evidence) VALUES(?,?,?,?,?,?,?,?,?,?)',(project_id,document_id,revision,name,name,provider,json.dumps(consumer_list),data,page,evidence))
        for source,target,page,evidence in deps:
            con.execute('INSERT INTO dependencies(project_id,document_id,revision,source,target,page,evidence) VALUES(?,?,?,?,?,?,?)',(project_id,document_id,revision,source,target,page,evidence))
    audit(project_id,'architecture_extracted',f'{len(comps)} components; {len(interfaces)} interfaces; {len(deps)} dependencies',document_id)
    return {'components':len(comps),'interfaces':len(interfaces),'dependencies':len(deps)}
