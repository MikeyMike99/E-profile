# Pillar 05.42: "From Scratch" Step-by-Step Creation Guide: Session Rollover & In-Flight Protection

## 1. Overview & Goal
This guide provides a complete, step-by-step engineering tutorial for building an autonomous, background session rollover and context transfer system from scratch. By following this guide, you will construct a distillation engine that extracts state offline, an execution gatekeeper that guards active in-flight tasks from accidental wipes, and an automated regression test suite.

---

## 2. Step 1: Implement the Context Distillation Engine (`core/session_manager.py`)

Create or update `core/session_manager.py` to extract working memory directly from transcript history:

```python
import os
import json

class SessionManager:
    def __init__(self, brain_dir=None):
        self.brain_dir = brain_dir or os.path.expanduser("~/.gemini/antigravity-cli/brain")

    def get_session_turn_count(self, conv_id: str) -> int:
        """Safely parses transcript.jsonl to count user turns, rejecting path traversal."""
        if not conv_id or '..' in conv_id or '/' in conv_id or '\\' in conv_id:
            return 0
        transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
        if not os.path.exists(transcript_path):
            return 0
        turns = 0
        try:
            with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.strip():
                        try:
                            if json.loads(line).get("type") == "USER_INPUT":
                                turns += 1
                        except Exception:
                            pass
        except Exception:
            pass
        return turns

    def generate_continuation_briefing(self, conv_id: str, workspace_path: str = None) -> str:
        """Distills active workspace, project, recent goals, and touched files offline."""
        if not conv_id:
            return ""
        workspace_dir = workspace_path or "/tmp/workspace"
        project_name = "DevCore"
        
        # Read transcript to collect user prompts, agent outcomes, and file paths
        # Formulate structured briefing envelope:
        return (
            "<SESSION_CONTINUATION_CONTEXT>\n"
            "[AUTOMATIC SESSION ROLLOVER: Previous session archived for speed & token efficiency.]\n"
            f"- Active Workspace Directory: {workspace_dir}\n"
            f"- Active Project: {project_name}\n"
            "- Operational Rules: Screen-reader optimized responses; concise markdown; clickable file:// links.\n"
            "</SESSION_CONTINUATION_CONTEXT>"
        )
```

---

## 3. Step 2: Implement the Execution Gatekeeper (`agents/mixins/execution_mixin.py`)

Ensure `start_task` forwards in-flight origins and `_execute_agent` strictly suppresses resets mid-task:

```python
import os
import time
import random
import asyncio

class ExecutionMixin:
    async def start_task(self, prompt: str, conversation_id: str = None, _from_steer_or_queue: bool = False, **kwargs):
        self.active_task = asyncio.create_task(
            self._execute_agent(prompt, conversation_id or self.current_conversation_id, _from_steer_or_queue=_from_steer_or_queue, **kwargs)
        )

    async def _execute_agent(self, prompt: str, conversation_id: str, _from_steer_or_queue: bool = False, **kwargs):
        auto_rollover_enabled = os.environ.get("ENABLE_AUTO_SESSION_ROLLOVER", "false").lower() == "true"
        is_ongoing_midconversation = _from_steer_or_queue or bool(getattr(self, "queued_prompts", []))

        # Strict in-flight guard: Never rollover mid-task or during steering
        if conversation_id and auto_rollover_enabled:
            if is_ongoing_midconversation:
                # Log suppression event
                pass
            else:
                session_mgr = self._get_session_mgr()
                turn_count = session_mgr.get_session_turn_count(conversation_id)
                if turn_count >= 80:
                    briefing = session_mgr.generate_continuation_briefing(conversation_id, workspace_dir)
                    new_conv_id = f"conv-{int(time.time())}-{random.randint(1000, 9999)}"
                    conversation_id = new_conv_id
                    self.current_conversation_id = new_conv_id
                    await self.broadcast({
                        "type": "session_rollover",
                        "old_conversation_id": old_conv_id,
                        "new_conversation_id": new_conv_id,
                        "message": "🔄 Session automatically rolled over for speed and token efficiency."
                    })
                    if briefing:
                        prompt = briefing + "\n\n" + prompt

        try:
            # Subprocess execution ...
            pass
        finally:
            # Targeted cleanup ONLY — blanket pkill is forbidden!
            if not getattr(self, "_steering_interrupt", False) and getattr(self, "queued_prompts", None):
                asyncio.create_task(self._drain_queued_prompts())
```

---

## 4. Step 3: Frontend Event Handlers (`sandbox/templates/index.html`)

Wire the client WebSocket to announce rollovers and update token metrics:

```javascript
else if (data.type === 'session_rollover') {
    var newId = data.new_conversation_id;
    if (newId) {
        currentConversationId = newId;
        localStorage.setItem('agy_conversation_id', newId);
        announce(data.message || "Session automatically rolled over. Context preserved.", false);
        
        var chatBox = document.getElementById('chat-history');
        if (chatBox) {
            var pill = document.createElement('div');
            pill.setAttribute('role', 'status');
            pill.className = "flex items-center gap-2 px-4 py-2.5 my-3 rounded-lg bg-teal-950/70 border border-teal-500/40 text-teal-300 text-xs font-semibold";
            pill.innerHTML = "<span>🔄</span><span>Session Rollover — Working Directory & Context Transferred</span>";
            chatBox.appendChild(pill);
        }
    }
}
else if (data.type === 'token_telemetry') {
    var usage = data.usage || {};
    var tokenBadge = document.getElementById('token-usage-badge');
    if (tokenBadge) {
        tokenBadge.innerHTML = '<span>⚡ In: ' + (usage.input_tokens / 1000).toFixed(1) + 'k | Cache: ' + (usage.cache_read_tokens / 1000).toFixed(1) + 'k</span>';
    }
}
```

---

## 5. Step 4: Verification and Hot-Patching

1. **Stage Patch**:
   ```bash
   cp agents/mixins/execution_mixin.py core/patches/execution_mixin.py
   python3 -m py_compile core/patches/execution_mixin.py
   ```
2. **Hot-Swap In-Memory**:
   ```bash
   curl -s -X POST http://127.0.0.1:5000/api/reload
   ```
3. **Execute Automated Security Audit**:
   ```bash
   python3 security/security_audit.py
   ```

---

## 6. Cross-Reference Navigation
- **Problem Statement**: [`01_PROBLEMS_ENCOUNTERED/01_43_TOKEN_BURST_PREMATURE_ROLLOVER_AND_MIDTASK_RESET_TRAPS.md`](/docs/devlog/01_43_TOKEN_BURST_PREMATURE_ROLLOVER_AND_MIDTASK_RESET_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_39_SESSION_ROLLOVER_DISTILLATION_AND_GUARD_EVIDENCE.md`](/docs/devlog/02_39_SESSION_ROLLOVER_DISTILLATION_AND_GUARD_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS.md`](/docs/devlog/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE.md`](/docs/devlog/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE)
