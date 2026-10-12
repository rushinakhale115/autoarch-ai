from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .database import connect

def retrieve(project_id, question, document_ids=None, top_k=5):
    with connect() as con:
        sql = 'SELECT c.text,c.page,d.filename,d.revision,d.id document_id FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.project_id=?'
        args = [project_id]
        if document_ids:
            sql += ' AND c.document_id IN (' + ','.join('?' for _ in document_ids) + ')'
            args.extend(document_ids)
        rows = [dict(r) for r in con.execute(sql, args).fetchall()]
    if not rows or not question.strip():
        return []
    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words='english').fit_transform([question] + [r['text'] for r in rows])
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    except ValueError:
        return []
    ranked = sorted(zip(scores, rows), key=lambda pair: pair[0], reverse=True)
    return [dict(r, score=float(s)) for s, r in ranked[:top_k] if s > 0.01]
