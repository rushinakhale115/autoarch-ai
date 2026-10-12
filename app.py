import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.config import MAX_UPLOAD_MB, TOP_K, OPENAI_API_KEY
from src.database import init_db, connect, audit
from src.demo import load_demo
from src.document_service import save_pdf
from src.retrieval import retrieve
from src.llm_service import answer_question
from src.validation_engine import validate_project, compare_revisions, impact_candidates
from src.report_service import report_data, export_xlsx, export_csv
from src.extraction_service import extract_document

st.set_page_config(page_title='AutoArch AI', page_icon='🚘', layout='wide')
st.markdown('''<style>
:root{--navy:#10243a;--blue:#256b9a;--steel:#eaf0f5}
.stApp{background:#f5f7fa;color:#172b3d}.block-container{padding-top:1.5rem;max-width:1500px}
[data-testid="stSidebar"]{background:#10243a;color:#eef5fb}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *{
 color:#eef5fb!important
}
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] label *{color:#eef5fb!important}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea{
 color:#172b3d!important;background-color:#fff!important
}
[data-testid="stSidebar"] .stButton>button{
 background:#eaf0f5!important;color:#10243a!important;border:1px solid #c5d1dc
}
[data-testid="stSidebar"] .stButton>button *{color:#10243a!important}
div[data-testid="stMetric"]{background:white;border:1px solid #dce5ed;padding:16px;border-radius:10px;box-shadow:0 2px 8px #10243a0a}
h1,h2,h3{color:#10243a}.stButton>button{border-radius:7px;border:1px solid #c5d1dc}
</style>''',unsafe_allow_html=True)
init_db()

def rows(sql,args=()):
    with connect() as con: return [dict(r) for r in con.execute(sql,args).fetchall()]
def current_projects(): return rows('SELECT * FROM projects ORDER BY created_at DESC')
def select_project():
    ps=current_projects()
    if not ps: return None
    labels={f"{p['name']}" + (' · SYNTHETIC' if p['synthetic'] else ''):p['id'] for p in ps}
    choice=st.sidebar.selectbox('Project',list(labels))
    return labels[choice]
def load_counts(pid):
    with connect() as con:
        return [con.execute(q,(pid,)).fetchone()[0] for q in ['SELECT COUNT(*) FROM documents WHERE project_id=?','SELECT COUNT(*) FROM components WHERE project_id=?','SELECT COUNT(*) FROM interfaces WHERE project_id=?','SELECT COUNT(*) FROM dependencies WHERE project_id=?',"SELECT COUNT(*) FROM findings WHERE project_id=? AND status='Open'"]]

st.sidebar.markdown('## 🚘 AutoArch AI')
st.sidebar.caption('AI-Powered Automotive Architecture Intelligence')
page=st.sidebar.radio('Workspace',['Dashboard','Document Workspace','Ask the HLD','Architecture Explorer','Validation Findings','Revision Comparison','Reports and Exports','Settings and About'],key='nav')
if st.sidebar.button('Load synthetic demo project',use_container_width=True):
    load_demo(); st.session_state.project='demo-autoarch'; st.rerun()
pid=select_project()
if pid is None:
    st.title('AutoArch AI'); st.subheader('AI-Powered Automotive Architecture Intelligence')
    st.info('Start with the synthetic demo fixture or create a project in Document Workspace.')
    st.stop()
project=next(p for p in current_projects() if p['id']==pid)
st.title('AutoArch AI')
st.caption('AI-Powered Automotive Architecture Intelligence')
if project['synthetic']: st.info('Synthetic demonstration fixture · not production architecture data')

if page=='Dashboard':
    st.subheader('Engineering overview')
    vals=load_counts(pid); labels=['Documents','Components','Interfaces','Dependencies','Open findings awaiting review']
    cols=st.columns(5)
    for c,l,v in zip(cols,labels,vals): c.metric(l,v)
    a,b=st.columns([1.3,1])
    with a:
        st.markdown('### Recent documents')
        docs=rows('SELECT filename,revision,page_count,status,uploaded_at FROM documents WHERE project_id=? ORDER BY uploaded_at DESC',(pid,))
        st.dataframe(pd.DataFrame(docs),use_container_width=True,hide_index=True) if docs else st.caption('No uploaded documents yet. Upload an HLD PDF to begin.')
    with b:
        st.markdown('### Finding summary')
        fs=rows('SELECT severity,COUNT(*) count FROM findings WHERE project_id=? AND status=\'Open\' GROUP BY severity',(pid,))
        st.dataframe(pd.DataFrame(fs),use_container_width=True,hide_index=True) if fs else st.success('No open findings. Run validation after extraction or load the demo fixture.')
    st.markdown('### Next action')
    st.write('Upload a revision, inspect extracted architecture, then run deterministic validation and review findings.')
    st.button('Open Document Workspace',on_click=lambda: st.session_state.update(nav='Document Workspace'))
