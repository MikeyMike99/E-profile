import os
import glob
import re

def replace_in_file(filepath, old, new, match_case=False):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return False
        
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

root_dir = "."
for root, dirs, files in os.walk(root_dir):
    if '.git' in root or 'venv' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith(('.exe', '.pyc', '.tar', '.gz')):
            continue
        filepath = os.path.join(root, file)
        
        # Replace occurrences in text files
        # 1. Antigravity_Desktop.exe -> Antigravity_Desktop.exe
        replace_in_file(filepath, "Antigravity_Desktop.exe", "Antigravity_Desktop.exe")
        
        # 2. Antigravity Desktop -> Antigravity Desktop
        replace_in_file(filepath, "Antigravity Desktop", "Antigravity Desktop")
        replace_in_file(filepath, "Antigravity Agent", "Antigravity Agent")
        replace_in_file(filepath, "Antigravity Architecture", "Antigravity Architecture")
        
        # 3. Antigravity -> Antigravity
        replace_in_file(filepath, "Antigravity", "Antigravity")
        replace_in_file(filepath, "antigravity", "antigravity")

# Rename the actual exe if it exists
if os.path.exists("Antigravity_Desktop.exe"):
    os.rename("Antigravity_Desktop.exe", "Antigravity_Desktop.exe")
