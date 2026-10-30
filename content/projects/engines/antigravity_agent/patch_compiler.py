import re

with open('remote_compiler.py', 'r') as f:
    content = f.read()

# Remove the plaintext data dir inclusions
content = re.sub(r'    "--include-data-dir=sandbox/templates=sandbox/templates",\n', '', content)
content = re.sub(r'    "--include-data-dir=sandbox/static=sandbox/static",\n', '', content)
content = re.sub(r'    "--include-data-file=core/ui_config.json=core/ui_config.json",\n', '', content)

# Insert the assets.bin inclusion
content = content.replace(
    '    "--output-filename=Siraugga.exe",',
    '    "--include-data-file=assets.bin=assets.bin",\n    "--output-filename=Siraugga.exe",'
)

# Insert the pack_vfs call at the start
pack_logic = """
print("[Build] Executing VFS Packer...")
subprocess.run([sys.executable, "pack_vfs.py"], check=True)
"""
content = content.replace('nuitka_args = [', pack_logic + '\nnuitka_args = [')

with open('remote_compiler.py', 'w') as f:
    f.write(content)
