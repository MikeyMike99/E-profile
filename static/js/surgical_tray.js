/**
 * ARCHITECT_OS // SURGICAL_CORE v.2.9.0_STABLE
 * Optimized for Pre-Loaded Server-Side Content.
 */

const portal = () => document.getElementById('surgical-portal');
const editor = () => document.getElementById('surgical-editor');
const consoleLog = () => document.getElementById('surgical-console');

// Attributes injected by surgery.py
const projectName = document.body.getAttribute('data-project');

/** * CRITICAL: This must match the nested prefix in projects_mod.py:
 * /api/projects (from app.py) + /surgery_logic (from projects_mod.py)
 */
const API_BASE = "/api/projects/surgery_logic";

let currentLevel = "FILES";
let currentFile = document.body.getAttribute('data-initial-file') || "main.py";

/**
 * 1. INITIALIZE: Sync the dropdown structure with the pre-loaded content.
 */
async function initializeSurgery() {
    updateConsole("SYNCING_NODE_STRUCTURE...");

    if (!projectName || projectName === "None" || projectName === "null") {
        updateConsole("CRITICAL_ERROR: PROJECT_CONTEXT_LOST", true);
        return;
    }

    try {
        // We fetch the structure (files/blocks) for the dropdown.
        // The code itself is already in the editor thanks to Jinja2 {{ initial_content }}.
        const response = await fetch(`${API_BASE}/get_block_source?project=${projectName}&file=${currentFile}`);

        if (!response.ok) {
            const errorText = await response.text();
            if (errorText.includes("<!DOCTYPE")) {
                throw new Error("SERVER_ROUTE_MISMATCH (Check Blueprint Prefix)");
            }
            throw new Error(`HTTP_${response.status}`);
        }

        const data = await response.json();

        if (data.status === "success") {
            populatePortal(data.files, data.blocks);
            updateConsole(`SYSTEM_READY // NODE: ${projectName.toUpperCase()} // FILE: ${currentFile.toUpperCase()}`);
        } else {
            updateConsole("FS_ERROR: " + data.message, true);
        }
    } catch (err) {
        updateConsole("CONNECTION_FAILURE: " + err.message, true);
        console.error("Full Error:", err);
    }
}

/**
 * 2. PORTAL: Populate dropdown options
 */
function populatePortal(files, blocks) {
    let options = "";

    if (currentLevel === "BLOCKS") {
        options += '<option value="BACK:..">[ BACK_TO_FILE_LIST ]</option>';
        if (blocks && blocks.length > 0) {
            blocks.forEach(b => {
                options += `<option value="BLOCK:${b}">⚡ ${b}()</option>`;
            });
        } else {
            options += '<option disabled>-- NO_BLOCKS_FOUND --</option>';
        }
    } else {
        if (files && files.length > 0) {
            files.forEach(f => {
                const selected = (f === currentFile) ? "selected" : "";
                options += `<option value="FILE:${f}" ${selected}>📄 ${f.toUpperCase()}</option>`;
            });
        }
    }

    portal().innerHTML = options;
}

/**
 * 3. NAVIGATION: Handle switching files or blocks manually
 */
portal().addEventListener('change', async (e) => {
    const val = e.target.value;
    if (!val) return;

    const [type, name] = val.split(':');

    if (type === 'BACK') {
        currentLevel = "FILES";
        initializeSurgery();
    } else if (type === 'FILE') {
        currentFile = name;
        loadRawFile(name);
    } else if (type === 'BLOCK') {
        loadBlock(name);
    }
});

/**
 * 4. DRILL-DOWN: Press Enter to switch modes
 */
