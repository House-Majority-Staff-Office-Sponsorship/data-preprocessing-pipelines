#!/usr/bin/env python
# coding: utf-8

# # Hawaii LRB Scraper + LlamaCloud Pipeline
# 
# **This notebook has two parts:**
# 
# 1. **Scraper (cells below)** — visits the Hawaii LRB pages, downloads all linked PDFs, saves page text, and packages the PDFs into `pdfs.zip` ready for LlamaCloud
# 2. **LlamaCloud pipeline (part 2 of notebook)** — takes `pdfs.zip`, sends each PDF through LlamaCloud for AI text extraction, and writes `rag_dataset2.jsonl`
# 
# **Run order:** run all scraper cells top to bottom first, then continue into the LlamaCloud cells.
# 
# ---
# 
# **Scraper output files:**
# 
# | File | Contents |
# |------|----------|
# | `pdfs.zip` | All downloaded PDFs — this is what the LlamaCloud cells below expect |
# | `scraped_output/page_text.jsonl` | Visible text scraped from each target web page |
# | `scraped_output/document_log.csv` | URL + hash log — skips unchanged PDFs on future runs |
# | `scraped_output/pdfs/` | The raw PDF files on disk |
# | `scraper_audit.log` | Timestamped log of every request, download, and skip |

# ## Scraper — Step 1: Install dependencies
# Run this cell once. Skip it on future runs.

# In[ ]:


get_ipython().run_line_magic('pip', 'install requests beautifulsoup4 lxml pandas')


# ## Scraper — Step 2: Config
# Edit `TARGET_URLS` to add or remove pages. Everything else can stay as-is.

# In[7]:


from pathlib import Path

# ── URLs to scrape ────────────────────────────────────────────────────────────
TARGET_URLS = [
    "https://lrb.hawaii.gov/par/mission-history/",
    "https://lrb.hawaii.gov/par/current-legislature/",
    "https://lrb.hawaii.gov/par/hawaiis-legislature-and-government/hawaiis-legislative-branch/",
    "https://lrb.hawaii.gov/par/hawaiis-legislature-and-government/overview-of-branches-of-government/",
    "https://lrb.hawaii.gov/directory/",
]

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUT_DIR    = Path("scraped_output")
PDF_DIR       = OUTPUT_DIR / "pdfs"
CSV_LOG       = OUTPUT_DIR / "document_log.csv"
PAGE_JSONL    = OUTPUT_DIR / "page_text.jsonl"  # page text (no PDFs)
ZIP_FILE_PATH = "pdfs.zip"   # ← this is what the LlamaCloud cells below expect

OUTPUT_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

# ── Politeness settings ───────────────────────────────────────────────────────
MIN_DELAY       = 2.0   # seconds between page fetches
MAX_DELAY       = 5.0
PDF_MIN_DELAY   = 1.0   # seconds between PDF downloads
PDF_MAX_DELAY   = 2.5
REQUEST_TIMEOUT = 60

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "HawaiiLegResearch/1.0"
)

print(f"Target URLs  : {len(TARGET_URLS)}")
print(f"PDF folder   : {PDF_DIR}")
print(f"ZIP output   : {ZIP_FILE_PATH}")
print(f"Page text    : {PAGE_JSONL}")
print(f"Hash log     : {CSV_LOG}")


# ## Scraper — Step 3: Imports and helpers

# In[8]:


import hashlib
import json
import logging
import random
import time
import zipfile
from datetime import datetime
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Utility functions ─────────────────────────────────────────────────────────
def polite_sleep(min_s=MIN_DELAY, max_s=MAX_DELAY):
    time.sleep(random.uniform(min_s, max_s))

def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_hash_log() -> pd.DataFrame:
    if CSV_LOG.exists():
        df = pd.read_csv(CSV_LOG)
        log.info("Loaded hash log: %d records", len(df))
        return df
    return pd.DataFrame(columns=["url", "hash"])

def save_hash_log(df: pd.DataFrame):
    df.to_csv(CSV_LOG, index=False)

def is_changed(df: pd.DataFrame, url: str, new_hash: str) -> bool:
    row = df[df["url"] == url]
    return row.empty or row.iloc[0]["hash"] != new_hash

def update_hash_log(df: pd.DataFrame, url: str, new_hash: str) -> pd.DataFrame:
    if df[df["url"] == url].empty:
        df = pd.concat([df, pd.DataFrame([{"url": url, "hash": new_hash}])], ignore_index=True)
    else:
        df.loc[df["url"] == url, "hash"] = new_hash
    return df

print("✅ Helpers loaded.")


# ## Scraper — Step 4: Fetch and parse pages

# In[9]:


