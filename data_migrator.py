import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

TARGET_SCHEMA_VERSION = 2

def create_backup(filepath: Path):
    if not filepath.exists():
        return None
        
    backups_dir = filepath.parent / "backups"
    backups_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.name}.v{timestamp}.bak"
    backup_path = backups_dir / backup_name
    
    shutil.copy2(filepath, backup_path)
    return backup_path

def migrate_v0_to_v2(data, sys_log=None):
    """
    Migrates raw dictionary of profiles to schema v2 envelope.
    Handles legacy 'role' strings and sets up ABAC + is_admin.
    """
    new_data = {}
    migrated_count = 0
    for token_hash, profile in data.items():
        if token_hash == 'metadata' or token_hash == 'data':
            continue # skip if somehow it already had envelope keys but version 0
            
        migrated_profile = {
            "username": profile.get("username", "Unknown"),
            "label": profile.get("label", profile.get("role", "Guest")),
            "uuid": profile.get("uuid", str(uuid.uuid4())),
            "require_click_only": profile.get("require_click_only", False),
            "is_admin": profile.get("is_admin", False),
            "permissions": profile.get("permissions", [])
        }
        
        # Legacy role conversion if 'role' existed
        old_role = profile.get("role")
        if old_role:
            if old_role == 'admin':
                migrated_profile['is_admin'] = True
            elif old_role == 'cert-viewer':
                if 'master:view_certs' not in migrated_profile['permissions']:
                    migrated_profile['permissions'].append('master:view_certs')
            elif old_role == 'blog-viewer':
                if 'master:view_blogs' not in migrated_profile['permissions']:
                    migrated_profile['permissions'].append('master:view_blogs')
                
        # If they had the old 'system:admin' permission string
        if 'system:admin' in migrated_profile['permissions']:
            migrated_profile['is_admin'] = True
            migrated_profile['permissions'].remove('system:admin')
            
        new_data[token_hash] = migrated_profile
        migrated_count += 1
        
    envelope = {
        "metadata": {
            "schema_version": TARGET_SCHEMA_VERSION,
            "last_migrated": datetime.now().isoformat()
        },
        "data": new_data
    }
    
    if sys_log and migrated_count > 0:
        sys_log.info(f"[MIGRATION] Converted {migrated_count} profiles to v{TARGET_SCHEMA_VERSION}.")
        
    return envelope

def verify_and_migrate_profiles(filepath: Path, sys_log=None):
    if not filepath.exists():
        # Return empty envelope
        return {
            "metadata": {"schema_version": TARGET_SCHEMA_VERSION},
            "data": {}
        }
        
    try:
        content = json.loads(filepath.read_text(encoding='utf-8'))
    except Exception as e:
        if sys_log: sys_log.error(f"Failed to read JSON: {e}")
        return {"metadata": {"schema_version": TARGET_SCHEMA_VERSION}, "data": {}}
        
    current_version = content.get('metadata', {}).get('schema_version', 0)
    
    if current_version == TARGET_SCHEMA_VERSION:
        return content
        
    # Migration needed
    backup_path = create_backup(filepath)
    if sys_log and backup_path: 
        sys_log.info(f"[MIGRATION_START] Backup created at backups/{backup_path.name}")
    
    if current_version == 0:
        # It's the old raw dictionary or missing metadata
        raw_data = content.get('data', content) if isinstance(content, dict) else content
        if not isinstance(raw_data, dict):
            raw_data = {}
            
        new_content = migrate_v0_to_v2(raw_data, sys_log)
    else:
        # Future migration steps would go here
        new_content = content
        
    # Save the migrated content back
    filepath.write_text(json.dumps(new_content, indent=4), encoding='utf-8')
    if sys_log: sys_log.info(f"[MIGRATION_COMPLETE] Successfully upgraded to Schema v{TARGET_SCHEMA_VERSION}.")
    
    return new_content
