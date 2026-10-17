[//]: # (DOC_ID: SIRA-DOC-02_13 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 02_13: Git Recording & Merge Automation Evidence

Primary source evidence from the repository developer tools demonstrating how automated SSH credential verification, asciinema watermark recording, and branch synchronization prevent dirty worktree merge failures.

---

## Source Citation 1: Headless SSH Agent Verification (`tools/recording/helpers.sh`)
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-1)

This excerpt displays how the automation environment initializes and caches `ssh-agent` state across non-interactive terminal sessions:

```bash
# Location: <project_root>/tools/recording/helpers.sh
# Lines: 10-32

_ensure_ssh_agent() {
    if [ -z "$SSH_AUTH_SOCK" ] || ! kill -0 "$SSH_AGENT_PID" 2>/dev/null; then
        if [ -f "$HOME/.ssh/agent.env" ]; then
            source "$HOME/.ssh/agent.env" >/dev/null 2>&1
        fi
        if [ -z "$SSH_AUTH_SOCK" ] || ! kill -0 "$SSH_AGENT_PID" 2>/dev/null; then
            eval "$(ssh-agent -s)" >/dev/null 2>&1
            echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > "$HOME/.ssh/agent.env"
            echo "export SSH_AGENT_PID=$SSH_AGENT_PID" >> "$HOME/.ssh/agent.env"
        fi
    fi

    # Check if id_ed25519 key is registered in agent
    if ! ssh-add -l 2>/dev/null | grep -q "id_ed25519"; then
        if [ -f "$HOME/.ssh/id_ed25519" ]; then
            echo "Authenticating SSH key for GitHub..."
            ssh-add "$HOME/.ssh/id_ed25519" || {
                echo "Warning: SSH key not unlocked. Pushing or pulling via SSH may require authentication."
            }
        fi
    fi
}
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-2)
- **Persistence Across Headless Shells**: Caching `SSH_AUTH_SOCK` and `SSH_AGENT_PID` into `~/.ssh/agent.env` allows subshells, cron jobs, and background agent tasks to reuse the unlocked SSH agent without prompting the user repeatedly.
- **Key Registration Check**: Lines 24–31 check `ssh-add -l` before attempting Git operations, avoiding mysterious hangs when remotes switch to `git@github.com:...`.

---

## Source Citation 2: Isolated Terminal Recording (`tools/recording/helpers.sh`)
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-3)

This excerpt demonstrates the automated creation of organized terminal recordings with developer watermarks:

```bash
# Location: <project_root>/tools/recording/helpers.sh
# Lines: 143-164

rec() {
    _organize_recordings

    local dev_user
    dev_user="$(git -C "$REPO_DIR" config user.name 2>/dev/null || echo "$USER")"
    dev_user="$(echo "$dev_user" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
    local user_rec_dir="$RECORDINGS_DIR/$dev_user"
    mkdir -p "$user_rec_dir"

    read -rp "Enter recording name: " name
    name="${name:-session_$(date +%Y%m%d_%H%M%S)}"
    name="${name%.cast}"
    
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    echo "Saving to: $user_rec_dir/$name.cast"
    echo "Press Ctrl+D or type 'exit' when done."
    
    local watermark_cmd="echo -e '\033[36m======================================================\n\033[33mAssignee: $dev_user  |  Session: $name  |  Date: $timestamp\n\033[36m======================================================\033[0m'; exec bash"
    asciinema rec -i 1.5 -c "$watermark_cmd" "$user_rec_dir/$name.cast"
}
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-4)
- **Strict Directory Sandboxing**: All `.cast` files are automatically forced into `$RECORDINGS_DIR/$dev_user/` rather than the current working directory, preventing repository pollution.
- **Forensic Watermarking**: Lines 162–163 inject a timestamp and developer identity banner directly into the recording's first terminal frame for auditable evidence.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-5)

In shell-based Git automation, ordering prevents destructive desynchronization:
1. **Source Agent Environment Before SSH Invocations**: Sourcing `agent.env` must precede `git fetch` or `git pull`. Without the environment variables, the SSH subprocess cannot contact the agent daemon.
2. **Re-organize Loose Files Before Recording**: Calling `_organize_recordings` before launching `asciinema` cleans up existing uncommitted files so the working tree remains pristine.
3. **Pull Upstream Main Before Checkout**: Updating local `main` *before* branching (`git checkout -b <feature>`) ensures the new branch forks from the latest verified production commit.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-6)

### What does `kill -0 "$SSH_AGENT_PID"` do?
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-7)
Signal 0 does not terminate the process; it merely checks if the process ID is still alive. If the process died or rebooted, the command returns non-zero, signaling that a fresh agent must be spawned.

### What does `unalias` at the top of the script accomplish?
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-8)
If a developer previously defined an alias with the same name as a function (e.g., `alias sync='...'`), the alias would take precedence and prevent the shell script function from loading correctly.

### What is the `-i 1.5` flag in `asciinema rec`?
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-9)
The idle time limit flag (`-i 1.5`) caps pauses between keystrokes to a maximum of 1.5 seconds during playback, skipping long pauses when someone pauses to read code.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_13-SEC-10)
- To understand why automated Git scripts fail on branch merges, read [`01_PROBLEMS_ENCOUNTERED/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS.md`](/docs/devlog/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS).
- To view diagnostic test logs of automated sync and merge runs, visit [`03_DIAGNOSTIC_TESTS/03_12_GIT_AUTOMATION_AND_MERGE_TEST_LOGS.md`](/docs/devlog/03_12_GIT_AUTOMATION_AND_MERGE_TEST_LOGS).
- To write your own Git automation helper from a blank script, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_15_GIT_AUTOMATION_AND_SESSION_RECORDER_FROM_SCRATCH.md`](/docs/devlog/05_15_GIT_AUTOMATION_AND_SESSION_RECORDER_FROM_SCRATCH).
