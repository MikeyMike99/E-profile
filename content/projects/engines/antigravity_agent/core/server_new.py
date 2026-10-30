import json
import asyncio
import os
import time
import html
from quart import Quart, websocket, render_template_string

app = Quart(__name__)

HTML_CLIENT = """<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Antigravity Dev Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        .markdown-body { font-size: 0.95rem; line-height: 1.6; }
        .markdown-body p { margin-bottom: 0.75rem; }
        .markdown-body p:last-child { margin-bottom: 0; }
        .markdown-subheading { font-weight: 600; margin-top: 1rem; margin-bottom: 0.4rem; color: #f1f5f9; }
        .markdown-body ul, .markdown-body ol { margin-left: 1.5rem; margin-bottom: 0.75rem; list-style-type: disc; }
        .markdown-body ol { list-style-type: decimal; }
        .markdown-body li { margin-bottom: 0.25rem; }
        .markdown-body pre { background: #0b1120; padding: 0.85rem; border-radius: 0.5rem; overflow-x: auto; margin-bottom: 0.75rem; border: 1px solid #1e293b; font-size: 0.85rem; }
        .markdown-body code { background: #1e293b; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.875em; }
        .markdown-body pre code { background: transparent; padding: 0; }
        .markdown-body blockquote { border-left: 4px solid #0d9488; padding-left: 1rem; margin-bottom: 0.75rem; color: #94a3b8; font-style: italic; }
        .markdown-body table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; font-size: 0.875rem; }
        .markdown-body th, .markdown-body td { border: 1px solid #334155; padding: 0.45rem; text-align: left; }
        .markdown-body th { background: #1e293b; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border-width: 0; }
        .skip-link:focus { position: static; width: auto; height: auto; padding: 0.5rem 1rem; clip: auto; white-space: normal; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 h-full flex flex-col font-sans overflow-hidden select-text">

    <!-- Screen Reader Live Region for Announcements -->
    <div id="sr-announcer" role="status" aria-live="polite" aria-atomic="true" class="sr-only"></div>
    <div id="sr-alerts" role="alert" aria-live="assertive" aria-atomic="true" class="sr-only"></div>

    <!-- Skip Links for Keyboard / Screen Reader Navigation -->
    <a href="#prompt" class="sr-only skip-link bg-teal-600 text-white font-medium z-50 rounded m-2 focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-teal-400">Skip to prompt input</a>
    <a href="#chat-feed" class="sr-only skip-link bg-teal-600 text-white font-medium z-50 rounded m-2 focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-teal-400">Skip to conversation messages</a>

    <!-- Header Landmark -->
    <header role="banner" class="bg-slate-900/95 backdrop-blur border-b border-slate-800 px-6 py-3 flex items-center justify-between shrink-0 shadow-sm">
        <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-teal-500 to-cyan-400 flex items-center justify-center font-black text-slate-950 text-sm shadow-md shadow-teal-500/20" aria-hidden="true">
                AG
            </div>
            <div>
                <h1 class="text-base font-bold text-white leading-tight flex items-center gap-2">
                    Antigravity Dev Portal
                    <span class="text-xs font-normal px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800/80 text-teal-400">Background Resilient</span>
                </h1>
                <p class="text-xs text-slate-400 font-mono">Workspace: antigravity_test</p>
            </div>
        </div>

        <div class="flex items-center gap-3">
            <!-- Model Selection Dropdown -->
            <div class="flex items-center gap-2 bg-slate-950/80 border border-slate-700/80 rounded-lg px-2.5 py-1">
                <label for="model-selector" class="text-xs font-semibold text-teal-400 shrink-0">Model:</label>
                <select id="model-selector" onchange="onModelChange()" aria-label="Select AI Model" class="bg-transparent text-slate-200 text-xs font-medium focus:outline-none cursor-pointer pr-1">
                    <option value="gemini-3.8-flash-high" selected>Gemini 3.8 Flash (Fast &amp; Responsive)</option>
                    <option value="gemini-3.1-pro-high">Gemini 3.1 Pro (Deep Reasoning &amp; Planning)</option>
                    <option value="claude-sonnet-4-6">Claude Sonnet 4.6 (Thinking)</option>
                    <option value="claude-opus-4-6-thinking">Claude Opus 4.6 (Complex Coding)</option>
                    <option value="gpt-oss-120b-medium">GPT-OSS 120B (Medium)</option>
                </select>
            </div>

            <!-- Connection Status -->
            <div id="connection-badge" role="status" aria-label="Connection Status" class="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 border border-slate-700 text-yellow-400">
                <span class="w-2 h-2 rounded-full bg-yellow-400" aria-hidden="true"></span>
                <span id="connection-text">Connecting...</span>
            </div>

            <!-- Clear Chat Button -->
            <button onclick="clearHistory()" aria-label="Clear chat history display" class="text-xs px-2.5 py-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded border border-slate-700/60 transition-colors">
                Clear View
            </button>
        </div>
    </header>

    <!-- Active Task Progress Bar (Shown during execution) -->
    <div id="task-banner" role="region" aria-label="Current Task Status" class="hidden bg-slate-900 border-b border-teal-800/60 px-6 py-2.5 flex items-center justify-between shadow-inner shrink-0">
        <div class="flex items-center gap-3 text-sm">
            <span class="relative flex h-3 w-3" aria-hidden="true">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-3 w-3 bg-teal-500"></span>
            </span>
            <div>
                <div class="flex items-center gap-2">
                    <span class="font-semibold text-teal-300">Task Running</span>
                    <span class="text-slate-500" aria-hidden="true">•</span>
                    <span id="timer-display" class="font-mono text-teal-400 font-medium">00:00</span>
                    <span class="text-xs text-slate-400 font-mono" id="task-model-badge">Gemini 3.8 Flash</span>
                </div>
                <div class="text-xs text-slate-400 flex items-center gap-2">
                    <span class="truncate max-w-md text-slate-300 font-medium" id="current-task-prompt">Executing...</span>
                    <span class="text-slate-600" aria-hidden="true">|</span>
                    <span class="text-emerald-400/90 text-xs">Background process resilient to reloads</span>
                </div>
            </div>
        </div>

        <button onclick="cancelTask()" id="cancel-btn" aria-label="Cancel active task" class="text-xs font-medium px-3 py-1.5 rounded-md bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 transition-colors flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            Cancel Task
        </button>
    </div>

    <!-- Main Content Area -->
    <main id="main-content" class="flex-1 flex flex-col overflow-hidden max-w-5xl mx-auto w-full border-x border-slate-800/80 bg-slate-950/50">
        <!-- Messages Feed Landmark -->
        <section id="chat-feed" role="feed" aria-label="Conversation Feed" class="flex-1 overflow-y-auto p-6 space-y-5 scroll-smooth">
            <!-- Initial Welcome Card -->
            <article class="p-4 rounded-xl bg-slate-900/90 text-slate-300 border border-slate-800 shadow-sm flex gap-3 message-welcome" aria-labelledby="welcome-heading">
                <div class="w-7 h-7 rounded bg-teal-900/60 border border-teal-700/50 text-teal-300 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5" aria-hidden="true">
                    AG
                </div>
                <div class="text-sm">
                    <h2 id="welcome-heading" class="font-bold text-teal-400 text-sm mb-1">Antigravity Dev Portal Ready</h2>
                    <p class="mb-2">Accessible interface with live screen reader announcements, clean heading navigation (press <strong>H</strong> or <strong>2</strong> to navigate messages), collapsed action logs, and model selection.</p>
                    <p class="text-xs text-slate-400">Tasks run as resilient background processes. Page reloads or disconnections will not cancel active tasks.</p>
                </div>
            </article>
        </section>

        <!-- Chat Input Bar -->
        <div class="p-4 bg-slate-900 border-t border-slate-800/80 shrink-0">
            <form id="chat-form" role="form" aria-label="Send prompt" class="flex gap-2.5 items-end" onsubmit="sendPrompt(event)">
                <div class="flex-1 relative">
                    <label for="prompt" class="sr-only">Enter instructions for Antigravity</label>
                    <textarea 
                        id="prompt" 
                        rows="2"
                        class="w-full bg-slate-950 text-slate-100 rounded-lg px-4 py-2.5 border border-slate-700 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 resize-none text-sm placeholder-slate-500" 
                        placeholder="Enter instructions (e.g. modify file, test feature, refactor code)... Press Enter to execute."
                        onkeydown="handleKeyDown(event)"></textarea>
                    <div class="text-[11px] text-slate-500 absolute bottom-2 right-3 pointer-events-none" aria-hidden="true">
                        Enter to run • Shift+Enter for newline
                    </div>
                </div>
                <button 
                    type="submit" 
                    id="send-btn" 
                    aria-label="Execute prompt"
                    class="bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg px-6 py-2.5 transition-colors h-[58px] flex items-center justify-center gap-2 shadow-sm shrink-0">
                    <span id="send-btn-spinner" class="hidden w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" aria-hidden="true"></span>
                    <span id="send-btn-text">Execute</span>
                </button>
            </form>
        </div>
    </main>

    <script>
        // Custom Marked renderer to avoid markdown headings polluting screen reader H/2 navigation
        var renderer = new marked.Renderer();
        renderer.heading = function(arg1, arg2) {
            var text = '';
            var depth = 3;
            if (typeof arg1 === 'object' && arg1 !== null) {
                depth = arg1.depth || 3;
                text = arg1.text || (this.parser && this.parser.parseInline ? this.parser.parseInline(arg1.tokens) : '');
            } else {
                text = arg1 || '';
                depth = arg2 || 3;
            }
            var safeLevel = Math.min(depth + 2, 6); // Renders as h3 - h6
            return '<h' + safeLevel + ' class="markdown-subheading text-sm text-teal-200 mt-3 mb-1.5 font-bold">' + text + '</h' + safeLevel + '>';
        };
        marked.use({ renderer: renderer, breaks: true, gfm: true });

        var ws = null;
        var chatFeed = document.getElementById('chat-feed');
        var connBadge = document.getElementById('connection-badge');
        var connText = document.getElementById('connection-text');
        var sendBtn = document.getElementById('send-btn');
        var sendBtnText = document.getElementById('send-btn-text');
        var sendBtnSpinner = document.getElementById('send-btn-spinner');
        var inputEl = document.getElementById('prompt');
        var taskBanner = document.getElementById('task-banner');
        var timerDisplay = document.getElementById('timer-display');
        var currentTaskPromptEl = document.getElementById('current-task-prompt');
        var taskModelBadge = document.getElementById('task-model-badge');
        var modelSelector = document.getElementById('model-selector');
        var srAnnouncer = document.getElementById('sr-announcer');
        var srAlerts = document.getElementById('sr-alerts');

        var isTaskRunning = false;
        var taskStartTime = null;
        var timerInterval = null;
        var currentAgentArticle = null;
        var currentAgentId = null;
        var reconnectAttempts = 0;
        var messageCounter = 0;

        // Restore model preference
        var savedModel = localStorage.getItem('agy_selected_model');
        if (savedModel && modelSelector) {
            modelSelector.value = savedModel;
        }

        // Load saved chat from localStorage on startup
        loadChatHistory();

        function announce(text, isAlert) {
            var target = isAlert ? srAlerts : srAnnouncer;
            if (!target) return;
            target.textContent = '';
            setTimeout(function() {
                target.textContent = text;
            }, 50);
        }

        function onModelChange() {
            var selected = modelSelector.value;
            localStorage.setItem('agy_selected_model', selected);
            var modelLabel = modelSelector.options[modelSelector.selectedIndex].text;
            announce('Model switched to ' + modelLabel);
        }

        function setConnectionStatus(state) {
            if (state === 'connected') {
                connBadge.className = "flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-950/80 border border-emerald-800 text-emerald-400";
                connBadge.children[0].className = "w-2 h-2 rounded-full bg-emerald-400";
                connText.innerText = "Connected";
                announce("Connected to Antigravity server.");
            } else if (state === 'reconnecting') {
                connBadge.className = "flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-amber-950/80 border border-amber-800 text-amber-400";
                connBadge.children[0].className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";
                connText.innerText = "Reconnecting...";
            } else {
                connBadge.className = "flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-rose-950/80 border border-rose-800 text-rose-400";
                connBadge.children[0].className = "w-2 h-2 rounded-full bg-rose-400";
                connText.innerText = "Disconnected";
                announce("Disconnected from server. Retrying connection...", true);
            }
        }

        function connectWebSocket() {
            var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            var wsUrl = protocol + '//' + location.host + '/ws';
            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                reconnectAttempts = 0;
                setConnectionStatus('connected');
                if (!isTaskRunning) {
                    sendBtn.disabled = false;
                }
            };

            ws.onclose = function() {
                setConnectionStatus('reconnecting');
                sendBtn.disabled = true;
                reconnectAttempts++;
                var delay = Math.min(3000, 1000 * reconnectAttempts);
                setTimeout(connectWebSocket, delay);
            };

            ws.onerror = function() {
                ws.close();
            };

            ws.onmessage = function(event) {
                try {
                    var data = JSON.parse(event.data);
                    handleServerMessage(data);
                } catch(e) {
                    console.error("Message parse error:", e, event.data);
                }
            };
        }

        function handleServerMessage(data) {
            if (data.type === 'init') {
                // Initial handshake
            }
            else if (data.type === 'system') {
                appendSystemMessage(data.message, data.level || 'info');
                announce(data.message, data.level === 'warning');
            }
            else if (data.type === 'task_started') {
                startTaskUI(data.prompt, data.model, data.start_time);
            }
            else if (data.type === 'task_active') {
                startTaskUI(data.prompt, data.model, data.start_time);
                if (!currentAgentArticle) {
                    currentAgentArticle = appendAgentMessageContainer(data.model);
                }
                // Render any actions already completed
                if (data.actions && Array.isArray(data.actions)) {
                    data.actions.forEach(function(act) {
                        appendOrUpdateAction(act);
                    });
                }
                if (data.buffered_output) {
                    currentAgentArticle.dataset.rawMarkdown = data.buffered_output;
                    currentAgentArticle.querySelector('.agent-text').innerHTML = marked.parse(data.buffered_output);
                }
                chatFeed.scrollTop = chatFeed.scrollHeight;
            }
            else if (data.type === 'agent_start') {
                if (!currentAgentArticle) {
                    currentAgentArticle = appendAgentMessageContainer(data.model);
                }
            }
            else if (data.type === 'action_start') {
                if (!currentAgentArticle) {
                    currentAgentArticle = appendAgentMessageContainer();
                }
                appendOrUpdateAction(data.action);
                announce("Action running: " + formatToolName(data.action.tool));
            }
            else if (data.type === 'action_done') {
                if (!currentAgentArticle) {
                    currentAgentArticle = appendAgentMessageContainer();
                }
                appendOrUpdateAction(data.action);
                announce("Action complete: " + formatToolName(data.action.tool));
            }
            else if (data.type === 'agent_chunk') {
                if (!currentAgentArticle) {
                    currentAgentArticle = appendAgentMessageContainer();
                }
                var prev = currentAgentArticle.dataset.rawMarkdown || '';
                var updated = prev + data.chunk;
                currentAgentArticle.dataset.rawMarkdown = updated;
                currentAgentArticle.querySelector('.agent-text').innerHTML = marked.parse(updated);
                chatFeed.scrollTop = chatFeed.scrollHeight;
            }
            else if (data.type === 'agent_done') {
                finishTaskUI(data.cancelled, data.elapsed, data.status);
            }
        }

        function formatToolName(tool) {
            if (!tool) return 'Operation';
            return tool.replace(/_/g, ' ');
        }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function startTaskUI(prompt, model, startTime) {
            isTaskRunning = true;
            taskStartTime = startTime || Date.now() / 1000;
            currentTaskPromptEl.innerText = prompt || 'Executing instruction...';
            if (taskModelBadge) {
                taskModelBadge.innerText = model || (modelSelector ? modelSelector.value : 'Gemini');
            }
            taskBanner.classList.remove('hidden');

            sendBtn.disabled = true;
            sendBtnSpinner.classList.remove('hidden');
            sendBtnText.innerText = "Running...";

            updateTimer();
            clearInterval(timerInterval);
            timerInterval = setInterval(updateTimer, 500);

            announce("Task started: " + prompt + ". Running in background.");

            window.onbeforeunload = function() {
                return "Task is running in the background. It will continue safely.";
            };
        }

        function finishTaskUI(cancelled, elapsed, status) {
            isTaskRunning = false;
            taskBanner.classList.add('hidden');
            clearInterval(timerInterval);
            window.onbeforeunload = null;

            sendBtn.disabled = false;
            sendBtnSpinner.classList.add('hidden');
            sendBtnText.innerText = "Execute";

            if (currentAgentArticle) {
                // Remove typing pulse
                var pulse = currentAgentArticle.querySelector('.typing-indicator');
                if (pulse) pulse.remove();

                var statusBadge = currentAgentArticle.querySelector('.status-badge');
                if (cancelled) {
                    if (statusBadge) {
                        statusBadge.className = "text-[11px] text-rose-400 font-mono flex items-center gap-1";
                        statusBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Cancelled';
                    }
                    var cancelNotice = document.createElement('div');
                    cancelNotice.className = "text-xs font-semibold text-rose-400 mt-2 italic";
                    cancelNotice.innerText = "[Task cancelled by user]";
                    currentAgentArticle.querySelector('.agent-text').appendChild(cancelNotice);
                    announce("Task was cancelled.", true);
                } else {
                    var elapStr = elapsed ? elapsed + 's' : '';
                    if (statusBadge) {
                        statusBadge.className = "text-[11px] text-emerald-400 font-mono flex items-center gap-1";
                        statusBadge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Completed ' + elapStr;
                    }
                    announce("Task completed successfully in " + elapStr + ". Press H to review response.");
                }

                // Focus response heading for seamless screen reader accessibility
                var respHeading = currentAgentArticle.querySelector('h2');
                if (respHeading) {
                    respHeading.focus();
                }

                currentAgentArticle = null;
                currentAgentId = null;
            }

            saveChatHistory();
        }

        function updateTimer() {
            if (!taskStartTime) return;
            var elapsedSec = Math.floor((Date.now() / 1000) - taskStartTime);
            if (elapsedSec < 0) elapsedSec = 0;
            var mins = Math.floor(elapsedSec / 60);
            var secs = elapsedSec % 60;
            timerDisplay.innerText = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
        }

        function appendUserMessage(text) {
            messageCounter++;
            var msgId = 'msg-user-' + messageCounter;

            var article = document.createElement('article');
            article.className = 'message-card user-message mb-4';
            article.setAttribute('aria-labelledby', msgId);
            article.dataset.sender = 'user';
            article.dataset.text = text;

            var timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            article.innerHTML = `
                <div class="flex items-center justify-between mb-1.5">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-teal-400" aria-hidden="true"></span>
                        <h2 id="${msgId}" class="text-xs font-bold uppercase tracking-wider text-teal-300">You asked:</h2>
                    </div>
                    <time class="text-[11px] text-slate-500 font-mono">${timeStr}</time>
                </div>
                <div class="bg-teal-950/60 border border-teal-800/60 rounded-xl p-3.5 text-slate-100 text-sm shadow-sm whitespace-pre-wrap">${escapeHtml(text)}</div>
            `;

            chatFeed.appendChild(article);
            chatFeed.scrollTop = chatFeed.scrollHeight;
            saveChatHistory();
        }

        function appendAgentMessageContainer(modelName) {
            messageCounter++;
            var msgId = 'msg-agent-' + messageCounter;
            currentAgentId = msgId;

            var article = document.createElement('article');
            article.className = 'message-card agent-message mb-4';
            article.setAttribute('aria-labelledby', msgId);
            article.dataset.sender = 'agent';
            article.dataset.rawMarkdown = '';

            var modelDisplay = modelName || (modelSelector ? modelSelector.value : 'Gemini');

            article.innerHTML = `
                <div class="flex items-center justify-between mb-1.5">
                    <div class="flex items-center gap-2">
                        <div class="w-5 h-5 rounded bg-teal-900/60 border border-teal-700/50 text-teal-300 flex items-center justify-center text-[10px] font-bold" aria-hidden="true">AG</div>
                        <h2 id="${msgId}" tabindex="-1" class="text-xs font-bold uppercase tracking-wider text-cyan-300 focus:outline-none focus:ring-1 focus:ring-teal-400 rounded px-1">
                            Antigravity response:
                        </h2>
                        <span class="text-[10px] text-slate-400 font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800">${escapeHtml(modelDisplay)}</span>
                    </div>
                    <div class="status-badge text-[11px] text-teal-400 font-mono flex items-center gap-1.5">
                        <span class="w-1.5 h-1.5 rounded-full bg-teal-400 animate-ping" aria-hidden="true"></span> Processing...
                    </div>
                </div>
                <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
                    <!-- Actions container (collapsed logs, not polluting main text) -->
                    <div class="actions-list space-y-1.5 mb-2.5"></div>
                    
                    <!-- Response markdown text -->
                    <div class="agent-text markdown-body text-slate-200 text-sm"></div>

                    <!-- Streaming typing indicator -->
                    <div class="typing-indicator flex items-center gap-2 text-xs text-teal-400 mt-2 font-medium" aria-hidden="true">
                        <span class="w-2 h-2 rounded-full bg-teal-400 animate-ping"></span> Thinking &amp; streaming...
                    </div>
                </div>
            `;

            chatFeed.appendChild(article);
            chatFeed.scrollTop = chatFeed.scrollHeight;
            return article;
        }

        function appendOrUpdateAction(action) {
            if (!currentAgentArticle || !action) return;
            var actionsList = currentAgentArticle.querySelector('.actions-list');
            if (!actionsList) return;

            var actionId = 'act-' + (action.id || action.tool || 'op');
            var existing = document.getElementById(actionId);

            var toolLabel = formatToolName(action.tool);
            var isDone = action.status === 'done';
            var statusColor = isDone ? 'text-emerald-400' : 'text-cyan-400';
            var dotColor = isDone ? 'bg-emerald-400' : 'bg-cyan-400 animate-pulse';
            var durationText = action.duration ? (action.duration + 's') : (isDone ? 'done' : 'running...');

            var paramsFormatted = '';
            if (action.params && Object.keys(action.params).length > 0) {
                paramsFormatted = typeof action.params === 'string' ? action.params : JSON.stringify(action.params, null, 2);
            }
            var outputFormatted = action.output || '';

            var detailsHtml = `
                <summary class="px-3 py-1.5 cursor-pointer text-slate-300 font-mono text-xs flex items-center justify-between hover:bg-slate-800/80 select-none">
                    <span class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full ${dotColor}" aria-hidden="true"></span>
                        <span class="font-semibold ${statusColor}">Action: ${escapeHtml(toolLabel)}</span>
                    </span>
                    <span class="text-[11px] text-slate-400 font-sans">${durationText} • Click for logs</span>
                </summary>
                <div class="p-3 bg-slate-950 border-t border-slate-800 font-mono text-[12px] text-slate-400 space-y-2 max-h-48 overflow-y-auto">
                    ${paramsFormatted ? '<div><div class="text-teal-400 font-semibold text-[11px] mb-0.5">Parameters:</div><pre class="bg-slate-900/80 p-2 rounded border border-slate-800/60 overflow-x-auto whitespace-pre-wrap">' + escapeHtml(paramsFormatted) + '</pre></div>' : ''}
                    ${outputFormatted ? '<div><div class="text-slate-400 font-semibold text-[11px] mb-0.5">Execution Log:</div><pre class="bg-slate-900/80 p-2 rounded border border-slate-800/60 overflow-x-auto whitespace-pre-wrap">' + escapeHtml(outputFormatted) + '</pre></div>' : ''}
                </div>
            `;

            if (existing) {
                existing.innerHTML = detailsHtml;
            } else {
                var details = document.createElement('details');
                details.id = actionId;
                details.className = 'tool-action border border-slate-800/90 rounded-lg bg-slate-950/60 overflow-hidden';
                details.innerHTML = detailsHtml;
                actionsList.appendChild(details);
            }
        }

        function appendSystemMessage(msg, level) {
            var div = document.createElement('div');
            div.className = 'flex justify-center my-2';
            var pill = document.createElement('div');
            pill.className = `text-xs px-3.5 py-1 rounded-full border ${level === 'warning' ? 'bg-amber-950/80 text-amber-300 border-amber-800' : 'bg-slate-900 text-slate-400 border-slate-800'}`;
            pill.innerText = msg;
            div.appendChild(pill);
            chatFeed.appendChild(div);
            chatFeed.scrollTop = chatFeed.scrollHeight;
        }

        function sendPrompt(e) {
            if (e) e.preventDefault();
            var prompt = inputEl.value.trim();
            if (!prompt || isTaskRunning) return;

            var model = modelSelector ? modelSelector.value : 'gemini-3.8-flash-high';

            appendUserMessage(prompt);
            inputEl.value = '';

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'prompt',
                    prompt: prompt,
                    model: model
                }));
            } else {
                appendSystemMessage("Connection not open. Reconnecting...", "warning");
            }
        }

        function handleKeyDown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendPrompt();
            }
        }

        function cancelTask() {
            if (ws && ws.readyState === WebSocket.OPEN && isTaskRunning) {
                ws.send(JSON.stringify({ type: 'cancel' }));
            }
        }

        function saveChatHistory() {
            var items = [];
            var messageEls = chatFeed.querySelectorAll('.message-card');
            messageEls.forEach(function(el) {
                if (el.dataset.sender === 'user') {
                    items.push({ sender: 'user', text: el.dataset.text });
                } else if (el.dataset.sender === 'agent') {
                    items.push({ sender: 'agent', markdown: el.dataset.rawMarkdown || '' });
                }
            });
            try {
                localStorage.setItem('agy_chat_items_v2', JSON.stringify(items.slice(-50)));
            } catch(e) {}
        }

        function loadChatHistory() {
            try {
                var stored = localStorage.getItem('agy_chat_items_v2') || localStorage.getItem('agy_chat_items');
                if (!stored) return;
                var items = JSON.parse(stored);
                items.forEach(function(item) {
                    if (item.sender === 'user') {
                        appendUserMessage(item.text);
                    } else if (item.sender === 'agent' && item.markdown) {
                        var art = appendAgentMessageContainer();
                        art.dataset.rawMarkdown = item.markdown;
                        art.querySelector('.agent-text').innerHTML = marked.parse(item.markdown);
                        var pulse = art.querySelector('.typing-indicator');
                        if (pulse) pulse.remove();
                        var badge = art.querySelector('.status-badge');
                        if (badge) {
                            badge.className = "text-[11px] text-slate-400 font-mono flex items-center gap-1";
                            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Stored';
                        }
                    }
                });
            } catch(e) {}
        }

        function clearHistory() {
            if (confirm("Clear local chat display? Active background tasks will continue running.")) {
                try {
                    localStorage.removeItem('agy_chat_items_v2');
                    localStorage.removeItem('agy_chat_items');
                } catch(e) {}
                location.reload();
            }
        }

        // Start WebSocket
        connectWebSocket();
    </script>
</body>
</html>
"""

