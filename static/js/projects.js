/**
 * ARCHITECT_OS // PROJECTS_DASHBOARD_LOGIC
 * Version: 2.8.6.STABLE_SYNC
 * * All routes use the /api/projects/ prefix for Blueprint compatibility.
 */

let activeVoteType = "";
let sessionState = { voted: new Set(), tested: new Set() };

// --- 1. SEARCH & FILTERING ---
function filterProjects() {
    const input = document.getElementById('project-search').value.toLowerCase();
    const cards = document.querySelectorAll('.project-card');
    let visibleCount = 0;

    cards.forEach(card => {
        // Using dataset for cleaner name retrieval
        const name = card.dataset.name ? card.dataset.name.toLowerCase() : card.id.replace('card-', '').toLowerCase();
        const isMatch = name.includes(input);
        card.style.display = isMatch ? "" : "none";
        if (isMatch) visibleCount++;
    });
    announce(`${visibleCount} NODES_FILTERED`);
}

// --- 2. ACCORDION ENGINE ---
function toggleProject(name) {
    const card = document.getElementById(`card-${name}`);
    const content = document.getElementById(`details-${name}`);
    const label = document.getElementById(`label-${name}`);

    if (!content) return; // Safety check
    const isOpen = content.style.display === 'block';

    // Close all other open details first (Accordion Style)
    document.querySelectorAll('.details-content-glass').forEach(el => {
        el.style.display = 'none';
        const otherName = el.id.replace('details-', '');
        const otherCard = document.getElementById(`card-${otherName}`);
        if (otherCard) otherCard.classList.remove('is-open');
        const otherLabel = document.getElementById(`label-${otherName}`);
        if (otherLabel) otherLabel.innerHTML = '<span class="symbol">[ + ]</span> VIEW_NODE_DETAILS';
    });

    if (!isOpen) {
        content.style.display = 'block';
        card.classList.add('is-open');
        label.innerHTML = '<span class="symbol">[ - ]</span> HIDE_NODE_DETAILS';
        content.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// --- 3. THE GLOBAL KEY LISTENER ---
document.addEventListener('keydown', async (e) => {
    const active = document.activeElement;
    // Press '/' to focus search unless typing in an input
    if (e.key === '/' && active.tagName !== 'INPUT') {
        e.preventDefault();
        const searchInput = document.getElementById('project-search');
        if (searchInput) searchInput.focus();
    }
});

// --- 4. ENGINE LAUNCH (TESTING) ---
function lockTestButton(btn, name, isAdmin, status) {
    const url = `/api/projects/execute/${name}`;

    if (!isAdmin && (sessionState.tested.has(name) || status === 'locked')) {
        alert("ACCESS_EXPIRED");
        return;
    }

    // Launching the engine in a new tab
    window.open(url, '_blank');

    if (!isAdmin) {
        sessionState.tested.add(name);
        btn.disabled = true;
        btn.innerHTML = "🔒 NODE_LOCKED";
    }
}

// --- 5. FEEDBACK SYSTEM ---
function handleFeedbackKey(event, name, isAdmin) {
    if (event.key === 'Enter') confirmVote(name);
    if (event.key === 'Escape') cancelFeedback(name);
}

function initVote(name, type) {
    activeVoteType = type;
    const voteArea = document.getElementById(`vote-area-${name}`);
    if (voteArea) voteArea.style.display = 'none';

    const input = document.getElementById(`edit-${name}`);
    if (input) {
        input.style.display = 'block';
        setTimeout(() => input.focus(), 50);
    }
}

function cancelFeedback(name) {
    const input = document.getElementById(`edit-${name}`);
    if (input) {
        input.value = "";
        input.style.display = 'none';
    }
    const voteArea = document.getElementById(`vote-area-${name}`);
    if (voteArea) voteArea.style.display = 'flex';
}

async function confirmVote(name) {
    const editInput = document.getElementById(`edit-${name}`);
    const note = editInput ? editInput.value : "";

    const res = await fetch('/api/projects/submit_feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: name, vote: activeVoteType, note: note })
    });
    if (res.ok) {
        announce("SYNC_SUCCESS");
        cancelFeedback(name);
    }
}

// --- 6. ADMIN SYNC & ACTIONS ---
async function manualJump(name, newValue) {
    const list = document.getElementById('project-list');
    if (!list) return;

    const cards = Array.from(list.querySelectorAll('.project-card'));
    const targetCard = document.getElementById(`card-${name}`);
    if (!targetCard) return;

    const oldIndex = cards.indexOf(targetCard);
    let newIndex = parseInt(newValue) - 1;
    newIndex = Math.max(0, Math.min(newIndex, cards.length - 1));

    if (newIndex !== oldIndex) {
        // Move in DOM
        if (newIndex >= cards.length - 1) {
            list.appendChild(targetCard);
        } else {
            const referenceNode = newIndex > oldIndex ? cards[newIndex + 1] : cards[newIndex];
            list.insertBefore(targetCard, referenceNode);
        }
    }

    // Collect new order and update visual numbers
    const updatedCards = Array.from(list.querySelectorAll('.project-card'));
    const order = updatedCards.map((c, index) => {
        const id = c.id.replace('card-', '');
        const input = document.getElementById('pos-input-' + id);
        if (input) input.value = index + 1;
        return id;
    });

    await fetch('/api/projects/reorder_projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: order })
    });
    announce("ORDER_SYNCHRONIZED");
}

async function buildProject() {
    const input = document.getElementById('new-project-name');
    const val = input ? input.value.trim() : "";
    if (!val) return;

    announce("CONSTRUCTING_NODE...");
    const res = await fetch('/api/projects/build_project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: val })
    });

    if (res.ok) {
        location.reload();
    } else {
        announce("CONSTRUCTION_FAILED");
    }
}

async function deleteProject(name) {
    if (confirm(`DECOMMISSION ${name}?`)) {
        announce(`PURGING_${name}...`);
        const res = await fetch(`/api/projects/delete_project/${name}`, { method: 'POST' });
        if (res.ok) {
            const card = document.getElementById(`card-${name}`);
            if (card) card.remove();
            announce("NODE_PURGED");
        } else {
            announce("PURGE_FAILED");
        }
    }
}

// --- 7. UTILS & NAVIGATION ---
function announce(msg) {
    const a = document.getElementById('live-status-announcer');
    if (a) a.textContent = `[SYSTEM]: ${msg}`;
}

/**
 * FIXED: Opens Code Editor (Surgery) in a NEW TAB
 */
function openSurgery(name) {
    const cleanName = String(name).trim();
    const target = (cleanName === 'root' || cleanName === 'SYSTEM_CORE') ? 'root' : cleanName;
    const url = `/api/projects/surgery/interface/${target}`;
    window.open(url, '_blank');
}

/**
 * FIXED: Opens File Manager (Explorer) in a NEW TAB
 */
function openExplorer(name) {
    const cleanName = String(name).trim();
    const target = (cleanName === 'root' || cleanName === 'SYSTEM_CORE') ? 'root' : cleanName;
    const url = `/api/projects/explorer/${target}`;
    window.open(url, '_blank');
}