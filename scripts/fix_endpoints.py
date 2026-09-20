with open("content/projects/engines/antigravity_agent/templates/ai_index.html", "r") as f:
    html = f.read()

html = html.replace("fetch('/api/stream')", "fetch('/ai_agent/api/stream')")
html = html.replace("fetch('/api/chat'", "fetch('/ai_agent/api/chat'")
html = html.replace("fetch('/api/kill'", "fetch('/ai_agent/api/kill'")

with open("content/projects/engines/antigravity_agent/templates/ai_index.html", "w") as f:
    f.write(html)
