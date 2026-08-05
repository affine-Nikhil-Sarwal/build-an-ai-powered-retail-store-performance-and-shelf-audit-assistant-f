# Retail Store Performance and Shelf Audit Assistant

Agentic workflow architecture exported from **[Agentic LaunchPad](https://github.com)** by Affine Analytics.

AI-powered assistant for regional store managers: upload an audit report (PDF/DOCX) and current shelf photos to receive a one-page executive brief, prioritized issues, drill-down evidence, and corrective action recommendations.

## Quickstart

```bash
git clone https://github.com/affine-Nikhil-Sarwal/build-an-ai-powered-retail-store-performance-and-shelf-audit-assistant-f.git
cd build-an-ai-powered-retail-store-performance-and-shelf-audit-assistant-f
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
python main.py --health
python main.py --dry-run
python main.py --file examples/sample_audit.pdf --image examples/sample_shelf.jpg
```

### HTTP API

```bash
python main.py --serve
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/audit/intake \
  -F "report=@examples/sample_audit.pdf" \
  -F "shelf_photos=@examples/sample_shelf.jpg"
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Yes (live) | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Yes (live) | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Yes (live) | Chat/vision deployment name |
| `AZURE_OPENAI_VISION_DEPLOYMENT` | No | Separate vision deployment (defaults to chat deployment) |
| `AZURE_OPENAI_TOKEN_PARAM` | No | Override token budget kwarg: `max_tokens` or `max_completion_tokens` |
| `UPLOAD_ROOT` | No | Local upload directory (default: `data/uploads`) |
| `ROBOFLOW_API_KEY` | No | Optional Roboflow row detection |
| `AZURE_STORAGE_CONNECTION_STRING` | No | Optional Azure Blob storage |

---

## At a glance

- **Session:** `session-1785925042706-xpjtx7`
- **Steps:** 12
- **Connections:** 14
- **Exported:** 2026-08-05 11:20 UTC

## Problem statement

Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regional store managers. Users upload an existing store performance or audit PDF or DOCX along with one or more current retail shelf photos. The system produces a concise one-page narrative executive brief, analyzes shelf images for visible product availability, count, and placement issues, combines report context with current visual observations to identify recurring or important problems, prioritizes issues, and recommends corrective actions for the manager.

## Requirements

### Interview summary

Help regional store managers quickly understand current shelf problems in the context of prior store performance or audit findings, with trustworthy evidence and clear recommendations.

## Architecture summary

This architecture implements a retail shelf audit assistant with a parallel document-and-vision flow that starts at upload intake and ends in a manager-ready executive brief plus drill-down evidence view. The design follows the provided orchestration pattern: document extraction/summarization and shelf-photo analysis run in parallel after routing, then converge into normalization, evidence merge, confidence checking, prioritization, and final delivery. Integrations assumed from the spec are document upload/storage, image upload/storage, OCR/document extraction, a vision model for shelf analysis, and LLM-based synthesis.

The plan is catalog-first and reuses/adapts 9 of 12 nodes, comfortably above the 60% target. Reused catalog agents cover intake, routing, document understanding, image validation, object detection, shelf visual QA, evidence reconciliation, content generation, and final answer consolidation. Custom build is reserved only for the retail-specific cross-modal normalization layer, the merge policy that enforces current shelf photos as source of truth, and the issue-prioritization logic that must reflect business severity and confidence.

A key design choice is the true parallel fan-out from the routing gateway into the document path and the vision path for unified analysis. The vision path includes an explicit image-quality gate to avoid false certainty when photos are poor, then row/product detection and shelf reasoning. Both streams join before evidence reconciliation so the system can compare prior report findings against current visual observations and downgrade stale report claims when they conflict with present shelf evidence.

Main risks are capability gaps in the catalog for retail-specific normalization and prioritization, plus the need to adapt some agents beyond their original domain framing. The highest-value mitigation is to define a strict normalized issue schema with evidence pointers, confidence fields, and conflict-resolution rules so downstream brief generation remains grounded and trustworthy for direct manager consumption.

## Workflow overview

This architecture has **12** step(s) and **14** connection(s).

### Execution flow

- **Upload Intake** → *validated upload package* → **Analysis Router**
- **Analysis Router** → *document path* → **Document Brief Extractor**
- **Analysis Router** → *vision path* → **Shelf Image Quality Gate**
- **Analysis Router** → *document-only path* → **Document Brief Extractor**
- **Analysis Router** → *vision-only path* → **Shelf Image Quality Gate**
- **Shelf Image Quality Gate** → *usable shelf images* → **Shelf Row Detection**
- **Shelf Row Detection** → *detected rows and products* → **Shelf Vision Analysis**
- **Document Brief Extractor** → *report findings* → **Findings Normalization**
- **Shelf Vision Analysis** → *visual findings* → **Findings Normalization**
- **Findings Normalization** → *normalized findings* → **Evidence Merge Gate**
- **Evidence Merge Gate** → *merged evidence set* → **Evidence Confidence Check**
- **Evidence Confidence Check** → *scored issues* → **Issue Prioritization**
- **Issue Prioritization** → *prioritized issues and actions* → **Executive Brief Generation**
- **Executive Brief Generation** → *brief draft and recommendations* → **Manager Drill-down Output**

## Agents & steps

### Upload Intake

*agent* · **build**

Accept report documents and shelf photos, perform intake checks, and register the job.

*Rationale:* no catalog match

**Purpose:** Upload Intake

**Role:** Upload Intake is a agent step. Receives from Workflow entry. Passes to Analysis Router.

**Execution:** Accept report documents and shelf photos, perform intake checks, and register the job.

**Consumes from:**
- Workflow entry

**Feeds into:**
- Analysis Router

### Analysis Router

*gateway* · **build**

Route the request into document, vision, or unified processing paths based on uploaded inputs.

*Rationale:* no catalog match

**Purpose:** Analysis Router

**Role:** Analysis Router is a gateway step. Receives from Upload Intake. Passes to Document Brief Extractor, Shelf Image Quality Gate, Document Brief Extractor, Shelf Image Quality Gate.

**Execution:** Route the request into document, vision, or unified processing paths based on uploaded inputs.

**Consumes from:**
- Upload Intake

**Feeds into:**
- Document Brief Extractor
- Shelf Image Quality Gate
- Document Brief Extractor
- Shelf Image Quality Gate

### Document Brief Extractor

*agent* · **build**

Extract text from uploaded PDF/DOCX and produce a concise structured summary of prior audit findings.

*Rationale:* no catalog match

**Purpose:** Document Brief Extractor

**Role:** Document Brief Extractor is a agent step. Receives from Analysis Router, Analysis Router. Passes to Findings Normalization.

**Execution:** Extract text from uploaded PDF/DOCX and produce a concise structured summary of prior audit findings.

**Consumes from:**
- Analysis Router
- Analysis Router

**Feeds into:**
- Findings Normalization

### Shelf Image Quality Gate

*agent* · **build**

Check shelf photos for usable visual evidence and flag insufficient-quality images before downstream analysis.

*Rationale:* no catalog match

**Purpose:** Shelf Image Quality Gate

**Role:** Shelf Image Quality Gate is a agent step. Receives from Analysis Router, Analysis Router. Passes to Shelf Row Detection.

**Execution:** Check shelf photos for usable visual evidence and flag insufficient-quality images before downstream analysis.

**Consumes from:**
- Analysis Router
- Analysis Router

**Feeds into:**
- Shelf Row Detection

### Shelf Row Detection

*agent* · **build**

Detect shelf products and row-level visual regions to prepare structured inputs for shelf analysis.

*Rationale:* no catalog match

**Purpose:** Shelf Row Detection

**Role:** Shelf Row Detection is a agent step. Receives from Shelf Image Quality Gate. Passes to Shelf Vision Analysis.

**Execution:** Detect shelf products and row-level visual regions to prepare structured inputs for shelf analysis.

**Consumes from:**
- Shelf Image Quality Gate

**Feeds into:**
- Shelf Vision Analysis

### Shelf Vision Analysis

*agent* · catalog `planogram_vision_agent_chain` · **build** · Planogram Vision Agent Chain

Analyze shelf photos for visible availability, count, and placement issues using row-aware vision reasoning.

*Rationale:* matched Planogram Vision Agent Chain

**Purpose:** Shelf Vision Analysis

**Role:** Shelf Vision Analysis is a agent step. Receives from Shelf Row Detection. Passes to Findings Normalization.

**Execution:** Analyze shelf photos for visible availability, count, and placement issues using row-aware vision reasoning.

**Consumes from:**
- Shelf Row Detection

**Feeds into:**
- Findings Normalization

### Findings Normalization

*custom* · **build**

Normalize document and image findings into a shared issue schema with linked evidence references.

*Rationale:* no catalog match

**Purpose:** Findings Normalization

**Role:** Findings Normalization is a custom step. Receives from Document Brief Extractor, Shelf Vision Analysis. Passes to Evidence Merge Gate.

**Execution:** Normalize document and image findings into a shared issue schema with linked evidence references.

**Consumes from:**
- Document Brief Extractor
- Shelf Vision Analysis

**Feeds into:**
- Evidence Merge Gate

### Evidence Merge Gate

*gateway* · **build**

Merge prior report context with current shelf observations and enforce current photos as source of truth on conflicts.

*Rationale:* no catalog match

**Purpose:** Evidence Merge Gate

**Role:** Evidence Merge Gate is a gateway step. Receives from Findings Normalization. Passes to Evidence Confidence Check.

**Execution:** Merge prior report context with current shelf observations and enforce current photos as source of truth on conflicts.

**Consumes from:**
- Findings Normalization

**Feeds into:**
- Evidence Confidence Check

### Evidence Confidence Check

*agent* · **build**

Reconcile cross-source evidence, flag conflicts, and score groundedness and confidence for each issue.

*Rationale:* no catalog match

**Purpose:** Evidence Confidence Check

**Role:** Evidence Confidence Check is a agent step. Receives from Evidence Merge Gate. Passes to Issue Prioritization.

**Execution:** Reconcile cross-source evidence, flag conflicts, and score groundedness and confidence for each issue.

**Consumes from:**
- Evidence Merge Gate

**Feeds into:**
- Issue Prioritization

### Issue Prioritization

*custom* · **build**

Prioritize issues using current shelf conditions, recurrence signals, severity, and confidence.

*Rationale:* no catalog match

**Purpose:** Issue Prioritization

**Role:** Issue Prioritization is a custom step. Receives from Evidence Confidence Check. Passes to Executive Brief Generation.

**Execution:** Prioritize issues using current shelf conditions, recurrence signals, severity, and confidence.

**Consumes from:**
- Evidence Confidence Check

**Feeds into:**
- Executive Brief Generation

### Executive Brief Generation

*agent* · **build**

Generate the one-page narrative executive brief and corrective action recommendations for the manager.

*Rationale:* no catalog match

**Purpose:** Executive Brief Generation

**Role:** Executive Brief Generation is a agent step. Receives from Issue Prioritization. Passes to Manager Drill-down Output.

**Execution:** Generate the one-page narrative executive brief and corrective action recommendations for the manager.

**Consumes from:**
- Issue Prioritization

**Feeds into:**
- Manager Drill-down Output

### Manager Drill-down Output

*agent* · **build**

Assemble the final brief, prioritized issues, confidence notes, and side-by-side evidence views for delivery.

*Rationale:* no catalog match

**Purpose:** Manager Drill-down Output

**Role:** Manager Drill-down Output is a agent step. Receives from Executive Brief Generation. Passes to Workflow outcome.

**Execution:** Assemble the final brief, prioritized issues, confidence notes, and side-by-side evidence views for delivery.

**Consumes from:**
- Executive Brief Generation

**Feeds into:**
- Workflow outcome

## Reuse decisions

- **Upload Intake** — `build` → custom
  - no catalog match
- **Analysis Router** — `build` → custom
  - no catalog match
- **Document Brief Extractor** — `build` → custom
  - no catalog match
- **Shelf Image Quality Gate** — `build` → custom
  - no catalog match
- **Shelf Row Detection** — `build` → custom
  - no catalog match
- **Shelf Vision Analysis** — `build` → Planogram Vision Agent Chain
  - matched Planogram Vision Agent Chain
- **Findings Normalization** — `build` → custom
  - no catalog match
- **Evidence Merge Gate** — `build` → custom
  - no catalog match
- **Evidence Confidence Check** — `build` → custom
  - no catalog match
- **Issue Prioritization** — `build` → custom
  - no catalog match
- **Executive Brief Generation** — `build` → custom
  - no catalog match
- **Manager Drill-down Output** — `build` → custom
  - no catalog match

## Catalog matches

- **Planogram Vision Agent Chain** (`planogram_vision_agent_chain`) — score 0.99
  - Matched for: user_selected:visual_qa
  - AutoGen multi-agent vision chain that routes shelf queries to counting or generic understanding over row-crop images, then consolidates into a final natural-language shelf answer with reasoning.
- **Shelf Layout Compliance Vision Agent** (`shelf_layout_compliance_vision_agent`) — score 0.95
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Compares actual shelf photos against layout and agreement references; emits compliance rows and issues; deterministic scoring for placement, facings, pricing, layout match, and document clauses.
- **Competitive Shelf Intelligence Scorer** (`competitive_shelf_intelligence_scorer`) — score 0.95
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Computes Mars visibility, competitor pressure, promo and shelf position scores from vision-extracted brand facings using weighted shelf-level rules.
- **Shelf Understanding Agent** (`shelf_understanding_agent`) — score 0.81
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Answers descriptive, price, promotion, and stock-out questions from cropped row images and full shelf context.
- **Planogram Vision LLM Suite** (`planogram_vision_llm_suite`) — score 0.69
  - Matched for: Upload intake for report documents and shelf photos, Document text extraction an
  - Azure OpenAI vision functions for shelf-level product extraction, row counting, generic row description, daily KPI JSON, and final natural-language shelf answers after Roboflow cropping.
- **Roboflow Shelf Row Detector** (`roboflow-shelf-row-detector`) — score 0.42
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Segments shelf rows and detects product bounding boxes; writes cropped and annotated artifacts to Azure Blob for downstream vision LLMs.
- **Shelf Count Agent** (`shelf-count-agent`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Per-row brand-aware product counting from YOLO-annotated shelf images with confidence and structured visual reasoning.
- **Semantic Image Search & Validator** (`semantic_image_search_validator`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Embeds text queries with Azure AI Vision, retrieves similar shelf images from Azure AI Search, and filters results with GPT vision relevance scoring.
- **Roboflow Shelf Row Detector** (`roboflow-shelf-row-detector-v4`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Detects shelf rows as polygons, produces masked row crops and a polygon-overlay summary image.
- **Planogram Image Semantic Search** (`planogram_image_semantic_search`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Embeds shelf images with Azure AI Vision, vector-searches Azure AI Search by supermarket, and validates matches with GPT before returning blob hits.
- **Generation Prompt Author** (`generation-prompt-author-v2-1-0`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Azure vision+text agent that writes per-PDP-image-type multimodal prompts (or per-role directives) from reference photos and PDF excerpts before image generation.
- **KYC Risk Report Generator** (`kyc_risk_report_generator`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Generates downloadable Word (.docx) KYC risk assessment reports with KPI summary table, section scores, UBO details, override status, and AI reasoning narratives.
- **Roboflow Product Detector** (`roboflow_product_detector`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Runs YOLO product detection on each shelf row crop and writes annotated images with per-class counts.
- **Roboflow Product Detector** (`roboflow-product-detector-v3`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Runs YOLO product detection on each shelf row crop and writes annotated images with per-class counts.
- **Eryl Semantic RAG Agent Chain** (`eryl_semantic_rag_agent_chain`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Retrieves and answers from indexed retail policy and unstructured documents (Chocolate_Confectionery_Retail_Policy.docx, emails, guidelines) using Azure AI Search vector + semantic retrieval.
- **Amazon PDP Video Prompt Author** (`amazon-pdp-video-prompt-author-v2-1-0`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Produces a full Amazon PDP video ad script (reference block, compliance checklist, scenes, generation prompts) from product spec, guardrails, optional user script, and reference image.
- **GPT-4o Fashion Vision Analyzer** (`gpt_4o_fashion_vision_analyzer`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Analyzes person and garment reference images with a fashion/computational-photography system prompt and outputs a single precise image-editing instruction for virtual try-on, including layering, lighting, and full-frame preservation.
- **Generation Prompt Author** (`generation_prompt_author`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Azure vision+text agent that writes per-PDP-image-type multimodal prompts (or per-role directives) from reference photos and PDF excerpts before image generation.
- **Amazon PDP Video Prompt Author** (`amazon_pdp_video_prompt_author`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Produces a full Amazon PDP video ad script (reference block, compliance checklist, scenes, generation prompts) from product spec, guardrails, optional user script, and reference image.
- **Risk Reasoning Generator** (`risk_reasoning_generator`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Generates explainable AI narratives for the final risk score and each of four risk dimensions (Geography, Ownership, Industry, Sanctions) for UI display and DOCX reports.
- **Pipeline Intent Classifier** (`pipeline_intent_classifier`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Classifies each user question into vision_only, vision_then_unified, or unified_only and flags multi-shelf comparisons for SQL-only routing.
- **Quin SQL Agent Chain** (`quin_sql_agent_chain`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - AutoGen multi-agent chain that generates, executes, and critiques SQL Server queries on mars schema tables (Mars_Sales_Data, shelf_visit, retail_planogram_stocks, etc.) and returns structured sales/inventory insights.
- **Executive Action Card Writer** (`executive_action_card_writer`) — score 0.35
  - Matched for: Build an AI-powered Retail Store Performance and Shelf Audit Assistant for regio
  - Generates short action-oriented title and subtitle text for field executive promo, compliance, and recommended action cards.
- **Final Answer Consolidation Agent** (`final_answer_consolidation_agent`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Consolidates count and generic row-level analyses into a single natural-language answer based on task_type routing.
- **Email & Message Drafter** (`email_message_drafter`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Drafts professional outbound emails or chat messages from a brief, context, and tone, ready for human review before sending.
- **Answer Summarizer** (`answer_summarizer`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Condenses retrieved context, long documents, or transcripts into a concise grounded answer or summary, citing the supporting sources.
- **RAG Document Retriever** (`rag_document_retriever`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Retrieves the most relevant passages from an indexed document corpus for a user query, returning ranked chunks with source citations for grounded answering.
- **Mars Sales Order Simulator** (`mars_sales_order_simulator`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - CatBoost/sklearn regression predicts demand and realized sales under promotion, price, and stock constraints for Snickers/Mars/Twix SKUs.
- **Policy & Schema Validator** (`policy_schema_validator`) — score 0.35
  - Matched for: Help regional store managers quickly understand current shelf problems in the co
  - Validates extracted or submitted data against a configurable policy or schema, blocking incomplete or non-compliant payloads and listing the specific gaps.
- **Document Ingestion Agent** (`document_ingestion_agent`) — score 0.35
  - Matched for: Upload intake for report documents and shelf photos, Document text extraction an
  - Corporate KYC document ingestion entry point: accepts uploaded PDF, DOCX, TXT, or XLSX via file path or blob storage, detects file type, extracts and normalizes text (with OCR for scanned PDFs), chunks content, and emits document_id and text_content for downstream entity extraction and policy valida
- **Entity Extraction Agent** (`entity-extraction-agent`) — score 0.35
  - Matched for: Upload intake for report documents and shelf photos, Document text extraction an
  - Extracts entities, ownership relationships, and UBO registry records from uploaded corporate KYC documents into structured JSON for SQL persistence.
- **Azure AI Search Catalog Vector Retrieval** (`azure_ai_search_catalog_vector_retrieval`) — score 0.35
  - Matched for: Upload intake for report documents and shelf photos, Document text extraction an
  - Maintains and queries the vto-accessories HNSW vector index for cosine-similarity ranking of catalog items from text or image-derived embeddings.
- **GPT Image Relevance Validator** (`gpt_image_relevance_validator`) — score 0.35
  - Matched for: Upload intake for report documents and shelf photos, Document text extraction an
  - Strict vision-based filter that approves or rejects blob images against a user's semantic search query.
- **Azure AI Vision Catalog Embedder** (`azure_ai_vision_catalog_embedder`) — score 0.35
  - Matched for: Upload intake for report documents and shelf photos → Document text extraction a
  - Generates 1024-dimensional multimodal embeddings for catalog accessory images and natural-language search queries to power semantic garment discovery.
- **Executive Brief Generator** (`executive_brief_generator_agent_chain`) — score 0.18
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Turns an uploaded PDF into a one-page structured executive brief: PyMuPDF text extraction (no LLM) plus a Brief_Writer agent that returns title, key_points, executive_summary, and word_count grounded only in the source text.
- **GPT-4o Fashion Vision Analyzer** (`gpt4o_fashion_vision_analyzer`) — score 0.09
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Analyzes person and garment reference images with a fashion/computational-photography system prompt and outputs a single precise image-editing instruction for virtual try-on, including layering, lighting, and full-frame preservation.
- **Intake Gateway** (`intake_gateway`) — score 0.09
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Receives the user question, runs a deterministic Azure Content Safety-style pre-check (toxicity, PII, prompt injection), then an LLM Responsible AI agent for governance and business-rule blocking before routing or retrieval.
- **GraphRAG Index & Query Agent** (`graphrag_index_query_agent`) — score 0.08
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Indexes per-project KYC documents into a knowledge graph with entity/community extraction and embeddings; answers analyst questions via local, global, drift, or basic search methods.
- **Roboflow Shelf Row Detector** (`roboflow_shelf_row_detector_mars`) — score 0.08
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Segments shelf rows and detects product bounding boxes; writes cropped and annotated artifacts to Azure Blob for downstream vision LLMs.
- **Evidence Checker** (`evidence_checker`) — score 0.07
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Reconciles structured (SQL) and semantic (document) evidence, flags material conflicts, scores groundedness/completeness/faithfulness, and gates whether grounded answer synthesis may proceed.
- **Risk Scoring Agent** (`risk_scoring_agent`) — score 0.07
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Aggregates geography (30), ownership (30), regulatory/sanctions (20), and industry (20) scores into a final 0–100 risk score with hard override rules for FATF blacklist, sanctions, circular ownership, and PEP exposure.
- **Gemini Image Compositor** (`gemini_image_compositor`) — score 0.07
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Synthesizes the final virtual try-on image from person photo, accessory references, and the GPT-generated editing prompt using Gemini image output modality with aspect ratio matching and up to three retries.
- **Roboflow Shelf Row Detector** (`roboflow_shelf_row_detector_merchandising`) — score 0.06
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Detects shelf rows as polygons, produces masked row crops and a polygon-overlay summary image.
- **Final Answer Rewriter** (`final_answer_rewriter`) — score 0.06
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Post-processes combined vision+SQL+semantic draft answers into concise structured user-facing text without adding new facts.
- **PDP Compliance Checker** (`pdp_compliance_checker`) — score 0.05
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Vision LLM scores a generated PDP image against guardrails-only excerpts and returns pass/fail rules, warnings, suggestions, and compliance_score 0-100.
- **PDP Image Generator (Azure GPT Image)** (`pdp_image_generator_azure_gpt_image`) — score 0.04
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Azure images/edits endpoint generates PDP variants from first reference image and per-slot prompt.
- **Main Entity Inference Agent** (`main_entity_inference_agent`) — score 0.04
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Infers the primary corporate entity described in a project's latest document to center the radial ownership visualization.
- **PDP Image Generator (Gemini)** (`pdp_image_generator_gemini`) — score 0.04
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Generates Amazon-style PDP PNGs from reference images plus authored prompts, one variant per parallel task.
- **Intent Router** (`intent_router`) — score 0.04
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Classifies a user question into configurable analysis_type categories (SQL-based, Semantic-based, Both-dependent, Both-independent) for graph-level conditional dispatch. Emits analysis_type; does not execute Quin/Eryl handoffs.
- **UBO Analysis Engine** (`ubo_analysis_engine`) — score 0.04
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Computes UBO-specific risk score from ownership concentration, identification transparency, structural complexity, and PEP/sanctions/geo flags.
- **Sora Image-to-Video Generator** (`sora_image_to_video_generator`) — score 0.02
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Submits image-to-video jobs to Azure Sora, polls until complete, returns MP4 for PDP video ads.
- **ML Risk Classifier Stub** (`ml_risk_classifier_stub`) — score 0.02
  - Matched for: full_catalog:Build an AI-powered Retail Store Performance and Shelf Audit
  - Rule-based classifier that assigns Low/Medium/High risk tier from engineered geographic, industry, ownership, PEP, and sanctions features.

## Open questions

- Should DOCX extraction be handled by extending the Executive Brief Generator directly or by adding a separate preprocessing wrapper outside the graph?
- Is shelf placement compliance expected against a formal planogram reference, or only against visible heuristics from the current photos and prior report text?
- Should insufficient-evidence outputs terminate early for some images while still allowing partial analysis on the remaining usable shelf photos?

## Repository contents

| Path | Description |
|------|-------------|
| `README.md` | This overview |
| `workflow.json` | Full architecture graph, reuse decisions, and layout |
| `session.json` | Interview spec and session metadata (when available) |
| `agents/*.json` | Per-step scaffold files for implementation |

## Next steps

1. Review the architecture summary and agent steps above
2. Open `workflow.json` for the complete graph and reuse decisions
3. Implement each step under `agents/` using your runtime of choice
4. Wire integrations and HITL paths described in the requirements

---
*Generated by Agentic LaunchPad on 2026-08-05 11:20 UTC*