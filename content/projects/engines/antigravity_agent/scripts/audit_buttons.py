#!/usr/bin/env python3
"""
=============================================================================
   INTERACTIVE BUTTON & ACCESSIBILITY AUDITOR (audit_buttons.py)
=============================================================================
Comprehensive static analysis and accessibility linter that audits all
interactive buttons, action triggers, and keyboard shortcuts across DevCore
and system web templates (sandbox/templates, templates, e_profile/templates).

Health Vectors Audited:
  1. DOM Identity: Verifies unique id or semantic selector for testability.
  2. Accessible Name (WCAG 4.1.2): Enforces inner text, aria-label, or title.
  3. Action Binding: Verifies onclick, form submit, or script event listener.
  4. Keyboard Operability (WCAG 2.1.1): Ensures role="button" elements have
     tabindex="0" and keyboard triggers (Enter / Space). Native <button> and
     <a href> are verified for standard keyboard interaction.
  5. Shortcut Integrity: Validates that aria-keyshortcuts (e.g. Alt+S, Alt+L)
     are actively bound in client JavaScript.
  6. JS Target Integrity: Checks that document.getElementById calls in onclick
     reference valid DOM elements defined in the document.

Usage:
  python3 scripts/audit_buttons.py
  python3 scripts/audit_buttons.py --json
  python3 scripts/audit_buttons.py sandbox/templates/index.html
  python3 scripts/audit_buttons.py --strict
=============================================================================
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class InteractiveElementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements: List[Dict[str, Any]] = []
        self.all_ids: Set[str] = set()
        self.scripts: List[str] = []
        self._current_tag: Optional[str] = None
        self._current_attrs: Dict[str, str] = {}
        self._current_start_line: int = 1
        self._text_buffer: List[str] = []
        self._in_script: bool = False
        self._script_buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        if "id" in attr_dict and attr_dict["id"]:
            self.all_ids.add(attr_dict["id"].strip())

        if tag == "script":
            self._in_script = True
            self._script_buffer = []
            return

        # Skip modal backdrops which are click-outside overlays, not interactive buttons
        is_backdrop = "backdrop" in attr_dict.get("class", "").lower()
        if is_backdrop:
            return

        is_button = (
            tag == "button"
            or attr_dict.get("role") == "button"
            or (tag == "a" and "btn" in attr_dict.get("class", ""))
            or ("onclick" in attr_dict and tag in ["div", "span", "a", "li"])
        )

        if is_button:
            self._current_tag = tag
            self._current_attrs = attr_dict
            self._current_start_line = self.getpos()[0]
            self._text_buffer = []

    def handle_data(self, data: str):
        if self._in_script:
            self._script_buffer.append(data)
        elif self._current_tag:
            cleaned = data.strip()
            if cleaned:
                self._text_buffer.append(cleaned)

    def handle_endtag(self, tag: str):
        if tag == "script":
            self._in_script = False
            self.scripts.append("".join(self._script_buffer))
            self._script_buffer = []
            return

        if self._current_tag and tag == self._current_tag:
            label = " ".join(self._text_buffer).strip()
            self.elements.append({
                "tag": self._current_tag,
                "line": self._current_start_line,
                "attrs": self._current_attrs,
                "inner_text": label,
            })
            self._current_tag = None
            self._current_attrs = {}
            self._text_buffer = []


def find_bound_identifiers_in_scripts(scripts_text: str) -> Tuple[Set[str], Set[str]]:
    """Extracts element IDs and CSS class names that have event listeners attached in JS."""
    bound_ids: Set[str] = set()
    bound_classes: Set[str] = set()

    # Pattern 1: document.getElementById('myId').addEventListener(...)
    for match in re.finditer(r"getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.addEventListener", scripts_text):
        bound_ids.add(match.group(1))

    # Pattern 2: const myVar = document.getElementById('myId'); ... myVar.addEventListener(...)
    var_to_id: Dict[str, str] = {}
    for match in re.finditer(r"(?:var|let|const)\s+([a-zA-Z0-9_$]+)\s*=\s*document\.getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", scripts_text):
        var_to_id[match.group(1)] = match.group(2)

    for var_name, el_id in var_to_id.items():
        if re.search(rf"\b{re.escape(var_name)}\s*\.addEventListener", scripts_text):
            bound_ids.add(el_id)

    # Pattern 3: querySelectorAll('.myClass') ... addEventListener
    for match in re.finditer(r"querySelectorAll\s*\(\s*['\"]\.[a-zA-Z0-9_\-\.\s]*?([a-zA-Z0-9_\-]+)['\"]\s*\)", scripts_text):
        bound_classes.add(match.group(1))

    for match in re.finditer(r"getElementsByClassName\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", scripts_text):
        bound_classes.add(match.group(1))

    return bound_ids, bound_classes


def audit_template(file_path: Path) -> Dict[str, Any]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "file": str(file_path),
            "error": f"Failed to read file: {e}",
            "total_buttons": 0,
            "compliant_buttons": 0,
            "issues": [{
                "severity": "CRITICAL",
                "message": f"Unreadable file: {e}",
                "line": 1
            }],
        }

    parser = InteractiveElementParser()
    parser.feed(content)

    combined_scripts = "\n".join(parser.scripts)
    bound_ids, bound_classes = find_bound_identifiers_in_scripts(combined_scripts)

    button_issues: List[Dict[str, Any]] = []
    audited_buttons: List[Dict[str, Any]] = []
    compliant_count = 0

    for idx, el in enumerate(parser.elements):
        tag = el["tag"]
        line = el["line"]
        attrs = el["attrs"]
        inner_text = el["inner_text"]

        btn_id = attrs.get("id")
        onclick = attrs.get("onclick", "")
        role = attrs.get("role", "")
        btn_type = attrs.get("type", "")
        aria_label = attrs.get("aria-label", "")
        aria_labelledby = attrs.get("aria-labelledby", "")
        aria_shortcuts = attrs.get("aria-keyshortcuts", "")
        title_attr = attrs.get("title", "")
        tabindex = attrs.get("tabindex", "")
        href = attrs.get("href", "")
        classes = set(attrs.get("class", "").split())

        issues_for_el: List[Dict[str, str]] = []

        # 1. Accessible Name Vector (WCAG 4.1.2)
        has_accessible_name = bool(inner_text or aria_label or aria_labelledby or title_attr)
        if not has_accessible_name:
            issues_for_el.append({
                "code": "MISSING_ACCESSIBLE_NAME",
                "severity": "CRITICAL",
                "message": f"<{tag}> at line {line} has no inner text, aria-label, aria-labelledby, or title.",
            })

        # 2. Keyboard Operability Vector (WCAG 2.1.1)
        # Note: <a href="..."> is natively keyboard-accessible (Enter key) without needing tabindex="0"
        is_native_focusable = (tag == "button") or (tag == "a" and bool(href))
        if not is_native_focusable and (role == "button" or onclick):
            if tabindex != "0":
                issues_for_el.append({
                    "code": "NON_NATIVE_TABINDEX_MISSING",
                    "severity": "CRITICAL",
                    "message": f"<{tag} role='button'> at line {line} requires tabindex='0' for keyboard focus.",
                })
            has_keyboard_handler = (
                "onkeydown" in attrs
                or "onkeyup" in attrs
                or "onkeypress" in attrs
                or (btn_id and btn_id in bound_ids)
                or bool(classes.intersection(bound_classes))
            )
            if not has_keyboard_handler:
                issues_for_el.append({
                    "code": "MISSING_KEYBOARD_TRIGGER",
                    "severity": "WARNING",
                    "message": f"<{tag} role='button'> at line {line} lacks an explicit Enter/Space keyboard handler.",
                })

        # 3. Action Binding Vector
        has_action = (
            bool(onclick)
            or btn_type == "submit"
            or (btn_id and btn_id in bound_ids)
            or bool(classes.intersection(bound_classes))
            or (tag == "a" and bool(href))
        )
        if not has_action and btn_type != "reset":
            issues_for_el.append({
                "code": "UNBOUND_ACTION",
                "severity": "WARNING",
                "message": f"<{tag}> '{btn_id or inner_text[:20]}' at line {line} has no onclick, submit type, or script listener.",
            })

        # 4. Shortcut Integrity Vector
        if aria_shortcuts:
            for shortcut in [s.strip() for s in aria_shortcuts.split(",") if s.strip()]:
                match = re.search(r"(?:Alt|Ctrl|Shift|Meta)\+([A-Za-z0-9])", shortcut, re.IGNORECASE)
                if match:
                    key_char = match.group(1).lower()
                    pattern = rf"e\.key(?:\.toLowerCase\(\))?\s*===?\s*['\"]{key_char}['\"]|key\s*===\s*['\"]{key_char.upper()}['\"]"
                    if not re.search(pattern, combined_scripts, re.IGNORECASE):
                        issues_for_el.append({
                            "code": "SHORTCUT_NOT_IMPLEMENTED",
                            "severity": "CRITICAL",
                            "message": f"Button advertises aria-keyshortcuts='{shortcut}', but no matching keydown listener for '{key_char}' exists in scripts.",
                        })

        # 5. JS Target Integrity Vector
        if onclick:
            id_calls = re.findall(r"document\.getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", onclick)
            for target_id in id_calls:
                if target_id not in parser.all_ids and "{{" not in target_id:
                    issues_for_el.append({
                        "code": "BROKEN_DOM_TARGET",
                        "severity": "CRITICAL",
                        "message": f"onclick references document.getElementById('{target_id}'), but id='{target_id}' is not found in the DOM.",
                    })

        # 6. DOM Identity Notice
        if not btn_id and tag == "button":
            issues_for_el.append({
                "code": "NO_EXPLICIT_ID",
                "severity": "NOTICE",
                "message": f"Button '{inner_text[:25]}' at line {line} lacks an explicit id attribute.",
            })

        has_critical = any(i["severity"] == "CRITICAL" for i in issues_for_el)
        if not has_critical:
            compliant_count += 1

        button_issues.extend(issues_for_el)
        audited_buttons.append({
            "index": idx + 1,
            "line": line,
            "tag": tag,
            "id": btn_id or "(none)",
            "label": inner_text or aria_label or title_attr or "(empty)",
            "issues": issues_for_el,
            "passed": not has_critical,
        })

    return {
        "file": str(file_path),
        "total_buttons": len(parser.elements),
        "compliant_buttons": compliant_count,
        "issues": button_issues,
        "buttons": audited_buttons,
    }


def find_target_templates(specified_path: Optional[str] = None) -> List[Path]:
    if specified_path:
        p = Path(specified_path).resolve()
        if p.is_file():
            return [p]
        elif p.is_dir():
            return list(p.glob("**/*.html"))
        return []

    templates: List[Path] = []
    base_dirs = [
        Path("/mnt/c/Users/michael/Documents/DevCore/sandbox/templates"),
        Path("/mnt/c/Users/michael/Documents/DevCore/templates"),
        Path("/mnt/c/Users/michael/Documents/e_profile/templates"),
    ]
    for b in base_dirs:
        if b.is_dir():
            for f in b.glob("*.html"):
                if f.name.endswith(".html") and not f.name.endswith("_test"):
                    templates.append(f)
    return sorted(set(templates))


def run_audit(target_path: Optional[str] = None, json_mode: bool = False, strict: bool = False) -> bool:
    targets = find_target_templates(target_path)
    if not targets:
        if json_mode:
            print(json.dumps({
                "status": "ERROR",
                "error": "No template files found to audit.",
                "summary": {"total_files": 0, "total_buttons": 0}
            }, indent=2))
        else:
            print("[ERROR] No template files found to audit.")
        return False

    all_results = []
    total_buttons = 0
    total_compliant = 0
    total_critical = 0
    total_warning = 0
    total_notice = 0

    for t in targets:
        res = audit_template(t)
        all_results.append(res)
        total_buttons += res.get("total_buttons", 0)
        total_compliant += res.get("compliant_buttons", 0)
        for iss in res.get("issues", []):
            sev = iss.get("severity")
            if sev == "CRITICAL":
                total_critical += 1
            elif sev == "WARNING":
                total_warning += 1
            elif sev == "NOTICE":
                total_notice += 1

    overall_pass = (total_critical == 0) and (not strict or total_warning == 0)
    status_str = "PASSED" if overall_pass else ("WARNING" if total_critical == 0 else "FAILED")

    if json_mode:
        output = {
            "status": status_str,
            "overall_status": status_str,
            "summary": {
                "overall_status": status_str,
                "total_templates": len(targets),
                "total_buttons": total_buttons,
                "compliant_buttons": total_compliant,
                "critical_violations": total_critical,
                "warning_violations": total_warning,
                "notice_count": total_notice,
                "compliance_pct": round((total_compliant / max(1, total_buttons)) * 100, 1),
            },
            "results": all_results,
        }
        print(json.dumps(output, indent=2))
    else:
        print("====================================================================")
        print("   INTERACTIVE BUTTON & ACCESSIBILITY AUDIT REPORT")
        print("====================================================================")
        for res in all_results:
            rel_name = os.path.basename(res["file"])
            pass_ratio = f"{res['compliant_buttons']}/{res['total_buttons']}"
            file_issues = [i for i in res.get("issues", []) if i["severity"] in ["CRITICAL", "WARNING"]]
            file_status = "🟢 PASS" if not file_issues else ("🔴 FAIL" if any(i["severity"] == "CRITICAL" for i in file_issues) else "🟡 WARN")
            print(f" {file_status} {rel_name:30s} | Buttons: {pass_ratio:8s} | Critical: {sum(1 for i in file_issues if i['severity'] == 'CRITICAL')} | Warnings: {sum(1 for i in file_issues if i['severity'] == 'WARNING')}")
            for iss in file_issues[:5]:
                print(f"    - [{iss['severity']}] {iss['message']}")
            if len(file_issues) > 5:
                print(f"    - ... and {len(file_issues) - 5} more issues.")

        print("--------------------------------------------------------------------")
        color = "\033[92m" if overall_pass else "\033[91m"
        print(f" {color}AUDIT STATUS: {status_str}\033[0m")
        print(f" Total Templates: {len(targets)} | Total Buttons: {total_buttons} | Compliant: {total_compliant}")
        if total_critical == 0:
            print(f" [ALL TESTS PASSED] 0 Severe Violations | Warnings: {total_warning} | Notices: {total_notice}")
        else:
            print(f" [FAIL] Severe Violations: {total_critical} | Warnings: {total_warning} | Notices: {total_notice}")
        print("====================================================================")

    return overall_pass


def main():
    parser = argparse.ArgumentParser(description="Interactive Button & Accessibility Auditor")
    parser.add_argument("path", type=str, nargs="?", default=None, help="Path to specific HTML file or template folder")
    parser.add_argument("--json", "-j", action="store_true", help="Output audit results in JSON format")
    parser.add_argument("--strict", "-s", action="store_true", help="Fail if any warnings are detected")
    args = parser.parse_args()

    success = run_audit(target_path=args.path, json_mode=args.json, strict=args.strict)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
