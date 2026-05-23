import os
import sys
import re
import argparse
import json
import time
import signal
import platform
from dotenv import load_dotenv
from openai import OpenAI
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

# Map SIGBREAK to raise KeyboardInterrupt on Windows so simulated events behave like Ctrl+C
if sys.platform == "win32":
    def sigbreak_handler(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGBREAK, sigbreak_handler)

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.status import Status
from rich.markdown import Markdown
from rich.align import Align
from rich.markup import escape

from model_choice import DEFAULT_MODEL, select_model_interactive as select_model_interactive_impl

# Initialize Rich Console
console = Console()

# Persistent state
cwd = os.getcwd()

# Tool runtime lives in tools/ so main.py can focus on UI and agent orchestration.
import tools
from tools import available_functions, tools_schema
tools.configure(runtime_console=console, initial_cwd=cwd, approve=False)

auto_approve = False
OPENROUTER_MODEL = DEFAULT_MODEL

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
            console.print(f"[yellow]⚠️ Mentioned path '@{escape(mention)}' not found relative to current directory.[/yellow]")
            continue
            
        if os.path.isdir(full_path):
            console.print(f"[green]📁 Attached directory @{escape(mention)}[/green]")
            context = get_folder_content_context(full_path, cwd)
            attachments_context.append(context)
        elif os.path.isfile(full_path):
            console.print(f"[green]📎 Attached file @{escape(mention)}[/green]")
            context = get_file_content_context(full_path, cwd)
            attachments_context.append(context)
            
    if not attachments_context:
        return prompt
        
    context_block = "\n\n---\n### Attached Context:\n" + "\n\n".join(attachments_context)
    return prompt + context_block


MAX_TOOL_MESSAGE_CHARS = 24000


def append_current_date_time_context(messages: list) -> None:
    """Adds current date/time context from the get_current_date_time tool before each agent turn."""
    try:
        current_date_time = available_functions["get_current_date_time"]()
    except Exception as e:
        current_date_time = f"Error getting current date/time: {str(e)}"
    messages.append({
        "role": "system",
        "content": (
            "Current date/time for this turn from tool `get_current_date_time`: "
            f"{current_date_time}"
        ),
    })


def limit_tool_output_for_context(tool_name: str, output: str) -> str:
    """Keeps tool responses small enough to send back through the model context."""
    if output is None:
        return ""
    if not isinstance(output, str):
        output = str(output)
    if len(output) <= MAX_TOOL_MESSAGE_CHARS:
        return output
    omitted = len(output) - MAX_TOOL_MESSAGE_CHARS
    return (
        output[:MAX_TOOL_MESSAGE_CHARS]
        + f"\n\n[TRUNCATED TOOL OUTPUT from {tool_name}: omitted {omitted} characters. "
        "Ask for a narrower query, line range, JSON field, or redirect full output to a file.]"
    )


def run_agent_turn(client: OpenAI, messages: list):
    """Executes a single agent turn, handling potential recursive tool calling loops."""
    global cwd
    initial_length = len(messages) - 1
    append_current_date_time_context(messages)
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
                        "HTTP-Referer": "https://github.com/google-gemini/tenz-ai",
                        "X-Title": "Tenz-AI",
                    }
                )
                
            if not response or not hasattr(response, 'choices') or response.choices is None or len(response.choices) == 0:
                err_msg = "API returned an empty response or no choices."
                if response and hasattr(response, 'error') and response.error:
                    err_msg = f"API Error: {response.error}"
                elif isinstance(response, dict) and "error" in response:
                    err_msg = f"API Error: {response['error']}"
                else:
                    try:
                        err_msg = f"API Response: {response}"
                    except Exception:
                        pass
                console.print(f"[red]❌ {err_msg}[/red]")
                break
                
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
                        title="[bold green]🤖 Tenz-AI[/bold green]",
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
                    tool_output = limit_tool_output_for_context(fn_name, tool_output)
                    cwd = tools.get_cwd()
                else:
                    tool_output = f"Error: Tool '{fn_name}' not found."
                    
                # Append tool response message to history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": tool_output,
                })
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Agent execution cancelled by user (Ctrl+C).[/yellow]")
            if len(messages) > initial_length:
                del messages[initial_length:]
            break
        except Exception as e:
            console.print(f"[red]Error during API transaction: {escape(str(e))}[/red]")
            break
