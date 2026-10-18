[//]: # (DOC_ID: SIRA-DEV-01_23 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 01_23: Slash Menu Enter Key Conflict & Accessibility Traps

Interactive autocomplete menus enhance user efficiency, but without strict event precedence and accessible ARIA attributes, they create severe UX barriers. This chapter documents how pressing Enter inside the slash command menu prematurely sent incomplete prompts, and how **WCAG ARIA Combobox patterns** restored seamless accessibility.

---

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-1)
## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-1)

When developers typed a forward slash (`/`) into the main prompt textarea, an autocomplete popup appeared displaying available commands (`/goal`, `/plan`, `/compact`, `/browser`):
- **Premature Prompt Submission**: When the user navigated the popup list using arrow keys and pressed Enter to pick a command, the prompt textarea's `keydown` listener fired first. Instead of selecting `/goal`, it immediately transmitted the raw unfinished text (`/g`) to the AI agent!
- **Assistive Technology Silence**: Screen readers (NVDA, JAWS, Narrator) remained completely silent when the popup opened. Visually impaired developers had no audible indication of how many commands were available or which option was currently focused.
- **Virtual Cursor Traps**: Tab navigation inside the popup bypassed the list entirely, jumping focus to the browser address bar.

---

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-2)
## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-2)

The failure stemmed from unmanaged DOM event bubbling and missing semantic accessibility roles:
- **Event Listener Precedence Conflict**: Both the prompt input box and the autocomplete menu listened for the Enter key. Because the textarea listener was attached to the outer form control, it triggered its default "submit prompt" action before the autocomplete selection handler could run.
- **Missing `e.preventDefault()`**: The autocomplete handler failed to call `event.preventDefault()` and `event.stopPropagation()`, allowing the Enter event to bubble up the DOM tree.
- **Lack of ARIA Combobox Markup**: The autocomplete menu was built using generic `<div>` tags without `role="combobox"`, `role="listbox"`, or `aria-activedescendant`, rendering it invisible to screen reader accessibility trees.

```
Broken Event Flow:
User hits Enter on "/goal" ---> Outer Textarea Listener fires first ---> Sends "/g" to AI! (Broken)

Hardened WCAG Combobox:
User hits Enter on "/goal" ---> e.preventDefault() blocks submit ---> Injects "/goal " into box! (Success)
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-3)

In complex interactive DOM components, event listener ordering guarantees intended behavior:
1. **Check Autocomplete State First**: Inside the textarea `keydown` handler, always check `if (slashMenuIsOpen)` before evaluating form submission rules.
2. **Call `e.preventDefault()` Before Modifying Input**: Calling `preventDefault()` halts the browser's default newline or submit action before your script inserts the selected command string.
3. **Update `aria-activedescendant` on Arrow Navigation**: Synchronize the active option's ID to the container's `aria-activedescendant` attribute at the exact moment the highlight changes so screen readers speak the new option immediately.

---

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-4)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-5)

### What is an ARIA Combobox?
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-5)
An ARIA Combobox is a standardized accessibility pattern for input fields that control an associated popup list (like a search bar with suggestions). It tells screen readers how to announce options as the user navigates.

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-6)
### What does `aria-activedescendant` do?
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-6)
Instead of physically moving DOM focus (which would cause the cursor to leave the text input box), `aria-activedescendant="option-2"` tells the screen reader which item in the popup list is currently active while the user keeps typing!

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-7)
### How do we prevent Enter from submitting the form?
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-7)
Inside the `keydown` event listener:
```javascript
if (e.key === 'Enter' && isMenuOpen) {
    e.preventDefault(); // Stop form from submitting
    selectCurrentOption();
}
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_23-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_23-SEC-8)
- To inspect primary source code of the accessible web portal, view [`02_SOURCE_EVIDENCE/02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE.md`](/docs/devlog/02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE).
- To view the architectural blueprint of the WCAG Combobox pattern, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_18_WCAG_ACCESSIBLE_SLASH_COMBOBOX_ARCHITECTURE.md`](/docs/devlog/04_18_WCAG_ACCESSIBLE_SLASH_COMBOBOX_ARCHITECTURE).
- To build the complete accessible autocomplete combobox from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_20_WCAG_ACCESSIBLE_COMBOBOX_FROM_SCRATCH.md`](/docs/devlog/05_20_WCAG_ACCESSIBLE_COMBOBOX_FROM_SCRATCH).
