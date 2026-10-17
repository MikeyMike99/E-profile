[//]: # (DOC_ID: SIRA-DOC-02_39 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 02.39: Source Code Evidence: Session Rollover Distillation, In-Flight Guards & SIEM Telemetry

## Overview & Context
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-1)
This document catalogs the exact production code implementations across the Siraugga backend and frontend architecture that govern session lifecycle management, transcript distillation, mid-conversation rollover suppression, and automated security auditing.

---

## 1. Context Distillation Engine (`core/session_manager.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-1)

### Safe Turn Counting with Directory Traversal Defense
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-2)
```python
def get_session_turn_count(self, conv_id: str) -> int:
    """Safely extracts the count of completed USER_INPUT turns without path escapes."""
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
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "USER_INPUT":
                        turns += 1
                except Exception:
                    pass
    except Exception:
        pass
    return turns
```

### Offline Context Briefing Generator
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-3)
```python
def generate_continuation_briefing(self, conv_id: str, workspace_path: str = None) -> str:
    """Extracts working directory, project, recent goals, and touched files offline."""
    if not conv_id:
        return ""
    
    self.ownership = self._load_ownership()
    meta = self.ownership.get(conv_id, {})
    project_name = meta.get("project") or "DevCore"
    workspace_dir = workspace_path or "/playground"
    
    # ... Reads transcript.jsonl safely, strips system wrappers, caps string lengths ...
    
    briefing = (
        "<SESSION_CONTINUATION_CONTEXT>\n"
        "[AUTOMATIC SESSION ROLLOVER: The previous session was archived to maintain peak responsiveness and eliminate token bloat.]\n"
        f"- Active Workspace Directory: {workspace_dir}\n"
        f"- Active Project: {project_name}\n"
        "- Recent Accomplished Goals:\n"
        f"{recent_goals_str}"
        "- Recently Touched Files:\n"
        f"{recent_files_str}"
        f"- Latest Context / Outcome: {latest_outcome}\n"
        "- Operational Rules: Screen-reader optimized responses; concise markdown; clickable file:// links; clean workspace protocol (no lingering scratch files).\n"
        "</SESSION_CONTINUATION_CONTEXT>"
    )
    return briefing
```

---

## 2. In-Flight Rollover Gatekeeper (`agents/mixins/execution_mixin.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-2)

### Parameter Passing & In-Flight Protection
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-4)
```python
async def start_task(
    self,
    prompt: str,
    model: str = "Gemini 3.8 Flash (Low)",
    conversation_id: str = None,
    user: dict = None,
    admin_override: bool = False,
    _from_steer_or_queue: bool = False,
    display_prompt: str = None,
    queued_user_prompt: str = None,
    logical_prompt: str = None,
):
    # ...
    self.active_task = asyncio.create_task(
        self._execute_agent(
            prompt,
            self.current_model,
            self.start_time,
            conversation_id or self.current_conversation_id,
            user=user,
            admin_override=is_admin,
            _from_steer_or_queue=_from_steer_or_queue,
        )
    )
```

### In-Flight Rollover Suppression & SIEM Telemetry
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-5)
```python
# --- AUTOMATED SILENT SESSION ROLLOVER CHECK ---
# Session reset MUST NOT happen when a task is still ongoing midconversation.
auto_rollover_enabled = os.environ.get("ENABLE_AUTO_SESSION_ROLLOVER", "false").lower() == "true"
is_ongoing_midconversation = _from_steer_or_queue or bool(getattr(self, "queued_prompts", []))

if conversation_id and auto_rollover_enabled:
    if is_ongoing_midconversation:
        try:
            from security.central_logger import log_siem_event
            log_siem_event(
                level="INFO",
                message=f"[SESSION_GUARD] Session rollover suppressed: Task is actively ongoing midconversation (conv_id={conversation_id})",
                module_name="execution_mixin",
                logger_name="agent.session"
            )
        except Exception:
            pass
    else:
        try:
            session_mgr = self._get_session_mgr()
            turn_count = session_mgr.get_session_turn_count(conversation_id)

            if turn_count >= 80:
                briefing = session_mgr.generate_continuation_briefing(conversation_id, workspace_dir)
                old_conv_id = conversation_id
                new_conv_id = f"conv-{int(time.time())}-{random.randint(1000, 9999)}"

                # Register ownership & switch conversation ID
                session_mgr.register_session_owner(new_conv_id, username, project_name)
                conversation_id = new_conv_id
                self.current_conversation_id = new_conv_id
                self.last_cache_read_tokens = 0

                # Log to SIEM & Broadcast over WebSocket
                from security.central_logger import log_siem_event
                log_siem_event(
                    level="INFO",
                    message=f"[SESSION_ROLLOVER] Session {old_conv_id} rolled over to {new_conv_id} after {turn_count} turns (user={username}, project={project_name})",
                    module_name="execution_mixin",
                    logger_name="agent.session"
                )
                await self.broadcast({
                    "type": "session_rollover",
                    "old_conversation_id": old_conv_id,
                    "new_conversation_id": new_conv_id,
                    "turns": turn_count,
                    "cached_tokens": 0,
                    "message": "🔄 Session automatically rolled over for speed and token efficiency. Working directory and project context were seamlessly transferred."
                })
                if briefing:
                    prompt = briefing + "\n\n" + prompt
        except Exception as e:
            logging.warning(f"[ExecutionMixin] Session rollover check warning: {e}")
```

### Turn Cleanup Subprocess Hygiene (No Blanket pkill)
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-6)
```python
finally:
    hb_task.cancel()
    if 'watchdog_task' in locals() and not watchdog_task.done():
        watchdog_task.cancel()
    self.active_proc = None
    self.active_task = None
    self.start_time = None
    
    is_steered_exit = bool(getattr(self, "_steering_interrupt", False))
    if not is_steered_exit:
        # Targeted queue drain only — blanket 'pkill -9 -f agy' removed!
        if not locals().get("was_cancelled", False) and getattr(self, "queued_prompts", None):
            asyncio.create_task(self._drain_queued_prompts())
```

---

## 3. Automated Guard Invariants (`security/security_audit.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-3)
```python
print("\n--- 4. Testing Session Stability & Rollover Guards ---")
# 4.1 In-Flight Task Protection AST Check
run_test(test_inflight_ast_guard)
# 4.2 No Premature Token Cache Rollover Trigger
run_test(test_no_cache_trap)
# 4.3 Subprocess Hygiene in Turn Exit
run_test(test_subprocess_hygiene)
# 4.4 Session Turn Count & Path Traversal Guard
run_test(test_turn_count_guard)
# 4.5 Context Distillation Engine Integrity
run_test(test_context_distillation)
# 4.6 Rollover Invariant Logic Simulation
run_test(test_rollover_invariants)
```

---

## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-02_39-SEC-4)
- **Problem Statement**: [`01_PROBLEMS_ENCOUNTERED/01_43_TOKEN_BURST_PREMATURE_ROLLOVER_AND_MIDTASK_RESET_TRAPS.md`](/docs/devlog/01_43_TOKEN_BURST_PREMATURE_ROLLOVER_AND_MIDTASK_RESET_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS.md`](/docs/devlog/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE.md`](/docs/devlog/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_42_SESSION_ROLLOVER_AND_GUARD_FROM_SCRATCH.md`](/docs/devlog/05_42_SESSION_ROLLOVER_AND_GUARD_FROM_SCRATCH)
