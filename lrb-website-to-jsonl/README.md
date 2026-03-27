# Hawaii LRB → RAG Pipeline

A two-notebook pipeline that scrapes the Hawaii Legislative Reference Bureau (LRB) website, downloads all linked PDFs, sends them through LlamaCloud for AI-powered text extraction, and produces a JSONL dataset ready for RAG ingestion.

---

## How the pipeline works

```
part1_scraper_tool_hawaii_lrb.ipynb
        ↓
  Visits 5 LRB pages
  Downloads 90 PDFs
  Saves page text
  Packages → pdfs.zip
        ↓
part2_document_to_jsonl.ipynb
        ↓
  Extracts ZIP
  Sends each PDF to LlamaCloud (agentic AI parsing)
  Writes → rag_dataset2.jsonl
```

You run Part 1 first, then Part 2. The handoff between them is `pdfs.zip` — Part 1 creates it, Part 2 reads it.

---

## Files at a glance

### Notebooks

| Notebook | What it does |
|----------|-------------|
| `part1_scraper_tool_hawaii_lrb.ipynb` | Scrapes LRB pages, downloads PDFs, produces `pdfs.zip` |
| `part2_document_to_jsonl.ipynb` | Sends PDFs through LlamaCloud, produces `rag_dataset2.jsonl` |

### Output files produced

| File | Created by | Contents |
|------|-----------|----------|
| `pdfs.zip` | Part 1 | All downloaded PDFs packaged for LlamaCloud |
| `scraped_output/page_text.jsonl` | Part 1 | Visible text from each scraped web page |
| `scraped_output/pdfs/` | Part 1 | Raw PDF files on disk |
| `scraped_output/document_log.csv` | Part 1 | URL + hash log for deduplication between runs |
| `rag_dataset2.jsonl` | Part 2 | Final output — one record per PDF page, AI-extracted text, ready for RAG |

---

## Requirements

**Python 3.10 or higher** and **Jupyter** (or JupyterLab / VS Code with Jupyter extension).

If you don't have Jupyter installed:
```bash
pip install notebook
```

