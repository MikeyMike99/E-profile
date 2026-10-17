import os
import sys
import time
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load local environment
load_dotenv()
SYNC_SECRET = os.environ.get("SYNC_SECRET")
SERVER_URL = "https://MikeyMike99.pythonanywhere.com/api/sync"
ROOT_DIR = Path(__file__).resolve().parent

if not SYNC_SECRET:
    print("[ERROR] SYNC_SECRET is not set in .env")
    print("Please add SYNC_SECRET=YourSecretKey to your .env file.")
    sys.exit(1)

class SyncHandler(FileSystemEventHandler):
    # debounce dict to prevent multiple rapid fires on single save
    last_synced = {}
    
    def on_modified(self, event):
        if event.is_directory:
            return
            
        filepath = Path(event.src_path)
        try:
            rel_path = filepath.relative_to(ROOT_DIR)
        except ValueError:
            return
        
        # Exclude directories and temporary files
        excludes = ['.git', '__pycache__', 'profiles.json', '.env', '.idea', 'venv', 'local_sync.py']
        rel_str = str(rel_path).replace("\\", "/")
        for ex in excludes:
            if ex in rel_str or rel_str.endswith('~'):
                return
                
        # Debounce (prevent firing 5 times for a single Ctrl+S)
        now = time.time()
        if rel_str in self.last_synced and (now - self.last_synced[rel_str]) < 2.0:
            return
        self.last_synced[rel_str] = now
                
        print(f"\n[SYNC] Detected change in: {rel_str}")
        self.push_file(filepath, rel_str)
        
    def push_file(self, filepath, rel_path):
        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filepath.name, f)}
                data = {
                    'secret': SYNC_SECRET,
                    'path': rel_path
                }
                response = requests.post(SERVER_URL, data=data, files=files)
                
            if response.status_code == 200:
                result = response.json()
                print(f"[SUCCESS] {result.get('message')}")
                if result.get('reloaded'):
                    print("[INFO] Remote server automatically restarted.")
            else:
                print(f"[ERROR] Sync failed ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"[EXCEPTION] Failed to sync: {e}")

if __name__ == "__main__":
    print("========================================")
    print(f"Starting Local-to-Production Sync Watcher")
    print(f"Monitoring: {ROOT_DIR}")
    print(f"Target: {SERVER_URL}")
    print("Press Ctrl+C to stop.")
    print("========================================")
    
    event_handler = SyncHandler()
    observer = Observer()
    observer.schedule(event_handler, str(ROOT_DIR), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
