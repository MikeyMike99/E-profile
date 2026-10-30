#!/bin/bash
echo "--- security/security_manager.py (Tiers/Roles) ---"
grep -iE 'class|def |tier|rbac|prompt|sandbox' ../security/security_manager.py | head -n 30
echo "--- security/raugus_resolver.py (Firewall/Traps) ---"
grep -iE 'class|def |firewall|trap|prompt|injection|leak' ../security/raugus_resolver.py | head -n 30
echo "--- core/server.py (Agent Execution/Sandbox) ---"
grep -iE 'sandbox|dangerously|agent|prompt|rule|dlp' ../core/server.py | head -n 30
