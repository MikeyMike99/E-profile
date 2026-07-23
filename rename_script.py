import os
import json
import re
from pathlib import Path
import argparse

def is_ambiguous(name):
    # Check for UUIDs
    uuid_pattern = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    if uuid_pattern.search(name):
        return True
    
    # Check for unusually long string of random alphanumeric (proxy for weird patterns)
    if len(name) > 60 and "certificate" in name.lower() and "-" in name:
        # e.g., Getting_Started_with_Cisco_Packet_Tracer_certificate_202511-hwacademy-org_cbba7d...
        return True
        
    if "out of list" in name.lower():
        return True
        
    return False

def clean_part(part, is_file, config):
    if is_file:
        # Handle extension
        if '.' in part:
            stem = part[:part.rfind('.')]
            ext = part[part.rfind('.'):]
        else:
            stem = part
            ext = ''
    else:
        stem = part
        ext = ''
        
    original_stem = stem
    
    # 1. Strip size tags
    # Handle specific weird cases observed, plus generic (small) / (Large)
    stem = re.sub(r'(?i)\.1\s*\(1\)small\(', '', stem)
    stem = re.sub(r'(?i)\s*\(1\)\(small\)', '', stem)
    stem = re.sub(r'(?i)\.1\s*\(size_small\)', '', stem)
    stem = re.sub(r'(?i)\(size_large\)', '', stem)
    stem = re.sub(r'(?i)\(size_small\)', '', stem)
    stem = re.sub(r'(?i)sizesmall', '', stem)
    stem = re.sub(r'(?i)sizelarge', '', stem)
    stem = re.sub(r'(?i)\s*\(small\)', '', stem)
    stem = re.sub(r'(?i)\s*\(large\)', '', stem)
    stem = re.sub(r'(?i)\.1\(large\)', '', stem)
    
    # Clean up trailing dots or spaces left over from stripping
    stem = stem.strip(' .')
    
    # 2. Known corrections
    # We sort by length descending so longer phrases match first
    known = config.get("known_corrections", {})
    sorted_known = sorted(known.items(), key=lambda x: len(x[0]), reverse=True)
    
    for k, v in sorted_known:
        # Simple case-insensitive replace
        pattern = re.compile(re.escape(k), re.IGNORECASE)
        stem = pattern.sub(v, stem)
        
    # 3. Capitalize standard acronyms
    acronyms = config.get("acronyms", [])
    for ac in acronyms:
        # word boundary match
        pattern = re.compile(r'\b' + re.escape(ac) + r'\b', re.IGNORECASE)
        stem = pattern.sub(ac, stem)
        
    # Optional: Capitalize first letters of words that aren't acronyms?
    # User didn't explicitly request general title case, just "proper casing for acronyms and terms".
    # We will leave other words alone, or rely on known_corrections.
    
    # Reassemble
    return stem + ext

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--undo', action='store_true', help='Revert renames using rename_history.json')
    parser.add_argument('--execute', action='store_true', help='Actually rename files instead of dry run')
    args = parser.parse_args()
    
    root_dir = Path(r"d:\my_programs\e_profile")
    cert_dir = root_dir / "content" / "certifications" / "digital badges and certificates"
    config_file = root_dir / "config.json"
    history_file = root_dir / "rename_history.json"
    
    if args.undo:
        if not history_file.exists():
            print("No rename_history.json found to undo.")
            return
        with open(history_file, 'r') as f:
            history = json.load(f)
        
        print(f"Reverting {len(history)} renames...")
        # Undo in reverse order (children then parents)
        for old_path, new_path in reversed(history):
            abs_new = cert_dir / new_path
            abs_old = cert_dir / old_path
            if abs_new.exists():
                abs_old.parent.mkdir(parents=True, exist_ok=True)
                abs_new.rename(abs_old)
                print(f"Reverted: {new_path} -> {old_path}")
            else:
                print(f"Warning: Could not find {new_path} to revert.")
        print("Undo complete.")
        return

    with open(config_file, 'r') as f:
        config = json.load(f)

    proposed_renames = {}
    review_needed = []
    
    # Collect all items
    items = []
    for path in cert_dir.rglob("*"):
        items.append(path)
        
    # Sort items by depth so we can map paths logically
    # For a dry run mapping, we just build the proposed relative paths piece by piece.
    for path in items:
        rel_path = path.relative_to(cert_dir)
        rel_str = str(rel_path).replace('\\', '/')
        
        # We need to process each part of the path
        parts = list(rel_path.parts)
        is_file = path.is_file()
        
        # Check if ambiguous
        if is_ambiguous(rel_str):
            review_needed.append(rel_str)
            continue
            
        new_parts = []
        changed = False
        for i, part in enumerate(parts):
            # It's a file only if it's the last part AND path is a file
            part_is_file = (i == len(parts) - 1) and is_file
            cleaned = clean_part(part, part_is_file, config)
            new_parts.append(cleaned)
            if cleaned != part:
                changed = True
                
        if changed:
            new_rel_str = "/".join(new_parts)
            proposed_renames[rel_str] = new_rel_str
            
    # Write output
    with open(root_dir / "proposed_renames.json", "w") as f:
        json.dump(proposed_renames, f, indent=4)
        
    with open(root_dir / "review_needed.txt", "w") as f:
        for p in review_needed:
            f.write(p + "\n")
            
    print("=== DRY RUN SUMMARY ===")
    print(f"Total items scanned: {len(items)}")
    print(f"Auto-approved renames: {len(proposed_renames)}")
    print(f"Flagged for review (Ambiguous): {len(review_needed)}")
    print("\nProposed renames saved to proposed_renames.json")
    print("Flagged files saved to review_needed.txt")
    print("\nTo execute actual renames, run this script with --execute")

    if args.execute:
        print("\nExecuting renames...")
        history = []
        
        # We must rename deep items first to avoid path invalidation
        # Sort by depth descending
        sorted_renames = sorted(proposed_renames.items(), key=lambda x: x[0].count('/'), reverse=True)
        
        # Actually since we only rename piece by piece, we should do bottom-up
        # But wait, proposed_renames maps original full relative path to new full relative path.
        # If we rename a parent directory, the original path of its children no longer exists.
        # To handle this safely, we should execute renames by renaming the exact basename of each path, bottom-up.
        
        actual_renames = []
        for old_rel, new_rel in sorted_renames:
            old_abs = cert_dir / old_rel
            new_abs = cert_dir / new_rel
            
            # Since we go bottom up, children are renamed before parents.
            # But wait, old_abs uses the ORIGINAL parent name. If the parent wasn't renamed yet, this works.
            if old_abs.exists():
                new_abs.parent.mkdir(parents=True, exist_ok=True)
                old_abs.rename(new_abs)
                history.append((old_rel, new_rel))
                actual_renames.append(f"{old_rel} -> {new_rel}")
            else:
                # If parent was renamed? We sorted by depth descending, so children ARE processed first.
                # So old_abs should still exist.
                pass
                
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=4)
            
        print(f"Successfully executed {len(history)} renames.")

if __name__ == '__main__':
    main()
