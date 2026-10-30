#!/bin/bash
source ~/.bashrc
source ~/.venvs/devcore/bin/activate
KEY=$(grep GEMINI_API_KEY ~/.bashrc | cut -d '=' -f 2- | tr -d '"' | tr -d "'")
export GEMINI_API_KEY=$KEY
python3 core/bootstrap_gateway.py --preflight-only --no-agent
python3 core/server.py