portal().addEventListener('keydown', async (e) => {
    if (e.key === "Enter") {
        const val = portal().value;
        if (!val) return;

        const [type, name] = val.split(':');

        if (type === "FILE") {
            currentLevel = "BLOCKS";
            currentFile = name;
            updateConsole(`EXPLORING_BLOCKS: ${name}...`);

            try {
                const res = await fetch(`${API_BASE}/get_block_source?project=${projectName}&file=${currentFile}`);
                const data = await res.json();

                if (data.status === "success") {
                    populatePortal(data.files, data.blocks);
                    if (data.blocks && data.blocks.length > 0) {
                        portal().value = `BLOCK:${data.blocks[0]}`;
                        loadBlock(data.blocks[0]);
                    } else {
                        updateConsole("NO_SURGICAL_MARKERS", true);
                    }
                }
            } catch (err) {
                updateConsole("DRILL_DOWN_FAILED", true);
            }
        } else if (type === "BACK") {
            currentLevel = "FILES";
            initializeSurgery();
        }
    }
});

/**
 * 5. DATA LOADERS
 */
async function loadRawFile(filename) {
    updateConsole(`READING_FILE: ${filename}...`);
    try {
        const res = await fetch(`${API_BASE}/get_raw_file?project=${projectName}&file=${filename}`);
        const data = await res.json();
        if (data.status === "success") {
            editor().value = data.content;
            editor().dataset.currentTarget = "";
            updateConsole(`FILE_LOADED: ${filename}`);
        }
    } catch (err) {
        updateConsole("LOAD_FILE_FAILED", true);
    }
}

async function loadBlock(blockName) {
    updateConsole(`EXTRACTING_BLOCK: ${blockName}...`);
    try {
        const res = await fetch(`${API_BASE}/get_block_source?project=${projectName}&file=${currentFile}&target=${blockName}`);
        const data = await res.json();

        if (data.status === "success") {
            editor().value = data.code;
            editor().dataset.currentTarget = blockName;
            updateConsole(`READY_FOR_SURGERY: ${blockName}`);
        }
    } catch (err) {
        updateConsole("BLOCK_EXTRACTION_FAILED", true);
    }
}

/**
 * 6. EXECUTE: Patching Logic
 */
async function executeSurgery() {
    const code = editor().value;
    const target = editor().dataset.currentTarget;

    updateConsole("INITIATING_RECONSTRUCTION...");

    try {
        const response = await fetch(`${API_BASE}/apply_patch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: projectName,
                file: currentFile,
                target: target,
                code: code
            })
        });

        const result = await response.json();
        if (result.status === "success") {
            updateConsole(`SUCCESS: ${result.message}`);
            editor().style.borderLeft = "5px solid #00ff88";
            setTimeout(() => editor().style.borderLeft = "none", 1000);
        } else {
            updateConsole("SURGERY_FAILED: " + result.message, true);
        }
    } catch (err) {
        updateConsole("CRITICAL_OS_FAULT: " + err.message, true);
    }
}

function updateConsole(msg, isError = false) {
    consoleLog().textContent = `> ${msg.toUpperCase()}`;
    consoleLog().style.color = isError ? "#ff0055" : "#00ff88";
}

function closeAndSave() {
    // If opened as a popup, this closes the window.
    window.close();
}

/**
 * 7. EXECUTE: Two-way Git Sync
 */
async function executeGitSync() {
    updateConsole("INITIATING_GIT_SYNC...");
    try {
        const response = await fetch(`/api/projects/explorer_logic/git_sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        if (response.ok && result.output && !result.output.includes("EXCEPTION:")) {
            updateConsole("GIT_SYNC_SUCCESSFUL");
            console.log(result.output);
        } else {
            updateConsole("GIT_SYNC_FAILED", true);
            console.error(result.output);
        }
    } catch (err) {
        updateConsole("GIT_SYNC_CONNECTION_ERROR", true);
    }
}

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 's' && !e.shiftKey) {
        e.preventDefault();
        executeSurgery();
    }
    if (e.ctrlKey && e.shiftKey && (e.key === 'S' || e.key === 's')) {
        e.preventDefault();
        executeGitSync();
    }
    if (e.key === "Escape") closeAndSave();
});

// Run sync on load
window.onload = initializeSurgery;