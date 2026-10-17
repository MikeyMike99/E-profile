# Pillar 04.4: Architecture Solutions: Extending Plugins & Protected Services

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_03_OPAQUE_VFS_AND_AST_DIFFING_ARCHITECTURE.md`](/docs/devlog/04_03_OPAQUE_VFS_AND_AST_DIFFING_ARCHITECTURE)
- **Next Architecture Chapter**: [`04_05_SOVEREIGN_AI_AND_OFFLINE_BROKER_RECIPES.md`](/docs/devlog/04_05_SOVEREIGN_AI_AND_OFFLINE_BROKER_RECIPES)

---

## Overview

This guide provides tested, copy-paste recipes for extending the Siraugga platform:
1. **The Ephemeral Plugin Pattern**: Adding interactive UI tools without modifying core HTML templates.
2. **The Protected RBAC Route Pattern**: Adding secure backend endpoints using safe in-memory hot-patching.

---

## Recipe 1: Creating an Ephemeral Plugin (Zero-Modification Pattern)

Siraugga plugins (such as the Exam Builder and Accessible Media Player) follow the **Zero-Modification Architecture**. The HTML and JavaScript files are permanent blueprints; all behavior is driven by injecting dynamic JSON schemas.

### Step 1: Create the Plugin HTML Blueprint
Create `templates/plugins/diff_viewer.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessible Diff Viewer</title>
    <link rel="stylesheet" href="/static/css/tailwind.css">
</head>
<body class="bg-gray-900 text-white p-4">
    <h1 class="text-xl font-bold mb-4" id="pluginTitle">Diff Viewer</h1>
    <pre id="diffContainer" class="bg-black p-4 rounded text-sm font-mono"></pre>

    <script>
        // Fetch dynamic schema payload injected by AI or backend
        fetch('/api/plugins/data?name=diff_temp.json')
            .then(res => res.json())
            .then(data => {
                document.getElementById('pluginTitle').innerText = data.title;
                document.getElementById('diffContainer').innerText = data.diff_content;
            })
            .catch(err => console.error("Failed to load payload:", err));
    </script>
</body>
</html>
```

### Step 2: Inject the Dynamic JSON Payload
When the AI or a user runs `/diff`, the system simply writes a temporary JSON payload:
```json
{
    "title": "Code Diff: server.py update",
    "diff_content": "+ safe_env['PYTHONUNBUFFERED'] = '1'"
}
```
The UI renders dynamically inside an accessible iframe without touching server templates.

---

## Recipe 2: Adding a Protected RBAC Route via Safe Hot-Patch

### Step 1: Create the Route in Staging
Never edit live engine files directly! Stage the route in `core/patches/custom_route.py`:

```python
from quart import Blueprint, jsonify, request
from security.security_manager import SecurityManager

custom_bp = Blueprint("custom", __name__)
sec_mgr = SecurityManager()

@custom_bp.route("/api/custom/action", methods=["POST"])
async def handle_custom_action():
    data = await request.get_json()
    user_path = data.get("path", "")
    
    # 1. Enforce Path Traversal Defense
    safe_path = sec_mgr.resolve_safe_path("./workspace", user_path)
    
    # 2. Return Verified Data
    return jsonify({
        "status": "success",
        "verified_path": safe_path
    })
```

### Step 2: Trigger Hot-Patch In-Memory Swap
Execute the safe simulation command in your terminal:
```bash
curl -s -X POST http://127.0.0.1:5000/api/simulate-patch
```
The server pre-compiles the file, takes a backup, swaps the module, and hot-reloads Quart routes in memory with zero connection drops.

---

## Why Order Matters in Extension Workflows

1. **JSON Schema Validation Before Iframe Spawn**:
   - The JSON data file must be written and validated on disk *before* triggering the iframe load. If the iframe requests the data before the write finishes, the user receives an empty screen error.
2. **Safe Path Resolution Before File Descriptors**:
   - In custom backend routes, `resolve_safe_path()` must execute before opening files. Skipping or postponing path resolution allows traversal attacks.

---

## Beginner Coder Q&A

### Q: Why shouldn't I just edit `index.html` directly when adding a feature?
**A:** Directly hacking client templates makes future system upgrades impossible and risks breaking screen reader keyboard bindings. Sticking to dynamic JSON payloads keeps your interface modular and clean.

### Q: What happens if my new route has a syntax error during hot-patching?
**A:** The `py_compile` step detects the syntax error immediately, halts the deployment, and leaves the live server untouched. Your website stays online without disruption.
