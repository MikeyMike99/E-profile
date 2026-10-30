#!/usr/bin/env python3
"""
DevCore Local Model Service Benchmark & Diagnostic Suite (benchmark_local_model.py).

Provides an extensible, automated benchmark for evaluating the offline local model
service (core/local_model_service.py). Measures natural intent pre-scanning, resilient
tool-call parsing, display text sanitization, path traversal defenses, file size
limits and scalability, and end-to-end autonomous file operations.

Extensibility Contract:
To add new benchmark test cases:
1. Directory Intent: Add (prompt, expected_matched_bool, expected_subpath) to DIRECTORY_INTENT_CASES.
2. Read Intent: Add (prompt, expected_filename) to READ_INTENT_CASES.
3. Write Intent: Add (prompt, expected_filename, expected_content) to WRITE_INTENT_CASES.
4. Tool Call Extraction: Add (raw_model_output, expected_action, expected_path) to TOOL_EXTRACTION_CASES.
5. Path Traversal: Add (operation_type, payload_path) to PATH_TRAVERSAL_CASES.
6. File Size Limits & Scalability: Add test configuration dictionaries to FILE_SIZE_CASES.
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

from core.local_model_service import (
    calculate_dynamic_execution_params,
    clean_local_model_display_text,
    execute_local_agent_task,
    extract_local_tool_calls,
    local_list_directory,
    local_read_file,
    local_write_file,
    parse_directory_intent,
    parse_read_intent,
    parse_write_intent,
)


def generate_dynamic_intent_suite() -> Dict[str, List[Any]]:
    read_verbs = ["read", "view", "open", "cat", "inspect", "check", "display", "examine", "show me"]
    read_fillers = ["the file", "file", "contents of", "inside", ""]
    read_targets = ["lab.py", "main.py", "config.json", "settings.cfg", "core/server.py", "notes.txt"]

    read_cases: List[Tuple[str, Optional[str]]] = []
    for verb in read_verbs:
        for filler in read_fillers:
            for target in read_targets:
                prefix = f"{verb} {filler}".strip()
                read_cases.append((f"{prefix} {target}", target))

    read_cases.extend([
        ("how do I read files in linux?", None),
        ("tell me about the python language", None),
        ("write a quick function to add numbers", None),
    ])

    write_templates = [
        ("create a file named {file} with '{content}'", "{file}", "{content}"),
        ("write {content} to {file}", "{file}", "{content}"),
        ("save {content} to {file}", "{file}", "{content}"),
        ('create file {file} with {content}', "{file}", "{content}"),
    ]
    write_samples = [
        ("notes.txt", "Hello from DevCore"),
        ("test.py", "hello"),
        ("hello.py", "print('hi')"),
        ("config.json", '{"debug": true}'),
    ]
    write_cases: List[Tuple[str, Optional[str], Optional[str]]] = []
    for tmpl, exp_file, exp_content in write_templates:
        for f, c in write_samples:
            prompt = tmpl.format(file=f, content=c)
            write_cases.append((prompt, f, c))
    write_cases.extend([
        ("write an essay about cybersecurity", None, None),
        ("how do I create a file?", None, None),
    ])

    dir_roots = [
        "what is in my directory?",
        "what's in my directory?",
        "what files do I have in the workspace?",
        "what files are here?",
        "list the files in this folder",
        "show me my files",
        "browse root",
        "check my directory",
        "ls",
    ]
    dir_sub_templates = [
        "ls {sub}",
        "browse the directory {sub}",
        "show contents of {sub}",
        "what is inside the folder {sub}",
        "list files in {sub}",
        "what files are in folder {sub}",
    ]
    subpaths = ["subfolder", "game_demo", "data", "src/components"]

    dir_cases: List[Tuple[str, bool, Optional[str]]] = [(p, True, "") for p in dir_roots]
    for tmpl in dir_sub_templates:
        for sub in subpaths:
            dir_cases.append((tmpl.format(sub=sub), True, sub))

    dir_cases.extend([
        ("explain what an AST is", False, None),
        ("write a python function to add two numbers", False, None),
        ("help me debug this error", False, None),
    ])

    return {
        "read": read_cases,
        "write": write_cases,
        "directory": dir_cases,
    }


DIRECTORY_INTENT_CASES: List[Tuple[str, bool, Optional[str]]] = [
    ("what is in my directory?", True, ""),
    ("what's in my directory?", True, ""),
    ("what files do I have in the workspace?", True, ""),
    ("what files are here?", True, ""),
    ("list the files in this folder", True, ""),
    ("show me my files", True, ""),
    ("browse root", True, ""),
    ("check my directory", True, ""),
    ("ls", True, ""),
    ("ls subfolder/test", True, "subfolder/test"),
    ("browse the directory subfolder", True, "subfolder"),
    ("show contents of game_demo", True, "game_demo"),
    ("what is inside the folder data", True, "data"),
    ("list files in src/components", True, "src/components"),
    ("what files are in folder src/components", True, "src/components"),
    ("explain what an AST is", False, None),
    ("write a python function to add two numbers", False, None),
    ("help me debug this error", False, None),
]

READ_INTENT_CASES: List[Tuple[str, Optional[str]]] = [
    ("read the file lab.py", "lab.py"),
    ("read lab.py", "lab.py"),
    ("view lab.py", "lab.py"),
    ("cat notes.txt", "notes.txt"),
    ("check the file config.json", "config.json"),
    ("open main.py", "main.py"),
    ("what is inside lab.py?", "lab.py"),
    ("show me what is in settings.cfg", "settings.cfg"),
    ("inspect file core/server.py", "core/server.py"),
    ("how do I read files in linux?", None),
    ("tell me about the python language", None),
]

WRITE_INTENT_CASES: List[Tuple[str, Optional[str], Optional[str]]] = [
    ("create a file named notes.txt with 'Hello from DevCore'", "notes.txt", "Hello from DevCore"),
    ("write hello to test.py", "test.py", "hello"),
    ("save print('hi') to hello.py", "hello.py", "print('hi')"),
    ('create file config.json with {"debug": true}', "config.json", '{"debug": true}'),
    ("write an essay about cybersecurity", None, None),
    ("how do I create a file?", None, None),
]

TOOL_EXTRACTION_CASES: List[Dict[str, Any]] = [
    {
        "name": "Standard Closed Tool Tag",
        "raw": '<tool_call>{"action": "list_dir", "path": "."}</tool_call>',
        "expected_count": 1,
        "expected_action": "list_dir",
        "expected_path": ".",
    },
    {
        "name": "Unclosed Tool Tag (Qwen 1.5B Truncation)",
        "raw": '<tool_call>{"action": "list_dir", "path": "."}',
        "expected_count": 1,
        "expected_action": "list_dir",
        "expected_path": ".",
    },
    {
        "name": "Unclosed Write Tool Tag",
        "raw": '<tool_call>{"action": "write_file", "path": "output.txt", "content": "benchmark payload"}',
        "expected_count": 1,
        "expected_action": "write_file",
        "expected_path": "output.txt",
    },
    {
        "name": "Tool Tag Followed By Text",
        "raw": '<tool_call>{"action": "read_file", "path": "main.py"}\nI will inspect this file now.',
        "expected_count": 1,
        "expected_action": "read_file",
        "expected_path": "main.py",
    },
    {
        "name": "Bracket Syntax Multi-Block",
        "raw": '[WRITE_FILE: script.py]\nprint("hello")\n[/WRITE_FILE]\n[READ_FILE: main.py]\n[LIST_DIR: src]',
        "expected_count": 3,
        "expected_action": "write_file",
        "expected_path": "script.py",
    },
]

DISPLAY_SANITIZATION_CASES: List[Dict[str, str]] = [
    {
        "name": "Strip Tool Call with Trailing Response",
        "input": '<tool_call>{"action": "list_dir", "path": "."} Here is your summary.',
        "expected": "Here is your summary.",
    },
    {
        "name": "Strip Bare Tool Call",
        "input": '<tool_call>{"action": "list_dir", "path": "."}',
        "expected": "",
    },
    {
        "name": "Strip Unclosed Write Call",
        "input": '<tool_call>{"action": "write_file", "path": "test.txt", "content": "foo"} File written successfully.',
        "expected": "File written successfully.",
    },
    {
        "name": "Preserve Markdown Formatting",
        "input": "### Directory Status\n- Item 1\n- Item 2\n\n```python\nprint('code')\n```",
        "expected": "### Directory Status\n- Item 1\n- Item 2\n\n```python\nprint('code')\n```",
    },
]

PATH_TRAVERSAL_CASES: List[Tuple[str, str]] = [
    ("read", "../../server.py"),
    ("read", "../../../etc/passwd"),
    ("list", "../../"),
    ("list", "../"),
    ("write", "../forbidden.txt"),
    ("write", "../../escape.py"),
]

def generate_file_size_sweep(
    max_size_mb: float = 2.5,
    custom_sizes: Optional[List[int]] = None,
    include_boundaries: bool = True,
) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    boundary_1mb = 1024 * 1024

    if custom_sizes is not None:
        sample_sizes = sorted(list(set(custom_sizes)))
    else:
        sample_sizes = [0, 128, 64 * 1024, 950 * 1024]
        if include_boundaries:
            sample_sizes.extend([boundary_1mb, boundary_1mb + 1, int(max_size_mb * boundary_1mb)])
        sample_sizes = sorted(list(set(sample_sizes)))

    for sz in sample_sizes:
        if sz <= boundary_1mb:
            if sz == 0:
                name = "Empty File Read (0 Bytes)"
            elif sz == 128:
                name = "Small File Read (128 Bytes)"
            elif sz == 64 * 1024:
                name = "Medium File Read (64 KB)"
            elif sz == 950 * 1024:
                name = "Near-Boundary File Read (950 KB)"
            elif sz == boundary_1mb:
                name = "Exact Boundary File Read (1 MB - 1,048,576 Bytes)"
            else:
                sz_str = f"{sz} B" if sz < 1024 else f"{sz // 1024} KB"
                name = f"File Read ({sz_str})"
            cases.append({
                "name": name,
                "type": "read",
                "size_bytes": sz,
                "expect_success": True,
                "description": f"Verified reading {sz} bytes within allowed viewable boundary",
            })
        else:
            mb_val = round(sz / boundary_1mb, 2)
            if sz == boundary_1mb + 1:
                name = "Oversized File Read Rejection (1 MB + 1 Byte)"
            else:
                name = f"Large Oversized File Rejection ({mb_val} MB)"
            cases.append({
                "name": name,
                "type": "read",
                "size_bytes": sz,
                "expect_success": False,
                "expected_error": "exceeds maximum viewable size",
                "description": f"Verified hard rejection of {sz} bytes to prevent memory exhaustion",
            })

    cases.extend([
        {
            "name": "Directory Listing Size Formatting (Bytes tier)",
            "type": "list_format",
            "filename": "bench_test_bytes.txt",
            "size_bytes": 512,
            "expected_token": "bench_test_bytes.txt (512 B)",
            "description": "Directory listing displays exact byte count for < 1 KB",
        },
        {
            "name": "Directory Listing Size Formatting (Kilobytes tier)",
            "type": "list_format",
            "filename": "bench_test_kb.txt",
            "size_bytes": 12 * 1024,
            "expected_token": "bench_test_kb.txt (12.0 KB)",
            "description": "Directory listing displays decimal KB for 1 KB - 1 MB",
        },
        {
            "name": "Directory Listing Size Formatting (Megabytes tier)",
            "type": "list_format",
            "filename": "bench_test_mb.txt",
            "size_bytes": int(1.5 * 1024 * 1024),
            "expected_token": "bench_test_mb.txt (1.5 MB)",
            "description": "Directory listing displays decimal MB for >= 1 MB",
        },
        {
            "name": "Empty File Write (0 Bytes)",
            "type": "write",
            "size_bytes": 0,
            "expect_success": True,
            "description": "Zero-byte file creation and disk synchronization",
        },
        {
            "name": "Small File Write (1 KB)",
            "type": "write",
            "size_bytes": 1024,
            "expect_success": True,
            "description": "Standard script / config write throughput and byte count",
        },
        {
            "name": "Medium File Write (64 KB)",
            "type": "write",
            "size_bytes": 64 * 1024,
            "expect_success": True,
            "description": "Multi-function module write throughput and byte integrity",
        },
        {
            "name": "Large File Write (256 KB)",
            "type": "write",
            "size_bytes": 256 * 1024,
            "expect_success": True,
            "description": "Large asset / log write throughput and byte integrity",
        },
        {
            "name": "Dynamic Context Scaling: Small Payload (100 tokens)",
            "type": "dynamic_ctx",
            "prompt_tokens": 100,
            "expected_min_ctx": 4096,
            "description": "Lightweight prompts use default safe 4096 context bucket",
        },
        {
            "name": "Dynamic Context Scaling: Medium Payload (5,000 tokens)",
            "type": "dynamic_ctx",
            "prompt_tokens": 5000,
            "expected_min_ctx": 6144,
            "description": "Scales up context bucket dynamically for medium documents",
        },
        {
            "name": "Dynamic Context Scaling: Large Payload (15,000 tokens)",
            "type": "dynamic_ctx",
            "prompt_tokens": 15000,
            "expected_min_ctx": 16384,
            "description": "Scales up context bucket dynamically for multi-chapter contexts",
        },
        {
            "name": "Tool Call Extraction: Large Multi-KB Payload (32 KB)",
            "type": "tool_call_size",
            "payload_size": 32768,
            "description": "Extracts complete 32 KB tool payload without truncation",
        },
        {
            "name": "Tool Call Extraction: Bracket Syntax Large Payload (32 KB)",
            "type": "tool_call_bracket_size",
            "payload_size": 32768,
            "description": "Extracts complete 32 KB bracket syntax tool payload without truncation",
        },
    ])

    return cases


FILE_SIZE_CASES: List[Dict[str, Any]] = generate_file_size_sweep(max_size_mb=2.5)


@dataclass
class CategoryResult:
    category: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    duration_ms: float = 0.0
    failures: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100.0) if self.total > 0 else 0.0


class MockAgentManager:
    """Lightweight test harness simulating the DevCore AgentManager execution loop."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.output_buffer: List[str] = []
        self.broadcast_events: List[dict] = []
        self.current_conversation_id: Optional[str] = None
        self.last_completed_task: Optional[dict] = None

        class PM:
            def __init__(self, wsp: str):
                self.wsp = wsp
                self.active_project = "benchmark_project"

            def get_active_workspace_path(self) -> str:
                return self.wsp

        self.project_manager = PM(workspace_path)

    async def broadcast(self, msg: dict):
        self.broadcast_events.append(msg)

    def _get_security(self):
        return None

    def _get_session_mgr(self):
        class MockSM:
            def _clean_prompt_text(self, p: str) -> str:
                return p

            def register_session_owner(self, *args, **kwargs):
                pass

            _conv_meta_cache = {}

        return MockSM()


