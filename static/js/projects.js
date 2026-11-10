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

// --- 8. LOCAL AGENT HTTP CONSOLE ENGINE (WITH 2S HEARTBEAT) ---
let currentAgentProject = 'root';
let agentPollTimer = null;
let agentLastSeq = 0;
let isAgentTaskRunning = false;
let currentAgentBubble = null;
let activeAgentBaseUrl = null;

// e_profile is only a front end: the agent's brain and back end run at Siraugga's domain, and this
// console talks to it there directly. credentials:'include' sends mikeytech.dev's own cookies, so a
// visitor is the same person here as on mikeytech.dev.
const SIRAUGGA_URL = 'https://mikeytech.dev';

async function resolveAgentBaseUrl() {
    activeAgentBaseUrl = SIRAUGGA_URL;
    return SIRAUGGA_URL;
}

function openAgent(name) {
    toggleAgentDrawer(name, true);
}

function toggleAgentDrawer(name, forceOpen) {
    const drawer = document.getElementById('agent-drawer');
    if (!drawer) return;

    if (name) {
        const cleanName = String(name).trim();
        currentAgentProject = (cleanName === 'root' || cleanName === 'SYSTEM_CORE') ? 'root' : cleanName;
        const scopeBadge = document.getElementById('agent-scope-badge');
        if (scopeBadge) {
            scopeBadge.textContent = `AGENT_SCOPE: ${currentAgentProject.toUpperCase()}`;
        }
    }

    const isOpen = drawer.style.display !== 'none';
    const shouldOpen = forceOpen !== undefined ? forceOpen : !isOpen;

    if (shouldOpen) {
        drawer.style.display = 'flex';
        drawer.setAttribute('aria-hidden', 'false');
        announce(`LOCAL_AGENT_CONSOLE_ENGAGED [SCOPE: ${currentAgentProject}]`);
        const input = document.getElementById('agent-prompt-input');
        if (input) {
            setTimeout(() => input.focus(), 80);
            initAgentInputKeyHandler();
        }
        startAgentHeartbeatAndPolling();
    } else {
        closeAgentDrawer();
    }
}

function closeAgentDrawer() {
    const drawer = document.getElementById('agent-drawer');
    if (drawer) {
        drawer.style.display = 'none';
        drawer.setAttribute('aria-hidden', 'true');
    }
    if (agentPollTimer) {
        clearInterval(agentPollTimer);
        agentPollTimer = null;
    }
}

function openFullAgentPortal() {
    window.open(SIRAUGGA_URL + '/', '_blank', 'noopener');   // the full Siraugga Command Center
}

function initAgentInputKeyHandler() {
    const input = document.getElementById('agent-prompt-input');
    if (!input || input.__keyAttached) return;
    input.__keyAttached = true;
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (e.shiftKey) return;
            e.preventDefault();
            if (e.ctrlKey || e.altKey || e.metaKey) {
                submitAgentPrompt('queue');
            } else {
                submitAgentPrompt(isAgentTaskRunning ? 'steer' : 'normal');
            }
        }
    });
}

function appendAgentMessage(text, role) {
    const feed = document.getElementById('agent-chat-feed');
    if (!feed) return null;
    const bubble = document.createElement('div');
    bubble.className = `agent-msg-bubble ${role}`;
    bubble.textContent = text;
    feed.appendChild(bubble);
    feed.scrollTop = feed.scrollHeight;
    return bubble;
}

function appendAgentAction(title, output, isDone) {
    const feed = document.getElementById('agent-chat-feed');
    if (!feed) return;
    const box = document.createElement('div');
    box.className = 'agent-action-box';
    box.innerHTML = `<span style="color: var(--accent-teal); font-weight: bold;">[TOOL]</span> ${escapeHtml(title || 'Action')}`;
    if (output) {
        const outPre = document.createElement('div');
        outPre.style.fontSize = '0.75rem';
        outPre.style.opacity = '0.85';
        outPre.style.marginTop = '4px';
        outPre.style.maxHeight = '120px';
        outPre.style.overflow = 'auto';
        outPre.textContent = output.length > 500 ? (output.substring(0, 500) + '... [truncated]') : output;
        box.appendChild(outPre);
    }
    feed.appendChild(box);
    feed.scrollTop = feed.scrollHeight;
}

