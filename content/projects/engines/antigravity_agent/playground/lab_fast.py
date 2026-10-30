import os
import time
import itertools
import string
import pyzipper

# Use PKWARE (standard zipcrypto) so it matches the lab's fast speed
passwords = {
    'file-1.zip': b'B',
    'file-2.zip': b'R2',
    'file-3.zip': b'0B1',
    'file-4.zip': b'Y0Da',
}

os.chdir('Zip-Files')
for filename, pwd in passwords.items():
    with pyzipper.AESZipFile(filename, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_PKWARE) as zf:
        zf.setpassword(pwd)
        zf.write('sample-1.txt')
        zf.write('sample-2.txt')
        zf.write('sample-3.txt')

def crack_zip(filename, min_len, max_len):
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
                    print(f"[{filename}] PASSWORD FOUND!!!!: pw == {guess.decode()} (Time: {elapsed:.4f}s)")
                    return
                except Exception:
                    pass
    print(f"[{filename}] Password not found.")

crack_zip('file-1.zip', 1, 1)
crack_zip('file-2.zip', 2, 2)
crack_zip('file-3.zip', 3, 3)
crack_zip('file-4.zip', 4, 4)
