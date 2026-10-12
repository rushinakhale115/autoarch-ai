import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', synthetic INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, filename TEXT NOT NULL, revision TEXT NOT NULL, sha256 TEXT NOT NULL, page_count INTEGER DEFAULT 0, status TEXT NOT NULL, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP, error TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, page INTEGER NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_chunks_scope ON chunks(project_id, document_id);
CREATE TABLE IF NOT EXISTS components(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, document_id TEXT REFERENCES documents(id) ON DELETE CASCADE, revision TEXT NOT NULL, entity_id TEXT, name TEXT NOT NULL, description TEXT DEFAULT '', responsibilities TEXT DEFAULT '', page INTEGER, evidence TEXT DEFAULT '', confidence TEXT DEFAULT 'unverified', human_edited INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS interfaces(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, document_id TEXT REFERENCES documents(id) ON DELETE CASCADE, revision TEXT NOT NULL, entity_id TEXT, name TEXT NOT NULL, provider TEXT, consumers TEXT DEFAULT '[]', data TEXT, direction TEXT, page INTEGER, evidence TEXT DEFAULT '', human_edited INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS dependencies(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, document_id TEXT REFERENCES documents(id) ON DELETE CASCADE, revision TEXT NOT NULL, source TEXT, target TEXT, reason TEXT, kind TEXT, page INTEGER, evidence TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, rule_id TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL, description TEXT NOT NULL, entity TEXT, document_id TEXT, page INTEGER, evidence TEXT DEFAULT '', action TEXT DEFAULT '', status TEXT DEFAULT 'Open', reviewer_comment TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, origin TEXT DEFAULT 'deterministic');
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, document_id TEXT, event TEXT NOT NULL, details TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)

def audit(project_id, event, details='', document_id=None):
    with connect() as con:
        con.execute('INSERT INTO audit_events(project_id,document_id,event,details) VALUES(?,?,?,?)', (project_id, document_id, event, details))
