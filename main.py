import os
import sys
import subprocess
import re
import argparse
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
import questionary
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings import named_commands


# Reconfigure stdout/stderr to use UTF-8 to avoid UnicodeEncodeErrors on legacy Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.status import Status
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.align import Align

# Initialize Rich Console
console = Console()

# Persistent state
cwd = os.getcwd()
auto_approve = False
OPENROUTER_MODEL = "openai/gpt-oss-120b:free"

# Regex to find cd commands
cd_pattern = re.compile(r'(?:^|&&|;)\s*cd\s+("[^"]+"|\'[^\']+\'|[^\s&;]+)', re.IGNORECASE)

class PathMentionCompleter(Completer):
    """Custom completer that suggests file/folder paths when typing after '@'."""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Find the last '@' token
        last_at_idx = text.rfind('@')
        if last_at_idx == -1:
            return
            
        # Check if there is space between the last '@' and the cursor (not typing the mention anymore)
        if ' ' in text[last_at_idx:]:
            return
            
        # The path query being typed
        query = text[last_at_idx + 1:]
        
        # Normalize slashes for cross-platform compatibility
        normalized_query = query.replace('\\', '/')
        
        # Separate directory part and current typing prefix
        if '/' in normalized_query:
            dir_part, file_prefix = normalized_query.rsplit('/', 1)
        else:
            dir_part, file_prefix = "", normalized_query
            
        global cwd
        # Resolve target directory based on current working directory
        target_dir = os.path.abspath(os.path.join(cwd, dir_part))
        
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            return
            
        try:
            # List contents
            for name in os.listdir(target_dir):
                # Skip hidden files or python caches to avoid noise
                if name.startswith('.') and not file_prefix.startswith('.'):
                    continue
                if name == '__pycache__':
                    continue
                    
                if name.lower().startswith(file_prefix.lower()):
                    full_path = os.path.join(target_dir, name)
                    is_dir = os.path.isdir(full_path)
                    
                    display_name = name + '/' if is_dir else name
                    completion_text = display_name
                    
                    yield Completion(
                        completion_text,
                        start_position=-len(file_prefix),
                        display=display_name
                    )
        except Exception:
            pass

def clean_mention_path(raw_path: str, cwd: str) -> str:
    """Cleans trailing punctuation from path matches by checking if the path exists."""
    full_path = os.path.abspath(os.path.join(cwd, raw_path))
    if os.path.exists(full_path):
        return raw_path
        
    cleaned = raw_path
    while cleaned and cleaned[-1] in '.,?!;:)]}':
        cleaned = cleaned[:-1]
        temp_path = os.path.abspath(os.path.join(cwd, cleaned))
        if os.path.exists(temp_path):
            return cleaned
            
    return raw_path

def parse_mentions(prompt: str, cwd: str) -> list[str]:
    """Parses @ mentions from the prompt supporting quoted and unquoted paths."""
    pattern = r'(?:^|\s)@(?:(?:"([^"]+)")|(?:\'([^\']+)\')|([^\s\x00-\x1F\x7F-\x9F]+))'
    matches = re.finditer(pattern, prompt)
    mentions = []
    for m in matches:
        raw_path = m.group(1) or m.group(2) or m.group(3)
        if raw_path:
            # Only clean punctuation if it's not quoted
            if not m.group(1) and not m.group(2):
                raw_path = clean_mention_path(raw_path, cwd)
            mentions.append(raw_path)
    return mentions

def get_file_content_context(filepath: str, cwd: str) -> str:
    """Reads the content of a text-based file or returns description of binary/large files."""
    try:
        size = os.path.getsize(filepath)
        rel_path = os.path.relpath(filepath, cwd)
        
        if size > 1024 * 1024:  # 1MB limit
            return f"### File: `{rel_path}`\n[File is too large to attach ({size} bytes)]"
            
        # Check if binary
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return f"### File: `{rel_path}`\n[Binary file ({size} bytes)]"
                
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        ext = os.path.splitext(filepath)[1].lower().strip('.')
        lang = ext if ext else "text"
        
        return f"### File: `{rel_path}`\n```{lang}\n{content}\n```"
    except Exception as e:
        rel_path = os.path.relpath(filepath, cwd)
        return f"### File: `{rel_path}`\n[Error reading file: {str(e)}]"

