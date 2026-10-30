import os
from security.raugus_resolver import resolver

class ProjectManager:
    """
    Manages workspace project directories and active project tracking.
    """
    EXCLUDED_DIRS = {
        'venv', '__pycache__', 'templates', 'static', 'sandbox',
        'node_modules', 'site-packages', 'Cryptodome', 'pyzipper',
        'Zip-Files', 'Offline_Crack_Lab', 'Online_Brute_Lab'
    }
    DEFAULT_PROJECTS = ('game_demo', 'npc_quest')

    def __init__(self, base_dir=None):
        if not base_dir:
            devcore_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            base_dir = os.path.join(devcore_root, "playground")
            os.makedirs(base_dir, exist_ok=True)
            
        self.base_dir = base_dir
        self.active_project = None
        self._ensure_default_projects()

    def _ensure_default_projects(self):
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            for proj in self.DEFAULT_PROJECTS:
                os.makedirs(os.path.join(self.base_dir, proj), exist_ok=True)
        except Exception as e:
            print(f"[ProjectManager] Error ensuring default projects: {e}")

    def _is_valid_project_dir(self, entry: str, full_path: str) -> bool:
        if not os.path.isdir(full_path):
            return False
        if entry.startswith('.'):
            return False
        if entry in self.EXCLUDED_DIRS:
            return False
        if entry.endswith('.dist-info') or entry.endswith('.egg-info'):
            return False
        return True

    def reinit(self):
        """Re-initializes project manager state."""
        devcore_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = os.path.join(devcore_root, "playground")
        self._ensure_default_projects()
        if self.active_project:
            full_p = os.path.join(self.base_dir, self.active_project)
            if not self._is_valid_project_dir(self.active_project, full_p):
                self.active_project = None

    def list_projects(self, user=None):
        projects = []
        if os.path.exists(self.base_dir):
            try:
                for entry in os.listdir(self.base_dir):
                    full_path = os.path.join(self.base_dir, entry)
                    if self._is_valid_project_dir(entry, full_path):
                        projects.append(entry)
            except Exception as e:
                print(f"[ProjectManager] Error listing projects: {e}")
        projects = sorted(projects)
        if user and user.get("role") not in ("admin", "super_admin", "super admin", "Tier5_SysAdmin"):
            allowed = user.get("allowed_projects", [])
            if "*" not in allowed:
                projects = [p for p in projects if p in allowed]
        return projects

    def create_project(self, name):
        if not name or '..' in name or '/' in name or '\\' in name:
            raise ValueError("Invalid project name")
        if name in self.EXCLUDED_DIRS or name.startswith('.') or name.endswith(('.dist-info', '.egg-info')):
            raise ValueError("Reserved directory name cannot be used as a project")
        
        project_dir = os.path.join(self.base_dir, name)
        
        resolver.enforce_path_security(project_dir, user_tier=1)
        
        if os.path.exists(project_dir):
            raise FileExistsError("Project already exists")
        
        os.makedirs(project_dir, exist_ok=True)
        return project_dir

    def set_active_project(self, name):
        if not name:
            self.active_project = None
            return self.base_dir
        
        if '..' in name or '/' in name or '\\' in name:
            raise ValueError("Invalid project name")
        
        project_dir = os.path.join(self.base_dir, name)
        
        resolver.enforce_path_security(project_dir, user_tier=1)
        
        if not self._is_valid_project_dir(name, project_dir):
            raise FileNotFoundError(f"Project directory '{name}' does not exist")
        
        self.active_project = name
        return project_dir

    def get_active_workspace_path(self):
        if self.active_project:
            p = os.path.join(self.base_dir, self.active_project)
            if self._is_valid_project_dir(self.active_project, p):
                return p
            self.active_project = None
        return self.base_dir
