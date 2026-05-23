# This module is part of the tools package split from tools/__init__.py.

import json
import urllib.error
import urllib.request

from . import runtime


def current_location() -> str:
    """
    Returns the user's approximate current location based on public IP geolocation.
    This is not GPS-level precision and may reflect a VPN, proxy, or ISP endpoint.
    """
    url = "https://ipapi.co/json/"
    runtime.console.print(f"\n[bold yellow]Current Location:[/bold yellow] Checking approximate location from public IP")
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "terminal-ai/0.1"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8", errors="replace")

        data = json.loads(raw)
        if data.get("error"):
            return f"Error getting current location: {data.get('reason') or data.get('message') or 'IP geolocation lookup failed.'}"

        fields = [
            ("City", data.get("city")),
            ("Region", data.get("region")),
            ("Country", data.get("country_name")),
            ("Timezone", data.get("timezone")),
            ("Latitude", data.get("latitude")),
            ("Longitude", data.get("longitude")),
            ("IP", data.get("ip")),
        ]
        lines = [f"{label}: {value}" for label, value in fields if value not in (None, "")]
        if not lines:
            return "Error getting current location: IP geolocation response did not include location details."

        lines.append("Note: This is an approximate location from public IP, not GPS.")
        return "\n".join(lines)
    except urllib.error.URLError as e:
        return f"Error getting current location: Network request failed: {e.reason}"
    except json.JSONDecodeError:
        return "Error getting current location: Location service returned invalid JSON."
    except Exception as e:
        return f"Error getting current location: {str(e)}"