def get_folder_content_context(folderpath: str, cwd: str) -> str:
    """Lists files and directories recursively up to depth 2 (ignores git, venv, pycache, node_modules)."""
    try:
        rel_path = os.path.relpath(folderpath, cwd)
        if rel_path == '.':
            rel_path = os.path.basename(folderpath) or folderpath
        lines = [f"### Directory Structure: `{rel_path}/`"]
        
        limit = 100
        count = 0
        
        def walk_dir(path, current_depth, max_depth=2):
            nonlocal count
            if current_depth > max_depth or count >= limit:
                return
                
            try:
                entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            except Exception as e:
                lines.append("  " * current_depth + f"- [Error reading: {str(e)}]")
                return
                
            for entry in entries:
                if count >= limit:
                    break
                    
                indent = "  " * current_depth
                if entry.is_dir():
                    if entry.name in ('.git', '.venv', '__pycache__', 'node_modules'):
                        continue
                    lines.append(f"{indent}- {entry.name}/")
                    count += 1
                    walk_dir(entry.path, current_depth + 1, max_depth)
                else:
                    lines.append(f"{indent}- {entry.name}")
                    count += 1
                    
        walk_dir(folderpath, 1)
        
        if count >= limit:
            lines.append("  - ... (listing truncated, too many items)")
            
        return "\n".join(lines)
    except Exception as e:
        rel_path = os.path.relpath(folderpath, cwd)
        return f"### Directory: `{rel_path}/`\n[Error listing directory: {str(e)}]"

def process_prompt_mentions(prompt: str, cwd: str) -> str:
    """Parses and attaches file/folder mentions context to the user prompt."""
    mentions = parse_mentions(prompt, cwd)
    if not mentions:
        return prompt
        
    attachments_context = []
    
    for mention in mentions:
        full_path = os.path.abspath(os.path.join(cwd, mention))
        if not os.path.exists(full_path):
            console.print(f"[yellow]⚠️ Mentioned path '@{mention}' not found relative to current directory.[/yellow]")
            continue
            
        if os.path.isdir(full_path):
            console.print(f"[green]📁 Attached directory @{mention}[/green]")
            context = get_folder_content_context(full_path, cwd)
            attachments_context.append(context)
        elif os.path.isfile(full_path):
            console.print(f"[green]📎 Attached file @{mention}[/green]")
            context = get_file_content_context(full_path, cwd)
            attachments_context.append(context)
            
    if not attachments_context:
        return prompt
        
    context_block = "\n\n---\n### Attached Context:\n" + "\n\n".join(attachments_context)
    return prompt + context_block

def safe_decode(bytes_data: bytes) -> str:
    """Decodes bytes safely by trying multiple encodings."""
    for encoding in ('utf-8', 'cp1252', 'cp850', 'ansi'):
        try:
            return bytes_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes_data.decode('utf-8', errors='replace')

