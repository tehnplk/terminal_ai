# This module is part of the tools package split from tools/__init__.py.

import os

from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax

from . import runtime


def read_text_file(filename: str, start_line: int = None, end_line: int = None) -> str:
    """
    Reads the content of a text-based file (like .txt, .md, .py, .toml, etc.) in the project directory.
    Supports reading specific line ranges for large files.
    
    Args:
        filename: The name or path of the file to read (relative to the current working directory).
        start_line: The 1-indexed line number to start reading from (inclusive).
        end_line: The 1-indexed line number to stop reading at (inclusive).
    """
    
    try:
        # Resolve full path relative to tracking runtime.cwd
        filepath = runtime.resolve_filepath(filename)
        
        # Verify extension is a text file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.gitignore', '.html', '.htm')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be read using this tool."
            
        if not os.path.exists(filepath):
            return f"Error: File '{filename}' not found in current directory '{runtime.cwd}'."
            
        if os.path.isdir(filepath):
            return f"Error: '{filename}' is a directory, not a file."
            
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        
        # Handle line range selection
        if start_line is not None or end_line is not None:
            start = (start_line - 1) if start_line is not None else 0
            end = end_line if end_line is not None else total_lines
            
            # Bounds check
            start = max(0, min(start, total_lines))
            end = max(0, min(end, total_lines))
            
            if start >= end:
                return f"Error: Invalid line range {start_line}-{end_line} (total lines: {total_lines})."
                
            selected_lines = lines[start:end]
            content = "".join(selected_lines)
            runtime.console.print(f"\n[bold cyan]📖 Reading file: {escape(filename)} (lines {start+1}-{end} of {total_lines})[/bold cyan]")
            return content
            
        # If no range specified, apply a safety limit of 1000 lines
        MAX_AUTO_LINES = 1000
        if total_lines > MAX_AUTO_LINES:
            content = "".join(lines[:MAX_AUTO_LINES])
            runtime.console.print(f"\n[bold cyan]📖 Reading file: {escape(filename)} (first {MAX_AUTO_LINES} of {total_lines} lines - TRUNCATED for safety)[/bold cyan]")
            return (
                f"[TRUNCATED - Showing first {MAX_AUTO_LINES} of {total_lines} lines. "
                f"The file is too large to read fully at once. Use the 'start_line' and 'end_line' "
                f"parameters of 'read_text_file' to read specific sections of the file.]\n\n"
                f"{content}"
            )
            
        content = "".join(lines)
        # Display feedback in runtime.console
        runtime.console.print(f"\n[bold cyan]📖 Reading file: {escape(filename)}[/bold cyan]")
        return content
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"


