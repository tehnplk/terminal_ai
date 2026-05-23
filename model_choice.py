import os

import questionary
from rich.markup import escape
from rich.prompt import Confirm


DEFAULT_MODEL = "openai/gpt-oss-120b:free"

MODEL_CHOICES = [
    DEFAULT_MODEL,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "arcee-ai/trinity-large-thinking:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "deepseek/deepseek-v4-flash:free",
    "deepseek/deepseek-v4-flash",
    "minimax/minimax-m2.5:free",
    "baidu/cobuddy:free",
    "google/gemma-4-31b-it:free",
]


def select_model_interactive(console, find_external_runtime_file, default_runtime_file_path) -> str:
    """Lets the user select an OpenRouter model and optionally saves it to .env."""
    selected = questionary.select(
        "Select OpenRouter Model (Use arrow keys):",
        choices=MODEL_CHOICES,
        default=DEFAULT_MODEL,
    ).ask()

    if not selected:
        console.print(f"[yellow]No model selected. Defaulting to {DEFAULT_MODEL}.[/yellow]")
        selected = DEFAULT_MODEL

    model_choice = selected

    save_model = Confirm.ask(f"Would you like to save model choice '{model_choice}' to your .env file?", default=True)
    if save_model:
        env_path = find_external_runtime_file(".env") or default_runtime_file_path(".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            with open(env_path, "w") as f:
                for line in lines:
                    if not line.strip().startswith("OPENROUTER_MODEL="):
                        f.write(line)
        with open(env_path, "a") as f:
            f.write(f"\nOPENROUTER_MODEL={model_choice}\n")
        console.print(f"[green]Saved model choice to {escape(env_path)}.[/green]")

    return model_choice
