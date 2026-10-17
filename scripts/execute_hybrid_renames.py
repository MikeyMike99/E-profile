import os
import json
import subprocess
import shutil
from pathlib import Path

root_dir = Path(r"d:\my_programs\e_profile")
cert_dir = root_dir / "content" / "certifications" / "digital badges and certificates"
proposed_file = root_dir / "proposed_renames.json"
order_file = root_dir / "content" / "certifications" / "order.json"
history_file = root_dir / "rename_history.json"

def is_tracked(filepath):
    try:
        rel_path = filepath.relative_to(root_dir).as_posix()
        result = subprocess.run(
            ['git', 'ls-files', '--error-unmatch', rel_path],
            cwd=str(root_dir),
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    if not proposed_file.exists():
        print("Error: proposed_renames.json not found.")
        return

    with open(proposed_file, 'r') as f:
        proposed_renames = json.load(f)

    file_moves = {}
    
    for path in cert_dir.rglob('*'):
        if not path.is_file():
            continue
            
        old_rel = path.relative_to(cert_dir).as_posix()
        
        if old_rel in proposed_renames:
            new_rel = proposed_renames[old_rel]
            file_moves[path] = cert_dir / new_rel
        else:
            parent_rel = path.parent.relative_to(cert_dir).as_posix()
            if parent_rel == '.':
                continue
            if parent_rel in proposed_renames:
                new_parent_rel = proposed_renames[parent_rel]
                new_rel = f"{new_parent_rel}/{path.name}"
                file_moves[path] = cert_dir / new_rel

    history = []
    success_count = 0
    deleted_count = 0
    
    for old_abs, new_abs in file_moves.items():
        if old_abs == new_abs:
            continue
            
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        tracked = is_tracked(old_abs)
        old_rel_git = old_abs.relative_to(root_dir).as_posix()
        new_rel_git = new_abs.relative_to(root_dir).as_posix()
        
        if new_abs.exists() or new_abs in file_moves.values() and list(file_moves.values()).index(new_abs) < list(file_moves.keys()).index(old_abs):
            # Check if destination already exists (redundant file)
            # Or if another file is already slated to move here and we are the duplicate
            if new_abs.exists():
                print(f"Target already exists. Deleting redundant: {old_abs.name}")
                if tracked:
                    subprocess.run(['git', 'rm', '-f', old_rel_git], cwd=str(root_dir))
                else:
                    old_abs.unlink()
                deleted_count += 1
                continue
                
        try:
            if tracked:
                # check if new_abs parent is tracked? git mv creates parent if needed but we used mkdir
                res = subprocess.run(['git', 'mv', old_rel_git, new_rel_git], cwd=str(root_dir), capture_output=True, text=True)
                if res.returncode != 0:
                    print(f"git mv failed for {old_abs.name}: {res.stderr}. Falling back to os.rename.")
                    os.rename(old_abs, new_abs)
            else:
                os.rename(old_abs, new_abs)
                
            history.append((old_abs.relative_to(cert_dir).as_posix(), new_abs.relative_to(cert_dir).as_posix()))
            success_count += 1
        except Exception as e:
            print(f"Failed to move {old_abs.name}: {e}")
            
    for root, dirs, files in os.walk(str(cert_dir), topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                os.rmdir(dir_path)
            except OSError:
                pass 
                
    if order_file.exists():
        try:
            with open(order_file, 'r') as f:
                order_data = json.load(f)
                
            new_order = {}
            for k, v in order_data.items():
                if k in proposed_renames:
                    new_order[proposed_renames[k]] = v
                else:
                    k_path = Path(k)
                    parent_k = k_path.parent.as_posix()
                    if parent_k in proposed_renames:
                        new_parent = proposed_renames[parent_k]
                        new_k = f"{new_parent}/{k_path.name}"
                        new_order[new_k] = v
                    else:
                        new_order[k] = v
                        
            with open(order_file, 'w') as f:
                json.dump(new_order, f, indent=4)
            print("Successfully updated order.json.")
        except Exception as e:
            print(f"Error updating order.json: {e}")

    if history_file.exists():
        try:
            with open(history_file, 'r') as f:
                existing_history = json.load(f)
            history = existing_history + history
        except:
            pass
            
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=4)
        
    print(f"\n--- SUMMARY ---")
    print(f"Successfully moved/renamed: {success_count} files.")
    print(f"Successfully removed redundant files: {deleted_count} files.")
    print(f"Rollback history saved to {history_file.name}.")
    
if __name__ == '__main__':
    main()
