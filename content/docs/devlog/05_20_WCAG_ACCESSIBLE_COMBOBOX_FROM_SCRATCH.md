[//]: # (DOC_ID: SIRA-DOC-05_20 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# WCAG Accessible Slash Command Combobox from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_20-SEC-1)
A common flaw in modern chat web applications is the uncoordinated slash command menu. When a developer types `/` and uses keyboard arrows to select a command, standard event handlers often submit the incomplete prompt on Enter or trap screen reader focus, violating accessibility standards.

This guide provides a standalone, zero-framework implementation of a WCAG 2.1 AA compliant ARIA Combobox. It coordinates keyboard events, manages virtual focus via `aria-activedescendant`, and cleanly separates command selection from prompt submission.

```
+-------------------------------------------------------------+
|               HTML Textarea (role="combobox")               |
|               Captures input, arrows, enter, esc            |
+-------------------------------------------------------------+
                              |
                Event & Semantic Coordination
                              |
               +--------------+--------------+
               |                             |
      ArrowDown / ArrowUp             Enter Key Pressed
               |                             |
     Update Virtual Focus         Check Menu Active State:
   aria-activedescendant         Active? -> Select Command!
     aria-selected="true"        Closed? -> Submit Prompt!
```

---

## 2. Complete HTML & JavaScript Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_20-SEC-2)
Save the following standalone file as `combobox.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WCAG Accessible Slash Command Combobox</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
        .combobox-container { position: relative; max-width: 600px; margin: 0 auto; }
        textarea { width: 100%; height: 100px; background: #1e293b; color: #fff; border: 1px solid #475569; border-radius: 8px; padding: 12px; font-size: 1rem; box-sizing: border-box; resize: vertical; }
        .listbox { position: absolute; bottom: 110px; left: 0; width: 100%; background: #1e293b; border: 1px solid #64748b; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); overflow: hidden; display: flex; flex-direction: column; }
        .hidden { display: none; }
        .list-header { padding: 8px 12px; background: #0f172a; font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; font-weight: bold; }
        .option-item { padding: 10px 14px; background: transparent; border: none; text-align: left; color: #e2e8f0; cursor: pointer; border-bottom: 1px solid #334155; }
        .option-item:hover, .option-item[aria-selected="true"] { background: #334155; outline: none; }
        .cmd-name { font-weight: bold; color: #34d399; }
        .cmd-desc { display: block; font-size: 0.8rem; color: #94a3b8; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
    </style>
</head>
<body>

<div class="combobox-container">
    <div id="sr-live" class="sr-only" aria-live="polite"></div>

    <!-- Dropdown Listbox -->
    <div id="slash-menu" role="listbox" aria-label="Available Slash Commands" class="listbox hidden">
        <div class="list-header">Commands</div>
        <button type="button" role="option" id="opt-0" class="option-item" aria-selected="false" data-cmd="/goal">
            <span class="cmd-name">/goal</span>
            <span class="cmd-desc">Execute an autonomous deep goal</span>
        </button>
        <button type="button" role="option" id="opt-1" class="option-item" aria-selected="false" data-cmd="/schedule">
            <span class="cmd-name">/schedule</span>
            <span class="cmd-desc">Set background cron timers</span>
        </button>
        <button type="button" role="option" id="opt-2" class="option-item" aria-selected="false" data-cmd="/browser">
            <span class="cmd-name">/browser</span>
            <span class="cmd-desc">Fetch web documentation</span>
        </button>
    </div>

    <!-- Prompt Textarea -->
    <textarea id="prompt-input"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded="false"
              aria-controls="slash-menu"
              aria-activedescendant=""
              placeholder="Type '/' to view commands, or ask a question..."></textarea>
</div>

<script>
    const input = document.getElementById('prompt-input');
    const menu = document.getElementById('slash-menu');
    const items = menu.querySelectorAll('.option-item');
    const srLive = document.getElementById('sr-live');
    let activeIndex = -1;

    function openMenu() {
        menu.classList.remove('hidden');
        input.setAttribute('aria-expanded', 'true');
        srLive.textContent = "Slash command menu opened with " + items.length + " options.";
    }

    function closeMenu() {
        menu.classList.add('hidden');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-activedescendant', '');
        items.forEach(el => el.setAttribute('aria-selected', 'false'));
        activeIndex = -1;
    }

    function setActiveItem(index) {
        items.forEach((el, i) => {
            const isSelected = (i === index);
            el.setAttribute('aria-selected', isSelected ? 'true' : 'false');
            if (isSelected) {
                input.setAttribute('aria-activedescendant', el.id);
                srLive.textContent = el.querySelector('.cmd-name').textContent + " highlighted.";
            }
        });
        activeIndex = index;
    }

    input.addEventListener('input', (e) => {
        if (input.value.startsWith('/')) {
            openMenu();
        } else {
            closeMenu();
        }
    });

    input.addEventListener('keydown', (e) => {
        const isMenuOpen = !menu.classList.contains('hidden');

        if (isMenuOpen) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                let next = (activeIndex + 1) % items.length;
                setActiveItem(next);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                let prev = (activeIndex - 1 + items.length) % items.length;
                setActiveItem(prev);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                closeMenu();
                return;
            }
            if (e.key === 'Enter' && activeIndex >= 0) {
                e.preventDefault();
                // Select highlighted item
                const selectedCmd = items[activeIndex].getAttribute('data-cmd');
                input.value = selectedCmd + ' ';
                closeMenu();
                input.focus();
                return;
            }
        }

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            alert("Prompt Submitted: " + input.value);
            input.value = '';
            closeMenu();
        }
    });

    items.forEach((item, idx) => {
        item.addEventListener('click', () => {
            input.value = item.getAttribute('data-cmd') + ' ';
            closeMenu();
            input.focus();
        });
    });
</script>
</body>
</html>
```

---

## 3. Why Order Matters in Combobox Event Logic
[//]: # (SECTION_ID: SIRA-DOC-05_20-SEC-3)
1. **Intercept Keydown Before Default Form Submission**: Catching `Enter` in the menu check and invoking `e.preventDefault()` halts prompt transmission before the server receives partial commands.
2. **Assign Active Descendant Before Announcement**: Screen reader live regions must refer to IDs that have already been stamped with `aria-selected="true"`.
3. **Reset State on Close**: Completely clearing `aria-activedescendant` and resetting `activeIndex = -1` guarantees subsequent typing starts from a clean virtual slate.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_20-SEC-4)
**Q: Why keep focus on the `<textarea>` instead of focusing the `<button>`?**  
A: Moving focus into the button forces screen readers to exit "Forms Mode" or "Edit Mode", stopping users from continuing to type their prompt.

**Q: What is the purpose of `sr-only` class?**  
A: It hides the element visually from sighted users while keeping it visible in the accessibility tree so screen readers can speak live updates.

**Q: Can this be used in React or Vue?**  
A: Absolutely! The same ARIA attributes (`aria-expanded`, `aria-activedescendant`) and event listener order apply across all modern JavaScript frontend frameworks.
