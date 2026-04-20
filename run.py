"""Double-click this file to launch BRUNs Logistics Dashboard."""
import os, sys, subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))

subprocess.run([
    sys.executable, "-m", "streamlit", "run", "app.py",
    "--theme.base", "dark",
    "--theme.primaryColor", "#6366F1",
    "--theme.backgroundColor", "#0B1020",
    "--theme.secondaryBackgroundColor", "#141A2E",
    "--theme.textColor", "#E6E9F2",
])
