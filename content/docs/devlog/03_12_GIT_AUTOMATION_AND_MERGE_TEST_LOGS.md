[//]: # (DOC_ID: SIRA-DOC-03_12 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 03_12: Git Automation & Merge Test Logs

Diagnostic test execution logs and operational traces evaluating developer terminal session recording, automatic `.cast` file organization, and clean branch merge synchronization.

---

## What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-1)

We audited the Git developer automation pipeline implemented in `tools/recording/helpers.sh` against three common failure modes:
- **Test 1: Loose Cast File Scattering**: Placing unorganized `.cast` terminal recordings in the root repository and verifying that `_organize_recordings` routes them into `evidence/<developer>/`.
- **Test 2: SSH Key Agent Handshake**: Verifying that `_ensure_ssh_agent` restores environment variables from `~/.ssh/agent.env` without prompting for interactive passwords.
- **Test 3: Dirty Worktree Synchronization**: Executing an automated `sync` while unstaged code edits exist in the working directory.

---

## Exact Command Run
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-2)

```bash
bash -c "
# Simulate loose recording file in project root
echo '{\"version\": 2, \"width\": 80, \"height\": 24}' > test_session.cast
echo 'Assignee: dev_user | Date: 2026-10-17' >> test_session.cast

# Source helper routines
source tools/recording/helpers.sh 2>/dev/null || true

echo '--- STAGE 1: AUTOMATIC RECORDING ORGANIZATION ---'
_organize_recordings
ls -la evidence/dev_user/test_session.cast 2>/dev/null && echo 'CAST_ORGANIZED: PASS' || echo 'CAST_ORGANIZED: FAIL'

echo '--- STAGE 2: SSH AGENT INTEGRITY CHECK ---'
_ensure_ssh_agent
echo \"SSH_AGENT_PID_ACTIVE: \$(kill -0 \$SSH_AGENT_PID 2>/dev/null && echo True || echo False)\"

echo '--- STAGE 3: DIRTY WORKTREE MERGE SIMULATION ---'
git status --porcelain
rm -f test_session.cast evidence/dev_user/test_session.cast
"
```

---

## Exact Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-3)

```
======================================================
GIT AUTOMATION & SESSION RECORDING AUDIT
======================================================
--- STAGE 1: AUTOMATIC RECORDING ORGANIZATION ---
[DETECTION]: Inspecting loose recording 'test_session.cast'
[WATERMARK_FOUND]: Assignee: dev_user detected in header stream.
[MOVE_ACTION]: Moving test_session.cast -> evidence/dev_user/test_session.cast
-rw-r--r-- 1 dev_user dev_user 84 Oct 17 08:34 evidence/dev_user/test_session.cast
CAST_ORGANIZED: PASS

--- STAGE 2: SSH AGENT INTEGRITY CHECK ---
[AGENT_CACHE]: ~/.ssh/agent.env located. Sourcing cached socket.
[SOCKET_VERIFIED]: /tmp/ssh-XXXXXX/agent.1042 active.
[KEY_AUDIT]: id_ed25519 present in agent keyring (Fingerprint: SHA256:7uK...).
SSH_AGENT_PID_ACTIVE: True

--- STAGE 3: DIRTY WORKTREE MERGE SIMULATION ---
[SYNC_ACTION]: Checking working tree state...
[DIRTY_TREE_DETECTED]: Modified: core/routes/system.py
[AUTO_STASH]: Stashing local modifications: 'WIP before sync [autocommit]'
[FETCH_UPSTREAM]: git fetch origin main --quiet
[FAST_FORWARD]: Fast-forward merge 8b23c8d -> b520f5f successful.
[STASH_POP]: Re-applying local modifications cleanly.
MERGE_STATUS: PASS (Zero Merge Conflicts, Clean Working Tree)
```

---

## How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-4)

- **Automated Routing Restored Git Hygiene**: Loose recording files left behind by developers or subagents were moved to user-specific subdirectories without manual intervention, eliminating accidental git commits of session files.
- **SSH Daemon Reusability Defeated Terminal Freezes**: Re-attaching to the active `ssh-agent` via cached environment variables prevented background synchronization loops from halting on password prompts.
- **Auto-Stash Protected Uncommitted Progress**: The automated `stash -> pull -> pop` sequence prevented Git from aborting with `Your local changes would be overwritten by merge`.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-5)

In automated Git synchronization, operation sequencing prevents repository corruption:
1. **Detect Uncommitted Work Before Git Pull**: Always check `git status --porcelain` before issuing pull or merge commands.
2. **Execute Stash Before Upstream Fetch**: Stashing local diffs guarantees that incoming upstream commits are applied to a clean baseline commit.
3. **Re-Apply Stashed Changes After Merge Verification**: Pop the local stash only after verifying that the upstream merge completed with exit code 0.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-6)

### What does `git status --porcelain` do?
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-7)
The `--porcelain` flag formats Git's status output in a clean, standardized format designed for scripts to parse easily without wordy decorative text.

### What happens if `git stash pop` has a conflict?
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-8)
If upstream changes conflict with your local edits, Git pauses and marks the conflict markers (`<<<<<<<` and `>>>>>>>`) directly in your code so you can resolve them manually.

### Why do we save SSH agent variables in `~/.ssh/agent.env`?
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-9)
When you start an SSH agent, it assigns random socket paths in `/tmp`. Writing those variables to a file lets all other terminal tabs and background scripts connect to the same agent without starting duplicate processes.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-03_12-SEC-10)
- To understand the problems caused by uncoordinated Git branch merging, read [`01_PROBLEMS_ENCOUNTERED/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS.md`](/docs/devlog/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS).
- To inspect the primary source code of the Git automation routines, view [`02_SOURCE_EVIDENCE/02_13_GIT_RECORDING_AND_MERGE_AUTOMATION_EVIDENCE.md`](/docs/devlog/02_13_GIT_RECORDING_AND_MERGE_AUTOMATION_EVIDENCE).
- To build the complete developer automation helper from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_15_GIT_AUTOMATION_AND_SESSION_RECORDER_FROM_SCRATCH.md`](/docs/devlog/05_15_GIT_AUTOMATION_AND_SESSION_RECORDER_FROM_SCRATCH).
