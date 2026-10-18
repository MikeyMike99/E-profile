#!/usr/bin/env python3
"""
=============================================================================
   DOCUMENTATION STRUCTURE & FORMAT AUDITOR (beginner-doc-suite)
=============================================================================
Automated structural and formatting linter that audits documentation across
all categories (Technical, DIY Creation Guides, Devstories, Devlog Pillars)
to enforce consistency, screen reader accessibility, and the Zero-Leak protocol.

Categories Audited:
  1. DIY / From-Scratch Creation Guides (Pillar 05 / Guides)
  2. Technical Documentation (Textbooks, Architecture, Operations Manual)
  3. Devstories / Manifesto (Origins, Chronicles, Forensic Timeline)
  4. Devlog Pillars (00 Primers, 01 Problems, 02 Evidence, 03 Diagnostics, 04 Solutions)
  5. Universal Rules (Heading cap at H3, 250-line ceiling, path sanitization, metadata)

Usage:
  python3 audit_doc_structure.py [PATH]
  python3 audit_doc_structure.py path/to/doc.md
  python3 audit_doc_structure.py /path/to/docs/ --category diy
  python3 audit_doc_structure.py --strict
  python3 audit_doc_structure.py --json
  python3 audit_doc_structure.py --fix path/to/doc.md
=============================================================================
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Forbidden absolute user paths that violate the Zero-Leak Protocol
LEAK_PATTERNS = [
    re.compile(r'/home/(?!<username>)[a-zA-Z0-9_\-\.]+/', re.IGNORECASE),
    re.compile(r'/mnt/c/Users/(?!<username>)[a-zA-Z0-9_\-\.]+/', re.IGNORECASE),
    re.compile(r'[a-zA-Z]:\\Users\\(?!<username>)[a-zA-Z0-9_\-\.]+\\', re.IGNORECASE),
    re.compile(r'file:///', re.IGNORECASE),
    re.compile(r'/tmp/sandbox_', re.IGNORECASE),
]

# Generic placeholders for path remediation
PATH_REPLACEMENTS = [
    (re.compile(r'/mnt/c/Users/[a-zA-Z0-9_\-\.]+/Documents/DevCore', re.IGNORECASE), '<project_root>'),
    (re.compile(r'/mnt/c/Users/[a-zA-Z0-9_\-\.]+/Documents/Central_Docs', re.IGNORECASE), '<central_docs_root>'),
    (re.compile(r'/mnt/c/Users/[a-zA-Z0-9_\-\.]+/Documents/e_profile', re.IGNORECASE), '<eprofile_root>'),
    (re.compile(r'/home/[a-zA-Z0-9_\-\.]+/', re.IGNORECASE), '$HOME/'),
    (re.compile(r'/mnt/c/Users/[a-zA-Z0-9_\-\.]+/', re.IGNORECASE), '%USERPROFILE%/'),
    (re.compile(r'C:\\Users\\[a-zA-Z0-9_\-\.]+\\', re.IGNORECASE), '%USERPROFILE%\\'),
    (re.compile(r'file:///+', re.IGNORECASE), './'),
]

# Metadata header regex
RE_DOC_ID = re.compile(r'\[//\]:\s*#\s*\(\s*DOC_ID:\s*([^|\s]+)\s*\|\s*VERSION:\s*([^|\s]+)', re.IGNORECASE)
RE_SECTION_ID = re.compile(r'\[//\]:\s*#\s*\(\s*SECTION_ID:\s*([^)]+)\)', re.IGNORECASE)


class IssueSeverity:
    CRITICAL = "CRITICAL"  # Fails the audit
    WARNING = "WARNING"    # Recommended improvement
    NOTICE = "NOTICE"      # Informational


class AuditIssue:
    def __init__(self, rule_id: str, severity: str, message: str, line_num: Optional[int] = None, fixable: bool = False):
        self.rule_id = rule_id
        self.severity = severity
        self.message = message
        self.line_num = line_num
        self.fixable = fixable

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "line_num": self.line_num,
            "fixable": self.fixable
        }


def detect_document_category(file_path: Path, content: str) -> str:
    """Infers the architectural documentation category of a markdown document."""
    path_str = str(file_path).replace("\\", "/").lower()
    filename = file_path.name.lower()
    text_sample = content[:3000].lower()

    # 1. Devstories / Manifesto / Origins (Folder context takes precedence)
    if (
        "manifesto" in path_str
        or "the_manifesto" in path_str
        or "story" in path_str
        or filename == "devlog.md"
        or "crucible" in filename
        or "timeline" in filename
    ):
        return "devstories"

    # 2. Technical Documentation (Textbook, Manual, Architecture Specs)
    if (
        "textbook" in path_str
        or "siraugga_textbook" in path_str
        or "manual" in path_str
        or "siraugga_master_manual" in path_str
        or "specs" in path_str
        or "reference" in path_str
    ):
        return "technical"

    # 3. DIY / From-Scratch Creation Guides
    if (
        "05_" in filename
        or "from_scratch" in path_str
        or "creation_guide" in filename
        or "bat_file_creation" in filename
        or ("blank notepad" in text_sample and "line by line" in text_sample)
    ):
        return "diy"

    # 4. Devlog Pillars (Inside devlog folder or pillar-numbered files)
    if "devlog" in path_str or "04_26" in filename:
        if "00_" in filename or "primer" in filename or "glossary" in filename:
            return "devlog_p00"
        if "01_" in filename or "problems" in path_str or "bug_" in filename:
            return "devlog_p01"
        if "02_" in filename or "evidence" in path_str or "source_" in filename:
            return "devlog_p02"
        if "03_" in filename or "diagnostics" in path_str or "test_" in filename:
            return "devlog_p03"
        if "04_" in filename or "solutions" in path_str or "blueprint" in filename:
            return "devlog_p04"
        return "devlog"

    # 5. General Guides
    if "guides" in path_str:
        if "creation" in filename or "bat_file" in filename:
            return "diy"
        return "technical"

    return "technical"


class DocStructureAuditor:
    def __init__(self, strict: bool = False):
        self.strict = strict

    def audit_document(self, file_path: Path, forced_category: Optional[str] = None) -> Tuple[str, List[AuditIssue]]:
        issues: List[AuditIssue] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return "unknown", [AuditIssue("FILE-READ", IssueSeverity.CRITICAL, f"Failed to read file: {e}")]

        lines = content.splitlines()
        category = forced_category or detect_document_category(file_path, content)

        # ---------------------------------------------------------------------
        # 1. Universal Checks (All Categories)
        # ---------------------------------------------------------------------
        self._check_h1_title(lines, issues)
        self._check_heading_hierarchy(lines, issues)
        self._check_path_sanitization(lines, issues)
        self._check_line_ceiling(lines, issues)
        self._check_metadata_tagging(content, issues)
        self._check_cross_references(content, issues, category)

        # ---------------------------------------------------------------------
        # 2. Category-Specific Checks
        # ---------------------------------------------------------------------
        if category == "diy":
            self._check_diy_category(content, issues)
        elif category == "technical":
            self._check_technical_category(content, issues)
        elif category == "devstories":
            self._check_devstories_category(content, issues)
        elif category.startswith("devlog"):
            self._check_devlog_category(content, issues, category)

        return category, issues

    # --- Universal Checkers ---

    def _check_h1_title(self, lines: List[str], issues: List[AuditIssue]):
        h1_count = 0
        h1_line = None
        for idx, line in enumerate(lines):
            # Exclude code blocks or comments
            if line.startswith("# ") and not line.startswith("## "):
                h1_count += 1
                if h1_line is None:
                    h1_line = idx + 1

        if h1_count == 0:
            issues.append(AuditIssue("UNI-H1-MISSING", IssueSeverity.CRITICAL, "Document lacks a top-level H1 title ('# Title')"))
        elif h1_count > 1:
            issues.append(AuditIssue("UNI-H1-MULTIPLE", IssueSeverity.WARNING, f"Document contains {h1_count} H1 headers; exactly one is recommended", h1_line))

    def _check_heading_hierarchy(self, lines: List[str], issues: List[AuditIssue]):
        """Ensures headings are strictly capped at H2 and H3 to protect screen readers."""
        in_code_block = False
        for idx, line in enumerate(lines):
            s_line = line.strip()
            if s_line.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            if s_line.startswith("####"):
                m = re.match(r'^(#{4,6})\s+(.+)$', s_line)
                if m:
                    level = len(m.group(1))
                    issues.append(AuditIssue(
                        "UNI-H4-CAP",
                        IssueSeverity.CRITICAL,
                        f"Screen reader rule violation: H{level} header detected ('{m.group(2)}'). Headings MUST be capped at H2 (##) and H3 (###).",
                        line_num=idx + 1,
                        fixable=True
                    ))

    def _check_path_sanitization(self, lines: List[str], issues: List[AuditIssue]):
        """Enforces Zero-Leak Protocol against hardcoded personal absolute paths."""
        in_code_block = False
        for idx, line in enumerate(lines):
            s_line = line.strip()
            if s_line.startswith("```"):
                in_code_block = not in_code_block
                continue

            for pattern in LEAK_PATTERNS:
                m = pattern.search(line)
                if m:
                    issues.append(AuditIssue(
                        "SEC-PATH-LEAK",
                        IssueSeverity.CRITICAL,
                        f"Zero-Leak violation: Leaked real path pattern '{m.group(0)}'. Use generic placeholders ($HOME, ~) or relative paths.",
                        line_num=idx + 1,
                        fixable=True
                    ))
                    break

    def _check_line_ceiling(self, lines: List[str], issues: List[AuditIssue]):
        """The 250-Line Ceiling Rule from beginner-doc-suite."""
        total_lines = len(lines)
        if total_lines > 350:
            issues.append(AuditIssue(
                "UNI-LINE-CEILING",
                IssueSeverity.WARNING,
                f"Document exceeds the recommended line ceiling: {total_lines} lines (Recommended: ~250–300 lines). Consider splitting into sub-chapters."
            ))

    def _check_metadata_tagging(self, content: str, issues: List[AuditIssue]):
        """Checks for Pure Markdown Metadata definition comment."""
        m = RE_DOC_ID.search(content)
        if not m:
            issues.append(AuditIssue(
                "UNI-META-TAG",
                IssueSeverity.WARNING,
                "Document lacks Pure Markdown Metadata comment [//]: # (DOC_ID: ... | VERSION: ...).",
                fixable=True
            ))

    def _check_cross_references(self, content: str, issues: List[AuditIssue], category: str):
        """Validates the Cross-Referencing Protocol (The Dropdown Standard)."""
        # Forewords and short primers are exempt
        if category in ["devlog_p00"] or "foreword" in content[:200].lower():
            return

        has_crossref_heading = "cross-reference" in content.lower() or "system parallel" in content.lower()
        has_dropdown = "<details" in content.lower() or "crossref-dropdown" in content.lower()

        if not has_crossref_heading and not has_dropdown:
            issues.append(AuditIssue(
                "ACC-CROSSREF-MISSING",
                IssueSeverity.WARNING,
                "Document lacks '## Cross-References & System Parallels' section or accessible <details> dropdown."
            ))

    # --- Category Checkers ---

    def _check_diy_category(self, content: str, issues: List[AuditIssue]):
        """Audits DIY / Pillar 05 From-Scratch Creation Guides."""
        text_lower = content.lower()

        # 1. Blank notepad / starting from scratch
        if not any(k in text_lower for k in ["blank notepad", "blank editor", "blank file", "from scratch", "from a blank"]):
            issues.append(AuditIssue(
                "DIY-BLANK-NOTEPAD",
                IssueSeverity.CRITICAL,
                "DIY Guide must explicitly guide the reader to start from a blank Notepad/editor window."
            ))

        # 2. Line ending warnings (CRLF vs LF)
        if not any(k in text_lower for k in ["crlf", "line ending", "line-ending", "\\r\\n", "unix line ending"]):
            issues.append(AuditIssue(
                "DIY-LINE-ENDINGS",
                IssueSeverity.WARNING,
                "DIY Guide lacks Windows/Linux line ending (CRLF vs LF) trap warnings for executable/script creation."
            ))

        # 3. Permissions / Executable Execution
        if not any(k in text_lower for k in ["chmod +x", "executable", "run as administrator", ".bat", "batch script"]):
            issues.append(AuditIssue(
                "DIY-EXEC-PERMS",
                IssueSeverity.NOTICE,
                "DIY Guide does not mention script execution permissions (chmod +x or Windows execution)."
            ))

        # 4. The 'Why Order Matters' Mandate
        if not any(k in text_lower for k in ["order matters", "why order matters", "sequence matters", "top to bottom", "order of operations"]):
            issues.append(AuditIssue(
                "DIY-ORDER-MATTERS",
                IssueSeverity.CRITICAL,
                "DIY Guide lacks the mandatory 'Why Order Matters' explanation of command/line sequencing."
            ))

        # 5. Verification Checklist
        if not any(k in text_lower for k in ["verification checklist", "10-second verification", "verification checklist", "checklist"]):
            issues.append(AuditIssue(
                "DIY-CHECKLIST",
                IssueSeverity.WARNING,
                "DIY Guide lacks a 10-second verification checklist to prove the created file works."
            ))

        # 6. Beginner Coder Q&A
        if "beginner coder q&a" not in text_lower and "beginner q&a" not in text_lower:
            issues.append(AuditIssue(
                "DIY-BEGINNER-QA",
                IssueSeverity.CRITICAL,
                "DIY Guide lacks the mandatory '## Beginner Coder Q&A' section answering common stumbling blocks."
            ))

    def _check_technical_category(self, content: str, issues: List[AuditIssue]):
        """Audits Technical Architecture, Textbook & Operations Manual Documents."""
        text_lower = content.lower()

        # 1. Overview / Concept
        if not any(k in text_lower for k in ["overview", "architecture", "specification", "concept", "principle", "introduction"]):
            issues.append(AuditIssue(
                "TECH-OVERVIEW",
                IssueSeverity.WARNING,
                "Technical document lacks a clear architectural overview or introductory concept section."
            ))

        # 2. The 'Why Order Matters' Mandate
        if not any(k in text_lower for k in ["order matters", "why order matters", "sequence", "order of execution", "lifecycle", "dependency"]):
            issues.append(AuditIssue(
                "TECH-ORDER-MATTERS",
                IssueSeverity.WARNING,
                "Technical specification lacks the 'Why Order Matters' mandate explaining subsystem or execution sequencing."
            ))

        # 3. Security / Clearance Tier Awareness
        if not any(k in text_lower for k in ["tier", "security", "clearance", "rbac", "zero-trust", "sandbox", "permission"]):
            issues.append(AuditIssue(
                "TECH-TIER-AWARENESS",
                IssueSeverity.NOTICE,
                "Technical document does not document security tiers or RBAC clearance boundaries."
            ))

        # 4. Beginner Coder Q&A
        if "beginner coder q&a" not in text_lower and "beginner q&a" not in text_lower:
            issues.append(AuditIssue(
                "TECH-BEGINNER-QA",
                IssueSeverity.WARNING,
                "Technical document lacks the recommended '## Beginner Coder Q&A' section."
            ))

    def _check_devstories_category(self, content: str, issues: List[AuditIssue]):
        """Audits Devstories, The Manifesto, and Origin Chronicles."""
        text_lower = content.lower()

        # 1. Narrative Context & Journey
        if not any(k in text_lower for k in ["journey", "built", "timeline", "origin", "crucible", "story", "chronicle", "problem"]):
            issues.append(AuditIssue(
                "STORY-NARRATIVE",
                IssueSeverity.WARNING,
                "Devstory document lacks clear narrative context explaining the problem or journey."
            ))

        # 2. Principles / Lessons Learned
        if not any(k in text_lower for k in ["lesson", "principle", "sovereignty", "learned", "insight", "moral", "takeaway"]):
            issues.append(AuditIssue(
                "STORY-LESSONS",
                IssueSeverity.NOTICE,
                "Devstory document could benefit from explicit architectural principles or lessons learned."
            ))

    def _check_devlog_category(self, content: str, issues: List[AuditIssue], pillar_cat: str):
        """Audits 5-Pillar Devlog Documents according to their functional pillar."""
        text_lower = content.lower()

        # Pillar 01: Problems Encountered
        if pillar_cat == "devlog_p01" or "problem" in content[:400].lower():
            if not any(k in text_lower for k in ["what happened", "symptom", "error", "crash", "bug"]):
                issues.append(AuditIssue("DEVLOG-P01-SYMPTOM", IssueSeverity.WARNING, "Pillar 01 Problem breakdown lacks '### What Happened' / Symptom description."))
            if not any(k in text_lower for k in ["why it happened", "root cause", "underlying cause", "timing"]):
                issues.append(AuditIssue("DEVLOG-P01-ROOTCAUSE", IssueSeverity.WARNING, "Pillar 01 Problem breakdown lacks '### Why It Happened' / Root Cause explanation."))

        # Pillar 02: Source Code Evidence
        if pillar_cat == "devlog_p02" or "evidence" in content[:400].lower():
            if "```" not in content:
                issues.append(AuditIssue("DEVLOG-P02-CODE", IssueSeverity.CRITICAL, "Pillar 02 Evidence document must contain verbatim fenced code excerpts (` ``` `)."))
            if not any(k in text_lower for k in ["what this proves", "what this source proves", "evidence proves", "proves that"]):
                issues.append(AuditIssue("DEVLOG-P02-PROOF", IssueSeverity.WARNING, "Pillar 02 Evidence document lacks '### What This Source Proves' analysis."))

        # Pillar 03: Diagnostic Tests
        if pillar_cat == "devlog_p03" or "diagnostic" in content[:400].lower():
            if not any(k in text_lower for k in ["what we tested", "test procedure", "test script"]):
                issues.append(AuditIssue("DEVLOG-P03-TESTED", IssueSeverity.NOTICE, "Pillar 03 Diagnostic document lacks '### What We Tested' specification."))
            if not any(k in text_lower for k in ["exact command", "command run", "executed"]):
                issues.append(AuditIssue("DEVLOG-P03-CMD", IssueSeverity.NOTICE, "Pillar 03 Diagnostic document lacks '### Exact Command Run'."))

        # Pillar 04: Solutions & Architecture
        if pillar_cat == "devlog_p04" or "solution" in content[:400].lower():
            if not any(k in text_lower for k in ["order matters", "why order matters", "sequence", "top to bottom"]):
                issues.append(AuditIssue("DEVLOG-P04-ORDER", IssueSeverity.WARNING, "Pillar 04 Solution document lacks the mandatory 'Why Order Matters' explanation."))

        # Beginner Q&A for Devlog chapters (Pillars 01-05)
        if pillar_cat in ["devlog_p01", "devlog_p02", "devlog_p03", "devlog_p04"]:
            if "beginner coder q&a" not in text_lower and "beginner q&a" not in text_lower:
                issues.append(AuditIssue("DEVLOG-BEGINNER-QA", IssueSeverity.WARNING, "Devlog chapter lacks '## Beginner Coder Q&A' section."))


def auto_fix_document(file_path: Path) -> bool:
    """Safely remediates common formatting and path violations in a markdown document."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    modified = False
    new_lines = []
    in_code_block = False

    for line in content.splitlines():
        s_line = line.strip()
        if s_line.startswith("```"):
            in_code_block = not in_code_block

        # 1. Remediate H4+ headings to H3 (Screen Reader Optimization)
        if not in_code_block and s_line.startswith("####"):
            m = re.match(r'^(#{4,6})\s+(.+)$', s_line)
            if m:
                heading_text = m.group(2)
                line = f"### {heading_text}"
                modified = True

        # 2. Remediate leaked paths using generic placeholders
        for pat, repl in PATH_REPLACEMENTS:
            if pat.search(line):
                line = pat.sub(repl, line)
                modified = True

        new_lines.append(line)

    if modified:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True
    return False


