import sys
import os
import argparse
import urllib.request
import urllib.parse
import json
import subprocess
from html.parser import HTMLParser

# Reconfigure stdout/stderr to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = None
        self.in_title_link = False
        self.in_snippet = False
        self.snippet_tag = None

    @staticmethod
    def has_class(attrs_dict, class_name):
        classes = attrs_dict.get("class", "")
        return class_name in classes.split()

    def finish_current_result(self):
        if self.current_result and self.current_result["title"]:
            self.current_result["title"] = " ".join(self.current_result["title"].split())
            self.current_result["snippet"] = " ".join(self.current_result["snippet"].split())
            self.results.append(self.current_result)
        self.current_result = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and self.has_class(attrs_dict, "result__a"):
            self.finish_current_result()
            self.current_result = {
                "title": "",
                "url": normalize_duckduckgo_url(attrs_dict.get("href", "")),
                "snippet": "",
            }
            self.in_title_link = True
        elif self.current_result and self.has_class(attrs_dict, "result__snippet"):
            self.in_snippet = True
            self.snippet_tag = tag

    def handle_endtag(self, tag):
        if self.in_title_link and tag == "a":
            self.in_title_link = False
        if self.in_snippet and tag == self.snippet_tag:
            self.in_snippet = False
            self.snippet_tag = None

    def handle_data(self, data):
        if not self.current_result:
            return
        if self.in_title_link:
            self.current_result["title"] += data
        elif self.in_snippet:
            self.current_result["snippet"] += data

    def close(self):
        super().close()
        self.finish_current_result()


def normalize_duckduckgo_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.path.startswith("/l/"):
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return urllib.parse.unquote(query["uddg"][0])
    return url


def format_duckduckgo_results(html):
    parser = DuckDuckGoParser()
    parser.feed(html)
    parser.close()

    if not parser.results:
        return "No results found."

    output = []
    for i, res in enumerate(parser.results, 1):
        output.append(f"{i}. Title: {res['title']}")
        output.append(f"   URL: {res['url']}")
        output.append(f"   Snippet: {res['snippet']}")
        output.append("-" * 40)
    return "\n".join(output)


# Parser for pure-python fetch fallback
class WebTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.ignored_tags = {"script", "style", "nav", "header", "footer", "form", "head", "meta", "link", "noscript", "svg", "aside"}
        self.current_path = []
        
    def handle_starttag(self, tag, attrs):
        void_elements = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
        if tag not in void_elements:
            self.current_path.append(tag)
            
        if tag in ["p", "div", "li", "tr"]:
            self.text_parts.append("\n")
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self.text_parts.append("\n\n")
        elif tag == "br":
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.current_path:
            while self.current_path and self.current_path[-1] != tag:
                self.current_path.pop()
            if self.current_path:
                self.current_path.pop()
                
        if tag in ["p", "div", "li", "tr"]:
            self.text_parts.append("\n")
        elif tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self.text_parts.append("\n\n")

    def handle_data(self, data):
        if any(ignored in self.current_path for ignored in self.ignored_tags):
            return
        text = data.strip()
        if text:
            if self.text_parts and not self.text_parts[-1].endswith("\n") and not self.text_parts[-1].endswith(" "):
                if data and (data[0].isspace() or data[-1].isspace()):
                    self.text_parts.append(" ")
            self.text_parts.append(text)


def search_with_urllib(query):
    return search_with_duckduckgo(query)


def search_with_duckduckgo(query):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8', errors='replace')
        return format_duckduckgo_results(html)


def get_playwright_config_path():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(exe_dir, "playwright_config.json")
    
    if not os.path.exists(config_path):
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "browser": {
                        "contextOptions": {
                            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                    }
                }, f, indent=2)
        except Exception:
            pass
    return config_path


