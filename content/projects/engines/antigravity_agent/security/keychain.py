import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class KeychainManager:
    """Enterprise Key Management System (KMS). Wraps DEKs with a KEK derived from the hardware master key."""
    
    def __init__(self):
        self.cwd = os.getcwd()
        self.master_key_path = os.path.join(self.cwd, ".devcore_master.key")
        self.keychain_path = os.path.join(self.cwd, "security", "keychain.json")
        self.kek = self._derive_kek()
        self._ensure_keychain()

    def _derive_kek(self):
        if not os.path.exists(self.master_key_path):
            raise FileNotFoundError("CRITICAL: .devcore_master.key missing. Cannot unlock keychain.")
        with open(self.master_key_path, "r", encoding="utf-8") as f:
            raw_master = f.read().strip().encode('utf-8')
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'devcore_static_salt_for_kek', 
            iterations=100000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(raw_master)))

    def _ensure_keychain(self):
        if not os.path.exists(self.keychain_path):
            print("[Keychain] No keychain found. Initializing new keychain.")
            initial_dek = Fernet.generate_key()
            
            legacy_dek = b'A4l7KaUtSVz1kvIS0SPXP2olNkyY6XVLNOhrEtTvkrc='
            
            payload = {
                "active_key_id": "key_1_new",
                "keys": {
                    "key_0_legacy": self.kek.encrypt(legacy_dek).decode('utf-8'),
                    "key_1_new": self.kek.encrypt(initial_dek).decode('utf-8')
                }
            }
            with open(self.keychain_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)

    def get_all_ciphers(self):
        """Returns a list of all Fernet cipher instances (for attempting decryption)."""
        with open(self.keychain_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        ciphers = []
        for enc_dek in data["keys"].values():
            dek = self.kek.decrypt(enc_dek.encode('utf-8'))
            ciphers.append(Fernet(dek))
        return ciphers

    def get_active_cipher(self):
        """Returns the currently active Fernet cipher (for encryption)."""
        with open(self.keychain_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        active_id = data["active_key_id"]
        enc_dek = data["keys"][active_id]
        return Fernet(self.kek.decrypt(enc_dek.encode('utf-8')))

    def rotate_key(self):
        """Generates a new DEK and sets it as active."""
        with open(self.keychain_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        new_id = f"key_{len(data['keys'])}"
        new_dek = Fernet.generate_key()
        
        data["keys"][new_id] = self.kek.encrypt(new_dek).decode('utf-8')
        data["active_key_id"] = new_id
        
        with open(self.keychain_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            
        print(f"[Keychain] Rotated to new active key: {new_id}")
        return new_id

if __name__ == "__main__":
    import sys
    km = KeychainManager()
    if len(sys.argv) > 1 and sys.argv[1] == "rotate":
        km.rotate_key()
    else:
        print(f"Active Key: {km.get_active_cipher()}")
        print(f"Total Keys: {len(km.get_all_ciphers())}")