def update_cwd_from_command(command: str):
    """Updates the tracking cwd variable if the command contains cd/drive changes."""
    global cwd
    command_clean = command.strip()
    
    # Handle Windows drive changes, e.g. D:
    if re.match(r'^[a-zA-Z]:$', command_clean):
        drive = command_clean.upper()
        if os.path.exists(drive + "\\"):
            cwd = drive + "\\"
            return
            
    # Find all cd matches
    matches = cd_pattern.findall(command)
    for match in matches:
        target = match.strip()
        if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
            target = target[1:-1]
        try:
            new_path = os.path.abspath(os.path.join(cwd, target))
            if os.path.exists(new_path) and os.path.isdir(new_path):
                cwd = new_path
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
    global cwd, auto_approve
    
    # 1. Print Proposed Command Panel
    console.print()
    console.print(Panel(
        Syntax(command, "bash", theme="monokai", line_numbers=False),
        title="[bold yellow]⚠️ Proposed Terminal Command[/bold yellow]",
        subtitle=f"[dim]CWD: {cwd}[/dim]",
        border_style="yellow",
        expand=False
    ))
    
    # 2. Get User Confirmation
    needs_confirmation = not auto_approve
    if needs_confirmation and not is_destructive_command(command):
        needs_confirmation = False
        
    if needs_confirmation:
        confirmed = Confirm.ask(
            "[bold red]⚠️ Destructive operation detected! Do you want to execute this command?[/bold red]",
            default=False
        )
    else:
        if auto_approve:
            console.print("[yellow]Auto-approving command execution (auto_approve mode)...[/yellow]")
        else:
            console.print("[yellow]Auto-approving non-destructive command execution...[/yellow]")
        confirmed = True
        
    if not confirmed:
        console.print("[red]❌ Execution denied by user.[/red]")
        return f"Error: User refused to execute this command: {command}. Suggest an alternative or ask the user for clarification."
        
    # 3. Execute Command
    console.print("[bold green]⏳ Running command...[/bold green]")
    
    # Update our tracking cwd if the command changes directories
    update_cwd_from_command(command)
    
    # Detect interactive commands that may require user input
    interactive_commands = ('date', 'time', 'pause', 'set /p', 'choice', 'more', 'edit', 'nslookup', 'diskpart', 'format', 'chkdsk')
    cmd_lower = command.strip().lower()
    is_interactive = any(cmd_lower == ic or cmd_lower.startswith(ic + ' ') or cmd_lower.startswith(ic + '\n') for ic in interactive_commands)
    
    try:
        if is_interactive:
            # Interactive mode: run with real-time stdin/stdout so user can type input
            console.print("[dim]ℹ️ Interactive command detected — type your input below (or press Ctrl+C to cancel).[/dim]")
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=os.environ.copy()
                )
                process.wait(timeout=120)
                exit_code = process.returncode
            except KeyboardInterrupt:
                process.kill()
                console.print("\n[yellow]⚠️ Command cancelled by user (Ctrl+C).[/yellow]")
                return "Command cancelled by user."
            except subprocess.TimeoutExpired:
                process.kill()
                console.print("[red]❌ Interactive command timed out after 120 seconds.[/red]")
                return "Error: Interactive command timed out after 120 seconds."
            
            status_text = "[green]Success (0)[/green]" if exit_code == 0 else f"[red]Failed ({exit_code})[/red]"
            border_color = "green" if exit_code == 0 else "red"
            console.print(Panel(
                "[italic dim]Interactive command finished.[/italic dim]",
                title=f"[bold {border_color}]📋 Command Output ({status_text})[/bold {border_color}]",
                border_style=border_color,
                expand=False
            ))
            return f"Exit Code: {exit_code}\nInteractive command completed."
        else:
            # Non-interactive mode: capture stdout/stderr via pipes
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                env=os.environ.copy()
            )
            
            stdout_str = safe_decode(result.stdout)
            stderr_str = safe_decode(result.stderr)
            exit_code = result.returncode
            
            # 4. Display Output Panel
            status_text = "[green]Success (0)[/green]" if exit_code == 0 else f"[red]Failed ({exit_code})[/red]"
            border_color = "green" if exit_code == 0 else "red"
            
            output_content = []
            if stdout_str.strip():
                output_content.append(f"[bold]Standard Output:[/bold]\n{stdout_str.strip()}")
            if stderr_str.strip():
                output_content.append(f"[bold red]Standard Error:[/bold]\n{stderr_str.strip()}")
            if not stdout_str.strip() and not stderr_str.strip():
                output_content.append("[italic dim]No output received.[/italic dim]")
                
            console.print(Panel(
                "\n\n".join(output_content),
                title=f"[bold {border_color}]📋 Command Output ({status_text})[/bold {border_color}]",
                border_style=border_color,
                expand=False
            ))
            
            return f"Exit Code: {exit_code}\n\nSTDOUT:\n{stdout_str}\n\nSTDERR:\n{stderr_str}"
        
    except subprocess.TimeoutExpired:
        console.print("[red]❌ Command timed out after 60 seconds.[/red]")
        return f"Error: Command timed out after 60 seconds."
    except Exception as e:
        console.print(f"[red]❌ Error running command: {str(e)}[/red]")
        return f"Error running command: {str(e)}"

def read_text_file(filename: str) -> str:
    """
    Reads the content of a text-based file (like .txt, .md, .py, .toml, etc.) in the project directory.
    
    Args:
        filename: The name or path of the file to read (relative to the current working directory).
    """
    global cwd
    
    try:
        # Resolve full path relative to tracking cwd
        filepath = os.path.abspath(os.path.join(cwd, filename))
        
        # Verify extension is a text file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.csv', '.gitignore')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be read using this tool."
            
        if not os.path.exists(filepath):
            return f"Error: File '{filename}' not found in current directory '{cwd}'."
            
        if os.path.isdir(filepath):
            return f"Error: '{filename}' is a directory, not a file."
            
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        # Display feedback in console
        console.print(f"\n[bold cyan]📖 Reading file: {filename}[/bold cyan]")
        return content
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"