def select_model_interactive() -> str:
    """Helper function to let the user select a model using arrow keys."""
    return select_model_interactive_impl(console, find_external_runtime_file, default_runtime_file_path)

def get_app_dir() -> str:
    """Returns the directory that owns editable runtime files."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def find_external_runtime_file(filename: str) -> str | None:
    """Finds an editable runtime file next to the app first, then in cwd."""
    candidates = [
        os.path.join(get_app_dir(), filename),
        os.path.join(os.getcwd(), filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def default_runtime_file_path(filename: str) -> str:
    """Returns where newly-created editable runtime files should be written."""
    return os.path.join(get_app_dir(), filename)

def main():
    parser = argparse.ArgumentParser(description="Tenz-AI - A command line assistant using OpenRouter.")
    parser.add_argument("prompt", nargs="*", help="Initial prompt/command for the AI agent.")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-approve all terminal commands and file writes.")
    args = parser.parse_args()
    
    global auto_approve, OPENROUTER_MODEL
    auto_approve = args.yes
    tools.set_auto_approve(auto_approve)
    tools.set_cwd(cwd)
    
    # Load editable environment variables from .env next to the app/exe first.
    env_path = find_external_runtime_file(".env")
    if env_path:
        load_dotenv(env_path)
    
    # Print welcome banner
    console.print()
    console.print(Align.center(Panel(
        Text("⚡ TENZ-AI (OpenRouter) ⚡\n[dim]A smart assistant with command execution capabilities[/dim]", justify="center", style="bold cyan"),
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
            env_path = default_runtime_file_path(".env")
            with open(env_path, "a") as f:
                f.write(f"\nOPENROUTER_API_KEY={api_key}\n")
            console.print(f"[green]Saved API key to {escape(env_path)}.[/green]")
            
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
        console.print(f"[red]Error initializing OpenAI Client: {escape(str(e))}[/red]")
        sys.exit(1)
        
    # Configure system instruction
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    shell_info = "cmd.exe" if platform.system() == "Windows" else "sh/bash"
    
    try:
        # system_prompt.md is intentionally external/editable, not bundled into the exe.
        prompt_path = find_external_runtime_file("system_prompt.md")
        if not prompt_path:
            raise FileNotFoundError(
                f"system_prompt.md not found next to app ({get_app_dir()}) or cwd ({os.getcwd()})"
            )

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        system_instruction = prompt_template.format(os_info=os_info, shell_info=shell_info)
    except Exception as e:
        console.print(f"[red]Warning: Could not load system_prompt.md: {escape(str(e))}[/red]")
        console.print("[yellow]Falling back to default built-in system prompt...[/yellow]")
        system_instruction = (
            "You are Tenz-AI, an advanced agentic coding and system administration assistant.\n"
            f"You are currently running on operating system: {os_info} (Shell: {shell_info}).\n"
            "You have direct access to the user's terminal through the `execute_terminal_command` tool, "
            "and direct file system access through `read_text_file`, `write_text_file`, and `edit_text_file`.\n"
            "Your goal is to help the user with their requests by executing appropriate commands and operations."
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
        console.print(f"\n[bold cyan]👤 Task:[/bold cyan] {escape(initial_prompt)}")
        run_agent_turn(client, messages)
    else:
        # Run in interactive REPL mode
        console.print("\n[green]Welcome to Tenz-AI! Type your instruction below (or 'exit' / 'quit' to exit).[/green]")
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
                    console.print(f"[bold cyan]🔄 Switched Model to: {escape(OPENROUTER_MODEL)}[/bold cyan]")
                    continue
                    
                # Check for /clear slash command
                if user_input.strip().lower() == "/clear":
                    console.clear()
                    messages = [
                        {"role": "system", "content": system_instruction}
                    ]
                    console.print("\n[green]Welcome to Tenz-AI! Chat context has been reset.[/green]")
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
                console.print(f"[red]Error in chat loop: {escape(str(e))}[/red]")

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
