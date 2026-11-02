"""Resumable, content-hashed chunk -> summarize -> merge pipeline.

A large document is split into overlapping chunks. Each chunk is PII-scrubbed,
summarized (by the offline local model by default) and written to disk as soon
as it is done, so an interrupted run picks up where it stopped. Chunk summaries
are then merged level by level until one digest remains:

    ~/.devcore/digests/<digest_id>/
        manifest.json          chunk spans, status, merge tree, metadata
        chunk_001.md ...       per-chunk summaries (scrubbed)
        merge_L1_001.md ...    intermediate merge summaries (scrubbed)
        digest.md              final digest + chunk index (scrubbed)
        source_001.txt ...     scrubbed chunk text, inline sources only

<digest_id> is derived from the source content and the pipeline parameters,
never from a path, so identical content shares one digest and nothing on disk
reveals where it came from. File sources never have their raw text persisted:
read_chunk() re-reads the file and slices the recorded span.

Everything here is synchronous and thread-safe per digest (an exclusive lock
file guards each digest dir), so callers run it via run_in_executor / to_thread.
"""

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

PIPELINE_VERSION = "1"

DIGEST_ROOT = os.path.expanduser(os.environ.get("DEVCORE_DIGEST_ROOT", "~/.devcore/digests"))

# A Summarizer takes (system_prompt, user_prompt, max_tokens, label) and returns text.
# Returning "" or a "[LOCAL_BRAIN_*]" marker means "failed" and triggers the fallback.
Summarizer = Callable[[str, str, int, str], str]
ProgressFn = Callable[[dict], None]

_CHUNK_SYSTEM = (
    "You are a precise technical summarization engine running offline. Summarize the "
    "document section you are given. Preserve every identifier (function, class, variable, "
    "key, endpoint, config name), signature, number, constraint and error message that "
    "matters. Note what the section defines, what it depends on, and any risks or TODOs. "
    "Use dense bullet points. No preamble."
)
_MERGE_SYSTEM = (
    "You are a precise technical summarization engine running offline. Merge the section "
    "summaries you are given into one coherent summary. Deduplicate, keep every important "
    "identifier, number and constraint, and keep the original order of the document. "
    "Use headings and dense bullet points. No preamble."
)


class DigestError(Exception):
    """Base class for pipeline failures callers may want to fall back from."""


class DigestBusy(DigestError):
    """Another worker holds this digest's lock and did not finish in time."""


class DigestCancelled(DigestError):
    """The caller's cancel event was set."""


class DigestStale(DigestError):
    """The source changed since the digest was built (read_chunk)."""


@dataclass
class DigestResult:
    digest_id: str
    digest_dir: str
    digest_text: str
    chunk_count: int
    complete: bool
    fallback_chunks: int = 0
    cached: bool = False
    manifest: dict = field(default_factory=dict)

    @property
    def digest_path(self) -> str:
        return os.path.join(self.digest_dir, "digest.md")

    @property
    def summary(self) -> str:
        """The merged summary alone, without the header and chunk index."""
        m = re.search(r"^## Summary\n(.*?)(?=^## Chunk index)", self.digest_text, re.S | re.M)
        return m.group(1).strip() if m else self.digest_text


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _default_summarizer(system_prompt: str, user_prompt: str, max_tokens: int, label: str) -> str:
    # Imported lazily: local_model_service imports this module.
    from core.local_model_service import run_dynamic_local_qwen
    return run_dynamic_local_qwen(system_prompt, user_prompt, max_tokens, label)


def _scrub(text: str, stage: str) -> str:
    """PII/secret scrub. Fails closed: if the scrubber is unavailable, refuse."""
    from security.local_brain_broker import offline_scrub_pii
    return offline_scrub_pii(text, stage=stage) if text else text


def _failed(text: Optional[str]) -> bool:
    return not text or not text.strip() or text.lstrip().startswith("[LOCAL_BRAIN_")


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8", errors="surrogatepass")).hexdigest()