function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function submitAgentPrompt(mode) {
    const input = document.getElementById('agent-prompt-input');
    if (!input) return;
    const prompt = input.value.trim();
    if (!prompt) return;

    input.value = '';
    const modelSelect = document.getElementById('agent-model-select');
    const selectedModel = modelSelect ? modelSelect.value : 'Claude Opus 5.5 (Low)';

    const effectiveMode = mode || (isAgentTaskRunning ? 'steer' : 'normal');
    const prefix = effectiveMode === 'queue' ? '[QUEUE] ' : (effectiveMode === 'steer' ? '[STEER] ' : '');
    appendAgentMessage(`${prefix}${prompt}`, 'user');

    currentAgentBubble = appendAgentMessage('Thinking...', 'agent');
    setAgentRunningState(true);

    const base = await resolveAgentBaseUrl();
    const token = localStorage.getItem('agy_auth_token') || '';

    try {
        const res = await fetch(`${base}/api/chat`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : ''
            },
            body: JSON.stringify({
                prompt: prompt,
                model: selectedModel,
                project: currentAgentProject,
                mode: effectiveMode,
                type: 'prompt'
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            if (currentAgentBubble && err.terms_required) {
                currentAgentBubble.textContent = '⚠️ Please accept Siraugga\'s Terms & Privacy first, then try again: ';
                const link = document.createElement('a');
                link.href = SIRAUGGA_URL + '/';
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = 'open Siraugga';
                currentAgentBubble.appendChild(link);
            } else if (currentAgentBubble) {
                currentAgentBubble.textContent = `⚠️ Error starting task: ${err.error || res.statusText}`;
            }
            setAgentRunningState(false);
            return;
        }

        announce(`PROMPT_DISPATCHED [${effectiveMode.toUpperCase()}]`);
    } catch (e) {
        if (currentAgentBubble) {
            currentAgentBubble.textContent = `⚠️ Network Error: ${e.message}. Verifying local connection...`;
        }
        setAgentRunningState(false);
    }
}

async function cancelAgentTask() {
    const base = await resolveAgentBaseUrl();
    try {
        const token = localStorage.getItem('agy_auth_token') || '';
        await fetch(`${base}/api/kill`, {
            method: 'POST', credentials: 'include',
            headers: Object.assign({ 'Content-Type': 'application/json' }, token ? { 'Authorization': `Bearer ${token}` } : {})
        });
        appendAgentMessage('[Task Cancel Requested by User]', 'agent');
        setAgentRunningState(false);
    } catch (e) {}
}

function setAgentRunningState(running) {
    isAgentTaskRunning = running;
    const statusBadge = document.getElementById('agent-status-badge');
    const sendBtn = document.getElementById('agent-send-btn');
    const cancelBtn = document.getElementById('agent-cancel-btn');

    if (statusBadge) {
        statusBadge.textContent = running ? '● RUNNING' : '● IDLE';
        statusBadge.style.borderColor = running ? '#f59e0b' : 'var(--border-default)';
        statusBadge.style.color = running ? '#f59e0b' : 'var(--text-secondary)';
    }
    if (sendBtn) {
        sendBtn.textContent = running ? 'STEER' : 'EXECUTE';
        sendBtn.className = running ? 'btn-launch-pill status-in_development' : 'btn-launch-pill status-ready';
    }
    if (cancelBtn) {
        cancelBtn.style.display = running ? 'inline-block' : 'none';
    }
}

function startAgentHeartbeatAndPolling() {
    if (agentPollTimer) clearInterval(agentPollTimer);

    const hbBadge = document.getElementById('agent-heartbeat-badge');
    let consecutiveFailures = 0;

    let pollInFlight = false;
    let primed = false;                      // first poll only notes where the stream is
    const poll = async () => {
        if (pollInFlight) return;            // a slow round trip must not start a second poll
        pollInFlight = true;
        try { await pollOnce(); } finally { pollInFlight = false; }
    };
    const pollOnce = async () => {
        const base = await resolveAgentBaseUrl();
        const token = localStorage.getItem('agy_auth_token') || '';

        try {
            const hbRes = await fetch(`${base}/api/heartbeat`, {
                credentials: 'include',
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            });
            if (hbRes.ok) {
                const hbData = await hbRes.json();
                consecutiveFailures = 0;
                if (hbBadge) {
                    if (hbData.bridge_online === false) {
                        hbBadge.textContent = `● BRIDGE: STANDBY (CORE OFFLINE)`;
                        hbBadge.className = 'badge-pulse heartbeat-dead';
                    } else {
                        const label = hbData.worker_id ? `● BRIDGE: ACTIVE [${escapeHtml(hbData.worker_id)}]` : `● BRIDGE: ACTIVE [2s]`;
                        hbBadge.textContent = label;
                        hbBadge.className = 'badge-pulse pulse-beat';
                        setTimeout(() => {
                            if (hbBadge) hbBadge.className = 'badge-pulse';
                        }, 400);
                    }
                }
                if (hbData.is_running !== undefined && hbData.is_running !== isAgentTaskRunning) {
                    setAgentRunningState(hbData.is_running);
                }
            } else {
                throw new Error(`HTTP ${hbRes.status}`);
            }
        } catch (e) {
            consecutiveFailures++;
            if (consecutiveFailures >= 3 && hbBadge) {
                hbBadge.textContent = `● BRIDGE: OFFLINE`;
                hbBadge.className = 'badge-pulse heartbeat-dead';
            }
        }

        try {
            const streamRes = await fetch(`${base}/api/stream?since_seq=${encodeURIComponent(agentLastSeq || 0)}`, {
                credentials: 'include',
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            });
            if (streamRes.ok) {
                const streamData = await streamRes.json();
                if (!primed) {
                    // Opening the console starts from "now": earlier replies from Siraugga's
                    // stream are not replayed into a new answer.
                    primed = true;
                    if (typeof streamData.last_seq === 'number' && streamData.last_seq > agentLastSeq) {
                        agentLastSeq = streamData.last_seq;
                    }
                    return;
                }
                if (streamData.is_running !== undefined && streamData.is_running !== isAgentTaskRunning) {
                    setAgentRunningState(streamData.is_running);
                }
                if (Array.isArray(streamData.messages) && streamData.messages.length > 0) {
                    streamData.messages.forEach(msg => {
                        if (typeof msg.seq === 'number') {
                            if (msg.seq <= agentLastSeq) return;   // already shown (overlapping polls)
                            agentLastSeq = msg.seq;
                        }
                        handleAgentStreamMessage(msg);
                    });
                }
                if (typeof streamData.last_seq === 'number' && streamData.last_seq > agentLastSeq) {
                    agentLastSeq = streamData.last_seq;
                }
            }
        } catch (e) {}
    };

    poll();
    agentPollTimer = setInterval(poll, 2000);
}

function handleAgentStreamMessage(msg) {
    const feed = document.getElementById('agent-chat-feed');
    if (!feed) return;

    if (msg.type === 'agent_chunk') {
        const chunk = msg.chunk || '';
        if (currentAgentBubble) {
            if (currentAgentBubble.textContent === 'Thinking...') {
                currentAgentBubble.textContent = '';
            }
            currentAgentBubble.textContent += chunk;
        } else {
            currentAgentBubble = appendAgentMessage(chunk, 'agent');
        }
        feed.scrollTop = feed.scrollHeight;
    } else if (msg.type === 'action_start') {
        const act = msg.action || {};
        appendAgentAction(act.announcement || act.friendly_name || 'Executing tool...', '', false);
    } else if (msg.type === 'action_done') {
        const act = msg.action || {};
        appendAgentAction(act.announcement || act.friendly_name || 'Tool completed', act.output, true);
    } else if (msg.type === 'agent_thought') {
        const thought = msg.thought || '';
        if (thought) {
            const tEl = document.createElement('div');
            tEl.style.fontSize = '0.78rem';
            tEl.style.color = 'var(--text-tertiary)';
            tEl.style.fontStyle = 'italic';
            tEl.style.padding = '4px 8px';
            tEl.textContent = `💭 ${thought}`;
            feed.appendChild(tEl);
            feed.scrollTop = feed.scrollHeight;
        }
    } else if (msg.type === 'agent_done' || msg.type === 'agent_stop') {
        setAgentRunningState(false);
        currentAgentBubble = null;
        announce("AGENT_TASK_COMPLETE");
    }
}
