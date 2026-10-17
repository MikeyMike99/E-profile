[//]: # (DOC_ID: SIRA-DOC-04_18 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# WCAG Accessible Slash Command Combobox Architecture

## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-1)
The Siraugga Web Portal provides an interactive command menu triggered when users type a leading forward slash (`/`). To satisfy Web Content Accessibility Guidelines (WCAG 2.1 AA) and prevent UI interaction traps, the command menu is built as an ARIA 1.2 Combobox pattern rather than a floating HTML popup.

Screen readers such as NVDA, JAWS, and Orca interpret standard dynamic dropdowns as intrusive visual noise if focus is jerked away from the main prompt input. The Combobox architecture maintains input focus on the `<textarea>` while controlling an active descendant state over the virtual list box.

```
+---------------------------------------------------------+
| Prompt Textarea: role="combobox", aria-expanded="true"  |
| aria-autocomplete="list", aria-controls="slash-menu"    |
| aria-activedescendant="slash-opt-2"                     |
+---------------------------------------------------------+
                            |
                            v
+---------------------------------------------------------+
| Dropdown Listbox: id="slash-menu", role="listbox"       |
|   [Item 0] /goal     - Run autonomous long-running task |
| * [Item 1] /schedule - Configure recurring cron timer   |
|   [Item 2] /browser  - Web search and documentation     |
+---------------------------------------------------------+
```

---

## 2. Event Precedence and Keyboard Trap Resolution
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-2)
A fatal conflict in initial web portals occurred when users typed `/g` and pressed the Enter key. The form submission listener intercepted the Enter key first, transmitting the partial prompt `/g` to the backend engine before the selection handler could insert `/goal`.

The Combobox architecture resolves this race condition through strict JavaScript event precedence:

```
[Keydown Event on Textarea]
            |
            v
 Is Slash Menu Visible?
   |              |
  YES             NO
   |              |
 Key == Enter?    Normal Form Submission
   |
  YES
   |
 1. e.preventDefault()
 2. e.stopPropagation()
 3. Read active option text
 4. Replace partial slash prefix in textarea
 5. Close menu and reset aria-activedescendant
```

---

## 3. Screen Reader Live Region & Active Descendant Sync
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-3)
Instead of moving physical DOM focus into the list element (which disrupts screen reader typing state), the architecture utilizes `aria-activedescendant`.

### Attribute Synchronization Lifecycle
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-1)
1. **Activation**: When `/` is typed, the menu container sets `hidden = false`, and the textarea updates `aria-expanded="true"`.
2. **Navigation**: ArrowDown or ArrowUp increments the virtual index, updates `aria-activedescendant="slash-opt-{idx}"`, and highlights the option with CSS class `active-descendant`.
3. **Announcement**: NVDA/JAWS immediately announces the active option label and shortcut description via the accessibility API without changing cursor focus.
4. **Dismissal**: Pressing Escape or typing a space character closes the menu and clears `aria-activedescendant`.

---

## 4. Why Order Matters in Combobox Implementation
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-4)
1. **Prevent Default Before Replacement**: You must call `e.preventDefault()` before extracting the selected text; otherwise, the browser inserts a newline or submits the form.
2. **DOM Attributes Before CSS Styling**: Setting `aria-expanded` and `aria-activedescendant` before updating CSS classes ensures screen readers receive the state change before layout recalculation occurs.
3. **Restoring Cursor Position After Insertion**: When the command text (e.g., `/goal `) replaces the partial prefix, the input's `selectionStart` and `selectionEnd` must be explicitly placed at the end of the text.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_18-SEC-5)
**Q: Why not use a standard HTML `<select>` element?**  
A: A native `<select>` cannot be embedded smoothly inside a multi-line chat textarea without breaking typing flow and visual alignment.

**Q: What does `aria-activedescendant` actually do?**  
A: It tells accessibility tools: "The user is still typing in the textarea, but visually and conceptually they have highlighted this specific item in the listbox."

**Q: How does this prevent prompt corruption?**  
A: By trapping the Enter key during menu navigation, accidental sub-command submissions are completely blocked from reaching the Quart server.
