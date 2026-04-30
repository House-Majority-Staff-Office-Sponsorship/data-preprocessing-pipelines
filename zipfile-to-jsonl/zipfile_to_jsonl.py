#!/usr/bin/env python
# coding: utf-8

# # ZIP → JSONL Pipeline (llama-cloud SDK)
# 
# Converts a ZIP archive of documents (PDF, PPTX, DOCX) and images into a JSONL file ready for RAG ingestion using the `llama-cloud` `AsyncLlamaCloud` client.
# 
# **Each JSONL record contains:**
# - `id` – stable MD5 hash of `source_file::page`
# - `title` – first heading found, or filename stem
# - `source_file` – original filename inside the ZIP
# - `file_type` – extension
# - `page_or_slide` – page number (when `SPLIT_BY="page"`)
# - `text` – extracted / AI-described markdown text
# - `metadata` – extra fields for filtering in your vector store
# 
# ---
# ### Requirements
# ```
# pip install llama-cloud nest-asyncio python-dotenv jupyter
# ```
# Get API key at **https://cloud.llamaindex.ai**

# In[ ]:


import os
import zipfile
import json
import asyncio
import hashlib
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  # walks up from cwd to find .env at repo root

import nest_asyncio
nest_asyncio.apply()   # allow asyncio.run() inside Jupyter

from dotenv import load_dotenv
load_dotenv()

from llama_cloud import AsyncLlamaCloud

print("✅ Imports OK")


# ## Configuration

# In[ ]:


# ── Paths ─────────────────────────────────────────────────────────────────────
ZIP_FILE_PATH = "training-files.zip"       # ← path to ZIP file with training docs
OUTPUT_JSONL  = "rag_dataset.jsonl"   # ← output JSONL path
EXTRACT_DIR   = tempfile.mkdtemp(prefix="zip_extracted_")

# ── LlamaCloud credentials ────────────────────────────────────────────────────
LLAMA_API_KEY = os.environ["LLAMA_CLOUD_API_KEY"]

# ── Parsing settings ──────────────────────────────────────────────────────────
# Tier options: "fast" | "cost_effective" | "agentic" | "agentic_plus"
# "agentic" is recommended — multimodal AI describes images/diagrams inline.
PARSE_TIER    = "agentic"
PARSE_VERSION = "latest"

# Splitting strategy:
#   "page" → one JSONL record per page/slide  (best granularity for RAG)
#   "file" → one JSONL record per file        (simpler, larger chunks)
SPLIT_BY = "page"

# ── Supported file types ──────────────────────────────────────────────────────
DOC_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".docx", ".doc"}
IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
ALL_SUPPORTED  = DOC_EXTENSIONS | IMG_EXTENSIONS

print(f"ZIP        : {ZIP_FILE_PATH}")
print(f"Output     : {OUTPUT_JSONL}")
print(f"Tier       : {PARSE_TIER} / {PARSE_VERSION}")
print(f"Split by   : {SPLIT_BY}")
print(f"Temp dir   : {EXTRACT_DIR}")


# ## Step 1 — Extract the ZIP

# In[10]:


