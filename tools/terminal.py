# This module is part of the tools package split from tools/__init__.py.

import os
import re
import subprocess

from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from . import runtime


def update_cwd_from_command(command: str):
    """Updates the tracking runtime.cwd variable if the command contains cd/drive changes."""
    command_clean = command.strip()
    
    # Handle Windows drive changes, e.g. D:
    if re.match(r'^[a-zA-Z]:$', command_clean):
        drive = command_clean.upper()
        if os.path.exists(drive + "\\"):
            runtime.cwd = drive + "\\"
            return
            
    # Find all cd matches
    matches = runtime.cd_pattern.findall(command)
    for match in matches:
        target = match.strip()
        if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
            target = target[1:-1]
        try:
            new_path = os.path.abspath(os.path.join(runtime.cwd, target))
            if os.path.exists(new_path) and os.path.isdir(new_path):
                runtime.cwd = new_path
        except Exception:
            pass


def is_destructive_command(command: str) -> bool:
    """Checks if a command appears to perform a destructive action (deleting files, folders, or databases)."""
    cmd_lower = command.lower()
    
    # Destructive patterns matching keywords that delete files, folders, or database entities
    destructive_patterns = [
        r'\brm\b',
        r'\bdel\b',
        r'\berase\b',
        r'\brmdir\b',
        r'\brd\b',
        r'\bremove-item\b',
        r'\bunlink\b',
        r'\bdrop\b',
        r'\bdelete\b',
        r'\btruncate\b',
        r'\bshred\b',
        r'\bwipe\b',
        r'\bclean\b',
        r'\bpurge\b',
        r'\bdestroy\b',
    ]
    
    for pattern in destructive_patterns:
        if re.search(pattern, cmd_lower):
            return True
            
    return False


def execute_terminal_command(command: str) -> str:
    """
    Executes a terminal command on the user's local system and returns its stdout and stderr.
    The command will run in the current working directory.
    
    Args:
        command: The terminal command to run.
    """
    
    # 1. Print Proposed Command Panel
    runtime.console.print()
    runtime.console.print(Panel(
        Syntax(command, "bash", theme="monokai", line_numbers=False),
        title="[bold yellow]⚠️ Proposed Terminal Command[/bold yellow]",
        subtitle=f"[dim]CWD: {escape(runtime.cwd)}[/dim]",
        border_style="yellow",
        expand=False
    ))
    
    # 2. Get User Confirmation
    needs_confirmation = not runtime.auto_approve
    if needs_confirmation and not is_destructive_command(command):
        needs_confirmation = False
        
    if needs_confirmation:
        confirmed = Confirm.ask(
            "[bold red]⚠️ Destructive operation detected! Do you want to execute this command?[/bold red]",
            default=False
        )
    else:
        if runtime.auto_approve:
            runtime.console.print("[yellow]Auto-approving command execution (runtime.auto_approve mode)...[/yellow]")
        else:
            runtime.console.print("[yellow]Auto-approving non-destructive command execution...[/yellow]")
        confirmed = True
        
    if not confirmed:
        runtime.console.print("[red]❌ Execution denied by user.[/red]")
        return f"Error: User refused to execute this command: {command}. Suggest an alternative or ask the user for clarification."
        
    # 3. Execute Command
    runtime.console.print("[bold green]⏳ Running command...[/bold green]")
    
    # Update our tracking runtime.cwd if the command changes directories
    update_cwd_from_command(command)
    
    # Detect interactive commands that may require user input
    interactive_commands = ('date', 'time', 'pause', 'set /p', 'choice', 'more', 'edit', 'nslookup', 'diskpart', 'format', 'chkdsk')
    cmd_lower = command.strip().lower()
    is_interactive = any(cmd_lower == ic or cmd_lower.startswith(ic + ' ') or cmd_lower.startswith(ic + '\n') for ic in interactive_commands)
    
    try:
        if is_interactive:
            # Interactive mode: run with real-time stdin/stdout so user can type input
            runtime.console.print("[dim]ℹ️ Interactive command detected — type your input below (or press Ctrl+C to cancel).[/dim]")
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=runtime.cwd,
                    env=os.environ.copy()
                )
                process.wait(timeout=120)
                exit_code = process.returncode
            except KeyboardInterrupt:
                process.kill()
                raise KeyboardInterrupt
            except subprocess.TimeoutExpired:
                process.kill()
                runtime.console.print("[red]❌ Interactive command timed out after 120 seconds.[/red]")
                return "Error: Interactive command timed out after 120 seconds."
            
            status_text = "[green]Success (0)[/green]" if exit_code == 0 else f"[red]Failed ({exit_code})[/red]"
            border_color = "green" if exit_code == 0 else "red"
            runtime.console.print(Panel(
                "[italic dim]Interactive command finished.[/italic dim]",
                title=f"[bold {border_color}]📋 Command Output ({status_text})[/]",
                border_style=border_color,
                expand=False
            ))
            return f"Exit Code: {exit_code}\nInteractive command completed."
        else:
            # Non-interactive mode: capture stdout/stderr via pipes
            # Run using Popen to allow proper interruption handling
            process = None
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=runtime.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=os.environ.copy()
                )
                stdout_bytes, stderr_bytes = process.communicate(timeout=60)
                stdout_str = runtime.safe_decode(stdout_bytes)
                stderr_str = runtime.safe_decode(stderr_bytes)
                exit_code = process.returncode
            except KeyboardInterrupt:
                if process:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    try:
                        process.kill()
                    except Exception:
                        pass
                raise KeyboardInterrupt
            except subprocess.TimeoutExpired:
                if process:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    try:
                        process.kill()
                    except Exception:
                        pass
                runtime.console.print("[red]❌ Command timed out after 60 seconds.[/red]")
                return "Error: Command timed out after 60 seconds."
            
            # 4. Display Output Panel
            status_text = "[green]Success (0)[/green]" if exit_code == 0 else f"[red]Failed ({exit_code})[/red]"
            border_color = "green" if exit_code == 0 else "red"
            
            output_content = []
            if stdout_str.strip():
                output_content.append(f"[bold]Standard Output:[/bold]\n{escape(stdout_str.strip())}")
            if stderr_str.strip():
                output_content.append(f"[bold red]Standard Error:[/bold red]\n{escape(stderr_str.strip())}")
            if not stdout_str.strip() and not stderr_str.strip():
                output_content.append("[italic dim]No output received.[/italic dim]")
                
            runtime.console.print(Panel(
                "\n\n".join(output_content),
                title=f"[bold {border_color}]📋 Command Output ({status_text})[/]",
                border_style=border_color,
                expand=False
            ))
            
            return f"Exit Code: {exit_code}\n\nSTDOUT:\n{stdout_str}\n\nSTDERR:\n{stderr_str}"
        
    except Exception as e:
        runtime.console.print(f"[red]❌ Error running command: {escape(str(e))}[/red]")
        return f"Error running command: {str(e)}"

