# BRUNs Logistics Dashboard — Installation & Run Guide

## 🚀 Option A — One-Click Launch (Recommended for daily use)

**Requirements:** Python 3.10+ installed

```
1. Double-click: launch.bat
2. Wait ~30 seconds the first time (installing dependencies)
3. Browser opens automatically at http://localhost:8501
```

The launcher:
- Creates a local virtual environment (`.venv/`) automatically on first run
- Installs all dependencies silently
- Checks if Ollama is running and warns you if not
- Opens the browser for you

---

## 📦 Option B — Standalone EXE (For sharing with your friend — NO Python needed)

### Step 1: Build the EXE (you do this once, on your machine)

```
1. Open launch.bat (to make sure dependencies are installed)
2. Double-click: build_exe.bat
3. Wait 2-3 minutes
4. Output: dist\BRUNs\  (contains BRUNs.exe and all dependencies)
```

### Step 2: Share it

Zip the entire `dist\BRUNs\` folder and send it to your friend.

The zip contains everything — Python runtime, Streamlit, all libraries.
**No Python installation needed on the receiving machine.**

### Step 3: Friend runs it

```
1. Unzip BRUNs anywhere (e.g. Desktop\BRUNs\)
2. Install Ollama: https://ollama.ai/download  ← still required for PDF processing
3. Run: ollama pull llama3   (first time only, ~4 GB download)
4. Double-click: BRUNs.exe
5. Browser opens automatically
```

---

## 🤖 Ollama Setup (Required for PDF processing)

Ollama is the local AI that reads your PDFs. It's free and runs locally — no data sent anywhere.

### Install Ollama
- Windows: https://ollama.ai/download/windows
- Just download and run the installer

### Download a model (one-time, ~4 GB)
```bash
ollama pull llama3
```

### Start Ollama (if it doesn't start automatically)
```bash
ollama serve
```

### Test it's running
Open a browser and go to: http://localhost:11434
You should see "Ollama is running"

---

## 📄 Using the Dashboard

### Dashboard page
- Shows all imported containers in a filterable grid
- **Quick Filter buttons** at top (En transit, Livrés, etc.)
- **Text search** searches across all fields simultaneously
- **Sort** by ETA, ETD, delivery date
- **Date window** filter (Last 7 days, Last 30 days, etc.)
- **Double-click** any card to see full document details
- **Keyboard navigation**: Press `F` to focus cards, then arrow keys to move, Enter to open, Esc to close

### Processing page
- Drag & drop PDF files (Booking Confirmations, Departure Notices, Bills of Lading)
- Click "Process All" — AI extracts all data and stores it
- See per-file results with success/failure details

### Export page
- Select exactly which columns to include
- Filter by status, carrier, or text search before exporting
- Download as CSV or Excel with formatted headers
- Preview first 10 rows before downloading

### Settings page
- Change Ollama model (e.g., switch from llama3 to mistral)
- Test connection to Ollama
- Adjust grid columns and animation speed
- Database stats and reset option

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| "Python not found" | Install from https://python.org (add to PATH during install) |
| "Ollama not detected" | Start Ollama: open a terminal and run `ollama serve` |
| App opens but no data | Go to Processing page and upload PDF files |
| PDF processing fails | Check Ollama is running and you have a model: `ollama pull llama3` |
| Browser doesn't open | Manually go to http://localhost:8501 |
| Port 8501 in use | Close other Streamlit apps, or edit launch.bat to change port |
| EXE won't start | Make sure you unzipped the ENTIRE dist\BRUNs\ folder, not just BRUNs.exe |

---

## 📁 File Structure

```
BRUNs logistics data scraper/
├── launch.bat           ← Double-click to start (daily use)
├── build_exe.bat        ← Creates standalone EXE for sharing
├── app_new.py           ← Main Streamlit app
├── bruns_launcher.py    ← EXE entry point
├── bruns.spec           ← PyInstaller build config
├── requirements.txt     ← Python dependencies
├── config.py            ← Ollama and path settings
├── data/
│   ├── logistics.db     ← SQLite database (all your data)
│   ├── input/           ← Place PDFs here for batch processing
│   └── logs/            ← Processing logs
├── ui/
│   ├── styles.py        ← Global CSS and color tokens
│   ├── layout.py        ← Bottom navbar, AOS framework
│   ├── components/
│   │   ├── doc_grid.py  ← Document cards, modal viewer, keyboard nav
│   │   └── filter_bar.py ← Filters, quick presets, sorting
│   └── pages/
│       ├── processing.py ← PDF upload and batch processing
│       ├── export.py     ← CSV/Excel export
│       └── settings.py  ← Configuration page
├── agents/
│   └── parser_agent.py  ← Ollama PDF parsing agent
├── db/
│   └── database.py      ← SQLite database operations
└── parsers/
    └── pdf_extractor.py ← PDF text extraction (PyMuPDF)
```

---

## 💾 Backup Your Data

Your data lives in `data/logistics.db`. To back it up:
- Copy `data/logistics.db` to a safe location
- To restore: replace `data/logistics.db` with your backup

---

**Built for:** Local logistics document management  
**Privacy:** All processing is local. Zero data leaves your machine.  
**AI Engine:** Ollama (local LLM — free, private, no account needed)
