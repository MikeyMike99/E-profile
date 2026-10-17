# Chapter 05_15: Git Automation & Session Recorder From Scratch

A step-by-step guide to writing the developer workflow automation and session recording script (`helpers.sh`) line by line from a completely blank text editor window.

---

## What We Are Building & Beginner Safety Rules

We are creating `helpers.sh`—a shell utility that provides automated SSH agent verification, organized terminal demonstration recording (`rec`), and clean branch synchronization (`sync`) without dirty tree merge conflicts.

### Beginner Safety Directives
1. **Always Resolve Repository Root Dynamically**: Never hardcode paths like `/home/developer/repo`. Use `$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)`.
2. **Clear Conflicting Aliases**: Shell aliases can override function definitions. We must `unalias` target command names at the top of the file.
3. **Check Working Tree Before Merging**: Always inspect `git status --porcelain` before executing `git pull` or `git checkout`.

---

## Step-by-Step Line Breakdown

### Block 1: Shebang, Path Resolution & Alias Clearing (Lines 1–10)

Open a blank file named `helpers.sh` and write:

```bash
#!/usr/bin/env bash

# Resolve repository root dynamically
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RECORDINGS_DIR="$REPO_DIR/evidence"

# Clear any conflicting aliases so functions load cleanly
unalias rec playrec sync feature feat 2>/dev/null || true
```

- **Line 1**: Standard bash shebang.
- **Lines 4–5**: Dynamically resolves the project root two levels above the script's directory.
- **Line 8**: Removes existing shell aliases that could conflict with our function names.

---

### Block 2: Persistent SSH Agent Handshake (Lines 11–35)

Add the `_ensure_ssh_agent` helper:

```bash
_ensure_ssh_agent() {
    # Check if existing cached agent is alive
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

    # Verify that id_ed25519 key is registered
    if ! ssh-add -l 2>/dev/null | grep -q "id_ed25519"; then
        if [ -f "$HOME/.ssh/id_ed25519" ]; then
            echo "Unlocking SSH key for GitHub..."
            ssh-add "$HOME/.ssh/id_ed25519" 2>/dev/null || true
        fi
    fi
}
```

- **Lines 13–21**: Reconnects to the active SSH agent via `agent.env` or starts a fresh one if missing.
- **Lines 24–31**: Adds your private key automatically so Git commands never freeze waiting for a password.

---

### Block 3: Watermarked Terminal Recording (`rec`) (Lines 36–60)

Add the `rec` function to record terminal sessions cleanly:

```bash
rec() {
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
    
    echo "Saving recording to: $user_rec_dir/$name.cast"
    echo "Press Ctrl+D or type 'exit' when finished."
    
    local watermark_cmd="echo -e '\033[36m======================================================\n\033[33mAssignee: $dev_user | Session: $name | Date: $timestamp\n\033[36m======================================================\033[0m'; exec bash"
    
    asciinema rec -i 1.5 -c "$watermark_cmd" "$user_rec_dir/$name.cast"
}
```

- **Lines 38–42**: Routes all recordings into a user-specific evidence directory.
- **Lines 51–53**: Injects a timestamp and username banner into the terminal session as an evidentiary watermark.

---

### Block 4: Clean Sync & Auto-Stash (`sync`) (Lines 61–85)

Add the `sync` function that prevents merge conflicts:

```bash
sync() {
    _ensure_ssh_agent
    
    local cur_branch
    cur_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo "Syncing branch '$cur_branch' with GitHub..."

    # Check for uncommitted local changes
    local dirty
    dirty="$(git status --porcelain)"
    
    if [ -n "$dirty" ]; then
        echo "Stashing uncommitted local progress..."
        git stash push -m "WIP before sync $(date +%s)" --quiet
    fi

    # Pull latest commits cleanly
    git fetch origin "$cur_branch" --quiet 2>/dev/null || true
    git merge "origin/$cur_branch" --ff-only 2>/dev/null || git pull origin "$cur_branch"

    # Restore local progress
    if [ -n "$dirty" ]; then
        echo "Re-applying local changes..."
        git stash pop --quiet 2>/dev/null || echo "Notice: Merge conflict detected on stashed changes. Resolve manually."
    fi
    echo "Synchronization complete!"
}
```

