
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
        var currentConversationId = localStorage.getItem('agy_conversation_id') || null;
        var conversations = JSON.parse(localStorage.getItem('agy_conversations')) || [];
        var convSelector = document.getElementById('conversation-selector');

        function initConversations() {
            if (conversations.length === 0 && currentConversationId) {
                conversations.push({id: currentConversationId, name: 'Session ' + currentConversationId.substring(5, 9)});
                localStorage.setItem('agy_conversations', JSON.stringify(conversations));
            }
            if (convSelector) {
                convSelector.innerHTML = '';
                conversations.forEach(function(c) {
                    var opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.name;
                    if (c.id === currentConversationId) opt.selected = true;
                    convSelector.appendChild(opt);
                });
            }
        }
        initConversations();

        function switchConversation() {
            if (convSelector) {
                var selected = convSelector.value;
                if (selected !== currentConversationId) {
                    localStorage.setItem('agy_conversation_id', selected);
                    location.reload();
                }
            }
        }

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

            if (!currentConversationId) {
                currentConversationId = 'conv-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                localStorage.setItem('agy_conversation_id', currentConversationId);
            }

            appendUserMessage(prompt);
            inputEl.value = '';

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'prompt',
                    prompt: prompt,
                    model: model,
                    conversation_id: currentConversationId
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
                if (currentConversationId) {
                    localStorage.setItem('agy_chat_items_v2_' + currentConversationId, JSON.stringify(items.slice(-50)));
                }
            } catch(e) {}
        }

        function loadChatHistory() {
            try {
                var stored = null;
                if (currentConversationId) {
                    stored = localStorage.getItem('agy_chat_items_v2_' + currentConversationId) || localStorage.getItem('agy_chat_items_v2');
                } else {
                    stored = localStorage.getItem('agy_chat_items_v2') || localStorage.getItem('agy_chat_items');
                }
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
                    if (currentConversationId) {
                        localStorage.removeItem('agy_chat_items_v2_' + currentConversationId);
                    }
                    localStorage.removeItem('agy_chat_items_v2');
                } catch(e) {}
                location.reload();
            }
        }

        function newConversation() {
            if (confirm("Start a new session? This will clear the current view and generate a fresh conversation ID.")) {
                try {
                    localStorage.removeItem('agy_conversation_id');
                } catch(e) {}
                location.reload();
            }
        }

        // Start WebSocket
        connectWebSocket();
    