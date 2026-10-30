import ast
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class AuditRegistry:
    """Manages system audit registration, discovery, execution, and persistent reporting."""

    def __init__(self, repo_root: Optional[str] = None):
        if repo_root is None:
            self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.repo_root = repo_root

        self.scripts_dir = os.path.join(self.repo_root, "scripts")
        self.manifest_path = os.path.join(self.repo_root, "core", "audits_manifest.json")
        self.results_cache_path = os.path.join(self.repo_root, "logs", "audit_results.json")
        self._audits: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._running_locks: Dict[str, bool] = {}

        self.load_results_cache()
        self.register_builtin_audits()
        self.discover_audits()

    def register_builtin_audits(self):
        builtins = [
            {
                "id": "interactive_buttons",
                "name": "Interactive Button & Accessibility Auditor",
                "category": "accessibility",
                "command": [sys.executable, os.path.join(self.repo_root, "scripts", "audit_buttons.py"), "--json"],
                "description": "Audits all HTML templates for interactive buttons, WCAG accessible names, keyboard operability (WCAG 2.1.1), Alt+S/Alt+L/Alt+C shortcut bindings, and DOM target integrity.",
                "target_file": "scripts/audit_buttons.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "system_network",
                "name": "System Network & Threat Intelligence Auditor",
                "category": "network",
                "command": [sys.executable, os.path.join(self.repo_root, "scripts", "audit_system_network.py"), "--json"],
                "description": "Inspects WebSocket socket transport (tcpdump), keep-alive heartbeats, sandbox egress, domain supply-chain vetting (whois), and IP threat triage.",
                "target_file": "scripts/audit_system_network.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "security_tier_rbac",
                "name": "Automated Security Tier & RBAC Audit",
                "category": "security",
                "command": [sys.executable, os.path.join(self.repo_root, "security", "security_audit.py")],
                "description": "Validates Role-Based Access Control, path traversal defenses, file classification tiers, and unauthorized tampering.",
                "target_file": "security/security_audit.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "tool_security_canary",
                "name": "5-Stage Workspace Tool Security Audit",
                "category": "security",
                "command": [sys.executable, os.path.join(self.repo_root, "security", "tool_security_auditor.py")],
                "description": "Enforces RBAC tiers, PreToolUse hook interceptions, AST static code hygiene, DLP canary scrubbing, and SIEM/MAQ logging.",
                "target_file": "security/tool_security_auditor.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "threat_vectors",
                "name": "Threat Vector Matrix & DAST Scan",
                "category": "threat",
                "command": [sys.executable, os.path.join(self.repo_root, "scripts", "audit_threat_vectors.py")],
                "description": "Executes the central threat vector matrix and dynamic application security testing suite.",
                "target_file": "scripts/audit_threat_vectors.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "bootstrap_preflight",
                "name": "Core Engine AST & Inode Preflight Check",
                "category": "system",
                "command": [
                    sys.executable,
                    "-c",
                    "import json; from core.bootstrap_gateway import run_preflight_checks; print(json.dumps(run_preflight_checks(spawn_agent=False, exit_on_failure=False, quiet=True)))",
                ],
                "description": "Verifies core backend Python module compilation (py_compile), file integrity, and JIT elevation status.",
                "target_file": "core/bootstrap_gateway.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "ast_efficiency",
                "name": "AST Token Reduction & Efficiency Auditor",
                "category": "efficiency",
                "command": [sys.executable, os.path.join(self.repo_root, "scripts", "audit_ast_efficiency.py"), "--json"],
                "description": "Measures AST surgical block extraction token savings, latency, and context headroom SLA (>= 80% reduction).",
                "target_file": "scripts/audit_ast_efficiency.py",
                "is_builtin": True,
                "enabled": True,
            },
            {
                "id": "doc_structure",
                "name": "Documentation Structure & Accessibility Linter",
                "category": "documentation",
                "command": [
                    sys.executable,
                    os.path.join(self.repo_root, "scripts", "audit_doc_structure.py"),
                    os.path.join(self.repo_root, "..", "Central_Docs", "projects", "siraugga_framework")
                    if os.path.isdir(os.path.join(self.repo_root, "..", "Central_Docs", "projects", "siraugga_framework"))
                    else "docs/",
                    "--json",
                ],
                "description": "Enforces screen-reader heading ceilings (H3), 250-line file limits, and Zero-Leak path sanitization.",
                "target_file": "scripts/audit_doc_structure.py",
                "is_builtin": True,
                "enabled": True,
            },
        ]
        for b in builtins:
            self._audits[b["id"]] = b

    def discover_audits(self) -> Dict[str, Dict[str, Any]]:
        if os.path.isdir(self.scripts_dir):
            for fname in os.listdir(self.scripts_dir):
                if not (fname.startswith("audit_") and fname.endswith(".py")):
                    continue
                full_path = os.path.join(self.scripts_dir, fname)
                rel_path = f"scripts/{fname}"

                already_registered = any(
                    a.get("target_file") == rel_path or a.get("id") == fname[:-3]
                    for a in self._audits.values()
                )
                if already_registered:
                    continue

                audit_id = fname[:-3]
                title, desc = self._extract_ast_docstring(full_path, fallback_title=audit_id.replace("_", " ").title())
                category = self._infer_category(fname, desc)

                self._audits[audit_id] = {
                    "id": audit_id,
                    "name": title,
                    "category": category,
                    "command": [sys.executable, full_path],
                    "description": desc,
                    "target_file": rel_path,
                    "is_builtin": False,
                    "enabled": True,
                }

        if os.path.isfile(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                custom_audits = manifest.get("custom_audits", [])
                for ca in custom_audits:
                    cid = ca.get("id")
                    if cid and cid not in self._audits:
                        self._audits[cid] = {
                            "id": cid,
                            "name": ca.get("name", cid),
                            "category": ca.get("category", "custom"),
                            "command": ca.get("command", []),
                            "description": ca.get("description", ""),
                            "target_file": ca.get("target_file", ""),
                            "is_builtin": False,
                            "enabled": ca.get("enabled", True),
                        }
            except Exception:
                pass

        return self._audits

    def _extract_ast_docstring(self, file_path: str, fallback_title: str) -> Tuple[str, str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=file_path)
            doc = ast.get_docstring(tree)
            if not doc:
                return fallback_title, "Custom workspace audit script."

            lines = [l.strip() for l in doc.splitlines() if l.strip() and not l.strip().startswith("=")]
            if not lines:
                return fallback_title, "Custom workspace audit script."

            title = lines[0]
            if len(title) > 60:
                title = title[:57] + "..."

            desc = " ".join(lines[1:3]) if len(lines) > 1 else lines[0]
            if len(desc) > 160:
                desc = desc[:157] + "..."

            return title, desc
        except Exception:
            return fallback_title, "Custom workspace audit script."

    def _infer_category(self, filename: str, desc: str) -> str:
        combined = f"{filename} {desc}".lower()
        if any(w in combined for w in ["efficiency", "benchmark", "token_reduction", "ast_efficiency"]):
            return "efficiency"
        if any(w in combined for w in ["button", "accessibility", "a11y", "wcag", "interactive"]):
            return "accessibility"
        if any(w in combined for w in ["network", "tcp", "whois", "egress", "stream"]):
            return "network"
        if any(w in combined for w in ["security", "rbac", "token", "auth", "permission"]):
            return "security"
        if any(w in combined for w in ["threat", "dast", "attack", "penetration"]):
            return "threat"
        if any(w in combined for w in ["doc", "markdown", "lint", "reader"]):
            return "documentation"
        if any(w in combined for w in ["system", "preflight", "engine", "inode"]):
            return "system"
        return "custom"

    def get_catalog(self) -> List[Dict[str, Any]]:
        self.discover_audits()
        catalog = []
        for aid, meta in self._audits.items():
            item = dict(meta)
            item.pop("command", None)
            res = self._results.get(aid, {})
            item["last_run"] = res.get("timestamp")
            item["last_status"] = res.get("status", "PENDING")
            item["duration_seconds"] = res.get("duration_seconds")
            item["summary"] = res.get("summary", "")
            catalog.append(item)
        return catalog

    def get_audit(self, audit_id: str) -> Optional[Dict[str, Any]]:
        if audit_id not in self._audits:
            return None
        meta = dict(self._audits[audit_id])
        meta.pop("command", None)
        res = self._results.get(audit_id, {})
        meta["result"] = res
        return meta

    async def run_audit(self, audit_id: str) -> Dict[str, Any]:
        if audit_id not in self._audits:
            return {"success": False, "error": f"Audit '{audit_id}' not found."}

        if self._running_locks.get(audit_id):
            return {"success": False, "error": f"Audit '{audit_id}' is already executing."}

        audit_meta = self._audits[audit_id]
        cmd = audit_meta.get("command")
        if not cmd:
            return {"success": False, "error": f"Audit '{audit_id}' has no executable command configured."}

        self._running_locks[audit_id] = True
        start_time = time.time()
        iso_timestamp = datetime.utcnow().isoformat() + "Z"

        try:
            if isinstance(cmd, list):
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=self.repo_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=self.repo_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=90.0)
            duration = round(time.time() - start_time, 2)
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            returncode = proc.returncode

            parsed_data, status, summary = self._parse_audit_output(stdout, stderr, returncode)

            result_entry = {
                "audit_id": audit_id,
                "name": audit_meta.get("name", audit_id),
                "category": audit_meta.get("category", "custom"),
                "status": status,
                "summary": summary,
                "returncode": returncode,
                "duration_seconds": duration,
                "timestamp": iso_timestamp,
                "stdout": stdout,
                "stderr": stderr,
                "parsed_data": parsed_data,
            }

            self._results[audit_id] = result_entry
            self.save_results_cache()
            return {"success": True, "result": result_entry}

        except asyncio.TimeoutError:
            duration = round(time.time() - start_time, 2)
            result_entry = {
                "audit_id": audit_id,
                "name": audit_meta.get("name", audit_id),
                "category": audit_meta.get("category", "custom"),
                "status": "FAIL",
                "summary": f"Audit timed out after {duration}s.",
                "returncode": -1,
                "duration_seconds": duration,
                "timestamp": iso_timestamp,
                "stdout": "",
                "stderr": "Execution exceeded timeout limit (90s).",
                "parsed_data": None,
            }
            self._results[audit_id] = result_entry
            self.save_results_cache()
            return {"success": False, "error": "Execution timed out", "result": result_entry}
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            result_entry = {
                "audit_id": audit_id,
                "name": audit_meta.get("name", audit_id),
                "category": audit_meta.get("category", "custom"),
                "status": "ERROR",
                "summary": f"Audit execution failed: {e}",
                "returncode": -1,
                "duration_seconds": duration,
                "timestamp": iso_timestamp,
                "stdout": "",
                "stderr": str(e),
                "parsed_data": None,
            }
            self._results[audit_id] = result_entry
            self.save_results_cache()
            return {"success": False, "error": str(e), "result": result_entry}
        finally:
            self._running_locks[audit_id] = False

    async def run_all_audits(self) -> List[Dict[str, Any]]:
        self.discover_audits()
        results = []
        for aid, meta in self._audits.items():
            if meta.get("enabled", True):
                res = await self.run_audit(aid)
                results.append(res.get("result", {}))
        return results

    def _parse_audit_output(self, stdout: str, stderr: str, returncode: int) -> Tuple[Any, str, str]:
        parsed = None
        trimmed = stdout.strip()
        if trimmed:
            try:
                parsed = json.loads(trimmed)
            except Exception:
                start_obj = trimmed.rfind("\n{")
                start_arr = trimmed.rfind("\n[")
                start = max(start_obj, start_arr)
                if start != -1:
                    try:
                        parsed = json.loads(trimmed[start:].strip())
                    except Exception:
                        pass

        if isinstance(parsed, dict):
            if "total_buttons" in parsed.get("summary", {}):
                status = parsed["summary"].get("overall_status", "PASS")
                s = parsed["summary"]
                summary = f"Total: {s.get('total_buttons')}, Compliant: {s.get('compliant_buttons')}, Critical: {s.get('critical_violations')}, Warnings: {s.get('warning_violations')}"
                return parsed, status, summary
            if "total_documents" in parsed.get("summary", {}):
                status = parsed["summary"].get("overall_status", "PASS")
                s = parsed["summary"]
                summary = f"Total: {s.get('total_documents')}, Clean: {s.get('clean_documents')}, Critical: {s.get('critical_violations')}, Warnings: {s.get('warning_violations')}"
                return parsed, status, summary
            if "total_tests" in parsed.get("summary", {}):
                s = parsed["summary"]
                status = "PASS" if s.get("failed", 0) == 0 else "FAIL"
                summary = f"{s.get('passed', 0)}/{s.get('total_tests', 0)} tests passed ({s.get('pass_rate_pct', 0)}% in {s.get('total_duration_ms', 0)}ms)"
                return parsed, status, summary
            if "overall_status" in parsed.get("summary", {}):
                status = parsed["summary"]["overall_status"]
                s = parsed["summary"]
                summary = f"Overall Status: {status}"
                return parsed, status, summary
            if "status" in parsed:
                status = str(parsed["status"]).upper()
                summary = f"Overall Status: {status}"
                return parsed, status, summary
            if "success" in parsed:
                status = "PASS" if parsed["success"] else "FAIL"
                summary = "Preflight checks passed." if parsed["success"] else f"Preflight error: {parsed.get('error', 'checks failed')}"
                return parsed, status, summary
            if "audits" in parsed:
                total_audits = len(parsed["audits"])
                passes = sum(1 for a in parsed["audits"].values() if isinstance(a, dict) and a.get("status") == "PASS")
                warns = sum(1 for a in parsed["audits"].values() if isinstance(a, dict) and a.get("status") == "WARN")
                status = "PASS" if passes == total_audits else ("WARN" if warns > 0 and (passes + warns == total_audits) else "FAIL")
                summary = f"{passes}/{total_audits} network audit probes passed ({warns} warnings)."
                return parsed, status, summary

        if isinstance(parsed, list):
            total = len(parsed)
            passes = sum(1 for item in parsed if isinstance(item, dict) and item.get("status") == "PASS")
            fails = sum(1 for item in parsed if isinstance(item, dict) and item.get("status") == "FAIL")
            status = "PASS" if fails == 0 else "FAIL"
            summary = f"{passes}/{total} stage checks verified successfully."
            return parsed, status, summary

        upper_out = stdout.upper()
        if returncode == 0:
            if "ALL TESTS PASSED" in upper_out or "23/23 TESTS PASSED" in upper_out:
                return None, "PASS", "All automated security test suites verified."
            if "[FAIL]" in stdout or "CRITICAL" in upper_out or "FAILED" in upper_out:
                return None, "FAIL", "Violations or test failures detected in stdout."
            if "[WARN]" in stdout:
                return None, "WARN", "Completed with warnings."
            return None, "PASS", "Completed successfully with returncode 0."
        else:
            return None, "FAIL", f"Process exited with non-zero returncode ({returncode})."

    def load_results_cache(self):
        if os.path.isfile(self.results_cache_path):
            try:
                with open(self.results_cache_path, "r", encoding="utf-8") as f:
                    self._results = json.load(f)
            except Exception:
                self._results = {}

    def save_results_cache(self):
        try:
            os.makedirs(os.path.dirname(self.results_cache_path), exist_ok=True)
            with open(self.results_cache_path, "w", encoding="utf-8") as f:
                json.dump(self._results, f, indent=2)
        except Exception:
            pass


_registry_instance: Optional[AuditRegistry] = None


def get_audit_registry() -> AuditRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AuditRegistry()
    return _registry_instance
