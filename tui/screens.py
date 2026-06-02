"""使用 rich 渲染主界面，不依赖 Layout/Live。"""

from rich.columns import Columns
from rich.console import Console, Group

from . import display


def render_main(console: Console, state, settings) -> None:
    console.clear()

    # header
    rule = "─" * console.width
    console.print(f"[bold blue]{rule}[/bold blue]")
    console.print("[bold]  OpenAI Chat API Debugger[/bold]")
    console.print(f"[bold blue]{rule}[/bold blue]")
    console.print()

    # top row: config | messages
    top = Columns([
        display.format_config(settings),
        display.format_messages(state.messages),
    ])
    console.print(top)

    # bottom row: params | response
    bottom = Columns([
        display.format_params(state.params),
        display.format_response_content(state.last_response),
    ])
    console.print(bottom)

    # status bar
    console.print()
    status = display.format_status(state)
    console.print(f"[dim]{status}[/dim]")
    console.print()
