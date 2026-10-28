/**
 * ARCHITECT_OS // WORKSTATION_CORE v.2.8.6_STABLE
 * Final Sync: Restored New Tab navigation for Surgical Tray.
 */

let activeContext = "";

document.addEventListener('DOMContentLoaded', () => {
    const term = document.getElementById('terminal-overlay');
    if (term) term.style.display = 'none';

    loadFolders();
    setupDragAndDrop();
    setupTerminalInput();
});

/**
 * Creates a clean file node for the UI.
 */
function createFileNode(file, parentFolder = "") {
    const fullPath = parentFolder ? `${parentFolder}/${file.name}` : file.name;
    const cleanLabel = `File: ${file.name}. Size: ${file.size}. Lines of code: ${file.loc}.`;

    return `
        <div class="file-node" 
             onclick="openSurgery('${fullPath}')" 
             tabindex="0" 
             role="link" 
             aria-label="${cleanLabel}">
            <span class="file-main">${file.name}</span>
            <span class="file-details" aria-hidden="true">
                [${file.size}] [MOD: ${file.modified}] [LOC: ${file.loc}]
            </span>
        </div>
    `;
}

// --- 1. THE SCROLL GUI (ACCORDION LOGIC) ---
async function loadFolders() {
    const project = document.body.getAttribute('data-project');
    const container = document.getElementById('explorer-view');

    try {
        // Uses prefix /api/projects/explorer_logic to hit the Python Blueprint
        const res = await fetch(`/api/projects/explorer_logic/get_structure?project=${project}`);
        if (!res.ok) throw new Error("FS_DISCONNECT");
        const data = await res.json();

        const folders = data.tabs.map(tab => `
            <div class="directory-tab" id="tab-${tab}">
                <div class="folder-header" onclick="toggleUnroll('${tab}')" role="button" aria-expanded="false">
                    ${tab.toUpperCase()}
                </div>
                <div class="file-unroll-zone" id="zone-${tab}"></div>
            </div>
        `).join('');

        const files = data.nodes.map(file => createFileNode(file)).join('');

        container.innerHTML = folders + (files ? `<div class="root-files-divider" aria-hidden="true">-- SYSTEM_NODES --</div>` + files : '');

        if (!folders && !files) {
            container.innerHTML = '<div class="file-node">-- SYSTEM_EMPTY --</div>';
        }
    } catch (e) {
        console.error("FS_ERROR:", e);
        container.innerHTML = '<div class="error" style="color:red; padding:20px;">!! BACKEND_CONNECTION_FAILED !!</div>';
    }
}

async function toggleUnroll(folderName) {
    const project = document.body.getAttribute('data-project');
    const tab = document.getElementById(`tab-${folderName}`);
    const zone = document.getElementById(`zone-${folderName}`);

    if (tab.classList.contains('open')) {
        tab.classList.remove('open');
        tab.querySelector('.folder-header').setAttribute('aria-expanded', 'false');
        activeContext = "";
    } else {
        const res = await fetch(`/api/projects/explorer_logic/get_structure?project=${project}&path=${folderName}`);
        if (!res.ok) return;
        const data = await res.json();

        zone.innerHTML = data.nodes.map(file => createFileNode(file, folderName)).join('')
            || '<div class="file-node empty">-- NO_NODES_FOUND --</div>';

        tab.classList.add('open');
        tab.querySelector('.folder-header').setAttribute('aria-expanded', 'true');
        activeContext = folderName;
    }
}

// --- 2. THE TERMINAL HUD ---
let commandHistory = [];
let historyIndex = -1;

function announceToScreenReader(message) {
    let announcer = document.getElementById('sr-announcer');
    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'sr-announcer';
        announcer.className = 'sr-only';
        announcer.setAttribute('aria-live', 'assertive');
        announcer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(announcer);
    }
    announcer.textContent = '';
    setTimeout(() => {
        announcer.textContent = message;
    }, 50);
}

function toggleTerminal() {
    const term = document.getElementById('terminal-overlay');
    const input = document.getElementById('terminal-input');
    if (!term) return;

    const computedDisplay = window.getComputedStyle ? window.getComputedStyle(term).display : term.style.display;
    const isHidden = computedDisplay === 'none' || term.style.display === 'none' || term.style.display === '';

    if (isHidden) {
        term.style.display = 'flex';
        const promptEl = document.getElementById('terminal-prompt');
        if (promptEl) promptEl.innerText = `${activeContext || 'root'}>`;
        if (input) {
            setTimeout(() => {
                input.focus();
                input.select();
            }, 60);
        }
        announceToScreenReader("CLI Terminal opened. Type a command, or press Escape to close.");
    } else {
        term.style.display = 'none';
        announceToScreenReader("CLI Terminal closed.");
    }
}

