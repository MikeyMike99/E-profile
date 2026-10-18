[//]: # (DOC_ID: SIRA-DEV-02_11 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_11: Ephemeral Blueprint & JSON Schema Evidence

Primary source evidence from the Siraugga ephemeral plugin suite illustrating how the **Zero-Modification Architecture** uses Python format normalizers to adapt dynamic JSON data into immutable frontend templates.

---

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-1)
## Source Citation 1: Question Structure Normalization (`format_exam.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-1)

This excerpt displays how raw LLM output is parsed and normalized to match the strict schema expected by the frontend template:

```python
# Location: <project_root>/.agents/skills/exam-generator/scripts/format_exam.py
# Lines: 14-43

    new_questions = []
    for q in data.get("questions", []):
        q_type = q.get("type")
        
        # Base transformation
        if "question" in q:
            q["text"] = q.pop("question")
            
        if q_type == "multiple_choice":
            if "correct_answer" in q and "options" in q:
                try:
                    idx = q["options"].index(q["correct_answer"])
                    q["correct_index"] = idx
                    del q["correct_answer"]
                except ValueError:
                    q["correct_index"] = 0
            new_questions.append(q)
            
        elif q_type == "multi_select":
            if "correct_answers" in q and "options" in q:
                indices = []
                for ans in q["correct_answers"]:
                    try:
                        indices.append(q["options"].index(ans))
                    except ValueError:
                        pass
                q["correct_indices"] = indices
                del q["correct_answers"]
            new_questions.append(q)
```

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-2)
- **Schema Mapping Over Code Rewriting**: Instead of rewriting the HTML/JS frontend to support string answers or varied key names, `format_exam.py` transforms the JSON data (`correct_answer` string to `correct_index` integer).
- **Graceful Fallbacks**: If an option is missing from the list, line 29 safely defaults `correct_index = 0` rather than throwing an unhandled exception in the browser.

---

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-3)
## Source Citation 2: Complex Component Flattening (`format_exam.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-3)

This excerpt shows how complex multi-blank dropdowns are transformed into deterministic single-blank templates:

```python
# Location: <project_root>/.agents/skills/exam-generator/scripts/format_exam.py
# Lines: 44-65

        elif q_type == "dropdown_blank":
            if "blanks" in q:
                blanks = q.pop("blanks")
                text = q["text"]
                
                if isinstance(blanks, dict):
                    for b_name, b_data in blanks.items():
                        b_target = b_name if b_name.startswith("[") else f"[{b_name}]"
                        new_text = text.replace(b_target, "[BLANK]")
                        nq = {
                            "type": "dropdown_blank",
                            "text": new_text,
                            "options": b_data.get("options", []),
                            "correct_text": b_data.get("correct_answer", ""),
                            "explanation": q.get("explanation", "")
                        }
                        new_questions.append(nq)
```

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-4)
- **Template Simplicity Guarantee**: Complex nested blank dictionaries are automatically mapped to standardized `[BLANK]` placeholders. The HTML frontend only needs to render one universal blank-filling component.
- **Strict Separation of Concerns**: Front-end markup remains pristine and untouched; all complexity is resolved server-side before delivery.

---

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-5)

In schema-driven application rendering, transformation order prevents malformed states:
1. **Load Raw JSON Before Transforming**: Always load and parse the raw JSON file into a Python dictionary (`json.load(f)`) before modifying any keys.
2. **Convert Key Names (`question` to `text`) First**: All downstream type handlers assume `q["text"]` is present. Renaming must occur before handling `multiple_choice` or `dropdown_blank`.
3. **Overwrite Target JSON Atomically**: Write the formatted output back to disk only after all questions validate cleanly. Never overwrite the original file mid-loop.

---

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-7)

### Why does the template require `correct_index` as a number instead of text?
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-7)
In frontend JavaScript, comparing numbers (`selectedOptionIndex === question.correct_index`) is faster and avoids bugs caused by whitespace, capitalization, or special character mismatches.

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-8)
### What happens if an AI outputs `"question"` instead of `"text"`?
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-8)
Line 20 detects if `"question"` exists and renames it to `"text"`. This ensures backward compatibility with different LLM prompting styles without altering the frontend.

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-9)
### Can I add a timer using this script?
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-9)
Yes. The script checks for top-level keys like `"time_limit_minutes"`. If present in the JSON payload, the frontend template automatically activates its countdown clock.

---

[//]: # (SECTION_ID: SIRA-DEV-02_11-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_11-SEC-10)
- To understand why agents must never edit core HTML templates, read [`01_PROBLEMS_ENCOUNTERED/01_16_EPHEMERAL_PLUGIN_MUTATION_AND_BLUEPRINT_TAMPERING_TRAPS.md`](/docs/devlog/01_16_EPHEMERAL_PLUGIN_MUTATION_AND_BLUEPRINT_TAMPERING_TRAPS).
- To view the architectural blueprint of ephemeral plugins, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_11_ZERO_MODIFICATION_EPHEMERAL_PLUGIN_ARCHITECTURE.md`](/docs/devlog/04_11_ZERO_MODIFICATION_EPHEMERAL_PLUGIN_ARCHITECTURE).
- To build the complete exam normalizer and schema engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_13_ZERO_MODIFICATION_EXAM_ENGINE_FROM_SCRATCH).
