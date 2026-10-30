import os
import signal
import subprocess

out = subprocess.check_output(['wsl', 'bash', '-c', 'ps aux | grep "python3 server.py" | grep -v grep']).decode('utf-8')
for line in out.strip().split('\n'):
    if line:
        pid = line.split()[1]
        print(f"Killing {pid}")
        os.system(f'wsl bash -c "kill -9 {pid}"')
