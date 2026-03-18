# data-preprocessing-pipelines

# 📄 ZIP → JSONL for RAG
### House Majority Staff Office — New Employee Knowledge Base

Uses **Docling** to convert a ZIP of PDFs, PPTX, and DOCX files into a `.jsonl` file.

---
### What Docling does
| Task | How Docling handles it |
|------|------------------------|
| PDF, DOCX, PPTX parsing | `DocumentConverter` — one API for all formats |
| Layout, reading order, tables | Built-in AI layout model |
| Smart chunking for RAG | `HybridChunker` — respects document structure + token limits |
| Rich metadata per chunk | Headings, page numbers, source filename |
| JSONL export | Native — one line per chunk |

---
### Output format example — one line per chunk
```json
{
  "title": "onboarding_guide.pdf",
  "text": "## HR Policies\n\nAll new employees must complete...",
  "headings": ["HR Policies"],
  "page": 3,
  "chunk_id": "onboarding_guide.pdf::chunk_0012"
}
```

Why this is good for our RAG model:
- ✅ Each chunk fits cleanly within our embedding model's token window
- ✅ Headings give the chatbot context about *where* in the document the answer came from
- ✅ Page numbers allow citing sources
- ✅ Tables are preserved as readable Markdown, not garbled text

---
**Run cells in order:**
1. 📦 Install
2. ⚙️ Configuration
3. 🔧 Imports
4. 🚀 Run
5. 🔍 Preview *(optional)*