You will also need a **LlamaCloud API key**. Get one free at [https://cloud.llamaindex.ai](https://cloud.llamaindex.ai).

---

## Setup

**1. Install dependencies**

Each notebook has an install cell at the top. Run it once when you first use the notebook, then skip it on future runs.

Part 1 installs:
```
requests, beautifulsoup4, lxml, pandas
```

Part 2 installs:
```
llama-cloud, nest-asyncio, python-dotenv
```

**2. Add your LlamaCloud API key**

Create a `.env` file in the same folder as the notebooks:
```
LLAMA_CLOUD_API_KEY=llx-your-key-here
```

The Part 2 notebook reads this automatically. If no `.env` file is found it falls back to the key hardcoded in the Config cell — you can paste it there directly if you prefer.

---

## How to run

### Part 1 — Scraper

1. Open `part1_scraper_tool_hawaii_lrb.ipynb`
2. Run the install cell once (skip on future runs)
3. Edit `TARGET_URLS` in the Config cell if you want to add or remove pages
4. Select `Kernel → Restart & Run All`

The notebook will work through each URL, print progress as it goes, save a checkpoint after every page, and finish by writing `pdfs.zip`. On a fresh run with 5 URLs it downloads 90 PDFs and takes around 5–10 minutes due to polite delays between requests.

**What you'll see when it finishes:**
```
✅ Created pdfs.zip — 90 PDFs, 25878.7 KB

Ready for LlamaCloud. Continue running the cells below.
```

### Part 2 — LlamaCloud extraction

1. Open `part2_document_to_jsonl.ipynb`
2. Confirm `ZIP_FILE_PATH = "pdfs.zip"` in the Config cell matches what Part 1 produced
3. Select `Kernel → Restart & Run All`

LlamaCloud will process each PDF page-by-page using its agentic AI parser. This step takes longer than Part 1 as each PDF is sent to the LlamaCloud API. When finished it writes `rag_dataset2.jsonl`.

**What you'll see when it finishes:**
```
✅ Wrote 1197 records → 'rag_dataset2.jsonl'
✅ All 1197 records are valid — JSONL is ready for RAG ingestion!
```

---

## Configuration

### Part 1 — Config cell settings

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `TARGET_URLS` | 5 LRB URLs | Pages to scrape — add or remove URLs here |
| `ZIP_FILE_PATH` | `pdfs.zip` | Name of the ZIP passed to Part 2 — keep in sync |
| `MIN_DELAY` / `MAX_DELAY` | 2.0 / 5.0s | Random wait between page fetches |
| `PDF_MIN_DELAY` / `PDF_MAX_DELAY` | 1.0 / 2.5s | Random wait between PDF downloads |
| `REQUEST_TIMEOUT` | 60s | How long before giving up on a slow request |
| `OUTPUT_DIR` | `scraped_output/` | Where all scraper output files are saved |

**Adding more URLs** — edit `TARGET_URLS` in the Config cell:
```python
TARGET_URLS = [
    "https://lrb.hawaii.gov/par/mission-history/",
    "https://lrb.hawaii.gov/par/current-legislature/",
    "https://lrb.hawaii.gov/par/hawaiis-legislature-and-government/hawaiis-legislative-branch/",
    "https://lrb.hawaii.gov/par/hawaiis-legislature-and-government/overview-of-branches-of-government/",
    "https://lrb.hawaii.gov/directory/",
]
```

### Part 2 — Config cell settings

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `ZIP_FILE_PATH` | `pdfs.zip` | ZIP file to read — must match Part 1 output |
| `OUTPUT_JSONL` | `rag_dataset2.jsonl` | Name of the final JSONL file |
| `PARSE_TIER` | `agentic` | LlamaCloud parsing quality — see tiers below |
| `SPLIT_BY` | `page` | `"page"` = one record per page, `"file"` = one record per PDF |

**LlamaCloud parse tiers** (set `PARSE_TIER` in the Config cell):

| Tier | Speed | Cost | Best for |
|------|-------|------|----------|
| `fast` | Fastest | Lowest | Simple text-only PDFs |
| `cost_effective` | Fast | Low | Most standard documents |
| `agentic` | Moderate | Medium | PDFs with tables, images, diagrams — **recommended** |
| `agentic_plus` | Slowest | Highest | Complex layouts, scanned documents |

---

## What the final JSONL looks like

Each line in `rag_dataset2.jsonl` is one page from one PDF:

```json
{
  "id": "e9dca4b07fc6c608e2b8fd2568168709",
  "title": "CITY AND COUNTY OF HONOLULU",
  "source_file": "pdfs/82f8f37c_Directory.pdf",
  "file_type": "pdf",
  "page_or_slide": 1,
  "text": "# CITY AND COUNTY OF HONOLULU\n\n## LEGISLATIVE BRANCH\n\nHonolulu Hale 530 South King Street...",
  "metadata": {
    "parse_tier": "agentic",
    "parsed_at": "2026-03-26T22:35:00Z"
  }
}
```

The `text` field contains AI-extracted markdown, including descriptions of any tables, images, or diagrams on the page.

---

## How deduplication works (Part 1)

On every run Part 1 checks whether each PDF has changed before downloading it:

1. Fetches the raw bytes of the PDF
2. Computes a SHA-256 fingerprint of those bytes
3. Compares against the hash stored in `scraped_output/document_log.csv` from the last run
4. If the hash matches — the file hasn't changed — it skips the download
5. If the hash is new or different, it downloads and saves the file

This makes the pipeline safe to run on a schedule. On repeat runs only new or updated PDFs are downloaded, and only those need to go through LlamaCloud again.

**To force a full re-scrape from scratch:** delete `scraped_output/document_log.csv` before running Part 1.

---

## Page text vs PDF text

The pipeline captures two types of content:

**Page text** (`scraped_output/page_text.jsonl`) — the visible text written directly on each LRB web page, such as the Mission & History page or the Current Legislature overview. This is saved by Part 1 and is separate from the PDFs. There are 5 records, one per URL.

**PDF text** (`rag_dataset2.jsonl`) — the text extracted from inside each PDF by LlamaCloud. This is the main output with 1,197 records across 90 PDFs.

If you're building a RAG system you'll likely want to combine both files so your assistant can answer questions about both the web page content and the PDF documents.

---

## Troubleshooting

**Part 1 finishes but `pdfs.zip` is empty or missing**
Try increasing `REQUEST_TIMEOUT` in the Config cell and re-running.

**Part 2 fails with an authentication error**
Your LlamaCloud API key is missing or incorrect. Check your `.env` file or the hardcoded key in the Part 2 Config cell.

**Part 2 is very slow**
This is normal — LlamaCloud processes each PDF page through an AI model. 90 PDFs with ~1,200 pages total takes time. The `agentic` tier is slower than `fast` or `cost_effective`. Switch to a lower tier in the Config cell if speed matters more than quality for your use case.

**Some records in `rag_dataset2.jsonl` have empty text**
Those PDFs may be scanned images. The `agentic` and `agentic_plus` tiers handle scans via OCR — if you're on a lower tier, switch to `agentic`.

**Kernel dies mid-run in Part 1**
Partial results are not lost — the hash log is saved after every page. Restart the kernel, skip the install cell, and run all cells again. Already-downloaded PDFs will be skipped automatically.

**I want to re-run Part 2 on only the new PDFs**
In Part 1's zip cell, `all_pdf_paths` only contains PDFs that were newly downloaded or changed. If you re-run Part 1 after the site updates, the ZIP it produces will only contain changed files — pass that to Part 2 to avoid re-processing everything.
