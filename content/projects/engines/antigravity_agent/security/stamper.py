import os
import sys
import json
from cryptography.fernet import Fernet

MAGIC_START = b"\n---AGY_STAMP_START---\n"
MAGIC_END = b"\n---AGY_STAMP_END---\n"

STAMP_KEY = b'A4l7KaUtSVz1kvIS0SPXP2olNkyY6XVLNOhrEtTvkrc='

def get_cipher():
    return Fernet(STAMP_KEY)

def stamp_exe(source_exe: str, dest_exe: str, payload: dict):
    """
    Copies the source .exe and safely appends an AES-encrypted JSON payload to the bottom.
    This creates a uniquely stamped executable without recompiling.
    """
    import shutil
    
    if not os.path.exists(source_exe):
        raise FileNotFoundError(f"Source executable {source_exe} not found.")
        
    shutil.copy2(source_exe, dest_exe)
    
    payload_bytes = json.dumps(payload).encode('utf-8')
    encrypted_payload = get_cipher().encrypt(payload_bytes)
    
    stamp_data = MAGIC_START + encrypted_payload + MAGIC_END
    with open(dest_exe, "ab") as f:
        f.write(stamp_data)
        
    print(f"Successfully stamped {dest_exe} with AES-encrypted payload: {payload}")

def read_stamp() -> dict:
    """
    Reads the currently executing binary (sys.executable) to see if it was stamped
    with an encrypted JSON payload. Decrypts and returns the dictionary if found in RAM.
    """
    if not getattr(sys, 'frozen', False):
        return None
        
    exe_path = sys.executable
    if not os.path.exists(exe_path):
        return None
        
    try:
        with open(exe_path, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            read_size = min(4096, file_size)
            f.seek(file_size - read_size)
            tail_data = f.read()
            
        start_idx = tail_data.rfind(MAGIC_START)
        end_idx = tail_data.rfind(MAGIC_END)
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            encrypted_payload = tail_data[start_idx + len(MAGIC_START) : end_idx]
            decrypted_bytes = get_cipher().decrypt(encrypted_payload)
            return json.loads(decrypted_bytes.decode('utf-8'))
            
    except Exception as e:
        print(f"[Stamper] Failed to read or decrypt executable stamp: {e}")
        
    return None

if __name__ == "__main__":
    import argparse
    import datetime
    
    parser = argparse.ArgumentParser(description="Stamp a DevCore Executable with a Client ID (AES Encrypted)")
    parser.add_argument("--source", default="Siraugga.exe", help="The master .exe file")
    parser.add_argument("--dest", required=True, help="The output stamped .exe file")
    parser.add_argument("--id", required=True, help="The unique EXE ID / Deployment Token")
    parser.add_argument("--days", type=int, default=7, help="Days until this exe expires")
    
    args = parser.parse_args()
    
    expire_date = (datetime.datetime.now() + datetime.timedelta(days=args.days)).isoformat()
    
    payload = {
        "exe_id": args.id,
        "expires": expire_date
    }
    
    stamp_exe(args.source, args.dest, payload)