def benchmark_directory_intents(cases: Optional[List[Tuple[str, bool, Optional[str]]]] = None, verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="Directory Intent Parsing")
    start = time.perf_counter()
    active_cases = cases if cases is not None else DIRECTORY_INTENT_CASES
    for query, exp_match, exp_target in active_cases:
        res.total += 1
        m, t = parse_directory_intent(query)
        if m == exp_match and t == exp_target:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {query!r} -> matched={m}, target={t!r}")
        else:
            res.failed += 1
            err = f"Failed {query!r}: expected ({exp_match}, {exp_target!r}), got ({m}, {t!r})"
            res.failures.append(err)
            if verbose:
                print(f"  [FAIL] {err}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_read_intents(cases: Optional[List[Tuple[str, Optional[str]]]] = None, verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="File Read Intent Parsing")
    start = time.perf_counter()
    active_cases = cases if cases is not None else READ_INTENT_CASES
    for query, exp_path in active_cases:
        res.total += 1
        m, p = parse_read_intent(query)
        expected_match = exp_path is not None
        if m == expected_match and p == exp_path:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {query!r} -> matched={m}, path={p!r}")
        else:
            res.failed += 1
            err = f"Failed {query!r}: expected ({expected_match}, {exp_path!r}), got ({m}, {p!r})"
            res.failures.append(err)
            if verbose:
                print(f"  [FAIL] {err}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_write_intents(cases: Optional[List[Tuple[str, Optional[str], Optional[str]]]] = None, verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="File Write Intent Parsing")
    start = time.perf_counter()
    active_cases = cases if cases is not None else WRITE_INTENT_CASES
    for query, exp_path, exp_content in active_cases:
        res.total += 1
        m, p, c = parse_write_intent(query)
        expected_match = exp_path is not None
        if m == expected_match and p == exp_path and c == exp_content:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {query!r} -> matched={m}, path={p!r}")
        else:
            res.failed += 1
            err = f"Failed {query!r}: expected ({expected_match}, {exp_path!r}), got ({m}, {p!r})"
            res.failures.append(err)
            if verbose:
                print(f"  [FAIL] {err}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_tool_call_extraction(verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="Tool Call Extraction Resilience")
    start = time.perf_counter()
    for case in TOOL_EXTRACTION_CASES:
        res.total += 1
        calls = extract_local_tool_calls(case["raw"])
        count_match = len(calls) == case["expected_count"]
        action_match = calls[0]["action"] == case["expected_action"] if calls else False
        path_match = calls[0].get("path") == case["expected_path"] if calls else False

        if count_match and action_match and path_match:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {case['name']}")
        else:
            res.failed += 1
            err = f"Failed {case['name']}: got {calls!r}"
            res.failures.append(err)
            if verbose:
                print(f"  [FAIL] {err}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_display_sanitization(verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="Display Text Sanitization")
    start = time.perf_counter()
    for case in DISPLAY_SANITIZATION_CASES:
        res.total += 1
        cleaned = clean_local_model_display_text(case["input"])
        if cleaned == case["expected"]:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {case['name']}")
        else:
            res.failed += 1
            err = f"Failed {case['name']}: expected {case['expected']!r}, got {cleaned!r}"
            res.failures.append(err)
            if verbose:
                print(f"  [FAIL] {err}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_path_traversal(workspace_path: str, verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="Path Traversal Security Defense")
    start = time.perf_counter()
    for op, target in PATH_TRAVERSAL_CASES:
        res.total += 1
        if op == "read":
            ok, err = local_read_file(workspace_path, target)
        elif op == "list":
            ok, err = local_list_directory(workspace_path, target)
        elif op == "write":
            ok, err = local_write_file(workspace_path, target, "blocked payload")
        else:
            ok, err = True, "Unknown operation"

        traversal_blocked = (not ok) and any(
            token in err.lower() for token in ["traversal", "boundary", "denied", "forbidden"]
        )
        if traversal_blocked:
            res.passed += 1
            if verbose:
                print(f"  [PASS] {op.upper()} {target!r} -> Blocked with {err!r}")
        else:
            res.failed += 1
            err_msg = f"Failed {op} on {target!r}: traversal was not blocked! (ok={ok}, msg={err!r})"
            res.failures.append(err_msg)
            if verbose:
                print(f"  [FAIL] {err_msg}")
    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def benchmark_file_sizes(
    workspace_path: str,
    verbose: bool = False,
    cases: Optional[List[Dict[str, Any]]] = None,
    max_size_mb: float = 2.5,
) -> CategoryResult:
    res = CategoryResult(category="File Size Limits & Scalability")
    start = time.perf_counter()

    test_dir = os.path.join(workspace_path, ".bench_file_size_suite")
    os.makedirs(test_dir, exist_ok=True)

    active_cases = cases if cases is not None else (
        generate_file_size_sweep(max_size_mb=max_size_mb) if max_size_mb != 2.5 else FILE_SIZE_CASES
    )

    try:
        for case in active_cases:
            res.total += 1
            case_type = case["type"]
            name = case["name"]

            try:
                if case_type == "read":
                    size = case["size_bytes"]
                    sample_file = f"temp_read_{size}.dat"
                    full_sample_path = os.path.join(test_dir, sample_file)
                    with open(full_sample_path, "wb") as f:
                        if size > 0:
                            f.write(b"Z" * size)

                    ok, out = local_read_file(test_dir, sample_file)
                    expected_success = case["expect_success"]

                    if expected_success:
                        pass_condition = ok and (len(out) == size)
                        fail_reason = f"expected success={expected_success} and len={size}, got ok={ok}, len={len(out)}"
                    else:
                        exp_err = case.get("expected_error", "").lower()
                        pass_condition = (not ok) and (exp_err in out.lower())
                        fail_reason = f"expected rejection with {exp_err!r}, got ok={ok}, msg={out!r}"

                    if pass_condition:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name}")
                    else:
                        res.failed += 1
                        err = f"Failed {name}: {fail_reason}"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                elif case_type == "list_format":
                    list_dir = os.path.join(test_dir, "listing_test")
                    os.makedirs(list_dir, exist_ok=True)
                    fname = case["filename"]
                    fpath = os.path.join(list_dir, fname)
                    with open(fpath, "wb") as f:
                        f.write(b"M" * case["size_bytes"])

                    ok, listing = local_list_directory(test_dir, "listing_test")
                    expected_token = case["expected_token"]
                    if ok and expected_token in listing:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name}")
                    else:
                        res.failed += 1
                        err = f"Failed {name}: expected token {expected_token!r} in listing, got: {listing!r}"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                elif case_type == "write":
                    size = case["size_bytes"]
                    write_fname = f"temp_written_{size}.dat"
                    written_full = os.path.join(test_dir, write_fname)
                    content = "W" * size
                    ok, msg = local_write_file(test_dir, write_fname, content)
                    file_exists = os.path.isfile(written_full)
                    actual_size = os.path.getsize(written_full) if file_exists else -1

                    if ok and file_exists and actual_size == size:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name} ({size} bytes written)")
                    else:
                        res.failed += 1
                        err = f"Failed {name}: ok={ok}, exists={file_exists}, size={actual_size} (expected {size})"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                elif case_type == "dynamic_ctx":
                    prompt_toks = case["prompt_tokens"]
                    exp_min = case["expected_min_ctx"]
                    params = calculate_dynamic_execution_params(prompt_toks)
                    ctx = params.get("ctx_size", 0)
                    if ctx >= exp_min:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name} (ctx={ctx} >= {exp_min})")
                    else:
                        res.failed += 1
                        err = f"Failed {name}: ctx_size={ctx} < expected {exp_min}"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                elif case_type == "tool_call_size":
                    size = case["payload_size"]
                    payload = "X" * size
                    raw = f'<tool_call>{{"action": "write_file", "path": "large_out.py", "content": "{payload}"}}</tool_call>'
                    calls = extract_local_tool_calls(raw)
                    if calls and calls[0].get("action") == "write_file" and len(calls[0].get("content", "")) == size:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name} (extracted {size} bytes)")
                    else:
                        got_len = len(calls[0].get("content", "")) if calls else 0
                        res.failed += 1
                        err = f"Failed {name}: expected {size} bytes, got {got_len} (calls={len(calls)})"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                elif case_type == "tool_call_bracket_size":
                    size = case["payload_size"]
                    payload = "Y" * size
                    raw = f'[WRITE_FILE: script_large.py]\n{payload}\n[/WRITE_FILE]'
                    calls = extract_local_tool_calls(raw)
                    if calls and calls[0].get("action") == "write_file" and len(calls[0].get("content", "")) == size:
                        res.passed += 1
                        if verbose:
                            print(f"  [PASS] {name} (bracket extracted {size} bytes)")
                    else:
                        got_len = len(calls[0].get("content", "")) if calls else 0
                        res.failed += 1
                        err = f"Failed {name}: expected {size} bytes, got {got_len} (calls={len(calls)})"
                        res.failures.append(err)
                        if verbose:
                            print(f"  [FAIL] {err}")

                else:
                    res.failed += 1
                    res.failures.append(f"Unknown test type: {case_type}")

            except Exception as e:
                res.failed += 1
                res.failures.append(f"Exception during {name}: {str(e)}")
                if verbose:
                    print(f"  [FAIL] {name}: {str(e)}")

    finally:
        if os.path.exists(test_dir):
            try:
                shutil.rmtree(test_dir, ignore_errors=True)
            except OSError:
                pass

    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


