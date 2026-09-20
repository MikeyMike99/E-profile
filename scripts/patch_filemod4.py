with open("file_mod.py", "r") as f:
    content = f.read()

content = content.replace("'--recurse-submodules', ", "")

with open("file_mod.py", "w") as f:
    f.write(content)
