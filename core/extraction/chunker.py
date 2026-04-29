"""
core/extraction/chunker.py

Map-Reduce PDF chunking pipeline.

Problem: LLMs have a fixed context window (typically 8,192 tokens).
A 50-page PDF can contain 50,000+ tokens, causing truncation or crashes.

Solution:
  1. MAP   — Split the PDF into overlapping N-page chunks
  2. REDUCE — Merge all per-chunk JSON results into one unified record
             (later fields win on conflict, lists are appended)
"""

import fitz
import json
from typing import Any

# Overlap between chunks to avoid losing data that straddles a page boundary
CHUNK_SIZE_PAGES = 5
OVERLAP_PAGES    = 1
# If extracted text is shorter than this threshold, skip chunking entirely
CHUNKING_THRESHOLD_CHARS = 3000


def _merge_dicts(base: dict, update: dict) -> dict:
    """
    Deep-merge two dicts:
    - Strings/numbers: non-null value from `update` wins
    - Lists: items are combined and deduplicated (order preserved)
    """
    merged = dict(base)
    for key, val in update.items():
        if val is None or val == "" or val == []:
            continue  # never overwrite with empty
        if key not in merged or merged[key] is None or merged[key] == "":
            merged[key] = val
        elif isinstance(val, list) and isinstance(merged[key], list):
            seen = set()
            combined = []
            for item in merged[key] + val:
                token = json.dumps(item, sort_keys=True)
                if token not in seen:
                    seen.add(token)
                    combined.append(item)
            merged[key] = combined
        else:
            # Non-null update value wins (later chunks have more context)
            merged[key] = val
    return merged


def chunk_pdf_text(pdf_path: str) -> list[dict[str, Any]]:
    """
    Extract text per page-group from a PDF.
    Returns a list of chunk dicts: {"text": str, "pages": [int, ...]}
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # For small documents, return a single chunk — no overhead
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    if len(full_text) < CHUNKING_THRESHOLD_CHARS:
        return [{"text": full_text, "pages": list(range(1, total_pages + 1))}]

    # Large document — chunk it
    doc = fitz.open(pdf_path)
    chunks = []
    step = CHUNK_SIZE_PAGES - OVERLAP_PAGES
    page_idx = 0

    while page_idx < total_pages:
        end_idx = min(page_idx + CHUNK_SIZE_PAGES, total_pages)
        chunk_text = ""
        page_nums = []
        for i in range(page_idx, end_idx):
            chunk_text += doc.load_page(i).get_text()
            page_nums.append(i + 1)
        if chunk_text.strip():
            chunks.append({"text": chunk_text, "pages": page_nums})
        page_idx += step

    doc.close()
    return chunks


def merge_chunk_results(chunk_results: list[dict]) -> dict:
    """
    Reduce a list of per-chunk JSON dicts into one unified record.
    """
    if not chunk_results:
        return {}
    merged = {}
    for result in chunk_results:
        merged = _merge_dicts(merged, result)
    return merged
