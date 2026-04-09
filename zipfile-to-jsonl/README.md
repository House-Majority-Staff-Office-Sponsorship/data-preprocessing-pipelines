# ZIP → JSONL Pipeline for RAG Ingestion

This notebook converts a ZIP archive of training documents into a structured JSONL file ready to feed into a Retrieval-Augmented Generation (RAG) model. It uses [LlamaCloud](https://cloud.llamaindex.ai) to parse and extract text — including AI-generated descriptions of images, diagrams, and charts embedded in documents.

---

## What It Does

1. **Extracts** a ZIP file containing your training documents
2. **Uploads and parses** each file using the LlamaCloud API (`agentic` tier)
3. **Splits** each document into one record per page or slide
4. **Writes** all records to a `.jsonl` file, one JSON object per line
5. **Validates** the output to confirm all records are complete and well-formed

Supported file types: `.pdf`, `.pptx`, `.ppt`, `.docx`, `.doc`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`

For images and diagrams — whether standalone files or embedded inside documents — the `agentic` parser generates a natural-language description so visual content is searchable in the RAG model.

---

## Setup

### 1. Install dependencies

```bash
pip install llama-cloud nest-asyncio python-dotenv jupyter
```

> **Note:** Make sure you are using `llama-cloud` version `1.6.0` or higher.
> Check your version with `pip show llama-cloud` and upgrade if needed:
> ```bash
> pip install --upgrade llama-cloud
> ```

### 2. Get a LlamaCloud API key

Sign up at [https://cloud.llamaindex.ai](https://cloud.llamaindex.ai) and copy your API key.

### 3. Set your API key

Create a `.env` file in the same folder as the notebook:

```
LLAMA_CLOUD_API_KEY=llx-your-key-here
```

Or paste it directly into the `LLAMA_API_KEY` line in the Configuration cell.

### 4. Place your ZIP file

Put your ZIP file in the same folder as the notebook. The default expected filename is:

```
training-files.zip
```

You can change this in the Configuration cell.

---

## How to Run

Open the notebook and run all cells top to bottom in order:

```
Kernel → Restart & Run All
```

> **Important:** Always use Restart & Run All rather than running individual cells out of order. The notebook relies on variables being set in sequence — running cells out of order can cause errors or stale data.

### Cell order

| Step | What it does |
|---|---|
| Imports | Loads all libraries |
| Configuration | Set your ZIP path, API key, and parsing settings |
| Step 1 | Extracts the ZIP and lists all supported files |
| Step 2 | Defines parsing helpers |
| Step 3 | Uploads and parses all files (runs concurrently, max 5 at a time) |
| Retry cell | Automatically re-parses any failed files using the `agentic_plus` tier |
| Step 4 | Writes all records to `rag_dataset.jsonl` |
| Step 5 | Previews records and validates the output file |

---

## Configuration Options

All settings are in the **Configuration** cell at the top of the notebook.

| Setting | Default | Description |
|---|---|---|
| `ZIP_FILE_PATH` | `training-files.zip` | Path to your input ZIP file |
| `OUTPUT_JSONL` | `rag_dataset.jsonl` | Path for the output JSONL file |
| `PARSE_TIER` | `agentic` | Parsing quality — see tiers below |
| `PARSE_VERSION` | `latest` | API version to use |
| `SPLIT_BY` | `page` | `"page"` = one record per page/slide; `"file"` = one record per file |
| `MAX_CONCURRENT` | `5` | Max files parsed at the same time |

### Parsing tiers

| Tier | Speed | Best for |
|---|---|---|
| `fast` | Fastest | Simple text-only documents |
| `cost_effective` | Fast | Standard documents, lower cost |
| `agentic` | Moderate | **Recommended** — handles images, diagrams, complex layouts |
| `agentic_plus` | Slowest | Used automatically as a fallback for files that fail on `agentic` |

---

## Output — JSONL Schema

The output file contains one JSON record per line. Each record has the following fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique ID (MD5 hash of filename + page number) — stable across re-runs |
| `title` | string | First heading found on the page, or the filename if no heading exists |
| `source_file` | string | Relative path of the original file inside the ZIP |
| `file_type` | string | File extension — `pdf`, `pptx`, `docx`, `png`, etc. |
| `page_or_slide` | integer or null | 1-indexed page/slide number (`null` when `SPLIT_BY="file"`) |
| `text` | string | Extracted text in Markdown format; images described inline |
| `metadata` | object | `parse_tier` used and `parsed_at` UTC timestamp |

### Example record

```json
{
  "id": "cf41afb4c8cc5c4935f31d31d5f1b6c5",
  "title": "House of Representatives",
  "source_file": "UH Capstone Training Files 2-16-26/HSAA Operations and General Responsibilities.pdf",
  "file_type": "pdf",
  "page_or_slide": 1,
  "text": "# House of Representatives\n## Operations and General Responsibilities\n\n![Seal of the State of Hawaii](image)\n\n1. Keys — if locked out, call HSAA...",
  "metadata": {
    "parse_tier": "agentic",
    "parsed_at": "2026-03-19T12:00:00+00:00"
  }
}
```

---

## Troubleshooting

**`ImportError: cannot import name 'AsyncLlamaCloud'`**
Your `llama-cloud` package is out of date. Run:
```bash
pip install --upgrade llama-cloud
```

**`Client Closed Request` errors**
The API dropped the connection under load. The notebook automatically retries failed files up to 3 times. If a file keeps failing, the retry cell will re-attempt it using the `agentic_plus` tier. If it still fails, the PDF may be corrupted or password-protected.

**Variables out of sync / wrong file counts**
This happens when cells are run out of order. Always use **Kernel → Restart & Run All** to start fresh.

**The same file fails every run**
Try opening the file manually to confirm it isn't password-protected or corrupted. If it opens fine, try changing `PARSE_TIER` to `"agentic_plus"` in the Configuration cell and re-running.

---

## Output Stats (Current Run)

| Metric | Value |
|---|---|
| Total records | 919 |
| PDF records | 804 |
| PPTX records | 105 |
| DOCX records | 10 |
| Total characters | 1,375,501 |
| Avg chars per record | 1,496 |
| Output file size | ~1.6 MB |


```

