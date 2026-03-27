# LRB Website Resources to JSONL File

A resumable web scraper for the Hawaii Legislative Reference Bureau (LRB) Public Access Room website. It collects visible page text and PDF documents from a list of target URLs, extracts the text content from PDFs, and saves everything in formats ready for search or AI use (RAG pipelines, vector databases).

Built and run as a Jupyter Notebook (`.ipynb`).

---

## What it does

- Scrapes visible text from each target page
- Finds and downloads all linked PDF files
- Extracts text from inside each PDF using pdfplumber
- Skips PDFs that haven't changed since the last run (SHA-256 deduplication)
- Saves a RAG-ready `.jsonl` file with one record per page and one per PDF
- Writes a full JSON dump and a timestamped audit log
- Waits politely between requests to avoid overloading the server

---

## Output files

| File | What's in it |
|------|-------------|
| `scraped_output/rag_metadata.jsonl` | One JSON record per page and per PDF — the main output for RAG/AI use |
| `scraped_output/results.json` | Full nested dump of everything including per-page PDF text breakdown |
| `scraped_output/document_log.csv` | URL + SHA-256 hash log used for deduplication between runs |
| `scraped_output/pdfs/` | Folder containing all downloaded PDF files |
| `scraper_audit.log` | Timestamped log of every request, download, skip, and error |

### What a record looks like in `rag_metadata.jsonl`

A page record (site content with no PDF):
```json
{
  "type": "page",
  "url": "https://lrb.hawaii.gov/par/mission-history/",
  "title": "Mission & History - LRB Public Access Room",
  "page_text": "Our Mission\nThe Public Access Room (PAR) provides...",
  "content_hash": "a3f9c1b2...",
  "last_synced": "2026-03-26T10:00:00",
  "source_page": "https://lrb.hawaii.gov/par/mission-history/"
}
```

A PDF record:
```json
{
  "type": "pdf",
  "url": "https://lrb.hawaii.gov/par/some-document.pdf",
  "title": "Hawaii Legislative Branch Overview",
  "local_path": "scraped_output/pdfs/a3f9c1b2_Hawaii Legislative Branch Overview.pdf",
  "content_hash": "b7e2d4f1...",
  "last_synced": "2026-03-26T10:00:00",
  "changed": true,
  "pdf_text": "Full extracted text from inside the PDF...",
  "page_count": 12,
  "source_page": "https://lrb.hawaii.gov/par/current-legislature/"
}
```

---

## Requirements

**Python 3.10 or higher**, with Jupyter installed.

If you don't have Jupyter yet:
```bash
pip install notebook
```

---

## Installation

Open the notebook and run the first cell, which installs all dependencies:
```python
%pip install requests beautifulsoup4 lxml pandas pdfplumber
```

If you need Selenium mode (see below), uncomment this line in the same cell:
```python
%pip install selenium webdriver-manager
```

You only need to run the install cell once. After that you can skip it on future runs.

---

## How to run it

1. Open `scraper.ipynb` in Jupyter (or VS Code, or JupyterLab)
2. Run the install cell once if it's your first time
3. Edit the **Config** cell if you want to change URLs or settings
4. Use **Run All** (`Kernel → Restart & Run All`) to run the full scraper from top to bottom

The notebook will work through each URL, print progress as it goes, save a checkpoint after every page, and display a summary at the end.

To run it again later, just use **Run All** again. It will load the existing hash log and skip any PDFs that haven't changed.

---

## Notebook structure

The notebook is organised into clearly labelled cells in this order:

| Cell | What it contains |
|------|-----------------|
| Title + description | Overview of what the notebook does |
| Install dependencies | `%pip install` commands — run once |
| Imports | All library imports |
| Config | `TARGET_URLS`, `USE_SELENIUM`, delays, paths — **edit this cell to customise** |
| Logging setup | Configures the audit log file and console output |
| Utility functions | Hashing, sleep, hash log helpers |
| Fetch functions | `requests` and optional Selenium page fetchers |
| Parse function | HTML parsing and PDF link extraction |
| PDF functions | Download, dedup, and text extraction |
| Scrape function | Orchestrates one full page scrape |
| Save functions | Writes `.jsonl`, `.json`, and `.csv` outputs |
| Run | Loops through all URLs and runs the scraper |

