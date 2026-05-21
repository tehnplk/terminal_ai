@echo off
title Terminal AI Agent Launcher
echo Opening Terminal AI Agent in a new window...
start powershell -NoExit -Command "Clear-Host; uv run python -u main.py"
