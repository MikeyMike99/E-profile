with open("content/projects/engines/antigravity_agent/agent_manager.py", "r") as f:
    content = f.read()

# 1. Pipe stdin
content = content.replace("stdout=asyncio.subprocess.PIPE,", "stdin=asyncio.subprocess.PIPE,\n                stdout=asyncio.subprocess.PIPE,")

# 2. Add send_input method
send_input_code = """
    async def send_input(self, text: str):
        if self.active_proc and self.active_proc.stdin:
            self.active_proc.stdin.write((text + "\\n").encode('utf-8'))
            await self.active_proc.stdin.drain()
"""
content = content.replace("async def cancel_task(self):", send_input_code + "\n    async def cancel_task(self):")

with open("content/projects/engines/antigravity_agent/agent_manager.py", "w") as f:
    f.write(content)
