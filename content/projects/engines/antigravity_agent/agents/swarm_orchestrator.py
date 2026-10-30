import os
import sys
import asyncio
import json
import shutil
import subprocess

class SwarmOrchestrator:
    def __init__(self, broadcast_callback=None):
        self.broadcast = broadcast_callback
        
    async def _send_status(self, msg: str):
        if self.broadcast:
            await self.broadcast({
                "type": "system",
                "level": "info",
                "message": f"🤖 [Swarm Orchestrator] {msg}"
            })
            
    async def _process_chunk(self, chunk_text: str, index: int, base_dir: str, agy_path: str, is_admin: bool):
        temp_path = os.path.join(base_dir, f"chunk_temp_{index}.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(chunk_text)
            
        cmd = []
        if sys.platform == "win32" and not agy_path.endswith(".exe"):
            cmd.extend(["wsl.exe", "-e"])
            
        is_pa = "PYTHONANYWHERE_DOMAIN" in os.environ or "PYTHONANYWHERE_SITE" in os.environ or os.path.exists("/var/www")
        cmd.extend([
            agy_path,
            "--dangerously-skip-permissions" if (is_admin or is_pa) else "--sandbox",
            "--model", "gemini-3.8-flash-low",
            "--print", f"SYSTEM TASK: Read the chunk provided in `{temp_path}`. Extract the core narrative milestones, key events, and crucial decisions. Discard massive code dumps and noise. Provide a highly compressed summary of what happened in this chunk."
        ])
        
        kwargs = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": base_dir,
            "limit": 1024 * 1024 * 50
        }
        if sys.platform == "win32":
            if cmd[0] != "wsl.exe":
                kwargs["creationflags"] = 0x08000000
        else:
            kwargs["start_new_session"] = True
            
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace").strip()
            final_text = ""
            for line in output.split("\n"):
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        if "step_update" in data and data["step_update"].get("step_type") == "agent_response":
                            if "text_delta" in data["step_update"]:
                                final_text += data["step_update"]["text_delta"]
                    except:
                        pass
            
            if not final_text:
                final_text = output
                
            return final_text
        except Exception as e:
            return f"[Error processing chunk {index}: {e}]"
        finally:
            try:
                os.remove(temp_path)
            except:
                pass

    async def distill_massive_file(self, file_path: str, real_agy: str, is_admin: bool) -> str:
        await self._send_status(f"Reading massive payload from {os.path.basename(file_path)}...")
        
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
            
        chunk_size = 30000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        await self._send_status(f"Partitioned into {len(chunks)} chunks. Deploying Flash Sub-Agents in parallel...")
        
        base_dir = os.path.dirname(file_path)
        
        tasks = []
        for i, chunk in enumerate(chunks):
            tasks.append(self._process_chunk(chunk, i, base_dir, real_agy, is_admin))
            
        results = await asyncio.gather(*tasks)
        
        distilled_path = file_path.replace(".txt", "_distilled.md")
        with open(distilled_path, "w", encoding="utf-8") as f:
            for i, res in enumerate(results):
                f.write(f"### Chronological Segment {i+1}\n")
                f.write(res)
                f.write("\n\n---\n\n")
                
        await self._send_status(f"Swarm distillation complete. Payload compressed by {(1 - (os.path.getsize(distilled_path) / len(text))) * 100:.1f}%. Handoff to Main Pro Agent.")
        return distilled_path
