#!/usr/bin/env python3
"""Scheduled Task Runner & CLI for Cyber Threat Feed (e_profile).

Can be executed standalone via cron, Windows Task Scheduler, or PythonAnywhere Scheduled Tasks:
  python3 /mnt/c/Users/michael/Documents/e_profile/update_cyber_feed.py [--force]

Guarantees the newest released cyber advisory is ALWAYS sorted on top.
Adheres strictly to upstream rate limits and quota conservation policies.
"""

import sys
import argparse
from pathlib import Path

# Ensure e_profile root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from threat_intel_engine import ThreatIntelEngine


def main():
    parser = argparse.ArgumentParser(description="Refresh the e_profile Cyber Threat Intelligence Feed.")
    parser.add_argument("--force", action="store_true", help="Bypass cooldown timers and force fresh fetch.")
    parser.add_argument("--status", action="store_true", help="Print current rate limit status and exit.")
    args = parser.parse_args()

    engine = ThreatIntelEngine()

    if args.status:
        status = engine.get_feed_status()
        print(f"Feed Status: {status.get('status')}")
        print(f"Dispatched At: {status.get('dispatched_at')}")
        print(f"Total Items: {status.get('total_items')}")
        print("Cooldowns:")
        for k, v in status.get("cooldowns", {}).items():
            print(f"  {k}: {v}")
        return 0

    print("🛡️ Refreshing Cyber Threat Intelligence Feed...")
    result = engine.refresh_feed(force=args.force)

    print(f"Status: {result.get('status')}")
    print(f"Dispatched At: {result.get('dispatched_at')}")
    print(f"Total Feed Items: {result.get('total_items')}")
    if result.get("newest_story"):
        print(f"⚡ Newest Story on Top: {result.get('newest_story')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