def search_with_playwright(query):
    session = "search_session"
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    config_path = get_playwright_config_path()
    try:
        # Open in headless mode with config file
        subprocess.run(["playwright-cli", f"-s={session}", "open", f"--config={config_path}", url], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True)
        
        # Check if blocked
        res = subprocess.run(["playwright-cli", f"-s={session}", "eval", "document.body.innerText", "--json"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True)
        stdout = res.stdout
        start = stdout.find('{')
        end = stdout.rfind('}')
        is_blocked = False
        if start != -1 and end != -1:
            json_str = stdout[start:end+1]
            data = json.loads(json_str)
            inner_text = data.get("result", "")
            if isinstance(inner_text, str):
                if inner_text.startswith('"') and inner_text.endswith('"'):
                    inner_text = json.loads(inner_text)
                if "403 - Forbidden" in inner_text or "automated queries" in inner_text or "unusual traffic" in inner_text or "bots use" in inner_text:
                    is_blocked = True
        else:
            is_blocked = True
            
        if is_blocked:
            raise Exception("Access blocked by search engine (detected as automation/bot).")
            
        # Extract search results from DuckDuckGo's static HTML layout.
        js_code = (
            "Array.from(document.querySelectorAll('a.result__a')).map(function(a){"
            "var container=a.closest('.result');"
            "var p=container?container.querySelector('.result__snippet'):null;"
            "var href=a.getAttribute('href')||a.href||'';"
            "try{"
            "var u=new URL(href,location.href);"
            "var uddg=u.searchParams.get('uddg');"
            "href=uddg?decodeURIComponent(uddg):u.href;"
            "}catch(e){}"
            "return {title:a.innerText||'',url:href,snippet:p?p.innerText:''};"
            "})"
        )
        cmd = f'playwright-cli -s={session} eval "{js_code}" --json'
        res = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True
        )
        
        # Close browser
        subprocess.run(["playwright-cli", f"-s={session}", "close"], capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
        
        stdout = res.stdout
        start = stdout.find('{')
        end = stdout.rfind('}')
        if start != -1 and end != -1:
            json_str = stdout[start:end+1]
            data = json.loads(json_str)
            results = data.get("result", [])
            if isinstance(results, str) and results.startswith("[") and results.endswith("]"):
                results = json.loads(results)
                
            if isinstance(results, list) and results:
                output = []
                for i, res_item in enumerate(results, 1):
                    title = res_item.get('title', '').strip()
                    url_val = res_item.get('url', '').strip()
                    snippet = res_item.get('snippet', '').strip()
                    if title and url_val:
                        output.append(f"{i}. Title: {title}")
                        output.append(f"   URL: {url_val}")
                        output.append(f"   Snippet: {snippet}")
                        output.append("-" * 40)
                if output:
                    return "\n".join(output)
                    
        raise Exception("No search results returned or parsed successfully.")
    except Exception as e:
        subprocess.run(["playwright-cli", f"-s={session}", "close"], capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
        raise e


def search_web(query):
    last_error = None

    # Try DuckDuckGo first because it works without an API key and has a static HTML endpoint.
    try:
        results = search_with_duckduckgo(query)
        if results and results.strip() and results.strip() != "No results found.":
            return results
    except Exception as e:
        last_error = e

    # Fallback to playwright-cli search.
    try:
        results = search_with_playwright(query)
        if results and results.strip():
            return results
    except Exception as e:
        last_error = e

    if last_error:
        return f"Error performing web search: {str(last_error)}"
    return "No results found."


def fetch_with_playwright(url):
    config_path = get_playwright_config_path()
    try:
        # Open URL with config
        subprocess.run(["playwright-cli", "open", f"--config={config_path}", url], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True)
        
        # Eval innerText with --json
        res = subprocess.run(["playwright-cli", "eval", "document.body.innerText", "--json"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True)
        
        # Close browser
        subprocess.run(["playwright-cli", "close"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True)
        
        stdout = res.stdout
        start = stdout.find('{')
        end = stdout.rfind('}')
        if start != -1 and end != -1:
            json_str = stdout[start:end+1]
            data = json.loads(json_str)
            inner_text = data.get("result", "")
            
            if isinstance(inner_text, str) and inner_text.startswith('"') and inner_text.endswith('"'):
                inner_text = json.loads(inner_text)
                
            return inner_text
        else:
            raise Exception("JSON block not found in playwright-cli output.")
            
    except Exception as e:
        # Ensure browser is closed on error
        subprocess.run(["playwright-cli", "close"], capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
        raise e


def fetch_with_urllib(url):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8', errors='replace')
        parser = WebTextParser()
        parser.feed(html)
        text = "".join(parser.text_parts)
        
        # Clean formatting
        lines = []
        for line in text.split("\n"):
            line_stripped = line.strip()
            if line_stripped:
                lines.append(line_stripped)
            else:
                if lines and lines[-1] != "":
                    lines.append("")
        return "\n".join(lines).strip()


def fetch_web(url):
    # Try urllib first for high performance
    try:
        text = fetch_with_urllib(url)
        # Check if we got substantial content (not a tiny block/stub page)
        if len(text.strip()) > 300:
            return text
    except Exception as e:
        pass

    # Fallback to playwright-cli
    try:
        text = fetch_with_playwright(url)
        if text.strip():
            return text
    except Exception as e:
        pass

    # Final fallback attempt with urllib
    try:
        return fetch_with_urllib(url)
    except Exception as e:
        return f"Error fetching page content: {str(e)}"


def main():
    parser = argparse.ArgumentParser(description="CLI tool to search and fetch internet web pages.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search the web using DuckDuckGo")
    search_parser.add_argument("query", help="The query string to search for")
    
    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch clean text content from a URL")
    fetch_parser.add_argument("url", help="The URL to fetch")
    
    args = parser.parse_args()
    
    if args.command == "search":
        try:
            results = search_web(args.query)
            print(results)
        except Exception as e:
            print(f"Error during search: {str(e)}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "fetch":
        try:
            text = fetch_web(args.url)
            print(text)
        except Exception as e:
            print(f"Error fetching URL: {str(e)}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
