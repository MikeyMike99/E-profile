with open("file_mod.py", "r") as f:
    content = f.read()

target = "run_git_cmd(['submodule', 'update', '--init', '--recursive'])"
replacement = "run_git_cmd(['submodule', 'sync'])\n        run_git_cmd(['submodule', 'update', '--init', '--recursive'])"

content = content.replace(target, replacement)

with open("file_mod.py", "w") as f:
    f.write(content)