window.addEventListener('keydown', (e) => {
    const isT = (e.key && e.key.toLowerCase() === 't') || e.code === 'KeyT';
    const isCtrlAltT = (e.ctrlKey || e.metaKey) && e.altKey && isT;
    const isAltT = e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && isT;

    if (isCtrlAltT || isAltT) {
        e.preventDefault();
        e.stopPropagation();
        toggleTerminal();
    } else if (e.key === 'Escape') {
        const term = document.getElementById('terminal-overlay');
        if (term && (term.style.display === 'flex' || (window.getComputedStyle && window.getComputedStyle(term).display === 'flex'))) {
            e.preventDefault();
            toggleTerminal();
        }
    }
});

function setupTerminalInput() {
    const input = document.getElementById('terminal-input');
    if (!input) return;
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter' && input.value.trim() !== '') {
            const cmd = input.value.trim();
            commandHistory.push(cmd);
            historyIndex = commandHistory.length;
            input.value = '';
            announceToScreenReader("Executing: " + cmd);
            await executeCommand(cmd);
        } else if (e.key === 'ArrowUp') {
            if (commandHistory.length > 0 && historyIndex > 0) {
                historyIndex--;
                input.value = commandHistory[historyIndex];
                setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0);
            }
        } else if (e.key === 'ArrowDown') {
            if (historyIndex < commandHistory.length - 1) {
                historyIndex++;
                input.value = commandHistory[historyIndex];
            } else {
                historyIndex = commandHistory.length;
                input.value = '';
            }
        }
    });
}

async function executeCommand(cmd) {
    const project = document.body.getAttribute('data-project');
    const out = document.getElementById('terminal-output');
    
    if (cmd.toLowerCase() === 'clear') {
        if (out) out.innerHTML = '';
        return;
    }
    if (cmd.toLowerCase() === 'exit') {
        toggleTerminal();
        return;
    }

    let runningIndicator = null;
    if (out) {
        out.innerHTML += `<div style="color:#888;">> ${cmd}</div>`;
        runningIndicator = document.createElement('div');
        runningIndicator.style.color = '#ffb700';
        runningIndicator.textContent = cmd.startsWith('agy') ? '⏳ Running agy CLI agent...' : '⏳ Executing...';
        out.appendChild(runningIndicator);
        out.scrollTop = out.scrollHeight;
    }

    try {
        const res = await fetch('/api/projects/explorer_logic/terminal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd, project: project, path: activeContext })
        });
        const data = await res.json();
        if (runningIndicator && runningIndicator.parentNode) {
            runningIndicator.remove();
        }
        if (out) {
            const resultDiv = document.createElement('div');
            resultDiv.textContent = data.output || '';
            if (data.returncode !== undefined && data.returncode !== 0) {
                resultDiv.style.color = '#ff5555';
            }
            out.appendChild(resultDiv);
            out.scrollTop = out.scrollHeight;
            const preview = (data.output || '').trim().slice(0, 120);
            announceToScreenReader("Command finished. " + (preview || "No output."));
        }
        if (!cmd.startsWith('cat') && !cmd.startsWith('agy')) loadFolders();
    } catch (e) {
        if (runningIndicator && runningIndicator.parentNode) {
            runningIndicator.remove();
        }
        if (out) out.innerHTML += `<div style="color:red;">!! OS_BRIDGE_FAULT: ${e.message} !!</div>`;
        announceToScreenReader("Error executing command: " + e.message);
    }
}
 * FIXED BRIDGE: Opens the Surgery interface in a NEW TAB
 */
function openSurgery(path) {
    const project = document.body.getAttribute('data-project');
    const url = `/api/projects/surgery/interface/${project}?file=${encodeURIComponent(path)}`;
    window.open(url, '_blank');
}

function setupDragAndDrop() {
    const zone = document.getElementById('explorer-view');
    if (!zone) return;
    zone.addEventListener('dragover', (e) => e.preventDefault());
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
    });
}