elif page=='Document Workspace':
    st.subheader('Document Workspace')
    with st.form('project_form'):
        name=st.text_input('Create a project')
        desc=st.text_input('Project description')
        add=st.form_submit_button('Create project')
    if add and name.strip():
        import uuid
        new_id=str(uuid.uuid4())
        with connect() as con: con.execute('INSERT INTO projects(id,name,description) VALUES(?,?,?)',(new_id,name.strip(),desc))
        audit(new_id,'project_created',name); st.success('Project created. Select it in the sidebar.'); st.rerun()
    st.markdown('#### Upload an HLD PDF')
    with st.form('upload'):
        file=st.file_uploader('PDF document',type=['pdf'])
        revision=st.text_input('Revision',value='1.0')
        submit=st.form_submit_button('Upload and process')
    if submit:
        if file is None: st.error('Choose a PDF first.')
        elif file.size>MAX_UPLOAD_MB*1024*1024: st.error(f'File exceeds the {MAX_UPLOAD_MB} MB upload limit.')
        else:
            try:
                did,pages=save_pdf(pid,file.name,revision,file.getvalue()); st.success(f'Processed {file.name}: {pages} pages.'); st.rerun()
            except ValueError as e: st.error(str(e))
    docs=rows('SELECT id,filename,revision,page_count,status,uploaded_at,error FROM documents WHERE project_id=? ORDER BY uploaded_at DESC',(pid,))
    st.markdown('#### Project documents')
    st.dataframe(pd.DataFrame(docs).drop(columns=['id','error']) if docs else pd.DataFrame(),use_container_width=True,hide_index=True)
    if docs:
        chosen=st.selectbox('Inspect or delete document',docs,format_func=lambda d:f"{d['filename']} · rev {d['revision']}")
        if st.button('Delete selected document',type='secondary'):
            st.session_state.confirm_delete=chosen['id']
        if st.session_state.get('confirm_delete')==chosen['id']:
            st.warning('Confirm deletion? This removes its chunks and extracted records.')
            c1,c2=st.columns(2)
            if c1.button('Confirm delete'):
                with connect() as con: con.execute('DELETE FROM documents WHERE id=? AND project_id=?',(chosen['id'],pid))
                audit(pid,'document_deleted',chosen['filename'],chosen['id']); del st.session_state.confirm_delete; st.rerun()
            if c2.button('Cancel'): del st.session_state.confirm_delete; st.rerun()
        if st.button('Extract architecture from selected document'):
            try:
                result=extract_document(chosen['id'],pid)
                st.success(f"Extracted {result['components']} components, {result['interfaces']} interfaces, and {result['dependencies']} dependencies using explicit text patterns. Unmatched layouts are left unfilled; review findings before use.")
            except ValueError as e: st.error(str(e))
    st.caption('Scanned PDFs without selectable text are detected. OCR is not configured in this MVP.')
