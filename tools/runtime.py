# This module is part of the tools package split from tools/__init__.py.

import os
import sys
import re

from rich.console import Console


console = Console()
cwd = os.getcwd()
auto_approve = False

# Regex to find cd commands
cd_pattern = re.compile(r'(?:^|&&|;)\s*cd\s+("[^"]+"|\'[^\']+\'|[^\s&;]+)', re.IGNORECASE)


def configure(runtime_console=None, initial_cwd=None, approve=False):
    global console, cwd, auto_approve
    if runtime_console is not None:
        console = runtime_console
    if initial_cwd is not None:
        cwd = initial_cwd
    auto_approve = approve


def set_auto_approve(value: bool):
    global auto_approve
    auto_approve = value


def get_cwd() -> str:
    return cwd


def set_cwd(value: str):
    global cwd
    cwd = value


def get_artifact_dir() -> str:
    global cwd
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = cwd
    return os.path.join(base_dir, "artifact")


def resolve_filepath(filename: str) -> str:
    global cwd
    if os.path.isabs(filename):
        try:
            filename = os.path.relpath(filename, cwd)
        except ValueError:
            filename = os.path.basename(filename)
            
    norm = os.path.normpath(filename)
    parts = []
    for part in norm.split(os.sep):
        if part not in ("..", "", "."):
            parts.append(part)
    filename = os.sep.join(parts)
        
    return os.path.abspath(os.path.join(get_artifact_dir(), filename))


def safe_decode(bytes_data: bytes) -> str:
    """Decodes bytes safely by trying multiple encodings."""
    for encoding in ('utf-8', 'cp1252', 'cp850', 'ansi'):
        try:
            return bytes_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes_data.decode('utf-8', errors='replace')

