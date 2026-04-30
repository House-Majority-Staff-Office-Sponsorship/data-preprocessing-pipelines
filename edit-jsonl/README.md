# edit-jsonl

Utilities for editing and filtering JSONL files in the data preprocessing pipeline.

## Tools

### remove_by_source_file.py

A command-line tool to remove JSONL records based on the `source_file` field value.

#### What it does

Reads a JSONL file (one JSON object per line), removes all records whose `source_file` field matches a given value, and writes the remaining records to a new JSONL file.

#### Usage

```bash
python remove_by_source_file.py INPUT_FILE SOURCE_FILE [OPTIONS]
```

#### Arguments

- `INPUT_FILE`: Path to the input JSONL file
- `SOURCE_FILE`: The value to match against the `source_file` field
  - Supports **full path matching**: `casey-pres/PRESENTATION 2026 CNF Training Staff.pptx`
  - Supports **basename matching**: `PRESENTATION 2026 CNF Training Staff.pptx` (matches any full path ending with this filename)

#### Options

| Flag | Description |
|------|-------------|
| `--output FILE` | Write filtered output to a specific file (default: `INPUT_FILE.filtered.jsonl`) |
| `--inplace` | Replace the input file with the filtered output |
| `--dry-run` | Preview how many records would be removed without writing a file |

#### Examples

**Remove records by full path:**
```bash
python remove_by_source_file.py data.jsonl "casey-pres/PRESENTATION 2026 CNF Training Staff.pptx"
```

**Remove records by basename (matches any directory):**
```bash
python remove_by_source_file.py data.jsonl "PRESENTATION 2026 CNF Training Staff.pptx"
```

**Preview changes without writing:**
```bash
python remove_by_source_file.py data.jsonl "PRESENTATION 2026 CNF Training Staff.pptx" --dry-run
```

**Write to a custom output file:**
```bash
python remove_by_source_file.py data.jsonl "PRESENTATION 2026 CNF Training Staff.pptx" --output cleaned_data.jsonl
```

**Replace the input file in place:**
```bash
python remove_by_source_file.py data.jsonl "PRESENTATION 2026 CNF Training Staff.pptx" --inplace
```

#### Input Format

Each line must be a valid JSON object. Example:

```json
{"id": "abc123", "title": "Slide 1", "source_file": "path/to/file.pptx", "text": "..."}
{"id": "def456", "title": "Slide 2", "source_file": "path/to/other.pptx", "text": "..."}
```

#### Output

A JSONL file with all matching records removed. Non-matching records are written as-is, preserving the original JSON structure and character encoding.

#### Error Handling

- **File not found**: Will raise an error if the input file doesn't exist
- **Invalid JSON**: Will raise an error if any line contains malformed JSON
- **Conflicting options**: Cannot use both `--output` and `--inplace` at the same time

#### Notes

- The script skips empty lines in the input file
- Uses UTF-8 encoding for reading and writing
- Preserves the original JSON structure of kept records
- For in-place operations, creates a temporary file before replacing the original
