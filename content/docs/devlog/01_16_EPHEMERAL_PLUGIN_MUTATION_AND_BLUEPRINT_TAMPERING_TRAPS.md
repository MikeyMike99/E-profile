[//]: # (DOC_ID: SIRA-DEV-01_16 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 01_16: Ephemeral Plugin Mutation & Blueprint Tampering Traps

Interactive tools such as the Exam Application and Accessible Media Player provide rich web experiences within the portal. This chapter documents the critical vulnerability of **Blueprint Tampering**—where autonomous agents tried to rewrite core frontend templates—and explains why the **Zero-Modification Architecture** mandates that all UI customization occur exclusively via dynamic JSON payloads.

---

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-1)
## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-1)

When users requested behavioral modifications to interactive mini-apps (for example, "add a timer to question 3" or "add an explanation textbox when an answer is wrong"), autonomous agents routinely broke the platform:
- **Template Destruction**: The agent used code editing tools to directly alter `exam_application.html` or `exam_builder.html`, stripping critical screen-reader ARIA live regions, damaging navigation event listeners, and corrupting responsive Tailwind styling.
- **Modularity Breakage**: Direct modifications made the application un-upgradeable. When a new core feature was deployed upstream, all user-specific tweaks were wiped out.
- **Infinite Refactoring Loops**: Small JavaScript syntax errors introduced by the agent triggered silent browser failures, leading the agent into repetitive, unsuccessful attempts to debug client-side DOM rendering.

---

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-2)
## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-2)

The vulnerability originated from treating dynamic web applications as static source code rather than schema-driven engines:
- **Lack of Architectural Separation**: The agent assumed that to change how an application behaves, it must edit the frontend code that renders it.
- **Missing Schema Constraints**: Without an explicit rule forbidding template edits, the agent selected the path of highest cognitive complexity—modifying HTML and JavaScript rather than injecting data.
- **Dynamic Feature Creep**: In-flight UI modifications bypass server-side validation and can introduce cross-site scripting (XSS) vectors into the developer portal.

```
Anti-Pattern (Direct Template Tampering):
User Request ---> Agent Edits exam_application.html ---> Broken JS / Ruined Upgrade Path!

The Blueprint Architecture (Zero-Modification):
User Request ---> Agent Injects exam_temp.json ---> format_exam.py Validates ---> Dynamic UI Renders!
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-3)

In schema-driven application rendering, the sequence of generation and validation guarantees stability:
1. **Define Schema Before Payload**: The data structure (questions, options, timers, media links) must conform to an immutable schema specification before any values are populated.
2. **Execute Format Normalization**: Before rendering an iframe or writing to the target directory, the generator MUST execute `format_exam.py` against the JSON payload to enforce structure and strip malformed fields.
3. **Inject Payload Without Touching Template**: The backend serves the fixed blueprint template, which dynamically fetches and parses the validated JSON file at runtime.

---

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-4)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-5)

### What is the "Blueprint Concept"?
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-5)
The Blueprint Concept treats HTML and JavaScript files as fixed, read-only engines. Just as a web browser engine doesn't change when you visit different websites, the Exam template never changes—it simply displays whatever data the JSON payload provides.

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-6)
### If I want to change a timer or add questions, what file do I edit?
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-6)
You never edit the HTML or JS. You only generate or edit `exam_temp.json`. Changing a value in that JSON file instantly changes the timer or question layout on the next page load.

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-7)
### What is the role of `format_exam.py`?
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-7)
`format_exam.py` is a Python validation and formatting script. It inspects `exam_temp.json` to ensure required keys exist, timestamps are valid numbers, and question types match allowed identifiers before the web UI attempts to display them.

---

[//]: # (SECTION_ID: SIRA-DEV-01_16-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_16-SEC-8)
- To inspect the primary source code of the exam normalizer and schema, view [`02_SOURCE_EVIDENCE/02_11_EPHEMERAL_BLUEPRINT_AND_JSON_SCHEMA_EVIDENCE.md`](/docs/devlog/02_11_EPHEMERAL_BLUEPRINT_AND_JSON_SCHEMA_EVIDENCE).
- To read the architectural specification of the Zero-Modification Pattern, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_11_ZERO_MODIFICATION_EPHEMERAL_PLUGIN_ARCHITECTURE.md`](/docs/devlog/04_11_ZERO_MODIFICATION_EPHEMERAL_PLUGIN_ARCHITECTURE).
- To build the schema normalizer and blueprint from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH).
