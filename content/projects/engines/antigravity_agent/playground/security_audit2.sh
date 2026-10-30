#!/bin/bash
echo "--- agents/agent_manager.py (sandbox / exec / DLP) ---"
grep -iE 'class|def |sandbox|dangerously|dlp|prompt|rule' ../agents/agent_manager.py | head -n 40