def write_text_file(filename: str, content: str) -> str:
    """
    Creates or overwrites a text-based file (like .txt, .csv, .md, .py, etc.) in the project directory.
    
    Args:
        filename: The name or path of the file to create/write (relative to the current working directory).
        content: The text content to write into the file.
    """
    global cwd, auto_approve
    
    try:
        # Resolve full path relative to tracking cwd
        filepath = os.path.abspath(os.path.join(cwd, filename))
        
        # Verify extension is a text-based file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.gitignore')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be created using this tool."
            
        # 1. Print Proposed File Creation Panel
        console.print()
        # Preview content (limit to first 10 lines for neat display)
        content_lines = content.splitlines()
        preview = "\n".join(content_lines[:10])
        if len(content_lines) > 10:
            preview += f"\n... and {len(content_lines) - 10} more lines ..."
            
        console.print(Panel(
            Syntax(preview, ext[1:] if ext[1:] else "text", theme="monokai", line_numbers=True),
            title=f"[bold yellow]📝 Proposed File Creation: {filename}[/bold yellow]",
            subtitle=f"[dim]CWD: {cwd}[/dim]",
            border_style="yellow",
            expand=False
        ))
        
        # 2. Get User Confirmation
        # Since writing/creating a file is not a deletion, it is non-destructive and auto-approved.
        console.print(f"[yellow]Auto-approving file write (non-destructive): {filename}[/yellow]")
        confirmed = True
            
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        console.print(f"[green]✓ Successfully wrote file: {filename}[/green]")
        return f"Success: File '{filename}' was successfully created/written."
        
    except Exception as e:
        console.print(f"[red]❌ Error creating file: {str(e)}[/red]")
        return f"Error creating file '{filename}': {str(e)}"

def edit_text_file(filename: str, find_str: str = None, replace_str: str = None, line_number: int = None, content: str = None) -> str:
    """
    Edits a text-based file in the project directory by finding and replacing a text block, 
    replacing a specific line, or appending content.
    
    Args:
        filename: The name or path of the file to edit (relative to current working directory).
        find_str: The exact text block to search for.
        replace_str: The replacement text for find_str.
        line_number: The 1-indexed line number to replace.
        content: The text content to write/replace/append.
    """
    global cwd
    
    try:
        # Resolve full path relative to tracking cwd
        filepath = os.path.abspath(os.path.join(cwd, filename))
        
        # Verify extension is a text-based file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.gitignore')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be edited using this tool."
            
        if not os.path.exists(filepath):
            return f"Error: File '{filename}' not found in current directory '{cwd}'."
            
        if os.path.isdir(filepath):
            return f"Error: '{filename}' is a directory, not a file."
            
        # 1. Print Proposed File Edit Panel
        console.print()
        edit_desc = ""
        if find_str is not None:
            edit_desc = f"Search and replace in '{filename}':\n[bold yellow]Find:[/bold yellow]\n{find_str}\n\n[bold green]Replace:[/bold green]\n{replace_str if replace_str else ''}"
        elif line_number is not None:
            edit_desc = f"Replace line {line_number} in '{filename}' with:\n{content}"
        elif content is not None:
            edit_desc = f"Append to '{filename}':\n{content}"
        else:
            return "Error: You must provide either find_str, line_number, or content to perform an edit."
            
        console.print(Panel(
            edit_desc,
            title=f"[bold yellow]📝 Proposed File Edit: {filename}[/bold yellow]",
            subtitle=f"[dim]CWD: {cwd}[/dim]",
            border_style="yellow",
            expand=False
        ))
        
        # 2. Auto-approve since it's non-destructive
        console.print(f"[yellow]Auto-approving file edit (non-destructive): {filename}[/yellow]")
        
        # Read current content
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            file_content = "".join(lines)
            
        if find_str is not None:
            if find_str not in file_content:
                return f"Error: The target text to find was not found in '{filename}'."
            new_content = file_content.replace(find_str, replace_str if replace_str is not None else "")
        elif line_number is not None:
            idx = line_number - 1
            if idx < 0 or idx >= len(lines):
                return f"Error: Line number {line_number} is out of bounds (total lines in file: {len(lines)})."
            lines[idx] = content + ('\n' if not content.endswith('\n') else '')
            new_content = "".join(lines)
        else:
            new_content = file_content + content
            
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        console.print(f"[green]✓ Successfully edited file: {filename}[/green]")
        return f"Success: File '{filename}' was successfully edited."
        
    except Exception as e:
        console.print(f"[red]❌ Error editing file: {str(e)}[/red]")
        return f"Error editing file '{filename}': {str(e)}"

