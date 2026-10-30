import asyncio
import json
import os
import time
import sys
import shutil
import random
import re
import traceback
import logging
from pathlib import Path


def _iter_transcript_roots():
    base_dir = Path(__file__).resolve().parent.parent.parent
    seen = set()
    for candidate in (
        base_dir,
        base_dir / "demo",
        Path.cwd(),
        Path.cwd() / "demo",
        base_dir.parent,
        base_dir.parent.parent,
        base_dir.parent.parent / "demo",
        base_dir.parent.parent.parent,
        Path.home(),
    ):
        try:
            resolved = candidate.resolve()
            if resolved not in seen and resolved.exists():
                seen.add(resolved)
                yield resolved
        except Exception:
            continue


class TranscriptMixin:
    @staticmethod
    def _strip_aria_noise(text: str) -> str:
        if not text:
            return ""
        s = str(text)
        s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)
        s = re.sub(
            r'file:///[^\s)>\]]+',
            lambda m: os.path.basename(re.sub(r'#L\d+(?:-L?\d+)?', '', m.group(0)).rstrip('/')),
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r'(?:/mnt/[a-zA-Z]/|/home/|/var/|/tmp/|/etc/|/opt/|/usr/|[A-Za-z]:\\)[^\s)>\]"\'`,;]+',
            lambda m: os.path.basename(
                re.sub(r'#L\d+(?:-L?\d+)?', '', re.sub(r':\d+(?:-\d+)?$', '', m.group(0))).replace('\\', '/').rstrip('/')
            ),
            s,
        )
        s = re.sub(r'#L\d+(?:-L?\d+)?\b', '', s, flags=re.IGNORECASE)
        s = re.sub(r'(\.[a-zA-Z0-9]{1,6}):\d+(?:-\d+)?\b', r'\1', s)
        s = re.sub(r'\(\s*lines?\s+L?\d+(?:\s*(?:-|–|to)\s*L?\d+)?\s*\)', '', s, flags=re.IGNORECASE)
        s = re.sub(r'\blines?\s+L?\d+\s*(?:-|–|to)\s*L?\d+\b', '', s, flags=re.IGNORECASE)
        s = re.sub(r'([a-zA-Z0-9])_([a-zA-Z0-9])', r'\1 \2', s)
        s = re.sub(r'([a-zA-Z0-9])_([a-zA-Z0-9])', r'\1 \2', s)
        s = re.sub(r'[*`#_()\[\]{}]', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _normalize_tool_name(name: str) -> str:
        if not name:
            return ""
        return str(name).split(":")[-1].split("__")[-1].strip().lower()

    @staticmethod
    def prune_transcript_symbol_blocks(transcript_path: str) -> dict:
        """
        Safely inspects transcript.jsonl and replaces bulky tool dumps (> 80 lines)
        with [CACHED_BLOCK: <ref> | HASH: <hash>] markers, preserving JSON Lines structure
        and returning statistics on tokens/bytes pruned.
        """
        if not os.path.exists(transcript_path):
            return {
                "success": False,
                "error": f"Transcript not found at {transcript_path}",
                "lines_processed": 0,
                "blocks_pruned": 0,
                "bytes_saved": 0,
                "tokens_saved_estimate": 0,
            }

        import hashlib
        pruned_lines = []
        blocks_pruned = 0
        bytes_saved = 0
        lines_processed = 0

        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                lines_processed += 1
                stripped = line.strip()
                if not stripped:
                    pruned_lines.append(line)
                    continue
                try:
                    data = json.loads(stripped)
                    content = data.get("content")
                    if isinstance(content, str):
                        lines = content.splitlines()
                        if len(lines) > 80:
                            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
                            match = re.search(r'(?:Path|TargetFile|target_file|key)["\s:=]+([^"\s,\n\\]+)', content)
                            ref_label = match.group(1) if match else "tool_dump"
                            new_content = f"[CACHED_BLOCK: {ref_label} | HASH: {content_hash}]"
                            old_bytes = len(content.encode("utf-8"))
                            new_bytes = len(new_content.encode("utf-8"))
                            data["content"] = new_content
                            blocks_pruned += 1
                            bytes_saved += max(0, old_bytes - new_bytes)
                    pruned_lines.append(json.dumps(data) + "\n")
                except Exception:
                    pruned_lines.append(line)

        if blocks_pruned > 0:
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.writelines(pruned_lines)

        return {
            "success": True,
            "transcript_path": transcript_path,
            "lines_processed": lines_processed,
            "blocks_pruned": blocks_pruned,
            "bytes_saved": bytes_saved,
            "tokens_saved_estimate": int(bytes_saved / 4),
        }

    async def _get_narrative_context(self, conversation_id, expected_tool_name=None):
        deep_insight = ""
        tool_args = {}
        try:
            from collections import deque
            conv_id = getattr(self, "current_conversation_id", None) or conversation_id
            if not conv_id:
                return "", {}

            candidate_dirs = []
            for root in _iter_transcript_roots():
                candidate_dirs.append(root / ".gemini" / "antigravity-cli" / "brain" / str(conv_id) / ".system_generated" / "logs")
                candidate_dirs.append(root / ".gemini" / "antigravity" / "brain" / str(conv_id) / ".system_generated" / "logs")

            t_path = None
            for c_dir in candidate_dirs:
                full_cand = c_dir / "transcript_full.jsonl"
                norm_cand = c_dir / "transcript.jsonl"
                if full_cand.exists():
                    t_path = str(full_cand)
                    break
                elif norm_cand.exists():
                    t_path = str(norm_cand)
                    break
            if not t_path:
                return "", {}

            norm_expected = self._normalize_tool_name(expected_tool_name)

            for _ in range(10):
                if os.path.exists(t_path):
                    with open(t_path, 'r', encoding='utf-8') as tf:
                        last_lines = deque(tf, maxlen=100)
                        for line in reversed(last_lines):
                            try:
                                d = json.loads(line)
                                if d.get("type") == "PLANNER_RESPONSE":
                                    if not norm_expected:
                                        if d.get("thinking"):
                                            deep_insight = d.get("thinking")
                                            break
                                    else:
                                        tool_calls = d.get("tool_calls", [])
                                        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                                            for t in reversed(tool_calls):
                                                t_norm = self._normalize_tool_name(t.get("name"))
                                                if norm_expected and t_norm != norm_expected:
                                                    continue
                                                if not tool_args:
                                                    tool_args = t.get("args", {}) or {}
                                                if not deep_insight and d.get("thinking"):
                                                    deep_insight = d.get("thinking")
                                                break

                                        if not deep_insight and d.get("thinking"):
                                            deep_insight = d.get("thinking")

                                        if tool_args and deep_insight:
                                            break
                            except Exception:
                                pass
                if deep_insight:
                    break
                await asyncio.sleep(0.08)

            if deep_insight:
                deep_insight = re.sub(r'CRITICAL INSTRUCTION.*?\n', '', deep_insight)
                deep_insight = re.sub(r'<planning_mode>.*?</planning_mode>', '', deep_insight, flags=re.DOTALL)
                deep_insight = re.sub(r'<bash_command_reminder>.*?</bash_command_reminder>', '', deep_insight, flags=re.DOTALL)
                deep_insight = re.sub(r'<[^>]+>', '', deep_insight)
                paras = [p.strip() for p in deep_insight.split('\n') if p.strip()]
                if paras:
                    deep_insight = self._strip_aria_noise(" ".join(paras))
                    if len(deep_insight) > 1200:
                        last_period = deep_insight[:1200].rfind('.')
                        if last_period > 200:
                            deep_insight = deep_insight[:last_period + 1]
                        else:
                            deep_insight = deep_insight[:1200] + "..."
        except Exception:
            pass
        return deep_insight, tool_args

    def _get_security(self):
        if self._local_sec is None:
            try:
                try:
                    from security.local_security import LocalSecurity
                except ImportError:
                    from local_security import LocalSecurity
                self._local_sec = LocalSecurity()
            except Exception as e:
                print(f"[Security] LocalSecurity init failed, using Dummy. Error: {e}")
                class Dummy:
                    def scrub_text(self, t): return t
                self._local_sec = Dummy()
        return self._local_sec

    async def tail_transcript(self, conv_id):
        import platform

        wsl_path = None
        for root in _iter_transcript_roots():
            cand = root / ".gemini" / "antigravity-cli" / "brain" / str(conv_id) / ".system_generated" / "logs" / "transcript.jsonl"
            if cand.exists():
                wsl_path = str(cand)
                break
        if not wsl_path:
            wsl_path = str(Path.home() / ".gemini" / "antigravity-cli" / "brain" / str(conv_id) / ".system_generated" / "logs" / "transcript.jsonl")

        await asyncio.sleep(2)

        if platform.system() == 'Windows':
            process = await asyncio.create_subprocess_exec(
                'wsl.exe', 'bash', '-c', f'stdbuf -oL tail -n 0 -F {wsl_path}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            process = await asyncio.create_subprocess_exec(
                'tail', '-n', '0', '-F', wsl_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        try:
            while self.current_conversation_id == conv_id:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace')
                if "Stop hook blocked termination" in line_str:
                    pass
                elif "automatically approved" in line_str:
                    pass
                elif "has gone idle" in line_str or "killed" in line_str or "terminated" in line_str:
                    await self.broadcast({"type": "audio", "sound": "completed"})
                elif "invoked subagent" in line_str or "message to another agent" in line_str:
                    await self.broadcast({"type": "audio", "sound": "incoming"})
        except asyncio.CancelledError:
            process.terminate()
        except Exception as e:
            logging.error(f"[TranscriptMixin] Transcript tailer failed: {e}")
            try:
                process.terminate()
            except Exception:
                pass
