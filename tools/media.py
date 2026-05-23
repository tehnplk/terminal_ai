# This module is part of the tools package split from tools/__init__.py.

import base64
import os
from datetime import datetime

from rich.markup import escape
from rich.panel import Panel

from . import runtime


def generate_image(prompt: str, filename: str = None, model: str = "gpt-image-2", size: str = None) -> str:
    """
    Generates an image from a text prompt using the OpenAI Images API and saves it to the artifact directory.

    Args:
        prompt: The image generation prompt.
        filename: Optional output filename or path relative to the current working directory. Defaults to a timestamped PNG.
        model: Optional image model name. Defaults to gpt-image-2.
        size: Optional image size supported by the selected model, such as 1024x1024.
    """
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return "Error: OPENAI_API_KEY is required to generate images."

        if not prompt or not prompt.strip():
            return "Error: prompt is required to generate an image."

        if filename is None or not filename.strip():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"generated-image-{timestamp}.png"

        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            return "Error: Output filename must end with .png, .jpg, .jpeg, or .webp."

        filepath = runtime.resolve_filepath(filename)

        runtime.console.print()
        runtime.console.print(Panel(
            escape(prompt.strip()),
            title=f"[bold yellow]Proposed Image Generation: {escape(filename)}[/bold yellow]",
            subtitle=f"[dim]Model: {escape(model)}[/dim]",
            border_style="yellow",
            expand=False
        ))
        runtime.console.print(f"[yellow]Auto-approving image generation (non-destructive): {escape(filename)}[/yellow]")

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        request_args = {
            "model": model,
            "prompt": prompt,
        }
        if size:
            request_args["size"] = size

        result = client.images.generate(**request_args)
        image_data = result.data[0]
        image_base64 = getattr(image_data, "b64_json", None)
        if not image_base64:
            return "Error: Image generation response did not include base64 image data."

        image_bytes = base64.b64decode(image_base64)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        runtime.console.print(f"[green]Successfully wrote image: {escape(filename)}[/green]")
        return f"Success: Image generated and saved to '{filepath}'."
    except Exception as e:
        return f"Error generating image: {str(e)}"

