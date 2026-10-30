import os
import time
import itertools
import string
import pyzipper
import zlib

def crack_zip(filename, min_len, max_len):
    print(f"\n--- Cracking {filename} (length {min_len}-{max_len}) ---")
    start_time = time.time()
    charset = string.ascii_letters + string.digits + "-"
    
    with pyzipper.AESZipFile(filename) as zf:
        for length in range(min_len, max_len + 1):
            for guess_tuple in itertools.product(charset, repeat=length):
                guess = "".join(guess_tuple).encode('utf-8')
                try:
                    zf.read('sample-1.txt', pwd=guess)
                    end_time = time.time()
                    elapsed = end_time - start_time
                    print(f"PASSWORD FOUND!!!!: pw == {guess.decode()}")
                    print(f"Time taken: {elapsed:.4f} seconds")
                    return
                except Exception:
                    pass
    print("Password not found within the specified length range.")

crack_zip('Zip-Files/file-3.zip', 3, 3)
