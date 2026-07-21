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
window.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 't') {
        const term = document.getElementById('terminal-overlay');
        const input = document.getElementById('terminal-input');
        const isHidden = term.style.display === 'none' || term.style.display === '';

        if (isHidden) {
            term.style.display = 'flex';
            input.focus();
            document.getElementById('terminal-prompt').innerText = `${activeContext || 'root'}>`;
        } else {
            term.style.display = 'none';
        }
    }
});

function setupTerminalInput() {
    const input = document.getElementById('terminal-input');
    if (!input) return;
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter' && input.value.trim() !== '') {
            const cmd = input.value.trim();
            input.value = '';
            await executeCommand(cmd);
        }
    });
}

async function executeCommand(cmd) {
    const project = document.body.getAttribute('data-project');
    const out = document.getElementById('terminal-output');
    try {
        const res = await fetch('/api/projects/explorer_logic/terminal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd, project: project, path: activeContext })
        });
        const data = await res.json();
        if (out) {
            out.innerHTML += `<div style="color:#888;">> ${cmd}</div><div>${data.output}</div>`;
            out.scrollTop = out.scrollHeight;
        }
        if (!cmd.startsWith('cat')) loadFolders();
    } catch (e) {
        if (out) out.innerHTML += `<div style="color:red;">!! OS_BRIDGE_FAULT !!</div>`;
    }
}

/**
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