# This module is part of the tools package split from tools/__init__.py.

import os
import subprocess

from rich.markup import escape

from . import runtime
from . import web_cli


def get_latest_snapshot_content() -> str:
    """Reads the latest .yml snapshot file in .playwright-cli/ and returns its content."""
    dir_path = os.path.join(os.getcwd(), ".playwright-cli")
    if not os.path.exists(dir_path):
        return "Error: No snapshot directory found. You may need to open a page first."
    try:
        files = [f for f in os.listdir(dir_path) if f.startswith("page-") and f.endswith(".yml")]
        if not files:
            return "Error: No snapshots found. The page might not have loaded successfully."
        # Sort alphabetically (chronological by timestamp)
        latest_file = sorted(files)[-1]
        filepath = os.path.join(dir_path, latest_file)
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return f"### Current Page Snapshot ({latest_file}):\n\n```yaml\n{content}\n```"
    except Exception as e:
        return f"Error reading latest snapshot: {str(e)}"


def web_search(query: str) -> str:
    """
    Searches the web using DuckDuckGo via the packaged web_cli helper.
    
    Args:
        query: The search query.
    """
    runtime.console.print(f"\n[bold yellow]🔍 Web Search:[/bold yellow] {escape(query)}")
    try:
        return web_cli.search_web(query)
    except Exception as e:
        return f"Error running search: {str(e)}"


def web_fetch(url: str) -> str:
    """
    Fetches the clean text content of a web page using the packaged web_cli helper.
    
    Args:
        url: The web page URL.
    """
    runtime.console.print(f"\n[bold yellow]🌐 Web Fetch:[/bold yellow] {escape(url)}")
    try:
        return web_cli.fetch_web(url)
    except Exception as e:
        return f"Error running fetch: {str(e)}"


def web_browser_open(url: str) -> str:
    """
    Opens a URL in a browser session using playwright-cli.
    
    Args:
        url: The URL to open.
    """
    runtime.console.print(f"\n[bold yellow]🖥️ Opening Browser:[/bold yellow] {escape(url)}")
    try:
        result = subprocess.run(
            ["playwright-cli", "open", url],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            cwd=runtime.cwd
        )
        if result.returncode != 0:
            return f"Failed to open browser (Exit Code {result.returncode}):\n{result.stderr}\n{result.stdout}"
        return get_latest_snapshot_content()
    except Exception as e:
        return f"Error opening browser: {str(e)}"


def web_browser_action(action: str, target: str = None, text: str = None) -> str:
    """
    Executes an action in the active browser session.
    
    Args:
        action: The action type (e.g. click, fill, type, press, select, hover, reload, go-back, go-forward).
        target: Optional element reference (e.g., e1, e2) or key name (e.g., Enter).
        text: Optional text input value (e.g. for fill/type).
    """
    runtime.console.print(f"\n[bold yellow]🖥️ Browser Action:[/bold yellow] {action} target={target} text={text}")
    cmd_args = ["playwright-cli", action]
    if target is not None:
        cmd_args.append(target)
    if text is not None:
        cmd_args.append(text)
    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            cwd=runtime.cwd
        )
        if result.returncode != 0:
            return f"Action failed (Exit Code {result.returncode}):\n{result.stderr}\n{result.stdout}"
        return get_latest_snapshot_content()
    except Exception as e:
        return f"Error performing browser action: {str(e)}"


def web_browser_close() -> str:
    """Closes the active browser session."""
    runtime.console.print("\n[bold yellow]🖥️ Closing Browser[/bold yellow]")
    try:
        result = subprocess.run(
            ["playwright-cli", "close"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            cwd=runtime.cwd
        )
        if result.returncode != 0:
            return f"Failed to close browser (Exit Code {result.returncode}):\n{result.stderr}"
        return "Success: Browser session closed successfully."
    except Exception as e:
        return f"Error closing browser: {str(e)}"