# Available functions for the agent loop mapping
available_functions = {
    "execute_terminal_command": execute_terminal_command,
    "read_text_file": read_text_file,
    "write_text_file": write_text_file,
    "edit_text_file": edit_text_file,
}

# OpenAI/OpenRouter compatible tools schema definition
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "execute_terminal_command",
            "description": "Executes a terminal command on the user's local system and returns its stdout and stderr. The command will run in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The terminal command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "Reads the content of a text-based file (like .txt, .md, .py, .toml, etc.) in the project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name or path of the file to read (relative to the current working directory)."
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_text_file",
            "description": "Creates or overwrites a text-based file (like .txt, .csv, .md, .py, etc.) in the project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name or path of the file to create/write (relative to the current working directory)."
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to write into the file."
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_text_file",
            "description": "Edits an existing text-based file in the project directory by finding and replacing a text block, replacing a specific line, or appending content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name or path of the file to edit (relative to the current working directory)."
                    },
                    "find_str": {
                        "type": "string",
                        "description": "The exact text block to search for and replace."
                    },
                    "replace_str": {
                        "type": "string",
                        "description": "The replacement text for find_str."
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "The 1-indexed line number to replace."
                    },
                    "content": {
                        "type": "string",
                        "description": "New line content (required when using line_number) or content to append."
                    }
                },
                "required": ["filename"]
            }
        }
    }
]

def run_agent_turn(client: OpenAI, messages: list):
    """Executes a single agent turn, handling potential recursive tool calling loops."""
    while True:
        try:
            # Call OpenRouter API with a nice spinner
            with Status(f"[bold blue]🤖 AI is thinking ({OPENROUTER_MODEL})...[/bold blue]", console=console, spinner="dots"):
                max_tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", "4096"))
                response = client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=messages,
                    tools=tools_schema,
                    tool_choice="auto",
                    max_tokens=max_tokens,
                    extra_headers={
                        "HTTP-Referer": "https://github.com/google-gemini/terminal-ai",
                        "X-Title": "TerminalAI",
                    }
                )
                
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # If no tool calls requested, we print the final output and end the turn
            if not tool_calls:
                # Add response to messages list
                messages.append({"role": "assistant", "content": response_message.content})
                if response_message.content:
                    console.print()
                    console.print(Panel(
                        Markdown(response_message.content),
                        title="[bold green]🤖 TerminalAI[/bold green]",
                        border_style="green",
                        expand=False
                    ))
                break
                
            # If tool calls are requested, append assistant tool call message to history
            # Convert ChatCompletionMessage to a dict to prevent serialization issues
            assistant_msg = {
                "role": "assistant",
                "content": response_message.content,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)
            
            # Loop and execute tool calls
            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                
                if fn_name in available_functions:
                    fn_to_call = available_functions[fn_name]
                    tool_output = fn_to_call(**fn_args)
                else:
                    tool_output = f"Error: Tool '{fn_name}' not found."
                    
                # Append tool response message to history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": tool_output,
                })
                
        except Exception as e:
            console.print(f"[red]Error during API transaction: {str(e)}[/red]")
            break
def select_model_interactive() -> str:
    """Helper function to let the user select a model using arrow keys."""
    choices = [
        "openai/gpt-oss-120b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "deepseek/deepseek-v4-flash:free",
        "minimax/minimax-m2.5:free",
        "baidu/cobuddy:free",
        "google/gemma-4-31b-it:free",
    ]
    
    selected = questionary.select(
        "Select OpenRouter Model (Use arrow keys):",
        choices=choices,
        default="openai/gpt-oss-120b:free"
    ).ask()
    
    # If user pressed Ctrl+C or exited questionary, select defaults safely
    if not selected:
        console.print("[yellow]No model selected. Defaulting to openai/gpt-oss-120b:free.[/yellow]")
        selected = "openai/gpt-oss-120b:free"
        
    model_choice = selected
        
    # Ask to save model to .env
    save_model = Confirm.ask(f"Would you like to save model choice '{model_choice}' to your .env file?", default=True)
    if save_model:
        # First remove existing OPENROUTER_MODEL lines from .env to avoid duplicates
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                lines = f.readlines()
            with open(".env", "w") as f:
                for line in lines:
                    if not line.strip().startswith("OPENROUTER_MODEL="):
                        f.write(line)
        # Append new choice
        with open(".env", "a") as f:
            f.write(f"\nOPENROUTER_MODEL={model_choice}\n")
        console.print(f"[green]Saved model choice to .env file.[/green]")
        
    return model_choice