async def benchmark_e2e_execution(workspace_path: str, verbose: bool = False) -> CategoryResult:
    res = CategoryResult(category="End-to-End Local Agent Execution")
    start = time.perf_counter()

    temp_read_file = os.path.join(workspace_path, ".bench_sample_target.py")
    temp_write_file = os.path.join(workspace_path, ".bench_auto_generated.txt")

    with open(temp_read_file, "w", encoding="utf-8") as f:
        f.write("# benchmark test file\ndef test_benchmark_metric():\n    return 100\n")

    try:
        res.total += 1
        mgr_dir = MockAgentManager(workspace_path)
        await execute_local_agent_task(
            mgr_dir,
            "what is in my directory?",
            "Local Qwen 2.5 (Offline)",
            time.time(),
            "bench-e2e-dir",
        )
        dir_out = mgr_dir.output_buffer[-1] if mgr_dir.output_buffer else ""
        if "Directory Browsed:" in dir_out and len(dir_out) > 30:
            res.passed += 1
            if verbose:
                print("  [PASS] E2E Directory Browsing Task")
        else:
            res.failed += 1
            res.failures.append(f"Directory browsing produced unexpected output: {dir_out[:100]!r}")

        res.total += 1
        mgr_read = MockAgentManager(workspace_path)
        await execute_local_agent_task(
            mgr_read,
            f"read the file {os.path.basename(temp_read_file)}",
            "Local Qwen 2.5 (Offline)",
            time.time(),
            "bench-e2e-read",
        )
        read_out = mgr_read.output_buffer[-1] if mgr_read.output_buffer else ""
        if "File Read:" in read_out and "test_benchmark_metric" in read_out:
            res.passed += 1
            if verbose:
                print("  [PASS] E2E File Reading Task")
        else:
            res.failed += 1
            res.failures.append(f"File reading produced unexpected output: {read_out[:100]!r}")

        res.total += 1
        mgr_write = MockAgentManager(workspace_path)
        write_content = "Benchmark automated payload token: 99482"
        await execute_local_agent_task(
            mgr_write,
            f"create a file named {os.path.basename(temp_write_file)} with '{write_content}'",
            "Local Qwen 2.5 (Offline)",
            time.time(),
            "bench-e2e-write",
        )
        write_out = mgr_write.output_buffer[-1] if mgr_write.output_buffer else ""
        file_created = os.path.exists(temp_write_file)
        content_matches = False
        if file_created:
            with open(temp_write_file, "r", encoding="utf-8") as wf:
                content_matches = wf.read() == write_content

        if "File Written:" in write_out and file_created and content_matches:
            res.passed += 1
            if verbose:
                print("  [PASS] E2E File Writing Task & Content Verification")
        else:
            res.failed += 1
            res.failures.append(
                f"File writing failed. created={file_created}, match={content_matches}, out={write_out[:100]!r}"
            )

    finally:
        if os.path.exists(temp_read_file):
            try:
                os.remove(temp_read_file)
            except OSError:
                pass
        if os.path.exists(temp_write_file):
            try:
                os.remove(temp_write_file)
            except OSError:
                pass

    res.duration_ms = (time.perf_counter() - start) * 1000.0
    return res


