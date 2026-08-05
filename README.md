# Retail Store Performance and Shelf Audit Assistant

AI-powered workflow for regional store managers: upload an audit report (PDF/DOCX) plus current shelf photos, receive a one-page executive brief, prioritized issues, drill-down evidence, and corrective action recommendations.

## Quickstart

```bash
git clone https://github.com/affine-Nikhil-Sarwal/build-an-ai-powered-retail-store-performance-and-shelf-audit-assistant-f.git
cd build-an-ai-powered-retail-store-performance-and-shelf-audit-assistant-f
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with real Azure OpenAI credentials
python main.py --health
python main.py --dry-run
python main.py --document examples/sample_audit.pdf --image examples/sample_shelf.jpg
```

## CLI

| Flag | Description |
|------|-------------|
| `--health` | Check integration health (storage, document extractor, Azure OpenAI, vision quality, row detector, policy validator) |
| `--dry-run` | Run full orchestration without live Azure calls (uses `examples/` fixtures when no files supplied) |
| `--document PATH` | Audit report PDF or DOCX |
| `--image PATH` | Shelf photo (repeatable) |
| `--file PATH` | Auto-detect document vs image by extension |
| `--input-json PATH` | JSON with `document_paths` and `image_paths` arrays |
| `--serve` | Start FastAPI on port 8000 |

## HTTP API

Start the server:

```bash
python main.py --serve
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```

### `GET /health`

Returns integration status (HTTP 200 when healthy, 503 when degraded). Includes `X-Request-ID` header.

### `POST /audit/intake`

Multipart form upload:

- `report` — PDF or DOCX audit report (required)
- `shelf_photos` — one or more shelf images (required)

Example:

```bash
curl -X POST http://localhost:8000/audit/intake \
  -F "report=@examples/sample_audit.pdf" \
  -F "shelf_photos=@examples/sample_shelf.jpg"
```

## Required environment variables

| Variable | Purpose |
|----------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Chat/vision deployment name (primary) |
| `AZURE_OPENAI_VISION_DEPLOYMENT` | Optional separate vision deployment |
| `AZURE_OPENAI_API_VERSION` | API version (default `2024-02-15-preview`) |
| `AZURE_OPENAI_TOKEN_PARAM` | Optional override: `max_tokens` or `max_completion_tokens` |
| `UPLOAD_ROOT` | Local upload directory (default `data/uploads`) |
| `ROBOFLOW_API_KEY` | Optional Roboflow row detection |
| `AZURE_STORAGE_CONNECTION_STRING` | Optional Azure Blob storage |

Legacy fallback: `GPT4_LLM_MODEL_DEPLOYMENT_NAME` is used only when `AZURE_OPENAI_DEPLOYMENT` is unset.

## Workflow architecture

12 build nodes wired in `orchestrator/graph.py`:

1. Upload Intake → 2. Analysis Router → parallel document + vision branches → findings normalization → evidence merge → confidence check → prioritization → executive brief → manager drill-down output.

See `workflow.json` and `workflow_manifest.json` for the full graph.

## Development

```bash
python scripts/check_placeholders.py
python -m pytest tests/ -q
python main.py --dry-run
```

## Agent Library reference

Implementation patterns for Azure OpenAI vision row analysis and PDF brief extraction were informed by the read-only [Agent-Library](https://github.com/AAIN1828/Agent-Library) repository (`planogram_vision/agent.py`, `executive_brief_generator/agent.py`).