def fetch_html(url: str, session: requests.Session) -> str | None:
    try:
        log.info("GET %s", url)
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.error("Failed to fetch %s: %s", url, e)
        return None


def parse_page(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("div", {"id": "content"})
        or soup.find("body")
    )
    text_content = main.get_text(separator="\n", strip=True) if main else ""

    # Collect PDF links with their label text
    seen = {}
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if full.lower().endswith(".pdf"):
            seen.setdefault(full, a.get_text(strip=True) or "Untitled")
    pdf_links = [{"url": u, "label": l} for u, l in seen.items()]

    return {"title": title, "text_content": text_content, "pdf_links": pdf_links}


print("✅ Fetch and parse functions loaded.")


# ## Scraper — Step 5: Download PDFs (with deduplication)

# In[10]:


def download_pdf(
    pdf_url: str,
    label: str,
    session: requests.Session,
    hash_df: pd.DataFrame,
) -> tuple[Path | None, pd.DataFrame]:
    """
    Download a PDF only if it is new or its content has changed.
    Returns (local_path | None, updated hash_df).
    Text extraction is intentionally NOT done here — LlamaCloud handles that.
    """
    try:
        log.info("Fetching PDF: %s", pdf_url)
        r = session.get(pdf_url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        content  = r.content
        new_hash = sha256_of_bytes(content)

        short = new_hash[:8]
        clean = "".join(c for c in label if c.isalnum() or c in " _")[:40].strip()
        local_path = PDF_DIR / f"{short}_{clean}.pdf"

        if not is_changed(hash_df, pdf_url, new_hash):
            log.info("No change — skipping: %s", local_path.name)
            return local_path, hash_df  # file already on disk, nothing to do

        with open(local_path, "wb") as f:
            f.write(content)
        log.info("Saved → %s (%.1f KB)", local_path.name, local_path.stat().st_size / 1024)

        hash_df = update_hash_log(hash_df, pdf_url, new_hash)
        polite_sleep(PDF_MIN_DELAY, PDF_MAX_DELAY)
        return local_path, hash_df

    except Exception as e:
        log.error("PDF download failed %s: %s", pdf_url, e)
        return None, hash_df


print("✅ PDF download function loaded.")


# ## Scraper — Step 6: Run the scraper

# In[11]:


run_time   = datetime.now().isoformat()
session    = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})
hash_df    = load_hash_log()

all_pdf_paths  = []   # every PDF path collected across all pages
page_records   = []   # one record per page for page_text.jsonl

for i, url in enumerate(TARGET_URLS, 1):
    log.info("── [%d/%d] %s", i, len(TARGET_URLS), url)

    html = fetch_html(url, session)
    if not html:
        log.error("Skipping %s — could not fetch page", url)
        continue

    parsed = parse_page(html, url)

    # Save page text record
    page_records.append({
        "type":         "page",
        "url":          url,
        "title":        parsed["title"],
        "page_text":    parsed["text_content"],
        "content_hash": sha256_of_bytes(parsed["text_content"].encode()),
        "scraped_at":   run_time,
    })

    log.info("Found %d PDF links on %s", len(parsed["pdf_links"]), url)

    for pdf_item in parsed["pdf_links"]:
        local_path, hash_df = download_pdf(
            pdf_item["url"], pdf_item["label"], session, hash_df
        )
        if local_path:
            all_pdf_paths.append(local_path)

    # Save hash log after every page so a crash loses at most one page
    save_hash_log(hash_df)

    if i < len(TARGET_URLS):
        polite_sleep()

# Write page text JSONL
with open(PAGE_JSONL, "w", encoding="utf-8") as f:
    for rec in page_records:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

log.info("Page text saved → %s (%d records)", PAGE_JSONL, len(page_records))
log.info("Total PDFs on disk: %d", len(all_pdf_paths))


# ## Scraper — Step 7: Package PDFs into pdfs.zip
# 
# This creates `pdfs.zip` in the format the LlamaCloud cells below expect —
# all PDFs inside a `pdfs/` folder inside the ZIP.

# In[12]:


with zipfile.ZipFile(ZIP_FILE_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for pdf_path in all_pdf_paths:
        # Store as pdfs/<filename> to match what the LlamaCloud cells expect
        zf.write(pdf_path, arcname=f"pdfs/{pdf_path.name}")

zip_size_kb = Path(ZIP_FILE_PATH).stat().st_size / 1024
print(f"✅ Created {ZIP_FILE_PATH} — {len(all_pdf_paths)} PDFs, {zip_size_kb:.1f} KB")
print(f"\nReady for LlamaCloud. Continue running the cells below.")


# In[ ]:




