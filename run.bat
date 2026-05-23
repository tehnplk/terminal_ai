@echo off
title Tenz-AI Launcher
echo Opening Tenz-AI in a new window...
start powershell -NoExit -Command "Clear-Host; uv run python -u main.py"
