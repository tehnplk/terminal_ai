---
name: db-cli
description: Execute SQL from command line for MySQL, PostgreSQL, and SQLite and return pipe-delimited output. Use when the user needs to run SQL quickly via `db-cli --exec`, list tables, inspect data, run write operations, or capture structured `status|message` errors without writing code.
---

# db-cli

Run SQL against MySQL, PostgreSQL, or SQLite using CLI options (no environment variables required).

## Installation

Install globally from GitHub:

```bash
npm install -g github:tehnplk/db-cli
```

Update to latest version:

```bash
npm install -g github:tehnplk/db-cli
```

If `db-cli` is not found, run with `.cmd` on Windows:

```bash
db-cli.cmd --help
```

## Run command

Short form (recommended):

```bash
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "<sql>"
```

SQLite short form:

```bash
db-cli -g sq -d <database-file> -e "<sql>"
```

Export to UTF-8 `.txt` file (pipe-delimited):

```bash
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "<sql>" -o result.txt
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "<sql>" > result.txt
```

Long form:

MySQL:

```bash
db-cli --engine mysql --host <host> --port <port> --user <user> --password <password> --database <database> --exec "<sql>"
```

PostgreSQL:

```bash
db-cli --engine postgres --host <host> --port <port> --user <user> --password <password> --database <database> --exec "<sql>"
```

SQLite:

```bash
db-cli --engine sqlite --database <database-file> --exec "<sql>"
```

Version and skill:

```bash
db-cli -v
db-cli --version
db-cli -s
db-cli --skill
```
## Options

- `-g, --engine <mysql|postgres|sqlite>` (supports `my`, `postgresql`, `pg`, `sqlite3`, `sq`; default `mysql`)
- `-H, --host <value>`
- `-P, --port <value>` (default `3306` for mysql, `5432` for postgres; ignored for sqlite)
- `-u, --user <value>` (required for mysql/postgres)
- `-p, --password <value>`
- `-d, --database, --db <value>` (database name, or SQLite database file path)
- `-e, --exec "<sql>"`
- `-o, --output <path>` (write UTF-8 text file, pipe-delimited)
- `-v, --version`
- `-s, --skill` (print `SKILL.md`)
- `-h, --help`
## Environment fallback

If options are not provided, use:

- `DB_ENGINE`
- `DB_HOST`
- `DB_PORT`
- `DB_USER` (required for mysql/postgres)
- `DB_PASSWORD`
- `DB_NAME` (database name, or SQLite database file path)

## Supported SQL operations

Supported on MySQL, PostgreSQL, and SQLite:

- `CREATE`
- `INSERT`
- `UPDATE`
- `DELETE`
- `TRUNCATE`
- `DROP`

Upsert syntax by vendor:

- MySQL: `INSERT ... ON DUPLICATE KEY UPDATE ...`
- PostgreSQL: `INSERT ... ON CONFLICT (...) DO UPDATE ...`
- SQLite: `INSERT ... ON CONFLICT (...) DO UPDATE ...`

## Output contract

Select query:

```text
col1|col2|col3
val1|val2|val3
```

Non-select query:

```text
status|affectedRows|insertId
ok|<affectedRows>|<insertId>
```

SQL/config error:

```text
status|message
error|<error message>
```

## Avoid common errors

Always choose the correct engine with `-g/--engine`. If the target is a `.db`, `.sqlite`, or `.sqlite3` file, use SQLite:

```powershell
db-cli -g sqlite -d "C:\Users\Admin\Desktop\F43.db" -e "SELECT name FROM sqlite_master WHERE type='table';"
```

For SQLite, do not pass `-H/--host`, `-P/--port`, `-u/--user`, or `-p/--password`; only `-g sqlite`, `-d <database-file>`, and `-e "<sql>"` are needed. Missing `-d/--database` causes:

```text
status|message
error|Missing database name. Use --database or DB_NAME.
```

Quote database paths on Windows because Desktop paths or project paths may contain spaces:

```powershell
db-cli -g sq -d "$env:USERPROFILE\Desktop\F43.db" -e "SELECT COUNT(*) AS total FROM PERSON;"
```

Use SQLite metadata to inspect unknown `.db` files before querying tables:

```powershell
db-cli -g sq -d "$env:USERPROFILE\Desktop\F43.db" -e "SELECT type, name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name;"
db-cli -g sq -d "$env:USERPROFILE\Desktop\F43.db" -e "PRAGMA table_info(PERSON);"
```

When building SQL dynamically in PowerShell, avoid backslash-escaped double quotes for SQLite identifiers because they may be sent literally and produce errors such as `unrecognized token`. Prefer simple table names when trusted, or bracket quoting for identifiers:

```powershell
db-cli -g sq -d "$env:USERPROFILE\Desktop\F43.db" -e "SELECT COUNT(*) AS total FROM [PERSON];"
```

Use only one `-e/--exec`. For multiple statements, put them in one SQL string separated by semicolons:

```powershell
db-cli -g sq -d "$env:TEMP\test.db" -e "CREATE TABLE t(id INTEGER); INSERT INTO t VALUES (1); SELECT * FROM t;"
```

If another script parses `db-cli` output in PowerShell, remember that `chcp 65001` can print `Active code page: 65001`. Either run `chcp 65001 | Out-Null` before parsing, set `DB_CLI_SKIP_UTF8_CONSOLE=1`, or filter that line from script output.

Terminal, redirected, and `-o/--output` output is written as UTF-8 on Windows, Linux, and macOS so Thai text remains readable. On Windows PowerShell, terminal output automatically switches the console to UTF-8; set `DB_CLI_SKIP_UTF8_CONSOLE=1` to disable that behavior. On Linux, use a UTF-8 locale such as `LANG=C.UTF-8` or `LANG=en_US.UTF-8`.

## OutputEncoding

If Thai text looks corrupted in PowerShell or redirected files, force UTF-8 before running `db-cli`:

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp 65001
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "SELECT pname, fname, lname FROM person LIMIT 10"
```

For file export, prefer `--output` because `db-cli` writes the file as UTF-8 directly:

```powershell
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "SELECT pname, fname, lname FROM person LIMIT 10" --output result.txt
Get-Content -Encoding UTF8 result.txt
```

On Linux, make sure the shell locale is UTF-8:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
db-cli -g my -H <host> -P <port> -u <user> -p <password> -d <database> -e "SELECT pname, fname, lname FROM person LIMIT 10"
```