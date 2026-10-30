import os
import glob
from cryptography.fernet import InvalidToken

def get_brain_dir():
    home = os.path.expanduser("~")
    return os.path.join(home, ".gemini", "antigravity-cli", "brain")

def lock_brain():
    """Encrypts all transcript files in the brain using the Active DEK."""
    brain_dir = get_brain_dir()
    if not os.path.exists(brain_dir):
        return

    from security.keychain import KeychainManager
    km = KeychainManager()
    cipher = km.get_active_cipher()

    search_pattern = os.path.join(brain_dir, "**", "transcript*.jsonl")
    for file_path in glob.glob(search_pattern, recursive=True):
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if data.startswith(b'gAAAAA'): 
                continue
                
            encrypted = cipher.encrypt(data)
            
            import tempfile
            fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), prefix=".secure_lock_")
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(encrypted)
                os.replace(tmp_path, file_path)
                print(f"[Cold Storage] Locked: {file_path}")
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
        except Exception as e:
            print(f"[Cold Storage Error] Failed to lock {file_path}: {e}")

def unlock_brain():
    """Decrypts all transcript files using the Keychain (tries all historical keys)."""
    brain_dir = get_brain_dir()
    if not os.path.exists(brain_dir):
        return

    from security.keychain import KeychainManager
    km = KeychainManager()
    ciphers = km.get_all_ciphers()

    search_pattern = os.path.join(brain_dir, "**", "transcript*.jsonl")
    for file_path in glob.glob(search_pattern, recursive=True):
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if data.startswith(b'gAAAAA'):
                decrypted = None
                for cipher in ciphers:
                    try:
                        decrypted = cipher.decrypt(data)
                        break
                    except InvalidToken:
                        continue
                
                if decrypted is None:
                    print(f"[Cold Storage Error] FATAL: No valid key found in keychain to decrypt {file_path}!")
                    continue
                    
                import tempfile
                fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), prefix=".secure_unlock_")
                try:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(decrypted)
                    os.replace(tmp_path, file_path)
                    print(f"[Cold Storage] Unlocked: {file_path}")
                except Exception as e:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise e
        except Exception as e:
            print(f"[Cold Storage Error] Failed to unlock {file_path}: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "lock":
        lock_brain()
    else:
        unlock_brain()
