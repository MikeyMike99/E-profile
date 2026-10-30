import os
import json

class SessionManager:
    """
    Manages discovery, isolation, and parsing of Antigravity conversation sessions.
    Enforces multi-tenant data boundaries so non-admin users cannot snoop on
    conversations created by other developers or administrators.
    """
    _GLOBAL_CONV_CACHE = {}

    def __init__(self, brain_dir=None, base_dir=None):
        self.brain_dir = brain_dir or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        os.makedirs(self.brain_dir, exist_ok=True)
        self.meta_file = os.path.join(self.brain_dir, "session_ownership.json")
        self._ownership_mtime = 0.0
        self._ownership_cache = {}
        self._conv_meta_cache = SessionManager._GLOBAL_CONV_CACHE
        self.ownership = self._load_ownership()

    def reinit(self):
        self.brain_dir = os.path.expanduser("~/.gemini/antigravity-cli/brain")
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(self.brain_dir, exist_ok=True)
        self.meta_file = os.path.join(self.brain_dir, "session_ownership.json")
        self.ownership = self._load_ownership()

    def _load_ownership(self):
        if os.path.exists(self.meta_file):
            try:
                st_mtime = os.path.getmtime(self.meta_file)
                if st_mtime == getattr(self, "_ownership_mtime", 0.0) and getattr(self, "_ownership_cache", None):
                    return self._ownership_cache
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._ownership_mtime = st_mtime
                self._ownership_cache = data
                return data
            except Exception:
                if getattr(self, "_ownership_cache", None):
                    return self._ownership_cache
        return {}

    def _save_ownership(self):
        try:
            import sys
            import os
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            from security.mantrap import SemanticMantrap
            import logging
            
            with SemanticMantrap.execution_chamber(self.meta_file, "CoreEngine_SessionManager"):
                with open(self.meta_file, 'w', encoding='utf-8') as f:
                    json.dump(self.ownership, f, indent=2)
                try:
                    self._ownership_mtime = os.path.getmtime(self.meta_file)
                    self._ownership_cache = self.ownership
                except Exception:
                    pass
                    
        except Exception as e:
            import logging
            logging.error(f"[SessionManager] Failed to save session ownership: {e}")

    def _is_admin(self, user: dict = None) -> bool:
        if not user:
            return False
        return user.get("role") in ("admin", "super_admin", "super admin", "Tier5_SysAdmin")

    def _clean_prompt_text(self, text: str) -> str:
        if not text:
            return ""
        import re
        text = re.sub(r'<SYSTEM_MESSAGE>[\s\S]*?</SYSTEM_MESSAGE>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<SESSION_CONTINUATION_CONTEXT>[\s\S]*?</SESSION_CONTINUATION_CONTEXT>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<USER_SETTINGS_CHANGE>[\s\S]*?</USER_SETTINGS_CHANGE>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<MID_TASK_STEERING_UPDATE>[\s\S]*?</MID_TASK_STEERING_UPDATE>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<CONTEXT_SUMMARY>[\s\S]*?</CONTEXT_SUMMARY>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?USER_REQUEST>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[(?:STEER_NOW|QUEUE_NEXT)\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def register_session_owner(self, conv_id: str, username: str, project_name: str = None):
        if not conv_id or not username:
            return
        import time
        self.ownership = self._load_ownership()
        now_ts = time.time()
        conv_dir = os.path.join(self.brain_dir, conv_id)
        default_created = os.path.getmtime(conv_dir) if os.path.exists(conv_dir) else now_ts
        if conv_id not in self.ownership:
            self.ownership[conv_id] = {
                "owner": username,
                "project": project_name,
                "created_at": default_created,
                "updated_at": now_ts
            }
        else:
            self.ownership[conv_id]["updated_at"] = now_ts
            if project_name and not self.ownership[conv_id].get("project"):
                self.ownership[conv_id]["project"] = project_name
        self._save_ownership()

    def register_rollover(self, new_conv_id: str, old_conv_id: str, last_outcome: str = ""):
        if not new_conv_id or not old_conv_id:
            return
        self.ownership = self._load_ownership()
        if new_conv_id in self.ownership:
            self.ownership[new_conv_id]["rolled_over_from"] = old_conv_id
            if last_outcome:
                self.ownership[new_conv_id]["rollover_last_outcome"] = last_outcome[:15000]
            self._save_ownership()
    def can_user_access_session(self, conv_id: str, user: dict = None) -> bool:
        self.ownership = self._load_ownership()
        if not user:
            try:
                from core.routes.auth import get_current_user
                user = get_current_user()
            except Exception:
                pass
        if not user:
            return False
        if self._is_admin(user):
            return True

        record = self.ownership.get(conv_id)
        if record:
            return record.get("owner") == user.get("username")

        return False

    def _resolve_transcript_stat(self, conv_id: str):
        p1 = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        try:
            st = os.stat(p1)
            return p1, st.st_mtime, st.st_size
        except OSError:
            p2 = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
            try:
                st = os.stat(p2)
                return p2, st.st_mtime, st.st_size
            except OSError:
                return None, 0.0, 0

    def list_conversations(self, project_name=None, user=None, limit=None):
        self.ownership = self._load_ownership()
        candidates = []
        is_admin = self._is_admin(user)
        excluded_projects = {
            'venv', '__pycache__', 'templates', 'static', 'sandbox',
            'node_modules', 'site-packages', 'Cryptodome', 'pyzipper',
            'Zip-Files', 'Offline_Crack_Lab', 'Online_Brute_Lab'
        }
        
        for conv_id, meta in self.ownership.items():
            proj = meta.get("project")
            if proj == "archived_deletions":
                continue
            if proj in excluded_projects:
                proj = None
            if project_name:
                if proj != project_name:
                    continue
            else:
                if proj not in (None, "", "default"):
                    continue
            if not is_admin:
                if not user or meta.get("owner") != user.get("username"):
                    continue
            t_path, file_mtime, file_size = self._resolve_transcript_stat(conv_id)
            meta_ts = meta.get("updated_at") or meta.get("created_at") or 0
            sort_ts = max(meta_ts, file_mtime)
            candidates.append((sort_ts, conv_id, meta, t_path, file_mtime, file_size))

        candidates.sort(key=lambda item: item[0], reverse=True)

        total_count = len(candidates)
        has_more = False
        if limit is not None and limit > 0:
            has_more = total_count > limit
            candidates = candidates[:limit]

        generic_prompts = {
            "proceed", "continue", "yes", "ok", "okay", "hello", "helllo",
            "hi", "say hello", "hello world", "help"
        }

        results = []
        for sort_ts, conv_id, meta, transcript_path, file_mtime, file_size in candidates:
            custom_title = meta.get("custom_title") or ""
            cache_key = (file_mtime, file_size, custom_title)
            cached = self._conv_meta_cache.get(conv_id)
            if cached and cached[0] == cache_key:
                title, summary = cached[1], cached[2]
            else:
                title = custom_title or f"Session {conv_id[:6]}"
                summary = "No summary available."
                if transcript_path and file_size > 0:
                    try:
                        user_prompts = []
                        agent_responses = []
                        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                            for line in f:
                                try:
                                    data = json.loads(line)
                                except Exception:
                                    continue
                                dtype = data.get("type")
                                if dtype == "USER_INPUT":
                                    cleaned = self._clean_prompt_text(data.get("content", ""))
                                    if cleaned:
                                        user_prompts.append(cleaned)
                                elif dtype == "PLANNER_RESPONSE":
                                    resp_txt = (data.get("content") or "").strip()
                                    if resp_txt:
                                        agent_responses.append(resp_txt)

                        if user_prompts and not custom_title:
                            meaningful = [
                                p for p in user_prompts
                                if p.lower().rstrip(".!?") not in generic_prompts
                                and not p.lower().startswith("you asked: heading level")
                                and len(p) > 4
                            ]
                            chosen_prompt = meaningful[0] if meaningful else user_prompts[0]
                            snippet = chosen_prompt[:42].strip()
                            title = f"{snippet}..." if len(chosen_prompt) > 42 else snippet

                        if user_prompts or agent_responses:
                            first_q = user_prompts[0][:120] if user_prompts else "N/A"
                            latest_q = user_prompts[-1][:120] if user_prompts else "N/A"
                            latest_a = agent_responses[-1][:200].replace("\n", " ") if agent_responses else "Awaiting response"
                            summary = (
                                f"Turns: {len(user_prompts)} | "
                                f"Initial Topic: {first_q} | "
                                f"Latest Prompt: {latest_q} | "
                                f"Latest Outcome: {latest_a}"
                            )
                    except Exception:
                        pass
                self._conv_meta_cache[conv_id] = (cache_key, title, summary)

            results.append({
                "id": conv_id,
                "title": title,
                "summary": summary,
                "updated_at": sort_ts,
                "custom_renamed": bool(custom_title)
            })
            
        return results, has_more

    def rename_session(self, conv_id: str, new_title: str, user: dict = None) -> bool:
        if not conv_id or not new_title or not new_title.strip():
            return False
        if not self.can_user_access_session(conv_id, user):
            return False
        import time
        self.ownership = self._load_ownership()
        clean_title = self._clean_prompt_text(new_title.strip())
        if not clean_title:
            return False
        if conv_id not in self.ownership:
            self.ownership[conv_id] = {
                "owner": user.get("username", "admin") if user else "admin",
                "project": None,
                "custom_title": clean_title,
                "created_at": time.time(),
                "updated_at": time.time()
            }
        else:
            self.ownership[conv_id]["custom_title"] = clean_title
        self._conv_meta_cache.pop(conv_id, None)
        self._save_ownership()
        return True

    def delete_session(self, conv_id, user):
        if not self.can_user_access_session(conv_id, user):
            return False
        print(f"[SessionManager] Archiving single session {conv_id} to admin access instead of deleting.")
        if conv_id in self.ownership:
            self.ownership[conv_id]["owner"] = "admin"
            self.ownership[conv_id]["project"] = "archived_deletions"
        else:
            self.ownership[conv_id] = {
                "owner": "admin",
                "project": "archived_deletions"
            }
        self._conv_meta_cache.pop(conv_id, None)
        self._save_ownership()
        return True

    def delete_project_sessions(self, project_name, user):
        self.ownership = self._load_ownership()
        to_delete = []
        is_admin = self._is_admin(user)
        excluded_projects = {
            'venv', '__pycache__', 'templates', 'static', 'sandbox',
            'node_modules', 'site-packages', 'Cryptodome', 'pyzipper',
            'Zip-Files', 'Offline_Crack_Lab', 'Online_Brute_Lab'
        }
        for conv_id, meta in list(self.ownership.items()):
            proj = meta.get("project")
            if proj == "archived_deletions":
                continue
            if proj in excluded_projects:
                proj = None
            matches_proj = (proj == project_name) if project_name else (proj in (None, "", "default"))
            if matches_proj:
                if is_admin or (user and meta.get("owner") == user.get("username")):
                    to_delete.append(conv_id)

        for conv_id in to_delete:
            print(f"[SessionManager] Archiving session {conv_id} to admin access instead of deleting.")
            self.ownership[conv_id]["owner"] = "admin"
            self.ownership[conv_id]["project"] = "archived_deletions"
            self._conv_meta_cache.pop(conv_id, None)
        self._save_ownership()

    def get_conversation_transcript(self, conv_id: str, user: dict = None):
        if not conv_id or '..' in conv_id or '/' in conv_id or '\\' in conv_id:
            raise ValueError("Invalid conversation ID")

        if not self.can_user_access_session(conv_id, user):
            raise PermissionError("Access Denied: You do not have permission to view this conversation session")

        transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")

        if not os.path.exists(transcript_path):
            return []

        items = []
        import re
        try:
            with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("type") == "USER_INPUT":
                            cleaned_user = self._clean_prompt_text(data.get("content", ""))
                            if cleaned_user:
                                items.append({"sender": "user", "text": cleaned_user})
                        elif data.get("type") == "PLANNER_RESPONSE":
                            md = (data.get("content") or "").strip()
                            if md:
                                md = re.sub(
                                    r'\[([^\]]+)\]\((file:///[^()\s]*?)\s*<truncated[^>]*>[^)\n]*',
                                    r'[\1](\2)',
                                    md
                                )
                                if len(md) > 35000:
                                    md = md[:35000] + "\n\n... *(output truncated for browser responsiveness)*"
                                items.append({"sender": "agent", "markdown": md})
                    except Exception:
                        pass
        except Exception as e:
            print(f"[SessionManager] Error reading transcript for {conv_id}: {e}")

        return items[-20:]

    def get_last_outcome(self, conv_id: str) -> str:
        if not conv_id or '..' in conv_id or '/' in conv_id or '\\' in conv_id:
            return ""
        transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
        if not os.path.exists(transcript_path):
            return ""
        last_resp = ""
        import re
        try:
            with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "PLANNER_RESPONSE":
                            md = (data.get("content") or "").strip()
                            if md:
                                md = re.sub(
                                    r'\[([^\]]+)\]\((file:///[^()\s]*?)\s*<truncated[^>]*>[^)\n]*',
                                    r'[\1](\2)',
                                    md
                                )
                                if len(md) > 35000:
                                    md = md[:35000] + "\n\n... *(output truncated for browser responsiveness)*"
                                last_resp = md
                    except Exception:
                        continue
        except Exception as e:
            print(f"[SessionManager] Error reading last outcome for {conv_id}: {e}")
        return last_resp

    def get_rollover_info(self, conv_id: str, user: dict = None) -> dict:
        if not conv_id or '..' in conv_id or '/' in conv_id or '\\' in conv_id:
            return None
        if not self.can_user_access_session(conv_id, user):
            return None
        self.ownership = self._load_ownership()
        meta = self.ownership.get(conv_id, {})
        old_id = meta.get("rolled_over_from")
        last_outcome = meta.get("rollover_last_outcome", "")

        if not old_id or not last_outcome:
            transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
            if not os.path.exists(transcript_path):
                transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
            if os.path.exists(transcript_path):
                try:
                    import re
                    with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                        for line in f:
                            try:
                                d = json.loads(line)
                                if d.get("type") == "USER_INPUT":
                                    c = d.get("content", "")
                                    if "<SESSION_CONTINUATION_CONTEXT>" in c:
                                        if not last_outcome:
                                            m = re.search(r'- Latest Context / Outcome:\s*(.*?)(?:\n- Operational Rules|\n</SESSION_CONTINUATION_CONTEXT>)', c, re.DOTALL)
                                            if m:
                                                last_outcome = m.group(1).strip()
                                        if not old_id:
                                            m_old = re.search(r'Session ([a-f0-9\-]{8,})', c)
                                            if m_old:
                                                old_id = m_old.group(1)
                                        break
                            except Exception:
                                continue
                except Exception:
                    pass

        if not last_outcome and old_id:
            last_outcome = self.get_last_outcome(old_id)

        if old_id or last_outcome:
            return {
                "old_conversation_id": old_id,
                "last_outcome": last_outcome
            }
        return None
    def get_session_metrics(self, conv_id: str) -> dict:
        metrics = {
            "user_turns": 0,
            "total_steps": 0,
            "cached_tokens": 0,
            "total_tokens": 0
        }
        if not conv_id or '..' in conv_id or '/' in conv_id or '\\' in conv_id:
            return metrics
        transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
        if not os.path.exists(transcript_path):
            return metrics
        try:
            with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        dtype = data.get("type")
                        if dtype == "USER_INPUT":
                            metrics["user_turns"] += 1
                        elif dtype == "PLANNER_RESPONSE":
                            metrics["total_steps"] += 1

                        usage = data.get("usage")
                        if isinstance(usage, dict):
                            metrics["cached_tokens"] = max(metrics["cached_tokens"], usage.get("cache_read_tokens", 0))
                            metrics["total_tokens"] = max(metrics["total_tokens"], usage.get("total_tokens", 0))
                        elif "cache_read_tokens" in data:
                            metrics["cached_tokens"] = max(metrics["cached_tokens"], data.get("cache_read_tokens", 0))
                            metrics["total_tokens"] = max(metrics["total_tokens"], data.get("total_tokens", 0))
                    except Exception:
                        pass
        except Exception:
            pass
        return metrics

    def get_session_turn_count(self, conv_id: str) -> int:
        return self.get_session_metrics(conv_id).get("user_turns", 0)

    def generate_continuation_briefing(self, conv_id: str, workspace_path: str = None) -> str:
        """
        Extracts key working state, active workspace, recent user intents,
        recently touched files, and operational rules from the expiring session
        without making any external LLM calls.
        """
        if not conv_id:
            return ""
        
        self.ownership = self._load_ownership()
        meta = self.ownership.get(conv_id, {})
        project_name = meta.get("project") or "DevCore"
        
        workspace_dir = workspace_path or "/mnt/c/Users/michael/Documents/DevCore/playground"
        
        transcript_path = os.path.join(self.brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(self.brain_dir, conv_id, "transcript.jsonl")
            
        user_prompts = []
        agent_outcomes = []
        files_touched = set()
        
        if os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue
                        
                        dtype = data.get("type")
                        if dtype == "USER_INPUT":
                            cleaned = self._clean_prompt_text(data.get("content", ""))
                            if cleaned and len(cleaned) > 3:
                                user_prompts.append(cleaned)
                        elif dtype == "PLANNER_RESPONSE":
                            resp_txt = (data.get("content") or "").strip()
                            if resp_txt and len(resp_txt) > 10:
                                agent_outcomes.append(resp_txt)
                                
                        for call in data.get("tool_calls", []):
                            args = call.get("args") or {}
                            f_cand = (
                                args.get("Path")
                                or args.get("path")
                                or args.get("TargetFile")
                                or args.get("target_file")
                                or args.get("AbsolutePath")
                                or args.get("File")
                            )
                            if f_cand and isinstance(f_cand, str) and not f_cand.endswith((".log", ".tmp")):
                                clean_f = f_cand.replace('"', "").replace("'", "").strip()
                                files_touched.add(clean_f)
            except Exception as e:
                print(f"[SessionManager] Warning during briefing extraction: {e}")
                
        recent_goals_str = ""
        meaningful_prompts = user_prompts[-5:] if user_prompts else ["Continue active software engineering task."]
        for p in meaningful_prompts:
            clean_p = p[:600].strip()
            recent_goals_str += f"  • {clean_p}\n"
            
        recent_files_str = ""
        if files_touched:
            for fn in list(files_touched)[-15:]:
                recent_files_str += f"  • {fn}\n"
        else:
            recent_files_str = "  • None recorded in recent turns.\n"
            
        latest_outcome = "Ready to proceed."
        if agent_outcomes:
            latest_outcome = agent_outcomes[-1][:2000].strip()
            
        briefing = (
            "<SESSION_CONTINUATION_CONTEXT>\n"
            f"[AUTOMATIC SESSION ROLLOVER: Session {conv_id} archived to maintain peak responsiveness and eliminate token bloat.]\n"
            f"- Active Workspace Directory: {workspace_dir}\n"
            f"- Active Project: {project_name}\n"
            "- Recent Accomplished Goals:\n"
            f"{recent_goals_str}"
            "- Recently Touched Files:\n"
            f"{recent_files_str}"
            f"- Latest Context / Outcome:\n{latest_outcome}\n"
            "- Operational Rules: Screen-reader optimized responses; concise markdown; clickable file:// links; clean workspace protocol (no lingering scratch files).\n"
            "</SESSION_CONTINUATION_CONTEXT>"
        )
        return briefing


_SYNCING_ROUTES = False


def _ensure_ipv6_loopback_bridge(main_mod):
    """
    Ensures an IPv6 loopback listener ([::1]:5000) is active and forwarding to 127.0.0.1:5000
    so Windows localhost IPv6 SYN probes complete in <1ms even if Hypercorn was started IPv4-only.
    """
    if getattr(main_mod, "_ipv6_bridge_started", False):
        return
    import socket
    import threading
    import asyncio

    def _run_bridge():
        import time
        time.sleep(2.0)
        try:
            probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            probe.settimeout(0.2)
            already_listening = (probe.connect_ex(("::1", 5000, 0, 0)) == 0)
            probe.close()
            if already_listening:
                return
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except Exception:
                pass
            sock.bind(("::1", 5000, 0, 0))
            sock.listen(128)
            sock.setblocking(False)
        except OSError:
            return

        async def _pipe(reader, writer):
            try:
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
            except Exception:
                pass
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

        async def _handle_client(c_reader, c_writer):
            try:
                b_reader, b_writer = await asyncio.open_connection("127.0.0.1", 5000)
                await asyncio.gather(_pipe(c_reader, b_writer), _pipe(b_reader, c_writer))
            except Exception:
                try:
                    c_writer.close()
                except Exception:
                    pass

        async def _serve():
            server = await asyncio.start_server(_handle_client, sock=sock)
            async with server:
                await server.serve_forever()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_serve())
        except Exception:
            pass

    main_mod._ipv6_bridge_started = True
    t = threading.Thread(target=_run_bridge, name="DevCore-IPv6-Bridge", daemon=True)
    t.start()


def _sync_live_blueprint_routes():
    global _SYNCING_ROUTES
    if _SYNCING_ROUTES:
        return
    _SYNCING_ROUTES = True
    try:
        import sys
        import importlib
        main_mod = sys.modules.get("__main__") or sys.modules.get("core.server")
        live_app = getattr(main_mod, "app", None) if main_mod else None
        if live_app is None or not hasattr(live_app, "view_functions"):
            return

        _ensure_ipv6_loopback_bridge(main_mod)

        if "core.local_model_service" in sys.modules:
            try:
                importlib.reload(sys.modules["core.local_model_service"])
            except Exception:
                pass

        try:
            from core.local_model_service import discover_local_models
            local_opts = discover_local_models()
        except Exception:
            local_opts = [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]

        try:
            ui_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_config.json")
            if os.path.exists(ui_cfg_path):
                with open(ui_cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                models = cfg.get("header", {}).get("models")
                local_vals = {o["value"] for o in local_opts}
                if isinstance(models, list) and models:
                    filtered = [m for m in models if m.get("value") not in local_vals]
                    models = ([filtered[0]] + local_opts + filtered[1:]) if filtered else list(local_opts)
                    main_mod.CACHED_MODELS = models

            async def _fast_fetch_dynamic_models(force_cli: bool = False):
                cached = getattr(main_mod, "CACHED_MODELS", None)
                if cached is not None and not force_cli:
                    return cached
                try:
                    from core.local_model_service import discover_local_models as _disc_local
                    dyn_local = _disc_local()
                except Exception:
                    dyn_local = list(local_opts)
                local_set = {o["value"] for o in dyn_local}
                try:
                    if os.path.exists(ui_cfg_path):
                        with open(ui_cfg_path, "r", encoding="utf-8") as f:
                            c = json.load(f)
                        m = c.get("header", {}).get("models")
                        if isinstance(m, list) and m:
                            flt = [x for x in m if x.get("value") not in local_set]
                            m = ([flt[0]] + dyn_local + flt[1:]) if flt else list(dyn_local)
                            main_mod.CACHED_MODELS = m
                            return m
                except Exception:
                    pass
                return cached

            main_mod.fetch_dynamic_models = _fast_fetch_dynamic_models
        except Exception:
            pass

        for sec_sub in ("security.raugus_resolver", "security.security_headers", "security.vfs"):
            if sec_sub in sys.modules:
                try:
                    reloaded_mod = importlib.reload(sys.modules[sec_sub])
                    if sec_sub == "security.security_headers" and hasattr(reloaded_mod, "apply_security_headers"):
                        after_funcs = getattr(live_app, "after_request_funcs", {}).get(None, [])
                        for idx, fn in enumerate(after_funcs):
                            if getattr(fn, "__name__", "") == "apply_security_headers":
                                after_funcs[idx] = reloaded_mod.apply_security_headers
                    elif sec_sub == "security.vfs" and hasattr(reloaded_mod, "vfs"):
                        reloaded_mod.vfs.load()
                except Exception:
                    pass

        try:
            live_agent_mgr = live_app.config.get("AGENT_MANAGER") or getattr(main_mod, "agent_mgr", None)
            if "agents.mixins.comms_mixin" in sys.modules:
                comms_mod = importlib.reload(sys.modules["agents.mixins.comms_mixin"])
                if hasattr(comms_mod, "CommsMixin") and live_agent_mgr is not None:
                    for attr_n in ("broadcast", "handle_ack", "sync_client"):
                        if hasattr(comms_mod.CommsMixin, attr_n):
                            setattr(live_agent_mgr.__class__, attr_n, getattr(comms_mod.CommsMixin, attr_n))
            if "agents.mixins.execution_mixin" in sys.modules:
                exec_mod = importlib.reload(sys.modules["agents.mixins.execution_mixin"])
                if hasattr(exec_mod, "ExecutionMixin") and live_agent_mgr is not None:
                    for attr_n in ("_execute_agent", "_heartbeat_worker"):
                        if hasattr(exec_mod.ExecutionMixin, attr_n):
                            setattr(live_agent_mgr.__class__, attr_n, getattr(exec_mod.ExecutionMixin, attr_n))
            if live_agent_mgr is not None and not live_agent_mgr.is_running():
                if hasattr(live_agent_mgr, "message_queue"):
                    live_agent_mgr.message_queue.clear()
        except Exception:
            pass

        if "core.token_telemetry" in sys.modules:
            try:
                tt_mod = importlib.reload(sys.modules["core.token_telemetry"])
                if hasattr(tt_mod, "_ENGINE_INSTANCE"):
                    tt_mod._ENGINE_INSTANCE = None
            except Exception:
                pass

        if "core.routes.system" in sys.modules:
            sys_mod = importlib.reload(sys.modules["core.routes.system"])
            for fn_name in (
                "trigger_hot_patch",
                "reload_system",
                "csp_report",
                "api_trigger_red_team",
                "api_bootstrap_preflight",
                "api_jit_status",
                "api_jit_elevate",
                "api_jit_revoke",
                "telemetry_page",
                "api_token_telemetry",
            ):
                if hasattr(sys_mod, fn_name):
                    live_app.view_functions[f"system_bp.{fn_name}"] = getattr(sys_mod, fn_name)
            existing_endpoints = {r.endpoint for r in live_app.url_map.iter_rules()}
            dynamic_sys_routes = [
                ('/api/bootstrap/preflight', 'system_bp.api_bootstrap_preflight', 'api_bootstrap_preflight', ['GET', 'POST']),
                ('/api/security/jit-status', 'system_bp.api_jit_status', 'api_jit_status', ['GET']),
                ('/api/security/jit-elevate', 'system_bp.api_jit_elevate', 'api_jit_elevate', ['POST']),
                ('/api/security/jit-revoke', 'system_bp.api_jit_revoke', 'api_jit_revoke', ['POST']),
                ('/telemetry', 'system_bp.telemetry_page', 'telemetry_page', ['GET']),
                ('/api/telemetry/tokens', 'system_bp.api_token_telemetry', 'api_token_telemetry', ['GET']),
            ]
            from werkzeug.routing import Rule
            for rule_path, ep_name, attr_name, methods in dynamic_sys_routes:
                if hasattr(sys_mod, attr_name):
                    live_app.view_functions[ep_name] = getattr(sys_mod, attr_name)
                    if ep_name not in existing_endpoints:
                        try:
                            live_app.url_map.add(Rule(rule_path, endpoint=ep_name, methods=methods))
                        except Exception:
                            try:
                                live_app.add_url_rule(
                                    rule_path,
                                    endpoint=ep_name,
                                    view_func=getattr(sys_mod, attr_name),
                                    methods=methods,
                                )
                            except Exception:
                                pass
            if hasattr(sys_mod, "execute_hot_patch_sequence") and main_mod:
                main_mod.execute_hot_patch_sequence = sys_mod.execute_hot_patch_sequence

        if "core.routes.projects" in sys.modules:
            proj_mod = importlib.reload(sys.modules["core.routes.projects"])
            for fn_name in (
                "list_projects",
                "create_project",
                "set_active_project",
                "list_conversations",
                "get_conversation",
                "delete_conversation",
                "clear_project_sessions",
                "rename_conversation",
            ):
                if hasattr(proj_mod, fn_name):
                    live_app.view_functions[f"projects_bp.{fn_name}"] = getattr(proj_mod, fn_name)
            if "projects_bp.rename_conversation" not in [r.endpoint for r in live_app.url_map.iter_rules()]:
                try:
                    live_app.add_url_rule(
                        '/api/conversations/<conv_id>/rename',
                        endpoint='projects_bp.rename_conversation',
                        view_func=proj_mod.rename_conversation,
                        methods=['POST']
                    )
                except Exception:
                    pass

        if "core.routes.auth" in sys.modules:
            auth_mod = importlib.reload(sys.modules["core.routes.auth"])
            for ep in list(live_app.view_functions.keys()):
                if ep.startswith("auth_bp."):
                    fn_name = ep.split(".", 1)[1]
                    if hasattr(auth_mod, fn_name):
                        live_app.view_functions[ep] = getattr(auth_mod, fn_name)
            if hasattr(auth_mod, "auth_demo") and "auth_bp.auth_demo" not in [r.endpoint for r in live_app.url_map.iter_rules()]:
                try:
                    live_app.add_url_rule(
                        '/api/auth_demo',
                        endpoint='auth_bp.auth_demo',
                        view_func=auth_mod.auth_demo,
                        methods=['GET', 'POST']
                    )
                except Exception:
                    pass

        if "core.routes.files" in sys.modules:
            files_mod = importlib.reload(sys.modules["core.routes.files"])
            for ep in list(live_app.view_functions.keys()):
                if ep.startswith("files_bp."):
                    fn_name = ep.split(".", 1)[1]
                    if hasattr(files_mod, fn_name):
                        live_app.view_functions[ep] = getattr(files_mod, fn_name)
    except Exception as e:
        print(f"[SessionManager] Route sync warning: {e}")
    finally:
        _SYNCING_ROUTES = False


_sync_live_blueprint_routes()
