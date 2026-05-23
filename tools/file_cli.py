import sys
import os
import argparse

def read_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(filepath):
        print(f"Error: '{filepath}' is a directory.", file=sys.stderr)
        sys.exit(1)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            print(f.read(), end='')
    except Exception as e:
        print(f"Error reading file: {str(e)}", file=sys.stderr)
        sys.exit(1)

def write_file(filepath, content):
    try:
        # Resolve path
        abspath = os.path.abspath(filepath)
        parent_dir = os.path.dirname(abspath)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(abspath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote to '{filepath}'")
    except Exception as e:
        print(f"Error writing file: {str(e)}", file=sys.stderr)
        sys.exit(1)

def append_file(filepath, content):
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully appended to '{filepath}'")
    except Exception as e:
        print(f"Error appending to file: {str(e)}", file=sys.stderr)
        sys.exit(1)

def edit_file(filepath, find_str, replace_str, line_number, content):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            file_content = "".join(lines)
            
        if find_str is not None:
            if find_str not in file_content:
                print(f"Error: Target text to find was not found in '{filepath}'", file=sys.stderr)
                sys.exit(1)
            new_content = file_content.replace(find_str, replace_str if replace_str is not None else "")
        elif line_number is not None:
            idx = line_number - 1
            if idx < 0 or idx >= len(lines):
                print(f"Error: Line number {line_number} is out of bounds for '{filepath}' (total lines: {len(lines)})", file=sys.stderr)
                sys.exit(1)
            lines[idx] = content + ('\n' if not content.endswith('\n') else '')
            new_content = "".join(lines)
        else:
            print("Error: Specify either --find or --line to edit.", file=sys.stderr)
            sys.exit(1)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully edited '{filepath}'")
    except Exception as e:
        print(f"Error editing file: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="CLI tool to read, write, and edit text-based files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Read parser
    read_parser = subparsers.add_parser("read", help="Read file contents")
    read_parser.add_argument("file", help="Path to the file to read")
    
    # Write parser
    write_parser = subparsers.add_parser("write", help="Write content to a file")
    write_parser.add_argument("file", help="Path to the file to write")
    write_parser.add_argument("content", nargs="?", default=None, help="Content to write. If omitted or '-', reads from stdin.")
    
    # Append parser
    append_parser = subparsers.add_parser("append", help="Append content to a file")
    append_parser.add_argument("file", help="Path to the file to append to")
    append_parser.add_argument("content", help="Content to append")
    
    # Edit parser
    edit_parser = subparsers.add_parser("edit", help="Edit file content (find/replace or replace specific line)")
    edit_parser.add_argument("file", help="Path to the file to edit")
    edit_parser.add_argument("--find", default=None, help="The exact text block to search for")
    edit_parser.add_argument("--replace", default=None, help="The replacement text")
    edit_parser.add_argument("--line", type=int, default=None, help="1-indexed line number to replace")
    edit_parser.add_argument("--content", default=None, help="New content for the line (required with --line)")
    
    args = parser.parse_args()
    
    if args.command == "read":
        read_file(args.file)
    elif args.command == "write":
        if args.content is None or args.content == "-":
            content = sys.stdin.read()
        else:
            content = args.content
        write_file(args.file, content)
    elif args.command == "append":
        append_file(args.file, args.content)
    elif args.command == "edit":
        if args.find is not None:
            edit_file(args.file, args.find, args.replace, None, None)
        elif args.line is not None:
            if args.content is None:
                print("Error: --content is required when using --line", file=sys.stderr)
                sys.exit(1)
            edit_file(args.file, None, None, args.line, args.content)
        else:
            print("Error: Must specify either --find or --line to edit.", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
