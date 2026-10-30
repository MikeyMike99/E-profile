# ==============================================================================
# ZERO-TRUST AI AGENT CONTAINER
# ==============================================================================
FROM python:3.11-slim

# Install necessary system utilities (cron, shred)
RUN apt-get update && apt-get install -y cron coreutils zip fcrackzip && rm -rf /var/lib/apt/lists/*

# Create a restricted non-root user (RBAC Enforcement)
RUN useradd --create-home --shell /bin/bash agentuser

WORKDIR /app

# Copy dependency requirements and install
# (Assuming a requirements.txt exists; if not, we install Quart & websockets)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt quart websockets marked

# Copy the server source code
COPY . /app

# Setup the Reaper Daemon script
RUN echo '#!/bin/bash\nfind /app/.agent_scratch -type f -mmin +10 -exec shred -u -z {} \\;' > /app/reaper_daemon.sh && chmod +x /app/reaper_daemon.sh

# Register the Reaper in the system cron for root (to ensure it can always wipe)
RUN echo "*/5 * * * * /app/reaper_daemon.sh >> /var/log/reaper.log 2>&1" | crontab -

# Secure the main source code (Read-Only for the agent user)
RUN chown -R root:root /app && chmod -R 755 /app

# Ensure the scratch directory exists and is owned by the agent
RUN mkdir -p /app/.agent_scratch && chown agentuser:agentuser /app/.agent_scratch

# Switch to the restricted user to run the application
USER agentuser

EXPOSE 5000

# Start both cron (as root if needed, but here we just start the server)
# Note: For production, a supervisor should manage cron + quart. 
# For this dockerfile, we just boot the Quart server.
CMD ["python", "server.py"]
