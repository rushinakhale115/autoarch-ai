import hashlib
import fitz
from .database import connect, audit

def extract_pdf(data: bytes):
    if not data or not data.startswith(b'%PDF-'):
        raise ValueError('The uploaded file is not a readable PDF.')
    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        raise ValueError('The PDF could not be opened. It may be corrupt or password protected.') from exc
    pages = [(i + 1, page.get_text('text').strip()) for i, page in enumerate(doc)]
    if not pages:
        raise ValueError('The PDF contains no pages.')
    if not any(text for _, text in pages):
        raise ValueError('No selectable text was found. This may be a scanned PDF; OCR is not configured.')
    return pages

def chunk_pages(pages, max_chars=1400):
    chunks = []
    for page, text in pages:
        # Page boundaries are retained so every retrieved passage has reliable provenance.
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        current = ''
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 1 > max_chars:
                chunks.append({'page': page, 'text': current})
                current = ''
            current = f'{current}\n{paragraph}'.strip()
        if current:
            chunks.append({'page': page, 'text': current})
    return chunks

def save_pdf(project_id, filename, revision, data):
    pages = extract_pdf(data)
    digest = hashlib.sha256(data).hexdigest()
    with connect() as con:
        if con.execute('SELECT 1 FROM documents WHERE project_id=? AND sha256=?', (project_id, digest)).fetchone():
            raise ValueError('This exact document is already in the selected project.')
        import uuid
        doc_id = str(uuid.uuid4())
        con.execute('INSERT INTO documents(id,project_id,filename,revision,sha256,page_count,status) VALUES(?,?,?,?,?,?,?)', (doc_id, project_id, filename, revision, digest, len(pages), 'Processed'))
        for item in chunk_pages(pages):
            con.execute('INSERT INTO chunks(project_id,document_id,page,text) VALUES(?,?,?,?)', (project_id, doc_id, item['page'], item['text']))
    audit(project_id, 'document_uploaded', f'{filename}; revision={revision}; pages={len(pages)}', doc_id)
    return doc_id, len(pages)
