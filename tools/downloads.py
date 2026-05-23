# This module is part of the tools package split from tools/__init__.py.

import os
import re
import sys
import urllib.parse
import urllib.request

from rich.markup import escape
from rich.panel import Panel

from . import runtime


INVALID_FILENAME_CHARS = r'<>:"/\|?*'


def get_download_dir() -> str:
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = runtime.cwd
    return os.path.join(base_dir, "download")


def sanitize_download_filename(filename: str) -> str:
    basename = os.path.basename(filename.strip())
    basename = "".join("_" if char in INVALID_FILENAME_CHARS else char for char in basename)
    basename = re.sub(r"\s+", " ", basename).strip(" .")
    return basename or "downloaded-file"


def filename_from_content_disposition(content_disposition: str) -> str | None:
    if not content_disposition:
        return None

    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
    if match:
        return urllib.parse.unquote(match.group(1).strip().strip('"'))

    match = re.search(r'filename="?([^";]+)"?', content_disposition, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    filename = urllib.parse.unquote(os.path.basename(parsed.path))
    return filename or "downloaded-file"


def quote_download_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url

    safe_path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/%")
    safe_query = urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&?/:+,%")
    safe_fragment = urllib.parse.quote(urllib.parse.unquote(parsed.fragment), safe="")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, safe_path, safe_query, safe_fragment))


def unique_download_path(download_dir: str, filename: str) -> str:
    root, ext = os.path.splitext(filename)
    candidate = os.path.join(download_dir, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(download_dir, f"{root}-{counter}{ext}")
        counter += 1
    return candidate


def download_file(url: str, filename: str = None) -> str:
    """
    Downloads a URL to the download directory next to the current runtime workspace/app.
    """
    runtime.console.print()
    runtime.console.print(Panel(
        escape(url),
        title="[bold cyan]Download File[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))

    try:
        download_dir = get_download_dir()
        os.makedirs(download_dir, exist_ok=True)

        request_url = quote_download_url(url)
        request = urllib.request.Request(
            request_url,
            headers={
                "User-Agent": "Tenz-AI/1.0 (+https://openrouter.ai)",
            },
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            chosen_filename = filename
            if not chosen_filename:
                chosen_filename = filename_from_content_disposition(response.headers.get("Content-Disposition", ""))
            if not chosen_filename:
                chosen_filename = filename_from_url(response.geturl() or url)

            safe_filename = sanitize_download_filename(chosen_filename)
            filepath = unique_download_path(download_dir, safe_filename)

            with open(filepath, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

        size = os.path.getsize(filepath)
        runtime.console.print(f"[green]Successfully downloaded file: {escape(filepath)} ({size} bytes)[/green]")
        return f"Downloaded file to: {filepath}\nSize: {size} bytes"
    except Exception as e:
        runtime.console.print(f"[red]Error downloading file: {escape(str(e))}[/red]")
        return f"Error downloading file: {str(e)}"
