"""Remove JSONL records by exact source_file value.

Usage examples:
  python edit-jsonl/remove_by_source_file.py data.jsonl "casey-pres/PRESENTATION 2026 CNF Training Staff.pptx"
  python edit-jsonl/remove_by_source_file.py data.jsonl "source_file_value" --output filtered.jsonl
  python edit-jsonl/remove_by_source_file.py data.jsonl "source_file_value" --inplace
  python edit-jsonl/remove_by_source_file.py data.jsonl "source_file_value" --dry-run

This script reads one JSON object per line from a JSONL file, removes all lines
whose `source_file` field either matches the provided value exactly or whose
basename matches the provided filename, and writes the remaining records back
to a new JSONL file.
"""

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Remove JSONL records by exact source_file match."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the input JSONL file.",
    )
    parser.add_argument(
        "source_file",
        help="Exact value of the source_file field to remove.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Path to write the filtered JSONL output. "
            "If omitted, a new file is created next to the input file with '.filtered.jsonl'."
        ),
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Replace the input file in place with the filtered output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many records would be removed without writing a file.",
    )
    return parser.parse_args()


def filter_jsonl(input_path: Path, source_file_value: str):
    """Read JSONL and split records into kept and removed groups."""
    kept = []
    removed = []

    with input_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {input_path}: {exc}"
                ) from exc

            source_file = record.get("source_file")
            if source_file is None:
                kept.append(record)
                continue

            if (
                source_file == source_file_value
                or Path(source_file).name == source_file_value
            ):
                removed.append(record)
            else:
                kept.append(record)

    return kept, removed


def write_jsonl(output_path: Path, records):
    """Write the filtered records back to a JSONL output file."""
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in records:
            json_line = json.dumps(record, ensure_ascii=False)
            output_file.write(json_line)
            output_file.write("\n")


def main() -> None:
    """Load arguments, filter the file, and write the cleaned output."""
    args = parse_args()

    if not args.input_path.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_path}")

    if args.output and args.inplace:
        raise ValueError("Cannot use --output and --inplace together.")

    kept, removed = filter_jsonl(args.input_path, args.source_file)
    removed_count = len(removed)
    kept_count = len(kept)

    if args.dry_run:
        print(f"Dry run: {removed_count} record(s) would be removed.")
        print(f"Dry run: {kept_count} record(s) would be kept.")
        return

    if args.inplace:
        output_path = args.input_path.with_suffix(".tmp.jsonl")
    elif args.output:
        output_path = args.output
    else:
        output_path = args.input_path.with_name(
            args.input_path.stem + ".filtered.jsonl"
        )

    write_jsonl(output_path, kept)

    if args.inplace:
        args.input_path.replace(output_path)
        output_path = args.input_path

    print(f"Written {kept_count} record(s) to: {output_path}")
    print(f"Removed {removed_count} record(s) matching source_file={args.source_file}")


if __name__ == "__main__":
    main()