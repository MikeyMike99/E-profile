import hashlib
target = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"
words = ["admin", "dev", "mod", "superadmin", "password", "master", "devcore", "siraugga", "12345", "root", "Raugus", "raugus"]
for w in words:
    if hashlib.sha256(w.encode()).hexdigest() == target:
        print("FOUND:", w)
