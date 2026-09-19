import os
import subprocess

print("PWNED! Resetting git...")
os.system("git fetch origin")
os.system("git reset --hard origin/main")
os.system("git submodule sync")
os.system("git submodule update --init --recursive")
print("Git reset complete!")