def grep(query: str, path: str = None, mode: str = "both", case_sensitive: bool = False, max_results: int = 100) -> str:
    """
    Searches file and folder names, text file contents, or both.

    Args:
        query: The text to search for.
        path: Optional directory or file path to search. Supports paths outside the current working directory.
        mode: Search mode: content, names, or both.
        case_sensitive: Whether matching should be case-sensitive.
        max_results: Maximum number of matches to return.
    """

    if not query:
        return "Error: query is required."

    mode = (mode or "both").lower()
    if mode not in ("content", "names", "both"):
        return "Error: mode must be one of: content, names, both."

    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        return "Error: max_results must be an integer."
    if max_results < 1:
        return "Error: max_results must be at least 1."

    search_root = os.path.abspath(path if path else runtime.cwd)
    if path and not os.path.isabs(path):
        search_root = os.path.abspath(os.path.join(runtime.cwd, path))

    if not os.path.exists(search_root):
        return f"Error: Search path not found: {search_root}"

    query_cmp = query if case_sensitive else query.lower()
    skip_dirs = {".git", ".venv", "venv", "env", "node_modules", "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache"}
    text_extensions = {
        ".txt", ".csv", ".md", ".py", ".toml", ".json", ".yaml", ".yml",
        ".ini", ".cfg", ".xml", ".gitignore", ".html", ".htm", ".css",
        ".js", ".jsx", ".ts", ".tsx", ".sql", ".bat", ".ps1", ".sh",
    }
    results = []

    def matches(value: str) -> bool:
        haystack = value if case_sensitive else value.lower()
        return query_cmp in haystack

    def add_result(line: str) -> bool:
        results.append(line)
        return len(results) >= max_results

    def search_file_content(file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in text_extensions:
            return False
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_number, line in enumerate(f, start=1):
                    if matches(line):
                        snippet = line.strip()
                        if len(snippet) > 240:
                            snippet = snippet[:237] + "..."
                        if add_result(f"content | {file_path}:{line_number}: {snippet}"):
                            return True
        except (OSError, UnicodeError):
            return False
        return False

    runtime.console.print(f"\n[bold cyan]Searching:[/bold cyan] {escape(query)} [dim]in {escape(search_root)}[/dim]")

    if os.path.isfile(search_root):
        if mode in ("names", "both") and matches(os.path.basename(search_root)):
            add_result(f"name | file | {search_root}")
        if len(results) < max_results and mode in ("content", "both"):
            search_file_content(search_root)
    else:
        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            if mode in ("names", "both"):
                for dirname in dirs:
                    full_path = os.path.join(root, dirname)
                    if matches(dirname) and add_result(f"name | folder | {full_path}"):
                        break
                if len(results) >= max_results:
                    break

                for filename in files:
                    full_path = os.path.join(root, filename)
                    if matches(filename) and add_result(f"name | file | {full_path}"):
                        break
                if len(results) >= max_results:
                    break

            if mode in ("content", "both"):
                for filename in files:
                    if search_file_content(os.path.join(root, filename)):
                        break
                if len(results) >= max_results:
                    break

    if not results:
        return f"No matches found for '{query}' in '{search_root}'."

    truncated_note = "\n[Results limited by max_results.]" if len(results) >= max_results else ""
    return "\n".join(results) + truncated_note


def write_text_file(filename: str, content: str) -> str:
    """
    Creates or overwrites a text-based file (like .txt, .csv, .md, .py, etc.) in the project directory.
    
    Args:
        filename: The name or path of the file to create/write (relative to the current working directory).
        content: The text content to write into the file.
    """
    
    try:
        # Resolve full path relative to tracking runtime.cwd
        filepath = runtime.resolve_filepath(filename)
        
        # Verify extension is a text-based file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.gitignore', '.html', '.htm')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be created using this tool."
            
        # 1. Print Proposed File Creation Panel
        runtime.console.print()
        # Preview content (limit to first 10 lines for neat display)
        content_lines = content.splitlines()
        preview = "\n".join(content_lines[:10])
        if len(content_lines) > 10:
            preview += f"\n... and {len(content_lines) - 10} more lines ..."
            
        runtime.console.print(Panel(
            Syntax(preview, ext[1:] if ext[1:] else "text", theme="monokai", line_numbers=True),
            title=f"[bold yellow]📝 Proposed File Creation: {escape(filename)}[/bold yellow]",
            subtitle=f"[dim]CWD: {escape(runtime.cwd)}[/dim]",
            border_style="yellow",
            expand=False
        ))
        
        # 2. Get User Confirmation
        # Since writing/creating a file is not a deletion, it is non-destructive and auto-approved.
        runtime.console.print(f"[yellow]Auto-approving file write (non-destructive): {escape(filename)}[/yellow]")
        confirmed = True
            
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        runtime.console.print(f"[green]✓ Successfully wrote file: {escape(filename)}[/green]")
        return f"Success: File '{filename}' was successfully created/written."
        
    except Exception as e:
        runtime.console.print(f"[red]❌ Error creating file: {escape(str(e))}[/red]")
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
    
    try:
        # Resolve full path relative to tracking runtime.cwd
        filepath = runtime.resolve_filepath(filename)
        
        # Verify extension is a text-based file
        ext = os.path.splitext(filepath)[1].lower()
        allowed_extensions = ('.txt', '.csv', '.md', '.py', '.toml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.xml', '.gitignore', '.html', '.htm')
        if ext not in allowed_extensions:
            return f"Error: Only text-based files ({', '.join(allowed_extensions)}) can be edited using this tool."
            
        if not os.path.exists(filepath):
            return f"Error: File '{filename}' not found in current directory '{runtime.cwd}'."
            
        if os.path.isdir(filepath):
            return f"Error: '{filename}' is a directory, not a file."
            
        # 1. Print Proposed File Edit Panel
        runtime.console.print()
        edit_desc = ""
        if find_str is not None:
            edit_desc = f"Search and replace in '{escape(filename)}':\n[bold yellow]Find:[/bold yellow]\n{escape(find_str)}\n\n[bold green]Replace:[/bold green]\n{escape(replace_str if replace_str is not None else '')}"
        elif line_number is not None:
            edit_desc = f"Replace line {line_number} in '{escape(filename)}' with:\n{escape(content)}"
        elif content is not None:
            edit_desc = f"Append to '{escape(filename)}':\n{escape(content)}"
        else:
            return "Error: You must provide either find_str, line_number, or content to perform an edit."
            
        runtime.console.print(Panel(
            edit_desc,
            title=f"[bold yellow]📝 Proposed File Edit: {escape(filename)}[/bold yellow]",
            subtitle=f"[dim]CWD: {escape(runtime.cwd)}[/dim]",
            border_style="yellow",
            expand=False
        ))
        
        # 2. Auto-approve since it's non-destructive
        runtime.console.print(f"[yellow]Auto-approving file edit (non-destructive): {escape(filename)}[/yellow]")
        
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
            
        runtime.console.print(f"[green]✓ Successfully edited file: {escape(filename)}[/green]")
        return f"Success: File '{filename}' was successfully edited."
        
    except Exception as e:
        runtime.console.print(f"[red]❌ Error editing file: {escape(str(e))}[/red]")
        return f"Error editing file '{filename}': {str(e)}"

