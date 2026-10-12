# AutoArch AI

AI-Powered Automotive Architecture Intelligence. A local Streamlit MVP for project-scoped PDF ingestion, evidence retrieval, architecture inventories, deterministic review prompts, revision comparison, and exports.

## Windows PowerShell setup

```powershell
cd C:\Users\Rushikesh\autoarch_ai_mvp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

The app runs locally and creates `data/autoarch.db` on first launch. To enable grounded LLM synthesis, put `OPENAI_API_KEY=your-key` in `.env` or set it in the process environment. The app reads the simple `.env` file at startup. The optional model is controlled by `OPENAI_MODEL` (default `gpt-4o-mini`). Do not commit `.env`.

PowerShell environment example:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "gpt-4o-mini"
streamlit run app.py
```

## Demo workflow

1. Launch the app and click **Load synthetic demo project** in the sidebar.
2. Dashboard shows synthetic inventory and an open unresolved interface endpoint finding.
3. Open **Architecture Explorer**, select revision 1.0 or 1.1, and inspect the actual stored graph.
4. Open **Revision Comparison**, compare 1.0 to 1.1, and explore candidate impacts.
5. In **Validation Findings**, run checks and accept, reject (with reason), or resolve the finding.
6. Download XLSX and CSV files under **Reports and Exports**.

For ingestion, select or create a project in Document Workspace, upload a selectable-text PDF and revision, then ask a scoped question in Ask the HLD. Duplicate file hashes are rejected within a project. Each chunk keeps document, revision, project, and page metadata. Scanned PDFs get a clear message because OCR is not bundled.

## Deploy on Streamlit Community Cloud

1. Push this project to a GitHub repository (public, or private with Community Cloud access granted).
2. In Community Cloud, choose **Create app**, select the repository and branch, and set `app.py` as the main file.
3. In the app's **Settings → Secrets**, add `OPENAI_API_KEY = "your-key"` and optionally `OPENAI_MODEL = "gpt-4o-mini"`.
4. Deploy and use the generated `*.streamlit.app` URL for the rubric demonstration.

Community Cloud's local filesystem is not durable storage. This MVP uses SQLite on that filesystem, so uploaded documents, projects, and review changes may be lost when the hosted app restarts or redeploys. Use the synthetic demo button to restore the fixture. Do not upload confidential HLDs to a public demo deployment.

## Implemented

- Project and document scoping in SQLite; upload validation, SHA-256 duplicate detection, page-level PyMuPDF extraction, chunking, and audit events.
- TF-IDF lexical retrieval and optional OpenAI JSON-mode grounded answer synthesis. Without a key, retrieved passages and citations are still available.
- Synthetic 1.0 and 1.1 architecture fixture; Plotly graph based on stored entities.
- Deterministic missing component references, unknown endpoints, duplicate IDs, missing evidence, and incomplete interface prompts.
- Finding filters and persistent human review status/comments.
- Structured revision comparison for components, interfaces, and dependencies plus downstream candidate impact traversal.
- Actual project data exports to CSV and multi-sheet XLSX.
- Streamlit dashboard, functional navigation, project workspace, and configuration disclosure.

## Limits

Extraction currently uses conservative explicit text patterns (for example, `Component: Name` and `Interface: Name`) rather than general semantic parsing. Arbitrary HLD layouts may produce few or no entities; inspect and correct results before relying on them. No OCR, embeddings/Chroma, FastAPI layer, or authentication is included. Use only in a local demo environment. Production multi-user use needs identity, authorization, secure deployment, and appropriate retention controls. AI suggestions and findings require qualified engineer review.

## Tests

```powershell
python -m pytest -q
```

Tests do not call paid AI services.