def print_scorecard(results: List[CategoryResult]):
    total_tests = sum(r.total for r in results)
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_duration = sum(r.duration_ms for r in results)
    overall_pass_rate = (total_passed / total_tests * 100.0) if total_tests > 0 else 0.0

    print("\n" + "=" * 70)
    print("      DEVCORE LOCAL MODEL SERVICE (OFFLINE QWEN 2.5) BENCHMARK      ")
    print("=" * 70)
    print(f"{'Category':<38} | {'Tests':<6} | {'Passed':<6} | {'Pass %':<7} | {'Time (ms)'}")
    print("-" * 70)

    for r in results:
        status_tag = f"{r.pass_rate:>5.1f}%"
        print(f"{r.category:<38} | {r.total:<6} | {r.passed:<6} | {status_tag:<7} | {r.duration_ms:>7.1f}ms")

    print("-" * 70)
    overall_str = f"{overall_pass_rate:>5.1f}%"
    print(f"{'OVERALL TOTALS':<38} | {total_tests:<6} | {total_passed:<6} | {overall_str:<7} | {total_duration:>7.1f}ms")
    print("=" * 70)

    all_failures = [f for r in results for f in r.failures]
    if all_failures:
        print("\n[!] Failure Details:")
        for idx, failure in enumerate(all_failures, start=1):
            print(f"  {idx}. {failure}")
    else:
        print("\n[+] All benchmark tests passed with 100% compliance.")
    print()


