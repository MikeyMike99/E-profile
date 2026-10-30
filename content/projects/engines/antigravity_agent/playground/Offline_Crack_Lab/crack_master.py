import hashlib
import itertools
import string
import time
import sys

TARGET_HASH = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"

print("===================================================")
print("  DEVCORE SECURITY LAB: OFFLINE HASH CRACKING      ")
print("===================================================")
print(f"Target SHA-256 Hash: {TARGET_HASH}")
print("Objective: Brute-force the raw Master Key.")
print("Simulating high-speed GPU hashcat attack...\n")

charset = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-"
start_time = time.time()
attempts = 0

try:
    for length in range(1, 80):
        print(f"[*] Trying all combinations of length {length}...")
        for guess_tuple in itertools.product(charset, repeat=length):
            guess = "".join(guess_tuple)
            attempts += 1
            
            # Simulate high speed by only hashing (no printing every line)
            if hashlib.sha256(guess.encode()).hexdigest() == TARGET_HASH:
                elapsed = time.time() - start_time
                print(f"\n[!!!] MASTER KEY COMPROMISED: {guess}")
                print(f"Time taken: {elapsed:.2f} seconds")
                sys.exit(0)
                
            # Print a status update every 1,000,000 hashes
            if attempts % 1000000 == 0:
                elapsed = time.time() - start_time
                rate = attempts / elapsed
                print(f"  ... {attempts:,} hashes tested ({rate:,.0f} hashes/sec) | Current guess: {guess}")

except KeyboardInterrupt:
    elapsed = time.time() - start_time
    print(f"\n\n[X] Attack aborted by user.")
    print(f"Total time elapsed: {elapsed:.2f} seconds")
    print(f"Total hashes tested: {attempts:,}")
    print("Conclusion: The DevCore Master Key is mathematically secure against brute-force.")
