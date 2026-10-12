import os
import tempfile
import pytest
from src.document_service import extract_pdf, chunk_pages
from src.database import init_db, connect
from src.demo import load_demo
from src.validation_engine import validate_project, compare_revisions, impact_candidates
from src.retrieval import retrieve
from src.report_service import export_csv, export_xlsx
from src.llm_service import answer_question

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch,tmp_path):
    from src import config
    monkeypatch.setattr(config,'DB_PATH',tmp_path/'test.db')
    from src import database
    monkeypatch.setattr(database,'DB_PATH',tmp_path/'test.db')
    init_db()

def test_invalid_pdf_rejected():
    with pytest.raises(ValueError): extract_pdf(b'not a pdf')

def test_pdf_pages_and_chunk_metadata():
    import fitz
    doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),'Component: Alpha')
    data=doc.tobytes(); pages=extract_pdf(data)
    assert pages[0][0]==1 and 'Alpha' in pages[0][1]
    assert chunk_pages(pages)[0]['page']==1

def test_demo_validation_and_revision():
    pid=load_demo()
    assert validate_project(pid)>=1
    with connect() as con:
        findings=con.execute('SELECT rule_id,description FROM findings WHERE project_id=?',(pid,)).fetchall()
    assert any(x['rule_id']=='UNKNOWN_ENDPOINT' and 'MissingDiagnosticClient' in x['description'] for x in findings)
    diff=compare_revisions(pid,'1.0','1.1')
    assert any(x['category']=='Added component' and x['entity']=='DisplayVehicleInfoAdapter' for x in diff)
    assert 'DriverDisplay' in impact_candidates(pid,'DisplayVehicleInfoAdapter','1.1')

def test_retrieval_is_project_scoped():
    with connect() as con:
        for pid in ('p1','p2'): con.execute('INSERT INTO projects(id,name) VALUES(?,?)',(pid,pid))
        for pid,doc,text in [('p1','d1','ThermalManager consumes BatteryStatusService'),('p2','d2','Private unrelated content')]:
            con.execute('INSERT INTO documents(id,project_id,filename,revision,sha256,status) VALUES(?,?,?,?,?,?)',(doc,pid,doc+'.pdf','1',doc,'Processed'))
            con.execute('INSERT INTO chunks(project_id,document_id,page,text) VALUES(?,?,?,?)',(pid,doc,1,text))
    found=retrieve('p1','BatteryStatusService',top_k=3)
    assert found and all(x['filename']=='d1.pdf' for x in found)

def test_export_formats_have_records():
    pid=load_demo()
    assert b'VehicleSpeedProvider' in export_csv(__import__('pandas').DataFrame([{'name':'VehicleSpeedProvider'}]))
    assert export_xlsx(pid).startswith(b'PK')

def test_changed_interface_endpoint_is_compared():
    pid=load_demo(); diff=compare_revisions(pid,'1.0','1.1')
    assert any(d['category']=='Changed interface consumers' and d['entity']=='VehicleSpeedService' for d in diff)

def test_finding_review_status_persists():
    pid=load_demo()
    with connect() as con:
        row=con.execute('SELECT id FROM findings WHERE project_id=? LIMIT 1',(pid,)).fetchone()
        con.execute("UPDATE findings SET status='Accepted',reviewer_comment='Investigate' WHERE id=?",(row['id'],))
        saved=con.execute('SELECT status,reviewer_comment FROM findings WHERE id=?',(row['id'],)).fetchone()
    assert saved['status']=='Accepted' and saved['reviewer_comment']=='Investigate'

def test_empty_pdf_is_rejected():
    with pytest.raises(ValueError): extract_pdf(b'')

def test_duplicate_identifier_is_flagged():
    with connect() as con:
        con.execute("INSERT INTO projects(id,name) VALUES('dup','dup')")
        con.execute("INSERT INTO components(project_id,revision,entity_id,name,page,evidence) VALUES('dup','1','X','X',1,'e'),('dup','1','X','X2',1,'e')")
    assert validate_project('dup')>=1
    with connect() as con: assert con.execute("SELECT COUNT(*) FROM findings WHERE project_id='dup' AND rule_id='DUPLICATE_ID'").fetchone()[0]>=1

def test_valid_dependency_does_not_create_missing_reference():
    with connect() as con:
        con.execute("INSERT INTO projects(id,name) VALUES('valid','valid')")
        con.execute("INSERT INTO components(project_id,revision,name) VALUES('valid','1','A'),('valid','1','B')")
        con.execute("INSERT INTO dependencies(project_id,revision,source,target) VALUES('valid','1','A','B')")
    validate_project('valid')
    with connect() as con: assert con.execute("SELECT COUNT(*) FROM findings WHERE project_id='valid' AND rule_id='MISSING_COMPONENT_REF'").fetchone()[0]==0

def test_unknown_endpoint_and_missing_component_reference_are_flagged():
    with connect() as con:
        con.execute("INSERT INTO projects(id,name) VALUES('bad','bad')")
        con.execute("INSERT INTO components(project_id,revision,name) VALUES('bad','1','Known')")
        con.execute("INSERT INTO interfaces(project_id,revision,name,provider,consumers) VALUES('bad','1','I','Ghost','[]')")
        con.execute("INSERT INTO dependencies(project_id,revision,source,target) VALUES('bad','1','Known','Absent')")
    validate_project('bad')
    with connect() as con:
        rules={r[0] for r in con.execute("SELECT rule_id FROM findings WHERE project_id='bad'")}
    assert {'UNKNOWN_ENDPOINT','MISSING_COMPONENT_REF'} <= rules

def test_no_evidence_answer_is_explicit():
    answer=answer_question('Where is this defined?',[])
    assert 'No relevant evidence' in answer['facts'] and not answer['citations']

def test_answer_citations_only_reference_retrieved_passages(monkeypatch):
    import src.llm_service as service
    monkeypatch.setattr(service,'OPENAI_API_KEY','')
    passage={'filename':'hld.pdf','page':3,'text':'ThermalManager consumes BatteryStatusService','score':0.8}
    answer=service.answer_question('What consumes BatteryStatusService?', [passage])
    assert answer['citations'][0]['filename']=='hld.pdf' and answer['citations'][0]['page']==3

def test_csv_export_contains_headers():
    import pandas as pd
    assert export_csv(pd.DataFrame([{'component':'A'}])).decode('utf-8-sig').startswith('component')

def test_revision_detects_removed_entities():
    pid=load_demo(); diff=compare_revisions(pid,'1.1','1.0')
    assert any(x['category']=='Removed component' and x['entity']=='DisplayVehicleInfoAdapter' for x in diff)
