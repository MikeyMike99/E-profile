[//]: # (DOC_ID: SIRA-DOC-04_11 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 04_11: Zero-Modification Ephemeral Plugin Architecture

An architectural guide to Siraugga's **Zero-Modification Blueprint Pattern**—enabling rich, interactive frontend applications whose behavior is controlled 100% via validated JSON schemas while core templates remain strictly immutable.

---

## The Blueprint Concept
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-1)

When autonomous coding agents are allowed to edit HTML, CSS, and JavaScript templates directly, they inevitably introduce syntax errors, break screen reader accessibility attributes, and destroy upstream upgradeability.

Siraugga enforces the **Zero-Modification Architecture**:
- **Fixed Frontend Blueprints**: HTML and JavaScript files are treated as immutable runtime engines. They are never edited by agents.
- **Dynamic JSON Payloads**: All behavioral changes (timers, question sequences, media URLs, form controls) are injected strictly through schema-validated JSON files (such as `exam_temp.json`).

```
┌─────────────────────────────────────────────────────────────┐
│                 IMMUTABLE CORE BLUEPRINTS                   │
│   (exam_application.html / exam_builder.html / player.html) │
│                                                             │
│   • Semantic HTML5 Markup                                   │
│   • Screen-Reader ARIA Live Regions                         │
│   • Keyboard Navigation Event Listeners                     │
│   • Responsive CSS Framework                                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                Dynamically Fetches at Runtime
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 DYNAMIC JSON SCHEMA PAYLOAD                 │
│                      (exam_temp.json)                       │
│                                                             │
│   • Questions Array (text, options, correct_index)          │
│   • Timers & Countdown Controls                             │
│   • Explanations & Accessible Guidance                      │
│   • Normalized by format_exam.py                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Architectural Advantages
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-2)

1. **Permanent Modularity & Clean Upgrades**:
   - The developer can upgrade the core frontend template (e.g., adding dark mode or updating Tailwind CSS) without breaking custom exams or user content.
2. **Defeating Prompt-Injection Code Tampering**:
   - Because the frontend is static and loaded from read-only disk mounts, malicious prompts cannot inject arbitrary JavaScript or XSS vectors into the portal.
3. **Guaranteed Screen-Reader Accessibility**:
   - ARIA tags (`aria-live="polite"`, `role="alert"`, `tabindex="0"`) remain pristine and protected from unintentional deletion by coding agents.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-3)

In schema-driven application rendering, transformation order prevents malformed UI states:
1. **Define Schema Rules in Agent Directives First**: Agent system prompts must explicitly forbid editing HTML/JS templates, directing all effort into JSON payload generation.
2. **Execute Format Normalization Before Display**: The generator script (`format_exam.py`) must run over the generated JSON to map types and calculate numeric indices.
3. **Serve Blueprint via Iframe After Validation**: The web portal renders the target iframe only after the JSON payload passes verification.

---

## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-4)

To build a zero-modification plugin in your project in under 2 minutes:

```python
import json, subprocess

def deploy_ephemeral_app(template_name: str, payload_data: dict, output_dir: str):
    # Step 1: Write raw payload to temporary JSON file
    temp_json_path = f"{output_dir}/app_temp.json"
    with open(temp_json_path, "w", encoding="utf-8") as f:
        json.dump(payload_data, f, indent=2)
        
    # Step 2: Execute format normalizer to enforce schema compliance
    subprocess.run(["python3", "scripts/format_exam.py", temp_json_path], check=True)
    
    # Step 3: Return target URL pointing to the static blueprint
    return f"/plugins/{template_name}?data=app_temp.json"
```

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-5)

### What is the difference between a "Blueprint" and a standard webpage?
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-6)
A standard webpage often mixes code and content together in HTML. A blueprint is a pure software engine designed to accept *any* content fed to it through a structured data format like JSON.

### What happens if the JSON data has a mistake?
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-7)
The `format_exam.py` normalizer catches missing keys and fixes common errors (like mapping `correct_answer: "Option B"` to `correct_index: 1`) before the browser ever attempts to render it.

### Can an agent add custom buttons using this pattern?
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-8)
Yes! The JSON schema can include a `"custom_actions"` array specifying button labels and callback identifiers, which the blueprint engine dynamically renders into accessible HTML buttons.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_11-SEC-9)
- To understand why agents broke frontend templates, read [`01_PROBLEMS_ENCOUNTERED/01_16_EPHEMERAL_PLUGIN_MUTATION_AND_BLUEPRINT_TAMPERING_TRAPS.md`](/docs/devlog/01_16_EPHEMERAL_PLUGIN_MUTATION_AND_BLUEPRINT_TAMPERING_TRAPS).
- To inspect the primary source code of the exam normalizer, view [`02_SOURCE_EVIDENCE/02_11_EPHEMERAL_BLUEPRINT_AND_JSON_SCHEMA_EVIDENCE.md`](/docs/devlog/02_11_EPHEMERAL_BLUEPRINT_AND_JSON_SCHEMA_EVIDENCE).
- To write your own schema-driven application engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH).
