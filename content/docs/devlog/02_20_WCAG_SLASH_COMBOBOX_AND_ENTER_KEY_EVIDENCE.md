[//]: # (DOC_ID: SIRA-DEV-02_20 | VERSION: v1.0 | SCOPE: DEV)

# WCAG Slash Combobox & Enter Key Resolution Source Evidence

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-1)
## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-1)
This document contains source code evidence from `sandbox/templates/index.html` (commits `659a312` and `04627a1`). It documents how ARIA Combobox semantics and event listener coordination resolved the Enter key prompt submission conflict while complying with WCAG 2.1 AA screen reader standards.

---

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-2)
## 2. ARIA Semantic Markup Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-2)
The command menu was upgraded from an unlabelled `<div>` to a fully accessible ARIA 1.2 Combobox listbox:

```html
<!-- sandbox/templates/index.html: ARIA Listbox definition -->
<div id="slash-command-menu" 
     role="listbox" 
     aria-label="Slash Commands" 
     class="hidden absolute bottom-[65px] left-0 w-full max-w-sm bg-slate-800 border border-slate-600 rounded-lg shadow-xl overflow-hidden z-50 flex flex-col">
    <div class="px-3 py-2 bg-slate-900 border-b border-slate-700 text-xs text-slate-400 font-bold uppercase tracking-wider">
        Slash Commands
    </div>
    <button type="button" 
            role="option" 
            id="slash-item-0" 
            aria-selected="false" 
            class="slash-item text-left px-4 py-3 hover:bg-slate-700 focus:bg-slate-700 focus:outline-none transition-colors border-b border-slate-700/50" 
            data-command="/help exam">
        <span class="font-semibold text-emerald-400">/help exam</span>
        <span class="block text-xs text-slate-400">Interactive exam builder guide</span>
    </button>
</div>
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-3)
## 3. Enter Key Conflict Resolution Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-3)
In earlier iterations, pressing Enter while highlighting a menu command submitted the prompt prematurely. The following check was added to `handleKeyDown` in `templates/index.html`:

```javascript
// sandbox/templates/index.html: handleKeyDown listener
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        // Prevent sending if the slash menu is active and an item is highlighted
        var menuEl = document.getElementById('slash-command-menu');
        if (menuEl && !menuEl.classList.contains('hidden')) {
            // Check if the user is navigating the menu (active item exists)
            var hasActiveItem = menuEl.querySelector('[aria-selected="true"]');
            if (hasActiveItem) {
                return; // Let the slash command event listener handle the selection
            }
        }
        e.preventDefault();
        sendPrompt();
    }
}
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-4)
## 4. Arrow Key Navigation and State Sync Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-4)
Arrow keys update visual focus and ARIA attributes simultaneously:

```javascript
// sandbox/templates/index.html: Arrow key combobox handler
function navigateSlashMenu(direction) {
    var items = document.querySelectorAll('#slash-command-menu .slash-item');
    if (!items.length) return;
    
    // Clear previous selection
    items.forEach(el => {
        el.setAttribute('aria-selected', 'false');
        el.classList.remove('bg-slate-700');
    });
    
    currentIndex = (currentIndex + direction + items.length) % items.length;
    var activeItem = items[currentIndex];
    
    activeItem.setAttribute('aria-selected', 'true');
    activeItem.classList.add('bg-slate-700');
    activeItem.scrollIntoView({ block: 'nearest' });
    
    // Sync active descendant on textarea for screen readers
    document.getElementById('prompt-input').setAttribute('aria-activedescendant', activeItem.id);
}
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-5)
## 5. Why Order Matters in Event Handling
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-5)
1. **Check Menu State Before Sending**: The event handler must check if `aria-selected="true"` exists before invoking `sendPrompt()`. If `sendPrompt()` executes first, incomplete commands are dispatched to the server.
2. **Clear Prior Selection Before Setting New One**: Leaving multiple items with `aria-selected="true"` confuses assistive tech and produces erroneous screen reader readouts.
3. **Scroll into View After State Assignment**: Updating accessibility attributes before calling `scrollIntoView()` ensures keyboard users don't trigger layout shifts before the item is recognized as active.

---

[//]: # (SECTION_ID: SIRA-DEV-02_20-SEC-6)
## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_20-SEC-6)
**Q: Why use `button role="option"` instead of an `<a>` or `<li>`?**  
A: A button natively supports keyboard focus and click events, and assigning `role="option"` informs screen readers that it belongs to the parent `role="listbox"`.

**Q: What is the purpose of `e.shiftKey` in `handleKeyDown`?**  
A: It allows multi-line typing! Pressing Shift+Enter inserts a line break in the textarea, whereas pressing Enter alone triggers prompt submission (or command selection).

**Q: How does `aria-activedescendant` help blind developers?**  
A: It keeps focus in the textarea so typing isn't interrupted, but causes the screen reader to speak the highlighted option whenever the user presses the arrow keys.
