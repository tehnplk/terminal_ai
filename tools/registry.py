# This module is part of the tools package split from tools/__init__.py.

from .terminal import execute_terminal_command
from .files import read_text_file, grep, write_text_file, edit_text_file
from .web import web_search, web_fetch, web_browser_open, web_browser_action, web_browser_close
from .documents import create_docx_file, create_xlsx_file, create_html_file
from .media import generate_image
from .location import current_location
from .time_tools import get_current_time


available_functions = {
    "execute_terminal_command": execute_terminal_command,
    "read_text_file": read_text_file,
    "grep": grep,
    "write_text_file": write_text_file,
    "edit_text_file": edit_text_file,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "web_browser_open": web_browser_open,
    "web_browser_action": web_browser_action,
    "web_browser_close": web_browser_close,
    "create_docx_file": create_docx_file,
    "create_xlsx_file": create_xlsx_file,
    "create_html_file": create_html_file,
    "generate_image": generate_image,
    "current_location": current_location,
    "get_current_time": get_current_time,
}


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
            "description": "Reads the content of a text-based file (like .txt, .md, .py, .toml, etc.) in the project directory. Supports reading specific line ranges for large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name or path of the file to read (relative to the current working directory)."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "The 1-indexed line number to start reading from (inclusive)."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "The 1-indexed line number to stop reading at (inclusive)."
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
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches the web for a given query and returns search results (titles, URLs, snippets). Uses DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetches clean, readable text content from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_browser_open",
            "description": "Opens a URL in a browser session and returns the structured page snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to open."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_browser_action",
            "description": "Performs an interactive action (click, fill, type, press, select, hover, reload, go-back, go-forward) in the active browser session and returns the updated snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action type (click, fill, type, press, select, hover, reload, go-back, go-forward)."
                    },
                    "target": {
                        "type": "string",
                        "description": "Optional element reference (e.g. e1, e2) or key name (e.g. Enter)."
                    },
                    "text": {
                        "type": "string",
                        "description": "Optional text input value (required for fill/type)."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_browser_close",
            "description": "Closes the active browser session.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_docx_file",
            "description": "Creates a Microsoft Word (.docx) document containing headings, paragraphs, lists, and tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The output filename or path (relative to the current working directory, e.g., 'report.docx')."
                    },
                    "content": {
                        "type": "array",
                        "description": "A list of content blocks to add to the document.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["heading", "paragraph", "list_bullet", "list_number", "table"],
                                    "description": "The type of content block."
                                },
                                "text": {
                                    "type": "string",
                                    "description": "The text content (for headings, paragraphs, and list items)."
                                },
                                "level": {
                                    "type": "integer",
                                    "description": "The heading level (required/used only when type is 'heading', e.g., 1 for title/main heading, 2 for subheading)."
                                },
                                "table_data": {
                                    "type": "array",
                                    "description": "A 2D array representing table cells (required/used only when type is 'table').",
                                    "items": {
                                        "type": "array"
                                    }
                                }
                            },
                            "required": ["type"]
                        }
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_xlsx_file",
            "description": "Creates a Microsoft Excel (.xlsx) workbook with one or more sheets containing tabular data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The output filename or path (relative to the current working directory, e.g., 'sales.xlsx')."
                    },
                    "sheets": {
                        "type": "object",
                        "description": "A dictionary mapping sheet names to a 2D array of cell values. Example: {'Sales': [['Product', 'Price'], ['Apple', 1.50], ['Banana', 2.00]]}"
                    }
                },
                "required": ["filename", "sheets"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_html_file",
            "description": "Creates or overwrites an HTML file (.html or .htm) containing HTML markup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The output filename or path (relative to the current working directory, e.g., 'index.html')."
                    },
                    "html_content": {
                        "type": "string",
                        "description": "The complete HTML markup/content to write into the file."
                    }
                },
                "required": ["filename", "html_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Searches file and folder names, text file contents, or both. Supports absolute paths outside the current working directory and limits output with max_results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional directory or file path to search. Supports absolute paths outside the current working directory. Defaults to the current working directory."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["content", "names", "both"],
                        "description": "Search mode: content, names, or both. Defaults to both."
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether matching should be case-sensitive. Defaults to false."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matches to return. Defaults to 100."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generates an image from a text prompt using the OpenAI Images API and saves it as an image file in the artifact directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The text prompt describing the image to generate."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional output filename or path relative to the current working directory. Defaults to a timestamped .png file."
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional OpenAI image model name. Defaults to gpt-image-2."
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional image size supported by the selected model, such as 1024x1024."
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "current_location",
            "description": "Returns the user's approximate current location based on public IP geolocation. This is not GPS-level precision and may reflect a VPN, proxy, or ISP endpoint.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Returns the current date and time in the Asia/Bangkok timezone (UTC+7).",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