def extract_zip(zip_path: str, dest_dir: str) -> list[Path]:
    """Unzip and return paths of all supported files."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    all_files = list(Path(dest_dir).rglob("*"))
    supported = [
        f for f in all_files
        if f.is_file()
        and f.suffix.lower() in ALL_SUPPORTED
        and not f.name.startswith(".")   # skip macOS __MACOSX junk
    ]

    print(f"Found {len(all_files)} total files → {len(supported)} supported:")
    for f in supported:
        print(f"  ✔  {f.relative_to(dest_dir)}")
    return supported


supported_files = extract_zip(ZIP_FILE_PATH, EXTRACT_DIR)


# In[11]:


all_items = list(Path(EXTRACT_DIR).rglob("*"))
dirs  = [f for f in all_items if f.is_dir()]
files = [f for f in all_items if f.is_file() and not f.name.startswith(".")]

print(f"Directories : {len(dirs)}")
print(f"Files       : {len(files)}")
print(f"Supported   : {len(supported_files)}")
print(f"Unsupported : {len(files) - len(supported_files)}")

if len(files) - len(supported_files) > 0:
    unsupported = [f for f in files if f not in supported_files and not f.name.startswith(".")]
    for f in unsupported:
        print(f"  skipped: {f.name}")


# ## Step 2 — Upload & parse with `AsyncLlamaCloud`
# 
# The `agentic` tier uses multimodal AI that:
# - Extracts structured text from PDFs, PPTX, DOCX with full layout awareness  
# - Generates natural-language descriptions for embedded images, charts, diagrams, and slides  
# - Returns results as clean Markdown (`markdown_full`) and plain text (`text_full`)

# In[4]:


def extract_title_from_markdown(md: str) -> str | None:
    """Return the first H1 or H2 heading found in a markdown string."""
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("## "):
            return line[3:].strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def make_id(source_file: str, page: int) -> str:
    """Stable MD5 identifier for a source_file + page combo."""
    return hashlib.md5(f"{source_file}::{page}".encode()).hexdigest()


def split_markdown_by_page(markdown_full: str) -> list[str]:
    """
    LlamaParse separates pages with a horizontal rule (---) in its markdown.
    Split on that delimiter to get per-page chunks.
    Falls back to the whole document as one chunk if no delimiter is found.
    """
    for delimiter in ["\n---\n", "\n\n---\n\n", "\n- - -\n"]:
        if delimiter in markdown_full:
            return [p.strip() for p in markdown_full.split(delimiter) if p.strip()]
    return [markdown_full.strip()]


async def parse_file(client: AsyncLlamaCloud, file_path: Path) -> list[dict]:
    """
    Upload one file to LlamaCloud, parse it, and return a list of
    page-level dicts: {page_or_slide, title, text}
    """
    # 1. Upload the file
    with open(file_path, "rb") as fh:
        file_obj = await client.files.create(
            file=(file_path.name, fh, "application/octet-stream"),
            purpose="parse",
        )

    # 2. Parse — same pattern as the reference snippet above
    result = await client.parsing.parse(
        file_id=file_obj.id,
        tier=PARSE_TIER,
        version=PARSE_VERSION,
        expand=["markdown_full", "text_full", "markdown"],
    )

    # 3. Prefer markdown_full for richness; fall back to text_full
    full_content = result.markdown_full or result.text_full or ""
    if not full_content.strip():
        return []

    # 4. Build page-level records
    if SPLIT_BY == "page":
        # Use per-page list from the API when available (most accurate)
        page_items = getattr(result, "markdown", None) or []
        if page_items and isinstance(page_items, list):
            chunks = [p for p in page_items if isinstance(p, str) and p.strip()]
        else:
            # Fall back to splitting markdown_full on LlamaParse page delimiters
            chunks = split_markdown_by_page(full_content)

        return [
            {
                "page_or_slide": i + 1,
                "title": extract_title_from_markdown(chunk) or file_path.stem,
                "text": chunk.strip(),
            }
            for i, chunk in enumerate(chunks)
        ]
    else:
        # SPLIT_BY == "file" — one record for the whole document
        return [{
            "page_or_slide": None,
            "title": extract_title_from_markdown(full_content) or file_path.stem,
            "text": full_content.strip(),
        }]


print("✅ Parsing helpers defined")


# ## Step 3 — Run parsing (concurrent)

# In[5]:


# Max files parsed at the same time.
# Raising this speeds things up but risks 'Client Closed Request' errors.
MAX_CONCURRENT = 5

# Tracks files that failed so we can report them clearly at the end.
failed_files: list[str] = []


async def parse_all(files: list[Path]) -> list[dict]:
    client    = AsyncLlamaCloud(api_key=LLAMA_API_KEY)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    records   = []

    async def parse_with_limit(file_path: Path):
        async with semaphore:                          # ← indented inside function
            for attempt in range(1, 4):
                try:
                    result = await parse_file(client, file_path)
                    if result:
                        return result
                except Exception as e:
                    if attempt < 3:
                        wait = attempt * 10
                        print(f"\n    ↻ retry {attempt}/3 after {wait}s ({e})")
                        await asyncio.sleep(wait)
                    else:
                        raise
            return []

    # Kick off all tasks — semaphore controls how many run at once
    tasks = {f: asyncio.create_task(parse_with_limit(f)) for f in files}

    for file_path, task in tasks.items():
        rel = str(file_path.relative_to(EXTRACT_DIR))
        ext = file_path.suffix.lower()
        print(f"  ⏳ {rel} ...", end=" ", flush=True)

        try:
            pages = await task
        except Exception as e:
            print(f"FAILED ({e})")
            failed_files.append(rel)
            continue

        if not pages:
            print("(empty result)")
            failed_files.append(rel)
            continue

        print(f"{len(pages)} page(s)")

        for p in pages:
            records.append({
                "id":            make_id(rel, p["page_or_slide"] or 0),
                "title":         p["title"],
                "source_file":   rel,
                "file_type":     ext.lstrip("."),
                "page_or_slide": p["page_or_slide"],
                "text":          p["text"],
                "metadata": {
                    "parse_tier": PARSE_TIER,
                    "parsed_at":  datetime.now(timezone.utc).isoformat(),
                },
            })

    return records


print(f"Parsing started (max {MAX_CONCURRENT} files at a time) ...")
records = asyncio.run(parse_all(supported_files))
print(f"\n✅ Done — {len(records)} JSONL records generated.")

if failed_files:
    print(f"\n⚠️  {len(failed_files)} file(s) failed and were skipped:")
    for f in failed_files:
        print(f"   ✗ {f}")
    print("\nRe-run the cell to retry.")
else:
    print("✅ All files parsed successfully — no failures.")


# In[12]:


# ── Retry failed files with agentic_plus tier ─────────────────────────────────
if failed_files:
    print(f"Retrying {len(failed_files)} failed file(s) with 'agentic_plus' tier...\n")

    async def retry_with_agentic_plus():
        client  = AsyncLlamaCloud(api_key=LLAMA_API_KEY)
        recovered = []

        for rel in failed_files:
            file_path = Path(EXTRACT_DIR) / rel
            ext = file_path.suffix.lower()
            print(f"  ⏳ {rel} ...", end=" ", flush=True)

            for attempt in range(1, 4):
                try:
                    # Upload
                    with open(file_path, "rb") as fh:
                        file_obj = await client.files.create(
                            file=(file_path.name, fh, "application/octet-stream"),
                            purpose="parse",
                        )

                    # Parse with agentic_plus
                    result = await client.parsing.parse(
                        file_id=file_obj.id,
                        tier="agentic_plus",        # ← upgraded tier
                        version=PARSE_VERSION,
                        expand=["markdown_full", "text_full", "markdown"],
                    )

                    full_content = result.markdown_full or result.text_full or ""
                    if not full_content.strip():
                        raise ValueError("Empty result returned")

                    # Split into pages
                    page_items = getattr(result, "markdown", None) or []
                    if page_items and isinstance(page_items, list):
                        chunks = [p for p in page_items if isinstance(p, str) and p.strip()]
                    else:
                        chunks = split_markdown_by_page(full_content)

                    pages = [
                        {
                            "page_or_slide": i + 1,
                            "title": extract_title_from_markdown(chunk) or file_path.stem,
                            "text": chunk.strip(),
                        }
                        for i, chunk in enumerate(chunks)
                    ]

                    print(f"{len(pages)} page(s) ✅")

                    for p in pages:
                        recovered.append({
                            "id":            make_id(rel, p["page_or_slide"]),
                            "title":         p["title"],
                            "source_file":   rel,
                            "file_type":     ext.lstrip("."),
                            "page_or_slide": p["page_or_slide"],
                            "text":          p["text"],
                            "metadata": {
                                "parse_tier": "agentic_plus",
                                "parsed_at":  datetime.now(timezone.utc).isoformat(),
                            },
                        })
                    break  # success — stop retrying

                except Exception as e:
                    if attempt < 3:
                        wait = attempt * 10
                        print(f"\n    ↻ retry {attempt}/3 after {wait}s ({e})", end=" ")
                        await asyncio.sleep(wait)
                    else:
                        print(f"FAILED after 3 attempts ({e})")

        return recovered

    recovered_records = asyncio.run(retry_with_agentic_plus())

    if recovered_records:
        records.extend(recovered_records)
        print(f"\n✅ Recovered {len(recovered_records)} records — total now: {len(records)}")
        # Also append to the JSONL file
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
            for rec in recovered_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"✅ Appended to '{OUTPUT_JSONL}'")
    else:
        print("\n❌ File still failed with agentic_plus — the PDF itself may be corrupted or password-protected.")
else:
    print("✅ No failed files to retry.")


# ## Step 4 — Write JSONL output

# In[13]:


with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
    for rec in records:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

size_kb = Path(OUTPUT_JSONL).stat().st_size / 1024
print(f"✅ Wrote {len(records)} records → '{OUTPUT_JSONL}' ({size_kb:.1f} KB)")


# ## Step 5 — Preview & validate

# In[14]:


# ── Stats ──────────────────────────────────────────────────────────────────────
type_counts = Counter(r["file_type"] for r in records)
total_chars = sum(len(r["text"]) for r in records)
avg_chars   = total_chars // max(len(records), 1)

print("Records by file type:")
for ft, cnt in type_counts.most_common():
    print(f"  {ft:8s}  {cnt} record(s)")
print(f"\nTotal characters : {total_chars:,}")
print(f"Avg chars/record : {avg_chars:,}")


# In[15]:


# ── Preview first 3 records ────────────────────────────────────────────────────
for rec in records[:3]:
    print("─" * 64)
    print(f"ID          : {rec['id']}")
    print(f"Title       : {rec['title']}")
    print(f"Source      : {rec['source_file']}  (page {rec['page_or_slide']})")
    print(f"Type        : {rec['file_type']}")
    snippet = rec['text'][:300].replace('\n', ' ')
    print(f"Text snip   : {snippet}...")
    print()


# In[16]:


# ── Reload & validate the written file ────────────────────────────────────────
required_keys = {"id", "title", "source_file", "file_type", "text", "metadata"}
loaded, bad   = [], []

with open(OUTPUT_JSONL, encoding="utf-8") as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        loaded.append(rec)
        if not required_keys.issubset(rec.keys()):
            bad.append(i)

assert len(loaded) == len(records), "Record count mismatch after reload!"

if bad:
    print(f"⚠️  {len(bad)} record(s) missing required keys at lines: {bad}")
else:
    print(f"✅ All {len(loaded)} records are valid — JSONL is ready for RAG ingestion!")


# ## Cleanup (optional)

# In[ ]:


# Uncomment to delete the temporary extraction directory when done
# shutil.rmtree(EXTRACT_DIR)
# print(f"Removed: {EXTRACT_DIR}")


# ---
# ## JSONL Schema Reference
# 
# | Field | Type | Description |
# |---|---|---|
# | `id` | string | Stable MD5 of `source_file::page` — safe to use as vector store doc ID |
# | `title` | string | First H1/H2 heading or filename stem |
# | `source_file` | string | Relative path inside the ZIP |
# | `file_type` | string | `pdf`, `pptx`, `docx`, `png`, … |
# | `page_or_slide` | int \| null | 1-indexed (null when `SPLIT_BY="file"`) |
# | `text` | string | Markdown text; images/diagrams described inline by the agentic parser |
# | `metadata` | object | `parse_tier`, `parsed_at` UTC timestamp |
# 
# ## Next Steps — Load into a Vector Store
# 
# ```python
# from llama_index.core import Document, VectorStoreIndex
# 
# docs = []
# with open("rag_dataset.jsonl") as f:
#     for line in f:
#         r = json.loads(line)
#         docs.append(Document(
#             doc_id   = r["id"],
#             text     = r["text"],
#             metadata = {
#                 "title":  r["title"],
#                 "source": r["source_file"],
#                 "page":   r["page_or_slide"],
#                 **r["metadata"],
#             },
#         ))
# 
# index = VectorStoreIndex.from_documents(docs)
# ```

# In[ ]:




