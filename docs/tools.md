# Tool Registry

This document lists the tool set exposed to the agent loop. The source of truth is `tools.tools_schema` in `tools/__init__.py`, with callable implementations registered in `tools.available_functions`.

## Tools

### `execute_terminal_command`

Executes a terminal command on the user's local system and returns stdout and stderr. The command runs in the current working directory tracked by the runtime.

Required parameters:
- `command` (`string`): The terminal command to run.

### `read_text_file`

Reads a text-based file from the project workspace. Supports reading specific line ranges for large files.

Required parameters:
- `filename` (`string`): File name or path relative to the current working directory.

Optional parameters:
- `start_line` (`integer`): 1-indexed start line, inclusive.
- `end_line` (`integer`): 1-indexed end line, inclusive.

### `grep`

Searches file and folder names, text file contents, or both. Supports absolute paths outside the current working directory and limits output with `max_results`.

Required parameters:
- `query` (`string`): Text to search for.

Optional parameters:
- `path` (`string`): Directory or file path to search. Supports absolute paths outside the current working directory. Defaults to the current working directory.
- `mode` (`string`): Search mode, one of `content`, `names`, or `both`. Defaults to `both`.
- `case_sensitive` (`boolean`): Whether matching should be case-sensitive. Defaults to `false`.
- `max_results` (`integer`): Maximum number of matches to return. Defaults to `100`.

### `write_text_file`

Creates or overwrites a text-based file in the project workspace.

Required parameters:
- `filename` (`string`): File name or path relative to the current working directory.
- `content` (`string`): Text content to write.

### `edit_text_file`

Edits an existing text-based file by find-and-replace, replacing a specific line, or appending content.

Required parameters:
- `filename` (`string`): File name or path relative to the current working directory.

Optional parameters:
- `find_str` (`string`): Exact text block to search for and replace.
- `replace_str` (`string`): Replacement text for `find_str`.
- `line_number` (`integer`): 1-indexed line number to replace.
- `content` (`string`): New line content for `line_number`, or content to append.

### `web_search`

Searches the web with DuckDuckGo and returns result titles, URLs, and snippets.

Required parameters:
- `query` (`string`): Search query string.

### `web_fetch`

Fetches clean, readable text content from a URL.

Required parameters:
- `url` (`string`): URL to fetch.

### `web_browser_open`

Opens a URL in a Playwright browser session and returns a structured page snapshot.

Required parameters:
- `url` (`string`): URL to open.

### `web_browser_action`

Performs an interactive action in the active browser session and returns an updated page snapshot.

Required parameters:
- `action` (`string`): Action type, such as `click`, `fill`, `type`, `press`, `select`, `hover`, `reload`, `go-back`, or `go-forward`.

Optional parameters:
- `target` (`string`): Element reference, such as `e1`, `e2`, or a key name such as `Enter`.
- `text` (`string`): Text input value, required for `fill` and `type`.

### `web_browser_close`

Closes the active browser session.

Parameters: none.

### `create_docx_file`

Creates a Microsoft Word `.docx` document containing headings, paragraphs, lists, and tables.

Required parameters:
- `filename` (`string`): Output file name or path relative to the current working directory, such as `report.docx`.
- `content` (`array`): List of content blocks to add to the document.

Content block fields:
- `type` (`string`, required): One of `heading`, `paragraph`, `list_bullet`, `list_number`, or `table`.
- `text` (`string`, optional): Text content for headings, paragraphs, and list items.
- `level` (`integer`, optional): Heading level used when `type` is `heading`.
- `table_data` (`array`, optional): 2D array of table cells used when `type` is `table`.

### `create_xlsx_file`

Creates a Microsoft Excel `.xlsx` workbook with one or more sheets of tabular data.

Required parameters:
- `filename` (`string`): Output file name or path relative to the current working directory, such as `sales.xlsx`.
- `sheets` (`object`): Mapping of sheet names to 2D arrays of cell values.

### `create_html_file`

Creates or overwrites an HTML file containing HTML markup.

Required parameters:
- `filename` (`string`): Output file name or path relative to the current working directory, ending in `.html` or `.htm`.
- `html_content` (`string`): Complete HTML markup to write.

### `generate_image`

Generates an image from a text prompt using the OpenAI Images API and saves it as an image file in the artifact directory. Requires `OPENAI_API_KEY`.

Required parameters:
- `prompt` (`string`): Text prompt describing the image to generate.

Optional parameters:
- `filename` (`string`): Output image file name or path relative to the current working directory. Defaults to a timestamped `.png` file.
- `model` (`string`): OpenAI image model name. Defaults to `gpt-image-2`.
- `size` (`string`): Image size supported by the selected model, such as `1024x1024`.

### `current_location`

Returns the user's approximate current location based on public IP geolocation. This is not GPS-level precision and may reflect a VPN, proxy, or ISP endpoint.

Parameters: none.

### `get_current_date_time`

Returns the current date and time in the Asia/Bangkok timezone, UTC+7.

Parameters: none.