def export_json_report(results: List[CategoryResult]) -> str:
    total_tests = sum(r.total for r in results)
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_duration = sum(r.duration_ms for r in results)
    overall_pass_rate = (total_passed / total_tests * 100.0) if total_tests > 0 else 0.0

    overall_status = "PASS" if total_failed == 0 else "FAIL"
    data = {
        "timestamp": time.time(),
        "status": overall_status,
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate_pct": round(overall_pass_rate, 2),
            "total_duration_ms": round(total_duration, 2),
        },
        "categories": [
            {
                "category": r.category,
                "total": r.total,
                "passed": r.passed,
                "failed": r.failed,
                "pass_rate_pct": round(r.pass_rate, 2),
                "duration_ms": round(r.duration_ms, 2),
                "failures": r.failures,
            }
            for r in results
        ],
    }
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="DevCore Local Model Service Benchmark & Diagnostic Suite"
    )
    parser.add_argument(
        "--workspace",
        default="/mnt/c/Users/michael/Documents/DevCore/playground",
        help="Workspace directory to use for path security and E2E file tests",
    )
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run only fast in-memory intent parsing and sanitization benchmarks",
    )
    parser.add_argument(
        "--file-size-only",
        action="store_true",
        help="Run only the file size limits and scalability benchmarks",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Run dynamic file size parameter sweep across boundary scales",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=2.5,
        help="Maximum file size in MB to sweep up to (default: 2.5 MB)",
    )
    parser.add_argument(
        "--fuzz-intents",
        "--auto-intents",
        action="store_true",
        help="Run combinatorial dynamic natural language intent generation suite",
    )
    parser.add_argument(
        "--e2e-only",
        action="store_true",
        help="Run only the end-to-end autonomous agent task execution benchmarks",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON scorecard instead of human-readable text",
    )
    parser.add_argument(
        "--save-report",
        type=str,
        default="",
        help="Optional path to write JSON benchmark scorecard",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose trace of individual test executions",
    )
    args = parser.parse_args()

    workspace_path = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace_path):
        os.makedirs(workspace_path, exist_ok=True)

    results: List[CategoryResult] = []

    if args.file_size_only or args.sweep:
        results.append(benchmark_file_sizes(workspace_path, verbose=args.verbose, max_size_mb=args.max_size_mb))
    else:
        if not args.e2e_only:
            if args.fuzz_intents:
                dyn_intents = generate_dynamic_intent_suite()
                results.append(benchmark_directory_intents(dyn_intents["directory"], verbose=args.verbose))
                results.append(benchmark_read_intents(dyn_intents["read"], verbose=args.verbose))
                results.append(benchmark_write_intents(dyn_intents["write"], verbose=args.verbose))
            else:
                results.append(benchmark_directory_intents(verbose=args.verbose))
                results.append(benchmark_read_intents(verbose=args.verbose))
                results.append(benchmark_write_intents(verbose=args.verbose))

            results.append(benchmark_tool_call_extraction(verbose=args.verbose))
            results.append(benchmark_display_sanitization(verbose=args.verbose))
            results.append(benchmark_path_traversal(workspace_path, verbose=args.verbose))
            results.append(benchmark_file_sizes(workspace_path, verbose=args.verbose, max_size_mb=args.max_size_mb))

        if not args.unit_only:
            e2e_result = asyncio.run(benchmark_e2e_execution(workspace_path, verbose=args.verbose))
            results.append(e2e_result)

    json_str = export_json_report(results)
    if args.save_report:
        save_path = os.path.abspath(args.save_report)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    if args.json:
        print(json_str)
    else:
        print_scorecard(results)

    total_failed = sum(r.failed for r in results)
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
