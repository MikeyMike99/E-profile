with open("file_mod.py", "r") as f:
    content = f.read()

target = "run_git_cmd(['config', 'submodule.content/projects/engines/antigravity_agent.url', f'https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git'])\n        run_git_cmd(['submodule', 'sync'])"

replacement = "run_git_cmd(['submodule', 'sync'])\n        run_git_cmd(['config', 'submodule.content/projects/engines/antigravity_agent.url', f'https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git'])"

content = content.replace(target, replacement)

with open("file_mod.py", "w") as f:
    f.write(content)
