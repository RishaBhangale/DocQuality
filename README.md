# DocQuality — AI Data Quality Management

A full-stack application for evaluating document quality using deterministic metrics and LLM-powered semantic analysis.

Supports **12 file types** across **4 specialized document categories** with 6 core metrics and 14 type-specific metrics.

---

## Prerequisites

- **Python** 3.10+ 
- **Node.js** 18+ and **npm**
- (Optional) **Tesseract OCR** — for image-based document text extraction

---

## Project Structure

```
DocQuality/
├── backend/
│   ├── app/
│   │   ├── config.py              # Settings & metric weights
│   │   ├── main.py                # FastAPI entry point
│   │   ├── models/
│   │   │   ├── db_models.py       # SQLAlchemy ORM models
│   │   │   └── schemas.py         # Pydantic request/response schemas
│   │   └── services/
│   │       ├── document_service.py         # Text extraction (12 formats)
│   │       ├── evaluation_orchestrator.py  # Pipeline coordinator
│   │       ├── insight_engine.py           # Deterministic AI insights
│   │       ├── llm_service.py              # Azure/OpenAI LLM integration
│   │       ├── rule_engine.py              # Core metric calculations
│   │       ├── scoring_engine.py           # Score blending & weighting
│   │       ├── type_specific_engine.py     # Document-type-specific metrics
│   │       └── visualization_service.py    # Dash/Plotly dashboard
│   ├── requirements.txt
│   └── .env                       # API keys (create this)
└── frontend/
    ├── src/app/
    │   ├── App.tsx
    │   └── components/
    │       ├── TypeSpecificMetrics.tsx   # Type-specific metric cards
    │       └── ...                      # Other UI components
    └── package.json
```

---

## Setup & Run

### 1. Backend Setup

```bash
# Navigate to backend
cd DocQuality/backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file (see below)
```

#### `.env` file (create in `backend/` directory):

```env
# LLM Configuration (Azure Foundry / OpenAI)
AZURE_INFERENCE_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_INFERENCE_CREDENTIAL=your-api-key
MODEL_NAME=gpt-4

# Optional: Tesseract OCR path (Windows)
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

> **Note:** The application works without LLM configuration — it will fall back to deterministic-only evaluation with the local insight engine.

#### Start the backend:

```bash
# From DocQuality/backend/
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
API docs at `http://localhost:8000/docs`.

---

### 2. Frontend Setup

```bash
# Navigate to frontend
cd DocQuality/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173` (default Vite port).

---

### 3. First Run

1. **Delete any existing database** (required after schema changes):  
   ```bash
   rm DocQuality/backend/document_quality.db
   ```
2. Start the backend (`uvicorn`)
3. Start the frontend (`npm run dev`)
4. Open `http://localhost:5173` in your browser
5. Upload a document to evaluate

---

## Supported File Types

| Format | Extension | Extraction Method |
|--------|-----------|-------------------|
| PDF | `.pdf` | pdfplumber + OCR fallback |
| Word | `.docx` | python-docx |
| JSON | `.json` | json parser |
| CSV | `.csv` | csv reader |
| Plain Text | `.txt` | UTF-8 decode |
| XML | `.xml` | ElementTree |
| HTML | `.html`, `.htm` | BeautifulSoup |
| Email | `.eml` | email parser |
| Images | `.png`, `.jpg` | Tesseract OCR |

---

## Metrics

### Core Metrics (all document types)
| Metric | Description |
|--------|-------------|
| Completeness | Required field presence |
| Validity | Format and pattern validation |
| Consistency | Cross-field logical alignment |
| Accuracy | Value verification against source |
| Timeliness | Date freshness and expiry |
| Uniqueness | Duplicate detection |

### Type-Specific Metrics

| Document Type | Metrics |
|---------------|---------|
| **Contract** | Clause Completeness, Signature Presence, Metadata Completeness, Risk Clause Detection |
| **Invoice** | Field Completeness, OCR Confidence, Amount Consistency |
| **JSON** | Schema Compliance, Type Validation, Cross-Field Consistency, Schema Drift Rate |
| **Social Media** | Language Consistency, Offensive Rate, Spam Detection |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/evaluate` | Upload and evaluate a document |
| `GET` | `/api/evaluations/{id}` | Get evaluation by ID |
| `GET` | `/api/evaluations` | List all evaluations |
| `GET` | `/dashboard` | Plotly dashboard |