elif page=='Ask the HLD':
    st.subheader('Ask the HLD')
    docs=rows('SELECT id,filename,revision FROM documents WHERE project_id=? ORDER BY uploaded_at DESC',(pid,))
    scope=st.multiselect('Document scope (empty means all project documents)',docs,format_func=lambda d:f"{d['filename']} · rev {d['revision']}")
    q=st.text_input('Ask an architecture question',placeholder='Which components consume VehicleSpeedService?')
    k=st.slider('Retrieval top-k',1,10,TOP_K)
    if st.button('Search and answer',type='primary') and q.strip():
        evidence=retrieve(pid,q,[d['id'] for d in scope] if scope else None,k)
        result=answer_question(q,evidence)
        st.markdown('#### Facts stated in source'); st.write(result.get('facts',''))
        st.markdown('#### Inferences'); st.write(result.get('inferences') or 'None stated.')
        st.markdown('#### Unknowns'); st.write(result.get('unknowns') or 'None stated.')
        with st.expander(f'Retrieved evidence ({len(evidence)} passages)',expanded=True):
            for e in evidence: st.markdown(f"**{e['filename']} · page {e['page']} · {e['revision']}** (score {e['score']:.2f})\n\n> {e['text']}")
        st.markdown('#### Citations')
        for c in result.get('citations',[]): st.markdown(f"**{c['filename']} · page {c['page']}**\n\n> {c['excerpt']}")
        audit(pid,'question_answered',q[:120])
    st.caption('Lexical TF-IDF retrieval is local. LLM synthesis is optional; configure OPENAI_API_KEY to enable it. Citations identify retrieved passages and do not certify correctness.')