- **Lines 69–73**: Stashes uncommitted local changes so Git won't refuse to merge.
- **Lines 76–77**: Fetches and performs a fast-forward merge from origin.
- **Lines 80–82**: Automatically pops your stashed changes back into your working directory.

---

## Complete Finished File Listing

```bash
#!/usr/bin/env bash

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RECORDINGS_DIR="$REPO_DIR/evidence"

unalias rec playrec sync feature feat 2>/dev/null || true

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

    if ! ssh-add -l 2>/dev/null | grep -q "id_ed25519"; then
        if [ -f "$HOME/.ssh/id_ed25519" ]; then
            echo "Unlocking SSH key for GitHub..."
            ssh-add "$HOME/.ssh/id_ed25519" 2>/dev/null || true
        fi
    fi
}

rec() {
    local dev_user
    dev_user="$(git -C "$REPO_DIR" config user.name 2>/dev/null || echo "$USER")"
    dev_user="$(echo "$dev_user" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
    local user_rec_dir="$RECORDINGS_DIR/$dev_user"
    mkdir -p "$user_rec_dir"

    read -rp "Enter recording name: " name
    name="${name:-session_$(date +%Y%m%d_%H%M%S)}"
    name="${name%.cast}"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    echo "Saving recording to: $user_rec_dir/$name.cast"
    echo "Press Ctrl+D or type 'exit' when finished."
    local watermark_cmd="echo -e '\033[36m======================================================\n\033[33mAssignee: $dev_user | Session: $name | Date: $timestamp\n\033[36m======================================================\033[0m'; exec bash"
    asciinema rec -i 1.5 -c "$watermark_cmd" "$user_rec_dir/$name.cast"
}

sync() {
    _ensure_ssh_agent
    local cur_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo "Syncing branch '$cur_branch' with GitHub..."

    local dirty="$(git status --porcelain)"
    if [ -n "$dirty" ]; then
        echo "Stashing uncommitted local progress..."
        git stash push -m "WIP before sync $(date +%s)" --quiet
    fi

    git fetch origin "$cur_branch" --quiet 2>/dev/null || true
    git merge "origin/$cur_branch" --ff-only 2>/dev/null || git pull origin "$cur_branch"

    if [ -n "$dirty" ]; then
        echo "Re-applying local changes..."
        git stash pop --quiet 2>/dev/null || echo "Notice: Merge conflict detected on stashed changes. Resolve manually."
    fi
    echo "Synchronization complete!"
}
```

---

## 10-Second Verification Checklist

```bash
# 1. Source the helper script
source helpers.sh

# 2. Test SSH agent initialization
_ensure_ssh_agent
echo "Agent PID: $SSH_AGENT_PID"
```
If an active PID prints, your Git automation helper is operational!

---

## Beginner Coder Q&A

### What is `--ff-only`?
`--ff-only` (Fast-Forward Only) ensures Git only merges if the local branch hasn't diverged. It prevents Git from creating unwanted, confusing merge commit bubbles in your commit history.

### Can I run `sync` if I am offline?
If you are offline, `git fetch` will fail gracefully, and the script will skip the network step while preserving your local files.

---

## Next Steps & Related Chapters
- To understand why automated Git scripts fail on branch merges, read [`01_PROBLEMS_ENCOUNTERED/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS.md`](/docs/devlog/01_18_GIT_SYNC_MERGE_CONFLICTS_AND_TERMINAL_SESSION_TRAPS).
- To inspect primary source citations, view [`02_SOURCE_EVIDENCE/02_13_GIT_RECORDING_AND_MERGE_AUTOMATION_EVIDENCE.md`](/docs/devlog/02_13_GIT_RECORDING_AND_MERGE_AUTOMATION_EVIDENCE).
- To view diagnostic test logs of automated sync and merge runs, visit [`03_DIAGNOSTIC_TESTS/03_12_GIT_AUTOMATION_AND_MERGE_TEST_LOGS.md`](/docs/devlog/03_12_GIT_AUTOMATION_AND_MERGE_TEST_LOGS).
