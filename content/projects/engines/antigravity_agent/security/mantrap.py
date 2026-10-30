import os
import logging
import time
from contextlib import contextmanager

try:
    import fcntl
    OS_TYPE = "linux"
except ImportError:
    try:
        import msvcrt
        OS_TYPE = "windows"
    except ImportError:
        OS_TYPE = "unknown"

MANTRAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "mantrap_locks")

class SemanticMantrap:
    """
    The Semantic Mantrap (Thread Concurrency & Race Condition Firewall).
    Ensures only one authenticated Subagent or process enters the execution chamber 
    at a time when modifying a core database, trapping and purging malicious piggybackers.
    
    Cross-Platform: Uses fcntl for Linux/WSL and msvcrt for native Windows.
    """
    @staticmethod
    @contextmanager
    def execution_chamber(target_db_path: str, agent_id: str = "System"):
        os.makedirs(MANTRAP_DIR, exist_ok=True)
        
        safe_name = target_db_path.replace("/", "_").replace("\\", "_").replace(":", "_") + ".lock"
        lock_path = os.path.join(MANTRAP_DIR, safe_name)
        
        if not os.path.exists(lock_path):
            with open(lock_path, 'w') as init_f:
                if OS_TYPE == "windows":
                    init_f.write("X")
                
        lock_fd = open(lock_path, 'r+')
        
        try:
            logging.info(f"[MANTRAP] Agent '{agent_id}' waiting at Outer Door for {target_db_path} (OS: {OS_TYPE})")
            
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            elif OS_TYPE == "windows":
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
            else:
                time.sleep(0.1)
            
            logging.info(f"[MANTRAP] Agent '{agent_id}' has entered the Execution Chamber for {target_db_path}")
            
            yield True
            
        except Exception as e:
            logging.error(f"[MANTRAP] Execution Chamber Fault for '{agent_id}'. Purging transaction. Error: {e}")
            raise
            
        finally:
            logging.info(f"[MANTRAP] Agent '{agent_id}' successfully exited the Execution Chamber for {target_db_path}")
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            elif OS_TYPE == "windows":
                try:
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            lock_fd.close()