class AgentTaskManager:
    """
    Manages Antigravity background tasks independently of client WebSocket connections.
    Uses --output-format stream-json to cleanly separate tool actions/logs from the main
    markdown response text, keeping the interface uncluttered and accessible.
    """
    def __init__(self):
        self.active_task: asyncio.Task = None
        self.active_proc: asyncio.subprocess.Process = None
        self.current_prompt: str = None
        self.current_model: str = "gemini-3.8-flash-high"
        self.start_time: float = None
        self.output_buffer: list = []
        self.actions: list = []
        self.connected_clients: set = set()
        self._lock = asyncio.Lock()
        
        self.last_run_finished: bool = True
        self.last_result: dict = None

    def is_running(self) -> bool:
        return self.active_proc is not None and self.active_proc.returncode is None

    async def broadcast(self, message: dict):
        if not self.connected_clients:
            return
        payload = json.dumps(message)
        dead_clients = []
        for client in list(self.connected_clients):
            try:
                await client.send(payload)
            except Exception:
                dead_clients.append(client)
        for dead in dead_clients:
            self.connected_clients.discard(dead)

    async def register_client(self, ws):
        self.connected_clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "init", "connected": True}))
            if self.is_running():
                await ws.send(json.dumps({
                    "type": "task_active",
                    "prompt": self.current_prompt,
                    "model": self.current_model,
                    "start_time": self.start_time,
                    "actions": self.actions,
                    "buffered_output": "".join(self.output_buffer)
                }))
            elif self.current_prompt is not None and self.last_run_finished:
                # Re-hydrate the client with the last finished task state
                await ws.send(json.dumps({
                    "type": "task_active",
                    "prompt": self.current_prompt,
                    "model": self.current_model,
                    "start_time": self.start_time,
                    "actions": self.actions,
                    "buffered_output": "".join(self.output_buffer)
                }))
                if self.last_result:
                    await ws.send(json.dumps(self.last_result))
        except Exception:
            self.connected_clients.discard(ws)

    async def unregister_client(self, ws):
        self.connected_clients.discard(ws)

    async def start_task(self, prompt: str, model: str = "gemini-3.8-flash-high"):
        async with self._lock:
            if self.is_running():
                await self.broadcast({
                    "type": "system",
                    "level": "warning",
                    "message": "A task is already actively running. Please wait for it to complete or click Cancel."
                })
                return

            self.current_prompt = prompt
            self.current_model = model or "gemini-3.8-flash-high"
            self.start_time = time.time()
            self.output_buffer = []
            self.actions = []
            self.last_run_finished = False
            self.last_result = None

            await self.broadcast({
                "type": "task_started",
                "prompt": prompt,
                "model": self.current_model,
                "start_time": self.start_time
            })

            self.active_task = asyncio.create_task(self._execute_agent(prompt, self.current_model, self.start_time))

    async def _execute_agent(self, prompt: str, model: str, task_time: float):
        try:
            workspace_dir = os.path.dirname(os.path.abspath(__file__))
            cmd = [
                "/home/michael/.local/bin/agy",
                "--dangerously-skip-permissions",
                "--model", model,
                "--output-format", "stream-json",
                "--print", prompt
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=workspace_dir
            )
            self.active_proc = proc

            await self.broadcast({"type": "agent_start", "model": model})

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace').strip()
                if not line_str:
                    continue

                # Parse stream-json events from agy
                try:
                    event_data = json.loads(line_str)
                    event_type = event_data.get("event")

                    if event_type == "step_update":
                        step = event_data.get("step_update", {})
                        stype = step.get("step_type")
                        state = step.get("state")

                        if stype == "tool":
                            tool_name = step.get("tool_name", "tool")
                            tool_info = step.get("tool_info", {})
                            if state == "ACTIVE":
                                act = {
                                    "id": step.get("step_index"),
                                    "tool": tool_name,
                                    "params": tool_info.get("parameters", {}),
                                    "status": "running"
                                }
                                self.actions.append(act)
                                await self.broadcast({"type": "action_start", "action": act})
                            elif state == "DONE":
                                act = {
                                    "id": step.get("step_index"),
                                    "tool": tool_name,
                                    "duration": round(step.get("duration_seconds", 0), 2),
                                    "output": tool_info.get("output", ""),
                                    "status": "done"
                                }
                                # Update in memory
                                for idx, existing in enumerate(self.actions):
                                    if existing.get("id") == act["id"]:
                                        self.actions[idx] = act
                                        break
                                else:
                                    self.actions.append(act)
                                await self.broadcast({"type": "action_done", "action": act})

                        elif stype == "agent_response":
                            delta = step.get("text_delta", "")
                            if delta:
                                self.output_buffer.append(delta)
                                await self.broadcast({"type": "agent_chunk", "chunk": delta})

                    elif event_type == "result":
                        res = event_data.get("result", {})
                        status = res.get("status", "SUCCESS")
                        final_resp = res.get("response", "")
                        # If output_buffer was empty (e.g. non-streaming), ensure response is sent
                        if not self.output_buffer and final_resp:
                            self.output_buffer.append(final_resp)
                            await self.broadcast({"type": "agent_chunk", "chunk": final_resp})

                except json.JSONDecodeError:
                    # Fallback for plain non-JSON output (e.g. startup errors or warnings)
                    self.output_buffer.append(line_str + "\n")
                    await self.broadcast({"type": "agent_chunk", "chunk": line_str + "\n"})

            await proc.wait()
            elapsed = round(time.time() - task_time, 1)
            self.last_result = {
                "type": "agent_done",
                "exit_code": proc.returncode,
                "elapsed": elapsed,
                "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
                "cancelled": False
            }
            await self.broadcast(self.last_result)
        except asyncio.CancelledError:
            if self.active_proc and self.active_proc.returncode is None:
                try:
                    self.active_proc.kill()
                except Exception:
                    pass
            self.last_result = {"type": "agent_done", "cancelled": True}
            await self.broadcast(self.last_result)
        except Exception as e:
            await self.broadcast({"type": "system", "level": "warning", "message": f"Execution error: {str(e)}"})
            self.last_result = {"type": "agent_done", "cancelled": True}
            await self.broadcast(self.last_result)
        finally:
            self.last_run_finished = True
            self.active_proc = None
            self.active_task = None
            self.start_time = None

    async def cancel_task(self):
        async with self._lock:
            if self.is_running():
                try:
                    self.active_proc.kill()
                except Exception:
                    pass
                if self.active_task and not self.active_task.done():
                    self.active_task.cancel()
                await self.broadcast({
                    "type": "system",
                    "level": "info",
                    "message": "Task cancelled by user."
                })
                await self.broadcast({
                    "type": "agent_done",
                    "cancelled": True
                })

agent_manager = AgentTaskManager()

@app.route('/')
async def index():
    return await render_template_string(HTML_CLIENT)

@app.websocket('/ws')
async def ws():
    await agent_manager.register_client(websocket)
    try:
        while True:
            raw_msg = await websocket.receive()
            if not raw_msg:
                continue
            
            prompt = None
            model = "gemini-3.8-flash-high"
            try:
                data = json.loads(raw_msg)
                msg_type = data.get("type", "prompt")
                if msg_type == "cancel":
                    await agent_manager.cancel_task()
                    continue
                elif msg_type == "prompt":
                    prompt = data.get("prompt", "").strip()
                    model = data.get("model", "gemini-3.8-flash-high")
            except (json.JSONDecodeError, AttributeError):
                prompt = str(raw_msg).strip()

            if prompt:
                await agent_manager.start_task(prompt, model=model)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        await agent_manager.unregister_client(websocket)

if __name__ == '__main__':
    print("Starting Resilient Accessible Antigravity Portal (Backend Mode)...")
    print("Internal Backend Port: 5001 (Use Gateway on 5000)")
    app.run(host='0.0.0.0', port=5001, use_reloader=False)
