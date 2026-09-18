import subprocess
import sys

print("=== Running Post-Sync Operations ===")

# 1. Antigravity Agent (AI Integration)
try:
    print("Verifying spaCy NLP models for DLP engine...")
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
    print("spaCy NLP models downloaded successfully.")
except Exception as e:
    print(f"Failed to download spaCy model: {e}")

# [Future integrations (e.g. database migrations, cache clearing) can be added below]

print("=== Post-Sync Operations Complete ===")
