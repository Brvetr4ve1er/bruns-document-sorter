# 🚢 BRUNs Logistics - Data Scraper

A premium, AI-powered logistics dashboard that extracts shipment and container data from PDF documents using Local LLMs (Ollama) and OCR.

---

### 🚀 Quick Start
To launch the application, simply double-click the file below:

### 👉 **`START_APP.bat`**

This script will automatically:
1.  Verify your Python environment.
2.  Install all necessary dependencies.
3.  Check if **Ollama** is running (required for AI parsing).
4.  Launch the Dashboard in your browser.

---

### 🛠️ Prerequisites
*   **Python 3.10+**: Ensure Python is installed and added to your [Windows PATH](https://python.org).
*   **Ollama**: Install from [ollama.com](https://ollama.com) and ensure it is running in the background.
    *   *Recommended Model*: `llama3` or `llama3.2-vision` (for OCR).
*   **Tesseract OCR** (Optional): For processing scanned images. The app includes a portable version, but installing it system-wide is recommended for better performance.

---

### 📁 Project Structure
*   **`app.py`**: The main Streamlit application.
*   **`database_logic/`**: Database schema and operations (SQLite).
*   **`agents/`**: AI logic for parsing document text.
*   **`parsers/`**: PDF text extraction and OCR fallback.
*   **`ui/`**: Modern glass-morphism interface components.
*   **`data/`**: Location for `logistics.db`, input PDFs, and exported results.

---

### 🛑 Stopping the App
To stop the application, just close the Command Prompt window that opened when you ran the script.

---
*Created for BRUNs Logistics — Phase 3 (Final)*