def run_audit(target_path: Path, forced_category: Optional[str] = None, strict: bool = False, json_mode: bool = False, fix_mode: bool = False) -> bool:
    auditor = DocStructureAuditor(strict=strict)
    files_to_audit = []

    if target_path.is_file():
        files_to_audit.append(target_path)
    else:
        for p in target_path.rglob("*.md"):
            if any(ignored in str(p) for ignored in [".git", "node_modules", "venv", ".archive", ".backup", "scratch"]):
                continue
            files_to_audit.append(p)

    files_to_audit.sort()
    total_files = len(files_to_audit)

    if not json_mode:
        print("====================================================================")
        print("   DOCUMENTATION STRUCTURE & FORMAT AUDITOR (beginner-doc-suite)")
        print("====================================================================")
        print(f"Target: {target_path} ({total_files} documents discovered)")
        if forced_category:
            print(f"Enforced Category Rule Set: {forced_category.upper()}")
        print("====================================================================\n")

    results = []
    total_critical = 0
    total_warning = 0
    total_notice = 0
    clean_files = 0
    fixed_count = 0

    for f_path in files_to_audit:
        if fix_mode and auto_fix_document(f_path):
            fixed_count += 1

        cat, issues = auditor.audit_document(f_path, forced_category=forced_category)
        crit_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        warn_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        note_count = sum(1 for i in issues if i.severity == IssueSeverity.NOTICE)

        total_critical += crit_count
        total_warning += warn_count
        total_notice += note_count

        if crit_count == 0 and warn_count == 0:
            clean_files += 1

        doc_result = {
            "file": str(f_path),
            "category": cat,
            "status": "PASS" if crit_count == 0 else "FAIL",
            "critical_count": crit_count,
            "warning_count": warn_count,
            "notice_count": note_count,
            "issues": [i.to_dict() for i in issues]
        }
        results.append(doc_result)

        if not json_mode and (issues or crit_count > 0):
            rel_name = f_path.name
            badge = "\033[92m[PASS]\033[0m" if crit_count == 0 else "\033[91m[FAIL]\033[0m"
            print(f"{badge} {rel_name} \033[90m({cat.upper()})\033[0m")
            for issue in issues:
                color = "\033[91m" if issue.severity == IssueSeverity.CRITICAL else ("\033[93m" if issue.severity == IssueSeverity.WARNING else "\033[90m")
                line_str = f":L{issue.line_num}" if issue.line_num else ""
                print(f"     {color}[{issue.severity}]{line_str}\033[0m {issue.message}")
            print()

    overall_pass = (total_critical == 0) if not strict else (total_critical == 0 and total_warning == 0)

    if json_mode:
        output = {
            "summary": {
                "total_documents": total_files,
                "clean_documents": clean_files,
                "critical_violations": total_critical,
                "warning_violations": total_warning,
                "notice_count": total_notice,
                "overall_status": "PASS" if overall_pass else "FAIL"
            },
            "documents": results
        }
        print(json.dumps(output, indent=2))
    else:
        print("====================================================================")
        summary_color = "\033[92m" if overall_pass else "\033[91m"
        print(f"   {summary_color}AUDIT SUMMARY: {clean_files}/{total_files} FULLY COMPLIANT DOCUMENTS\033[0m")
        print(f"   Critical Violations: {total_critical}  |  Warnings: {total_warning}  |  Notices: {total_notice}")
        if fix_mode:
            print(f"   Auto-Remediated Documents: {fixed_count}")
        print("====================================================================")

    return overall_pass


def main():
    parser = argparse.ArgumentParser(description="Documentation Structure & Format Auditor (beginner-doc-suite)")
    parser.add_argument("path", type=str, nargs="?", default=".", help="Path to markdown file or documentation folder (default: current directory)")
    parser.add_argument("--category", "-c", type=str, choices=["diy", "technical", "devstories", "devlog", "devlog_p00", "devlog_p01", "devlog_p02", "devlog_p03", "devlog_p04"], help="Force specific category audit rules")
    parser.add_argument("--strict", action="store_true", help="Enforce strict mode (fail on warnings as well as criticals)")
    parser.add_argument("--json", "-j", action="store_true", help="Output audit results in structured JSON format")
    parser.add_argument("--fix", action="store_true", help="Auto-remediate common path leaks and H4+ heading caps")
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"[ERROR] Target path does not exist: {target}")
        sys.exit(1)

    success = run_audit(target, forced_category=args.category, strict=args.strict, json_mode=args.json, fix_mode=args.fix)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