def main():
    parser = argparse.ArgumentParser(description="Terminal AI Agent - A command line assistant using OpenRouter.")
    parser.add_argument("prompt", nargs="*", help="Initial prompt/command for the AI agent.")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-approve all terminal commands and file writes.")
    args = parser.parse_args()
    
    global auto_approve, OPENROUTER_MODEL
    auto_approve = args.yes
    
    # Load environment variables from .env
    load_dotenv()
    
    # Print welcome banner
    console.print()
    console.print(Align.center(Panel(
        Text("⚡ TERMINAL AI AGENT (OpenRouter) ⚡\n[dim]A smart assistant with command execution capabilities[/dim]", justify="center", style="bold cyan"),
        border_style="cyan",
        expand=False
    )))
    
    # Check for API Key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[yellow]⚠️ OPENROUTER_API_KEY environment variable not found.[/yellow]")
        api_key = Prompt.ask("[bold white]Please enter your OpenRouter API Key[/bold white]", password=True)
        if not api_key.strip():
            console.print("[red]Error: API Key is required to run the agent.[/red]")
            sys.exit(1)
            
        save = Confirm.ask("Would you like to save this key to a .env file?", default=True)
        if save:
            with open(".env", "a") as f:
                f.write(f"\nOPENROUTER_API_KEY={api_key}\n")
            console.print("[green]Saved API key to .env file.[/green]")
            
        os.environ["OPENROUTER_API_KEY"] = api_key

    # Check for Model
    env_model = os.environ.get("OPENROUTER_MODEL")
    if env_model:
        OPENROUTER_MODEL = env_model
    else:
        OPENROUTER_MODEL = select_model_interactive()
                
    # Initialize OpenAI Client pointed to OpenRouter
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    except Exception as e:
        console.print(f"[red]Error initializing OpenAI Client: {str(e)}[/red]")
        sys.exit(1)
        
    # Configure system instruction
    system_instruction = (
        "You are TerminalAI, an advanced agentic coding and system administration assistant.\n"
        "You have direct access to the user's terminal through the `execute_terminal_command` tool, "
        "and direct file system access through `read_text_file`, `write_text_file`, and `edit_text_file`.\n"
        "Your goal is to help the user with their requests by executing appropriate commands and operations.\n\n"
        "Always follow these guidelines:\n"
        "1. Be concise and professional in your explanations.\n"
        "2. When the user asks you to do something, break it down into steps, explain your plan, "
        "and run the necessary tools. You can run multiple tools sequentially to accomplish a task.\n"
        "3. If a tool fails (e.g. exit code is non-zero), inspect the error output, explain the issue, and try a corrected tool call.\n"
        "4. Keep track of files and directories. Since you can read and write files, you can create, modify, "
        "and run programs.\n"
        "5. Never execute destructive commands (like deleting system files) without explaining it clearly first.\n"
        "6. Do not run interactive commands that require terminal input (such as raw `python`, `git commit` without `-m`, "
        "or entering passwords) because stdin is not attached. Instead, run commands with non-interactive flags "
        "or write scripts to files and run them.\n"
        "7. You can read text-based files (.txt, .md, .py, .toml, etc.) in the project directory using the `read_text_file` tool. "
        "Prefer using this tool over terminal commands (like cat or type) when you just need to inspect file contents.\n"
        "8. You can create or overwrite text-based files (.txt, .csv, .md, .py, etc.) in the project directory using the `write_text_file` tool. "
        "Prefer using this tool over terminal redirection (like echo > file) when creating or writing files.\n"
        "9. You can edit text-based files using the `edit_text_file` tool. Prefer using this tool for making targeted changes to existing files instead of rewriting them completely with `write_text_file`.\n"
        "10. The command-line tool `db-cli` is available on this system. When you need to access, inspect, query, or modify a database, "
        "you MUST use ONLY the `db-cli --skill` command inside `execute_terminal_command`. Do not use any other database tool, connection command, or custom script for database operations."
    )
    
    # Initialize message list
    messages = [
        {"role": "system", "content": system_instruction}
    ]
    
    # Check if a single-shot prompt was provided via command line arguments
    initial_prompt = " ".join(args.prompt).strip()
    if initial_prompt:
        processed_prompt = process_prompt_mentions(initial_prompt, cwd)
        messages.append({"role": "user", "content": processed_prompt})
        console.print(f"\n[bold cyan]👤 Task:[/bold cyan] {initial_prompt}")
        run_agent_turn(client, messages)
    else:
        # Run in interactive REPL mode
        console.print("\n[green]Welcome to TerminalAI! Type your instruction below (or 'exit' / 'quit' to exit).[/green]")
        console.print(f"[bold cyan]Selected Model: {OPENROUTER_MODEL}[/bold cyan]")
        if auto_approve:
            console.print("[bold red]⚠️ Auto-approve mode is ENABLED. Commands/Writes will run without confirmation.[/bold red]")
        else:
            console.print("[dim]Note: You will be prompted to approve destructive terminal commands (deleting files, folders, or databases).[/dim]")
            
        kb = KeyBindings()

        @kb.add('enter')
        def _enter_key(event):
            buff = event.current_buffer
            if buff.complete_state:
                current = buff.complete_state.current_completion
                if current:
                    buff.apply_completion(current)
                    buff.complete_state = None
                else:
                    completions = buff.complete_state.completions
                    if completions:
                        buff.apply_completion(completions[0])
                        buff.complete_state = None
                    else:
                        named_commands.accept_line(event)
            else:
                named_commands.accept_line(event)

        while True:
            try:
                # Use prompt_toolkit for interactive autocomplete
                user_input = pt_prompt(
                    HTML('\n<b><cyan>👤 You</cyan></b> > '),
                    completer=PathMentionCompleter(),
                    complete_while_typing=True,
                    key_bindings=kb,
                    style=PtStyle.from_dict({
                        'completion-menu.completion': 'bg:#2c2c2c #ffffff',
                        'completion-menu.completion.current': 'bg:#007acc #ffffff',
                    })
                )
                
                # Check for exit commands
                if user_input.strip().lower() in ("exit", "quit"):
                    console.print("[green]👋 Goodbye![/green]")
                    for i in range(5, 0, -1):
                        console.print(f"[dim]Closing in {i}...[/dim]", end="\r")
                        time.sleep(1)
                    break
                    
                # Check for /model slash command
                if user_input.strip().lower() == "/model":
                    OPENROUTER_MODEL = select_model_interactive()
                    console.print(f"[bold cyan]🔄 Switched Model to: {OPENROUTER_MODEL}[/bold cyan]")
                    continue
                    
                # Check for /clear slash command
                if user_input.strip().lower() == "/clear":
                    console.clear()
                    messages = [
                        {"role": "system", "content": system_instruction}
                    ]
                    console.print("\n[green]Welcome to TerminalAI! Chat context has been reset.[/green]")
                    console.print(f"[bold cyan]Active Model: {OPENROUTER_MODEL}[/bold cyan]")
                    if auto_approve:
                        console.print("[bold red]⚠️ Auto-approve mode is ENABLED. Commands/Writes will run without confirmation.[/bold red]")
                    else:
                        console.print("[dim]Note: You will be prompted to approve destructive terminal commands (deleting files, folders, or databases).[/dim]")
                    continue
                    
                if not user_input.strip():
                    continue
                    
                processed_input = process_prompt_mentions(user_input, cwd)
                messages.append({"role": "user", "content": processed_input})
                run_agent_turn(client, messages)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[green]👋 Goodbye![/green]")
                for i in range(5, 0, -1):
                    console.print(f"[dim]Closing in {i}...[/dim]", end="\r")
                    time.sleep(1)
                break
            except Exception as e:
                console.print(f"[red]Error in chat loop: {str(e)}[/red]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[green]👋 Goodbye![/green]")
        for i in range(5, 0, -1):
            console.print(f"[dim]Closing in {i}...[/dim]", end="\r")
            time.sleep(1)
        try:
            sys.exit(0)
        except SystemExit:
            import os
            os._exit(0)