def _atomic_write(path: str, text: str) -> None:
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def chunk_spans(text: str, max_chars: int = 10000, overlap: int = 800) -> list:
    """Split text into overlapping (start, end) character spans that break on a
    paragraph, line, or sentence boundary where possible. Deterministic, so the
    same text always yields the same spans."""
    n = len(text)
    if n == 0:
        return []
    if n <= max_chars:
        return [(0, n)]
    overlap = max(0, min(overlap, max_chars // 2))
    spans, start = [], 0
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            floor = start + max_chars // 2  # never cut a chunk below half size
            for sep in ("\n\n", "\n", ". "):
                bp = text.rfind(sep, floor, end)
                if bp != -1:
                    end = bp + len(sep)
                    break
        spans.append((start, end))
        if end >= n:
            break
        start = max(start + 1, end - overlap)
    return spans


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _extractive_summary(text: str, max_chars: int = 1800) -> str:
    """Deterministic fallback used when no summarizer is available: keeps
    headings, definitions, and key/value lines, then pads with the opening lines."""
    keep = re.compile(
        r"^\s*(#{1,6}\s|def |async def |class |function |export |const |let |var |"
        r"@\w|[A-Z_][A-Z0-9_]{2,}\s*=|\w[\w.\-]*\s*[:=]\s|[-*]\s|\d+\.\s|"
        r"(?:TODO|FIXME|WARNING|NOTE|ERROR)\b)"
    )
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    picked, used = [], 0
    for ln in lines:
        if keep.match(ln):
            ln = ln[:200]
            if used + len(ln) > max_chars:
                break
            picked.append(ln)
            used += len(ln) + 1
    if used < max_chars // 3:
        for ln in lines[:40]:
            if ln not in picked and used + len(ln) <= max_chars:
                picked.append(ln[:200])
                used += min(len(ln), 200) + 1
    return "[extractive fallback: local summarizer unavailable]\n" + "\n".join(picked)


class _DirLock:
    """Exclusive lock file for one digest dir. Portable (no fcntl), with stale
    lock recovery: a lock not refreshed for `stale_after` seconds is taken over."""

    def __init__(self, path: str, wait: float, stale_after: float = 1800.0):
        self.path, self.wait, self.stale_after = path, wait, stale_after
        self._held = False

    def __enter__(self):
        deadline = time.monotonic() + self.wait
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{os.getpid()} {time.time():.0f}\n")
                self._held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > self.stale_after:
                        os.unlink(self.path)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise DigestBusy("Digest is being built by another worker.")
                time.sleep(0.5)

    def touch(self):
        if self._held:
            try:
                os.utime(self.path, None)
            except OSError:
                pass

    def __exit__(self, *exc):
        if self._held:
            try:
                os.unlink(self.path)
            except OSError:
                pass
            self._held = False
        return False


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

class DigestPipeline:
    """Build (or resume) the digest of one text.

    Args:
        summarizer: callable used for chunk and merge summaries. Defaults to the
            offline local model, so raw content never leaves the machine.
        chunk_chars / overlap_chars: chunking parameters (part of the digest id).
        merge_input_chars: max characters of summaries fed into one merge call.
        chunk_tokens / merge_tokens: output budgets for the summarizer.
        throttle: seconds to sleep between model calls (protects a CPU-bound host).
        lock_wait: seconds to wait for a concurrent build of the same digest.
        retry_fallbacks: treat a finished digest that has extractive-fallback
            chunks as unfinished, so they are re-summarized once the model is back.
    """

    def __init__(
        self,
        summarizer: Optional[Summarizer] = None,
        root: str = DIGEST_ROOT,
        chunk_chars: int = 10000,
        overlap_chars: int = 800,
        merge_input_chars: int = 9000,
        chunk_tokens: int = 450,
        merge_tokens: int = 900,
        throttle: float = 0.2,
        lock_wait: float = 600.0,
        max_source_chars: int = 20_000_000,
        retry_fallbacks: bool = True,
    ):
        self.summarizer = summarizer or _default_summarizer
        self.root = root
        self.chunk_chars = chunk_chars
        self.overlap_chars = overlap_chars
        self.merge_input_chars = merge_input_chars
        self.chunk_tokens = chunk_tokens
        self.merge_tokens = merge_tokens
        self.throttle = throttle
        self.lock_wait = lock_wait
        self.max_source_chars = max_source_chars
        self.retry_fallbacks = retry_fallbacks

    # ---- identity ---------------------------------------------------------

    def digest_id(self, text: str, focus: str = "") -> str:
        params = f"v{PIPELINE_VERSION}|{self.chunk_chars}|{self.overlap_chars}|{focus.strip()}"
        return _sha256(params + "\x00" + _sha256(text))[:32]

    def digest_dir(self, digest_id: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{32}", digest_id or ""):
            raise DigestError("Invalid digest id.")
        return os.path.join(self.root, digest_id)

    # ---- public API -------------------------------------------------------

    def run(
        self,
        text: str,
        source_ref: str = "inline",
        focus: str = "",
        persist_source: bool = False,
        owner: str = "",
        on_progress: Optional[ProgressFn] = None,
        cancel: Optional[threading.Event] = None,
        deadline: Optional[float] = None,
    ) -> DigestResult:
        """Build or resume the digest for `text`.

        source_ref: opaque label stored in the manifest (a VFS key or a display
            name). Never pass an absolute host path.
        persist_source: store scrubbed chunk text on disk (needed for read_chunk
            on inline sources that cannot be re-read later).
        owner: principal allowed to read this digest's stored chunks back
            (recorded in manifest["owners"]; checked by the resolver).
        deadline: time.monotonic() value; when reached, the run stops cleanly and
            returns complete=False. Calling run() again resumes.
        """
        if not text or not text.strip():
            raise DigestError("Nothing to digest: source is empty.")
        if len(text) > self.max_source_chars:
            raise DigestError(f"Source too large to digest ({len(text)} chars).")

        did = self.digest_id(text, focus)
        ddir = self.digest_dir(did)
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        os.makedirs(ddir, mode=0o700, exist_ok=True)

        if not owner or not persist_source:
            cached = self._load_complete(ddir)
            if cached:
                return cached

        with _DirLock(os.path.join(ddir, ".lock"), self.lock_wait) as lock:
            # Another worker may have finished while we waited for the lock.
            cached = self._load_complete(ddir)
            if cached and persist_source and not cached.manifest.get("source_persisted"):
                cached = None  # rebuild pass writes the scrubbed source files
            if cached:
                if owner:
                    self._add_owner(ddir, cached.manifest, owner, lock)
                return cached
            return self._build(text, did, ddir, source_ref, focus, persist_source,
                               owner, on_progress, cancel, deadline, lock)

    def load(self, digest_id: str) -> Optional[dict]:
        """Return the manifest for a digest id, or None."""
        raw = _read(os.path.join(self.digest_dir(digest_id), "manifest.json"))
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    def read_chunk(self, digest_id: str, index: int, source_text: Optional[str] = None) -> dict:
        """Return one chunk (1-based) of a digested source, PII-scrubbed.

        For file sources pass the current `source_text`; it is verified against
        the content hash recorded at digest time (DigestStale if it changed).
        Inline sources are served from their persisted scrubbed chunk text."""
        manifest = self.load(digest_id)
        if not manifest:
            raise DigestError("Unknown digest id. Run digest_file first.")
        chunks = manifest.get("chunks", [])
        if not 1 <= index <= len(chunks):
            raise DigestError(f"Chunk index out of range (1..{len(chunks)}).")
        c = chunks[index - 1]
        ddir = self.digest_dir(digest_id)
        if source_text is not None:
            if _sha256(source_text) != manifest.get("source_sha256"):
                raise DigestStale("Source changed since it was digested. Re-run digest_file.")
            body = _scrub(source_text[c["start"]:c["end"]], stage=f"read_chunk_{index}")
        else:
            body = _read(os.path.join(ddir, f"source_{index:03d}.txt"))
            if body is None:
                raise DigestError("Chunk text is not stored for this digest; pass the source.")
        return {
            "digest_id": digest_id,
            "chunk": index,
            "chunk_count": len(chunks),
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "summary": _read(os.path.join(ddir, f"chunk_{index:03d}.md")) or "",
            "text": body,
        }

    # ---- internals --------------------------------------------------------

    def _load_complete(self, ddir: str) -> Optional[DigestResult]:
        raw = _read(os.path.join(ddir, "manifest.json"))
        if not raw:
            return None
        try:
            m = json.loads(raw)
        except ValueError:
            return None
        if m.get("status") != "complete":
            return None
        if self.retry_fallbacks and any(c.get("fallback") for c in m.get("chunks", [])):
            return None
        digest = _read(os.path.join(ddir, "digest.md"))
        if digest is None:
            return None
        return DigestResult(m["digest_id"], ddir, digest, len(m.get("chunks", [])), True,
                            sum(1 for c in m["chunks"] if c.get("fallback")), True, m)

    def _save_manifest(self, ddir: str, m: dict, lock: _DirLock) -> None:
        m["updated_at"] = time.time()
        _atomic_write(os.path.join(ddir, "manifest.json"), json.dumps(m, indent=2))
        lock.touch()

    def _summarize(self, system: str, user: str, tokens: int, label: str, fallback_src: str) -> tuple:
        """Return (scrubbed_summary, used_fallback)."""
        try:
            out = self.summarizer(system, user, tokens, label)
        except Exception:
            out = ""
        if _failed(out):
            return _scrub(_extractive_summary(fallback_src), stage="digest_fallback"), True
        return _scrub(out.strip(), stage="digest_output"), False

    def _add_owner(self, ddir: str, manifest: dict, owner: str, lock: _DirLock) -> None:
        owners = manifest.setdefault("owners", [])
        if owner not in owners:
            owners.append(owner)
            self._save_manifest(ddir, manifest, lock)

    def _build(self, text, did, ddir, source_ref, focus, persist_source,
               owner, on_progress, cancel, deadline, lock) -> DigestResult:
        spans = chunk_spans(text, self.chunk_chars, self.overlap_chars)
        manifest = self.load(did) or {}
        if manifest.get("source_sha256") != _sha256(text) or len(manifest.get("chunks", [])) != len(spans):
            manifest = {
                "digest_id": did,
                "pipeline_version": PIPELINE_VERSION,
                "source_ref": source_ref,
                "source_sha256": _sha256(text),
                "source_chars": len(text),
                "focus": focus,
                "chunk_chars": self.chunk_chars,
                "overlap_chars": self.overlap_chars,
                "created_at": time.time(),
                "status": "building",
                "chunks": [
                    {"index": i + 1, "start": s, "end": e,
                     "start_line": _line_of(text, s), "end_line": _line_of(text, max(s, e - 1)),
                     "status": "pending", "fallback": False}
                    for i, (s, e) in enumerate(spans)
                ],
                "levels": [],
                "owners": [],
            }
            self._save_manifest(ddir, manifest, lock)
        if owner and owner not in manifest.setdefault("owners", []):
            manifest["owners"].append(owner)

        def emit(stage, **kw):
            if on_progress:
                try:
                    on_progress({"digest_id": did, "stage": stage, **kw})
                except Exception:
                    pass

        def should_stop() -> bool:
            if cancel is not None and cancel.is_set():
                raise DigestCancelled("Digest cancelled.")
            return deadline is not None and time.monotonic() >= deadline

        chunks = manifest["chunks"]
        total = len(chunks)
        focus_line = f"\nFOCUS: pay particular attention to: {focus}\n" if focus else ""

        # Tier 1: per-chunk summaries. Fallback chunks are retried on later runs
        # so a digest built while the model was down upgrades itself. After two
        # consecutive model failures the rest of this run goes extractive rather
        # than waiting on a dead model for every chunk.
        failures = 0
        for c in chunks:
            path = os.path.join(ddir, f"chunk_{c['index']:03d}.md")
            exists = os.path.exists(path)
            if c["status"] == "done" and exists and (not c["fallback"] or failures >= 2):
                src_path = os.path.join(ddir, f"source_{c['index']:03d}.txt")
                if persist_source and not os.path.exists(src_path):
                    _atomic_write(src_path, _scrub(text[c["start"]:c["end"]],
                                                   stage=f"digest_chunk_{c['index']}"))
                continue
            if should_stop():
                return self._partial(did, ddir, manifest)
            raw = text[c["start"]:c["end"]]
            clean = _scrub(raw, stage=f"digest_chunk_{c['index']}")
            if persist_source:
                _atomic_write(os.path.join(ddir, f"source_{c['index']:03d}.txt"), clean)
            emit("chunk", index=c["index"], total=total)
            if failures >= 2:
                summary, fb = _scrub(_extractive_summary(clean), stage="digest_fallback"), True
            else:
                user = (f"DOCUMENT: {source_ref}\nSECTION {c['index']} OF {total} "
                        f"(lines {c['start_line']}-{c['end_line']}){focus_line}\n\n{clean}\n\n"
                        "Summary of this section:")
                summary, fb = self._summarize(_CHUNK_SYSTEM, user, self.chunk_tokens,
                                              f"digest:{did[:8]}:chunk_{c['index']}_of_{total}", clean)
                failures = failures + 1 if fb else 0
            header = f"<!-- chunk {c['index']}/{total} lines {c['start_line']}-{c['end_line']} -->\n"
            _atomic_write(path, header + summary + "\n")
            c.update(status="done", fallback=fb, summary_sha256=_sha256(summary))
            self._save_manifest(ddir, manifest, lock)
            if self.throttle and not fb:
                time.sleep(self.throttle)

        # Tier 2: hierarchical merge until one summary remains. Merge levels are
        # derived from chunk summaries, so they are rebuilt if any chunk changed.
        chunk_sig = _sha256("|".join(c.get("summary_sha256", "") for c in chunks))
        if manifest.get("levels_sig") != chunk_sig:
            manifest["levels"], manifest["levels_sig"] = [], chunk_sig
        items = [self._strip_header(_read(os.path.join(ddir, f"chunk_{c['index']:03d}.md")) or "")
                 for c in chunks]
        level = 0
        while len(items) > 1:
            level += 1
            groups = self._group(items)
            if len(manifest["levels"]) < level:
                manifest["levels"].append({"level": level, "groups": len(groups), "done": 0})
            lv = manifest["levels"][level - 1]
            merged = []
            for gi, group in enumerate(groups, 1):
                path = os.path.join(ddir, f"merge_L{level}_{gi:03d}.md")
                cached = _read(path) if gi <= lv["done"] else None
                if cached is not None:
                    merged.append(cached)
                    continue
                if len(group) == 1:
                    out = group[0]
                else:
                    if should_stop():
                        return self._partial(did, ddir, manifest)
                    emit("merge", level=level, group=gi, groups=len(groups))
                    joined = "\n\n".join(f"--- Part {i} ---\n{g}" for i, g in enumerate(group, 1))
                    user = f"DOCUMENT: {source_ref}{focus_line}\n\nSECTION SUMMARIES:\n{joined}\n\nMerged summary:"
                    out, _ = self._summarize(_MERGE_SYSTEM, user, self.merge_tokens,
                                             f"digest:{did[:8]}:merge_L{level}_{gi}", joined)
                    if self.throttle:
                        time.sleep(self.throttle)
                _atomic_write(path, out)
                merged.append(out)
                lv["done"] = gi
                self._save_manifest(ddir, manifest, lock)
            items = merged

        digest_text = self._render_digest(manifest, items[0] if items else "")
        _atomic_write(os.path.join(ddir, "digest.md"), digest_text)
        manifest["status"] = "complete"
        manifest["source_persisted"] = bool(persist_source or manifest.get("source_persisted"))
        self._save_manifest(ddir, manifest, lock)
        fb_count = sum(1 for c in chunks if c["fallback"])
        emit("done", chunks=total, fallback_chunks=fb_count)
        return DigestResult(did, ddir, digest_text, total, True, fb_count, False, manifest)

    def _partial(self, did, ddir, manifest) -> DigestResult:
        done = sum(1 for c in manifest["chunks"] if c["status"] == "done")
        return DigestResult(did, ddir, "", len(manifest["chunks"]), False,
                            sum(1 for c in manifest["chunks"] if c["fallback"]), False,
                            {**manifest, "chunks_done": done})

    def _group(self, items: list) -> list:
        """Pack consecutive summaries into groups under merge_input_chars, at
        least two per group so every level shrinks."""
        budget = self.merge_input_chars
        groups, cur, size = [], [], 0
        for it in items:
            if len(it) > budget // 2:
                it = it[: budget // 2] + "\n[...truncated]"
            if cur and len(cur) >= 2 and size + len(it) > budget:
                groups.append(cur)
                cur, size = [], 0
            cur.append(it)
            size += len(it)
        if cur:
            if len(cur) == 1 and groups:
                groups[-1].append(cur[0])
            else:
                groups.append(cur)
        return groups

    @staticmethod
    def _strip_header(text: str) -> str:
        return re.sub(r"^<!--.*?-->\n", "", text, count=1)

    def _render_digest(self, manifest: dict, top: str) -> str:
        chunks = manifest["chunks"]
        fb = sum(1 for c in chunks if c["fallback"])
        lines = [
            f"# Digest: {manifest['source_ref']}",
            "",
            f"- digest_id: `{manifest['digest_id']}`",
            f"- source: {manifest['source_chars']} chars, {chunks[-1]['end_line'] if chunks else 0} lines, "
            f"{len(chunks)} chunk(s), {len(manifest.get('levels', []))} merge level(s)",
        ]
        if manifest.get("focus"):
            lines.append(f"- focus: {manifest['focus']}")
        if fb:
            lines.append(f"- WARNING: {fb} chunk(s) used an extractive fallback (local model unavailable); "
                         "read those chunks directly before relying on details.")
        lines += ["", "## Summary", "", top.strip(), "", "## Chunk index",
                  "", "Use read_chunk(<key>, <n>) to read a chunk verbatim.", ""]
        for c in chunks:
            first = self._strip_header(_read(os.path.join(self.digest_dir(manifest["digest_id"]),
                                                          f"chunk_{c['index']:03d}.md")) or "")
            first = next((ln.strip(" -*#") for ln in first.splitlines() if ln.strip()), "")[:140]
            tag = " (fallback)" if c["fallback"] else ""
            lines.append(f"{c['index']}. lines {c['start_line']}-{c['end_line']}{tag}: {first}")
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Convenience wrappers
# --------------------------------------------------------------------------- #

def digest_text(text: str, source_ref: str = "inline", **kwargs) -> DigestResult:
    """One-shot helper with default settings. Extra kwargs go to run()."""
    return DigestPipeline().run(text, source_ref=source_ref, **kwargs)


async def adigest_text(text: str, source_ref: str = "inline", pipeline: Optional[DigestPipeline] = None,
                       on_progress: Optional[ProgressFn] = None, **kwargs) -> DigestResult:
    """Async wrapper: runs the pipeline in the default executor. `on_progress`
    is called on the event loop thread, so it may schedule coroutines safely."""
    import asyncio
    loop = asyncio.get_running_loop()
    pipe = pipeline or DigestPipeline()
    cb = (lambda ev: loop.call_soon_threadsafe(on_progress, ev)) if on_progress else None
    return await loop.run_in_executor(
        None, lambda: pipe.run(text, source_ref=source_ref, on_progress=cb, **kwargs))


def prune_digests(max_age_days: float = 30.0, root: str = DIGEST_ROOT) -> int:
    """Delete digests not updated in `max_age_days`. Returns how many were removed."""
    import shutil
    if not os.path.isdir(root):
        return 0
    cutoff, removed = time.time() - max_age_days * 86400, 0
    for name in os.listdir(root):
        d = os.path.join(root, name)
        if not re.fullmatch(r"[0-9a-f]{32}", name) or os.path.exists(os.path.join(d, ".lock")):
            continue
        try:
            if os.path.getmtime(os.path.join(d, "manifest.json")) < cutoff:
                shutil.rmtree(d)
                removed += 1
        except OSError:
            pass
    return removed
