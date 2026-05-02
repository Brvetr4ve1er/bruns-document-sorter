# doc/ — Third-Party Attribution

This folder contains upstream attribution for third-party software bundled
with or distributed alongside BRUNs.

## Contents

| File | What it is |
|------|-----------|
| `AUTHORS` | Tesseract OCR contributor list (upstream, maintained by the Tesseract project) |
| `LICENSE` | Tesseract OCR license (Apache License 2.0) |

## About the Tesseract bundling

BRUNs bundles the Tesseract OCR engine for offline use:

- **Binary:** `tesseract_bin/tesseract.exe` — Windows build from UB-Mannheim
- **Language data:** `tessdata/` — trained data for 100+ languages including
  `ara.traineddata` (Arabic), `fra.traineddata` (French), `eng.traineddata` (English)

Tesseract OCR is open-source software released under the Apache License 2.0.
The full license text is in `doc/LICENSE`. The list of contributors is in
`doc/AUTHORS`.

Upstream project: https://github.com/tesseract-ocr/tesseract

## BRUNs license

BRUNs itself is proprietary software. See the project root for licensing terms.

## Third-party dependency licenses

Other notable license considerations:

| Dependency | License | Note |
|------------|---------|------|
| PyMuPDF (`fitz`) | AGPL-3.0 | Requires paid license for closed-source commercial distribution |
| Tesseract | Apache-2.0 | Bundled binary, attribution in this folder |
| Ollama | MIT | Not bundled; installed separately by the user |
| ChromaDB | Apache-2.0 | |
| Pydantic | MIT | |
| Flask | BSD-3-Clause | |
| RapidFuzz | MIT | |
| PassportEye | MIT | |
| mrz | MIT | |
