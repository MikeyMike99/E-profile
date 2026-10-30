#!/bin/bash
docker run --rm python:3.11-slim bash -c "useradd --create-home --shell /bin/bash agentuser && id agentuser"