---

## Configuration

All settings are in the **Config** cell near the top of the notebook:

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `TARGET_URLS` | 5 LRB URLs | The pages to scrape — add or remove URLs here |
| `USE_SELENIUM` | `False` | Set to `True` if the site requires JavaScript to render content |
| `MIN_DELAY` / `MAX_DELAY` | 2.0 / 5.0s | Random wait between page fetches |
| `PDF_MIN_DELAY` / `PDF_MAX_DELAY` | 1.0 / 2.5s | Random wait between PDF downloads |
| `REQUEST_TIMEOUT` | 60s | How long to wait before giving up on a request |
| `OUTPUT_DIR` | `scraped_output/` | Where all output files are saved |

### Adding more URLs

In the Config cell, add URLs to the `TARGET_URLS` list:
```python
TARGET_URLS = [
    "https://lrb.hawaii.gov/par/mission-history/",
    "https://lrb.hawaii.gov/your-new-url/",   # ← add here
]
```

Then run all cells again.

---

## Do I need Selenium?

**No, not for lrb.hawaii.gov.** This is a WordPress site that renders its content server-side, meaning all text and links are present in the raw HTML. The plain `requests` approach is faster, lighter, and produces identical results.

You can verify this by running this snippet in a new notebook cell:
```python
import requests
from bs4 import BeautifulSoup

r = requests.get("https://lrb.hawaii.gov/par/mission-history/")
soup = BeautifulSoup(r.text, "lxml")
print(soup.find("main"))  # if this returns real content, Selenium is not needed
```

Only set `USE_SELENIUM = True` in the Config cell if the `<main>` tag comes back empty or the page relies on JavaScript to load its content.

---

## How deduplication works

On every run the scraper:
1. Downloads the raw bytes of each PDF it finds
2. Computes a SHA-256 fingerprint of those bytes
3. Compares it against the hash stored in `document_log.csv` from the last run
4. If the hash matches — the file is identical — it skips the download entirely
5. If the hash is different or the URL is new, it downloads and saves the file

This means the notebook is safe to run repeatedly. It will only do real work when something on the site has actually changed.

---

## PDF text extraction

Text is extracted using [pdfplumber](https://github.com/jsvine/pdfplumber), which reads the text layer embedded in a PDF.

**This works for:** PDFs created digitally — government reports, exported Word documents, official publications.

**This does not work for:** Scanned PDFs (images of physical pages). If a PDF was created by scanning a paper document, pdfplumber will return empty text. You would need an OCR tool such as Tesseract to handle those.

You can tell if a PDF was scanned by trying to select text in it with your cursor in a PDF viewer — if you can't select anything, it's a scan.

---

## Troubleshooting

**A cell crashes immediately with a Chrome error**
You have `USE_SELENIUM = True` in the Config cell but Chrome or ChromeDriver is not installed. Either install them or set `USE_SELENIUM = False`.

**PDFs are downloading but `pdf_text` is empty**
The PDFs are likely scanned images. pdfplumber cannot extract text from scans — see the PDF text extraction section above.

**A page returns an error in results.json**
Check `scraper_audit.log` for the exact error message. Common causes are network timeouts (try increasing `REQUEST_TIMEOUT` in the Config cell) or the URL returning a non-200 status code.

**I want to re-scrape everything from scratch**
Delete `scraped_output/document_log.csv` then run the notebook again. The scraper will treat every PDF as new and re-download everything.

**Kernel dies mid-run**
Partial results are saved after every page, so you won't lose completed work. Just restart the kernel, skip the install cell, and run all cells again — it will pick up where it left off thanks to the hash log.