elif page=='Architecture Explorer':
    st.subheader('Architecture Explorer')
    revs=sorted({x['revision'] for x in rows('SELECT revision FROM components WHERE project_id=? UNION SELECT revision FROM interfaces WHERE project_id=?',(pid,pid))})
    if not revs: st.info('No structured entities yet. Load the synthetic fixture or upload and extract a document.')
    else:
        rev=st.selectbox('Revision',revs)
        cs=rows('SELECT * FROM components WHERE project_id=? AND revision=?',(pid,rev)); ds=rows('SELECT * FROM dependencies WHERE project_id=? AND revision=?',(pid,rev)); ins=rows('SELECT * FROM interfaces WHERE project_id=? AND revision=?',(pid,rev))
        term=st.text_input('Filter components or interfaces')
        names=[c['name'] for c in cs if term.lower() in c['name'].lower()]
        edges=[d for d in ds if d.get('source') in names or d.get('target') in names]
        positions={n:(i%3, -(i//3)) for i,n in enumerate(names)}
        fig=go.Figure()
        for d in edges:
            a,b=d['source'],d['target']
            if a not in positions or b not in positions: continue
            x1,y1=positions[a]; x2,y2=positions[b]
            fig.add_trace(go.Scatter(x=[x1,x2],y=[y1,y2],mode='lines+markers',line={'color':'#7894aa','width':2},marker={'size':7},hoverinfo='text',text=[f"{a} → {b}"]*2,showlegend=False))
        fig.add_trace(go.Scatter(x=[positions[n][0] for n in names],y=[positions[n][1] for n in names],text=names,mode='markers+text',textposition='bottom center',marker={'size':30,'color':'#256b9a'},hovertext=[next((c['description'] for c in cs if c['name']==n),'') for n in names],hoverinfo='text',showlegend=False))
        fig.update_layout(height=500,plot_bgcolor='white',paper_bgcolor='white',xaxis={'visible':False},yaxis={'visible':False},margin={'l':10,'r':10,'t':10,'b':10})
        st.plotly_chart(fig,use_container_width=True)
        with st.expander('Component details and interface inventory'):
            st.dataframe(pd.DataFrame(cs),use_container_width=True,hide_index=True)
            st.dataframe(pd.DataFrame(ins),use_container_width=True,hide_index=True)
        st.caption('Graph reflects stored structured entities. Select a finding in Validation Findings to inspect related records.')
elif page=='Validation Findings':
    st.subheader('Validation Findings')
    if st.button('Run deterministic validation',type='primary'): st.success(f"Generated {validate_project(pid)} review prompts.")
    fs=rows('SELECT * FROM findings WHERE project_id=? ORDER BY created_at DESC',(pid,))
    if not fs: st.info('No findings yet. Run validation or load the sample project.')
    else:
        fdf=pd.DataFrame(fs); s1,s2,s3=st.columns(3)
        severity=s1.multiselect('Severity',sorted(fdf.severity.unique()),default=list(fdf.severity.unique()))
        statuses=s2.multiselect('Status',sorted(fdf.status.unique()),default=list(fdf.status.unique()))
        rules=s3.multiselect('Rule',sorted(fdf.rule_id.unique()),default=list(fdf.rule_id.unique()))
        visible=[f for f in fs if f['severity'] in severity and f['status'] in statuses and f['rule_id'] in rules]
        st.dataframe(pd.DataFrame(visible)[['title','rule_id','severity','entity','status','created_at']],use_container_width=True,hide_index=True)
        for f in visible:
            with st.expander(f"{f['severity']} · {f['title']} · {f['entity'] or ''}"):
                st.write(f['description']); st.caption(f"Source page: {f['page'] or 'Unknown'} · Origin: {f['origin']} · Review action: {f['action']}")
                if f['evidence']: st.code(f['evidence'])
                status=st.selectbox('Review status',['Open','Accepted','Rejected','Resolved'],index=['Open','Accepted','Rejected','Resolved'].index(f['status']),key=f"status_{f['id']}")
                comment=st.text_area('Reviewer comment',f['reviewer_comment'],key=f"comment_{f['id']}")
                if st.button('Save review',key=f"save_{f['id']}"):
                    if status=='Rejected' and not comment.strip(): st.error('Add a reason when rejecting a finding.')
                    else:
                        with connect() as con: con.execute('UPDATE findings SET status=?,reviewer_comment=? WHERE id=? AND project_id=?',(status,comment,f['id'],pid))
                        audit(pid,'finding_reviewed',f"{f['id']} -> {status}"); st.success('Review saved.'); st.rerun()
elif page=='Revision Comparison':
    st.subheader('Revision Comparison')
    revisions=sorted({r['revision'] for r in rows('SELECT revision FROM components WHERE project_id=? UNION SELECT revision FROM interfaces WHERE project_id=?',(pid,pid))})
    if len(revisions)<2: st.info('At least two structured revisions are needed. The synthetic fixture includes 1.0 and 1.1.')
    else:
        old,new=st.columns(2); prev=old.selectbox('Previous revision',revisions,index=0); curr=new.selectbox('New revision',revisions,index=len(revisions)-1)
        if prev!=curr:
            diff=compare_revisions(pid,prev,curr)
            st.dataframe(pd.DataFrame(diff),use_container_width=True,hide_index=True) if diff else st.success('No structured changes detected.')
            if diff:
                entity=st.selectbox('Explore candidate downstream impact',sorted({d['entity'] for d in diff}))
                impacted=impact_candidates(pid,entity,curr)
                st.write('Potentially affected components:',', '.join(impacted) if impacted else 'None found in stored dependency direction.')
                st.caption('Candidate impact list requires engineering review; textual or structured differences do not establish safety.')
                st.download_button('Download comparison CSV',export_csv(pd.DataFrame(diff)),'revision_comparison.csv','text/csv')
elif page=='Reports and Exports':
    st.subheader('Reports and Exports')
    data=report_data(pid)
    st.download_button('Download project report (XLSX)',export_xlsx(pid),f"autoarch_{pid}.xlsx",'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    for name,df in data.items():
        with st.expander(f'{name} · {len(df)} rows'):
            st.dataframe(df,use_container_width=True,hide_index=True)
            st.download_button(f'Download {name} CSV',export_csv(df),f'{name.lower()}_{pid}.csv','text/csv',key=f'csv_{name}')
    st.caption('Exports reflect actual records in the selected project and include the human review statuses saved in SQLite.')
elif page=='Settings and About':
    st.subheader('Settings and About')
    st.markdown('#### Runtime configuration')
    st.write(f'Model: `{__import__("src.config",fromlist=["OPENAI_MODEL"]).OPENAI_MODEL}`')
    st.write(f'OpenAI API configured: **{"Yes" if OPENAI_API_KEY else "No — local retrieval and saved data remain available"}**')
    st.write(f'PDF upload limit: **{MAX_UPLOAD_MB} MB** · Retrieval top-k default: **{TOP_K}**')
    st.markdown('#### Limitations')
    st.write('This local MVP does not provide enterprise authentication, OCR, or automatic high-confidence extraction from arbitrary HLD layouts. Model answers depend on retrieved passages. Human engineering review is required. The application makes no ISO 26262, ISO/SAE 21434, or AUTOSAR compliance claim.')
    st.markdown('#### Audit events')
    audit_rows=rows('SELECT event,details,document_id,created_at FROM audit_events WHERE project_id=? ORDER BY created_at DESC LIMIT 100',(pid,))
    st.dataframe(pd.DataFrame(audit_rows),use_container_width=True,hide_index=True) if audit_rows else st.caption('No audit activity yet.')
