import re

with open("content/projects/engines/antigravity_agent/templates/ai_index.html", "r") as f:
    html = f.read()

# Replace connectWebSocket()
new_connect = """
        function connectWebSocket() {
            setConnectionStatus('connected');
            if (!isTaskRunning) sendBtn.disabled = false;
            
            // Poll for stream updates
            setInterval(function() {
                fetch('/api/stream').then(res => res.json()).then(data => {
                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(msg => {
                            if (msg.type === 'agent_chunk') {
                                if (currentAgentId) {
                                    var article = document.getElementById(currentAgentId).closest('article');
                                    var textDiv = article.querySelector('.agent-text');
                                    article.dataset.rawMarkdown += msg.chunk;
                                    textDiv.innerHTML = marked.parse(article.dataset.rawMarkdown);
                                    chatFeed.scrollTop = chatFeed.scrollHeight;
                                } else {
                                    appendAgentMessageContainer();
                                    var article = document.getElementById(currentAgentId).closest('article');
                                    var textDiv = article.querySelector('.agent-text');
                                    article.dataset.rawMarkdown += msg.chunk;
                                    textDiv.innerHTML = marked.parse(article.dataset.rawMarkdown);
                                    chatFeed.scrollTop = chatFeed.scrollHeight;
                                }
                            } else if (msg.type === 'agent_done') {
                                if (currentAgentId) {
                                    var article = document.getElementById(currentAgentId).closest('article');
                                    var badge = article.querySelector('.status-badge');
                                    if (badge) {
                                        badge.className = 'status-badge text-[11px] text-teal-400 font-mono flex items-center gap-1.5';
                                        badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-teal-400"></span> Finished';
                                    }
                                }
                                isTaskRunning = false;
                                currentAgentId = null;
                                sendBtn.disabled = false;
                                sendBtnText.innerText = "Send";
                                sendBtnSpinner.classList.add('hidden');
                            }
                        });
                    }
                }).catch(err => console.error(err));
            }, 1500);
            
            // Auto-boot if empty
            var messageCount = chatFeed.querySelectorAll('.message-card').length;
            if (messageCount === 0) {
                fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: "boot"})
                });
            }
        }
"""

html = re.sub(r'function connectWebSocket\(\) \{.*?\n        \}\n', new_connect, html, flags=re.DOTALL)

# Replace ws.send in sendPrompt
new_send = """
            fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompt: prompt, model: model, conversation_id: currentConversationId, admin_override: adminOverride, token: authToken})
            });
            isTaskRunning = true;
            sendBtn.disabled = true;
            sendBtnText.innerText = "Processing...";
            sendBtnSpinner.classList.remove('hidden');
"""
html = re.sub(r'if \(ws && ws\.readyState === WebSocket\.OPEN\) \{.*?else \{.*?\}', new_send, html, flags=re.DOTALL)

# Replace ws.send in cancelTask
new_cancel = """
            fetch('/api/kill', {method: 'POST'});
            isTaskRunning = false;
            sendBtn.disabled = false;
            sendBtnText.innerText = "Send";
            sendBtnSpinner.classList.add('hidden');
"""
html = re.sub(r'if \(ws && ws\.readyState === WebSocket\.OPEN && isTaskRunning\) \{.*?\}', new_cancel, html, flags=re.DOTALL)

with open("content/projects/engines/antigravity_agent/templates/ai_index.html", "w") as f:
    f.write(html)
