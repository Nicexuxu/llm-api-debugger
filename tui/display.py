"""rich 渲染辅助函数。"""

import json

from rich.console import RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


ROLE_COLORS = {
    "system": "dim cyan",
    "user": "green",
    "assistant": "magenta",
    "tool": "yellow",
}
ROLE_LABELS = {
    "system": "System",
    "user": "User",
    "assistant": "Assistant",
    "tool": "Tool",
}


MAX_MSG_CHARS = 250  # 约 3 行


def _truncate(content: str) -> str:
    if len(content) <= MAX_MSG_CHARS:
        return content
    return content[:MAX_MSG_CHARS] + "..."


def format_messages(messages: list[dict]) -> RenderableType:
    if not messages:
        return Panel("(无消息)", border_style="dim")
    blocks: list[Text] = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")
        tool_calls = msg.get("tool_calls")
        color = ROLE_COLORS.get(role, "white")
        label = ROLE_LABELS.get(role, role)

        text = Text()
        text.append(f"[{i + 1}] {label}: ", style=f"bold {color}")

        # 思考内容 — 独立一行
        if reasoning:
            text.append("\n  [思考] ", style="dim")
            text.append(_truncate(reasoning), style="dim italic")

        # 工具调用 — 独立一行
        if tool_calls:
            text.append("\n  [工具调用] ", style="bold yellow")
            for j, tc in enumerate(tool_calls):
                fn = tc.get("function", {})
                name = fn.get("name", "?")
                args = fn.get("arguments", "{}")
                try:
                    import json as _json
                    args_obj = _json.loads(args) if isinstance(args, str) else args
                    args_short = _json.dumps(args_obj, ensure_ascii=False)
                    if len(args_short) > 80:
                        args_short = args_short[:80] + "..."
                except Exception:
                    args_short = str(args)[:80]
                text.append(f"\n    {name}({args_short})", style="yellow")

        # 正文 — 独立一行
        if content:
            text.append("\n  [回复] ", style="bold green")
            text.append(_truncate(content))

        blocks.append(text)
    return Panel("\n\n".join(str(t) for t in blocks), title="消息列表", border_style="blue")


def format_params(params: dict) -> RenderableType:
    table = Table(title="参数", border_style="dim", show_header=False, box=None)
    table.add_column("Key", style="dim")
    table.add_column("Value")
    for key, val in params.items():
        table.add_row(key, str(val))
    if not params:
        return Panel("(默认)", title="参数", border_style="dim")
    return table


def format_config(settings) -> RenderableType:
    table = Table(title="配置", border_style="dim", show_header=False, box=None)
    table.add_column("Key", style="dim")
    table.add_column("Value")
    table.add_row("model", settings.model)
    table.add_row("base_url", settings.base_url)
    masked = settings.api_key[:7] + "..." if len(settings.api_key) > 7 else "***"
    table.add_row("api_key", masked)
    return table


def format_payload(payload: dict) -> RenderableType:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    return Panel(Syntax(text, "json", theme="monokai"), title="当前 Payload", border_style="yellow")


def format_full_request(req: dict) -> RenderableType:
    """渲染完整 HTTP 请求：URL + Headers + Body。"""
    from rich.console import Group
    header_lines = [
        f"[bold]URL:[/bold] [cyan]{req['url']}[/cyan]",
        f"[bold]Method:[/bold] POST",
        "",
        "[bold]Headers:[/bold]",
    ]
    for k, v in req["headers"].items():
        header_lines.append(f"  [dim]{k}:[/dim] {v}")
    header_lines.append("")
    header_lines.append("[bold]Body:[/bold]")

    body_text = json.dumps(req["body"], indent=2, ensure_ascii=False)
    content = Group(
        Text.from_markup("\n".join(header_lines)),
        Syntax(body_text, "json", theme="monokai"),
    )
    return Panel(content, title="完整 HTTP 请求", border_style="yellow")


def format_thinking(reasoning_content: str) -> RenderableType:
    """渲染思考过程。"""
    text = Text(reasoning_content, style="dim italic")
    return Panel(text, title="思考过程", border_style="blue")


def format_tools(tools: list[dict]) -> RenderableType:
    if not tools:
        return Panel("(无工具声明)", title="工具", border_style="dim")
    lines: list[str] = []
    for i, tool in enumerate(tools):
        func = tool.get("function", {})
        name = func.get("name", "?")
        desc = func.get("description", "")[:80]
        lines.append(f"[{i + 1}] [bold cyan]{name}[/bold cyan] — {desc}")
    return Panel("\n".join(lines), title=f"工具 ({len(tools)})", border_style="dim")


def format_response_content(response: dict | None) -> RenderableType:
    if response is None:
        return Panel("(暂无响应)", title="响应", border_style="dim")
    try:
        choice = response["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")
        tool_calls = msg.get("tool_calls")

        parts: list[RenderableType] = []

        if reasoning:
            parts.append(format_thinking(reasoning))
        if tool_calls:
            cleaned = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "?")
                args_str = fn.get("arguments", "{}") or "{}"
                try:
                    args_obj = json.loads(args_str) if isinstance(args_str, str) else args_str
                except (json.JSONDecodeError, TypeError):
                    args_obj = args_str
                cleaned.append({"name": name, "args": args_obj})
            calls_text = json.dumps(cleaned, indent=2, ensure_ascii=False)
            parts.append(Panel(Syntax(calls_text, "json", theme="monokai"),
                               title="工具调用", border_style="yellow"))
        if content:
            role = msg.get("role", "assistant")
            color = ROLE_COLORS.get(role, "white")
            parts.append(Panel(Text(content, style=color), title="回复", border_style="green"))
        elif not parts:
            parts.append(Panel("(空响应)", border_style="dim"))

        from rich.console import Group
        return Group(*parts)
    except (KeyError, IndexError):
        text = json.dumps(response, indent=2, ensure_ascii=False)
        return Panel(Syntax(text, "json", theme="monokai"), title="响应 (原始数据)", border_style="yellow")


def format_usage(response: dict | None) -> str:
    if response is None or "usage" not in response:
        return ""
    usage = response["usage"]
    parts = []
    if "prompt_tokens" in usage:
        parts.append(f"输入: {usage['prompt_tokens']}")
    if "completion_tokens" in usage:
        parts.append(f"输出: {usage['completion_tokens']}")
    if "total_tokens" in usage:
        parts.append(f"总计: {usage['total_tokens']}")
    return " | ".join(parts)


def format_status(state) -> str:
    parts = [f"消息数: {len(state.messages)}"]
    if getattr(state, 'tools', None):
        parts.append(f"工具: {len(state.tools)}")
    if hasattr(state, 'thinking_enabled'):
        parts.append(f"思考: {'开' if state.thinking_enabled else '关'}")
    if hasattr(state, 'stream_mode'):
        parts.append(f"流式: {'开' if state.stream_mode else '关'}")
    if hasattr(state, 'last_usage') and state.last_usage:
        parts.append(f"上次用量: {state.last_usage}")
    parts.append("输入 ? 查看帮助")
    return " | ".join(parts)


def format_help() -> RenderableType:
    table = Table(title="命令列表", border_style="dim")
    table.add_column("命令", style="bold cyan")
    table.add_column("说明")
    table.add_row("直接输入文本", "作为 user 消息添加")
    table.add_row("system <文本>", "设置 system 消息")
    table.add_row("user <文本>", "添加 user 消息")
    table.add_row("assistant <文本>", "添加 assistant 消息")
    table.add_row("del", "删除最后一条 user 消息")
    table.add_row("clear", "清空所有消息")
    table.add_row("model <模型名>", "切换 model")
    table.add_row("param <key> <value>", "设置参数 (如 temperature, max_tokens)")
    table.add_row("param rm <key>", "删除参数，恢复默认值")
    table.add_row("think", "切换思考模式 (DeepSeek reasoning)")
    table.add_row("tool add <JSON>", "添加工具声明")
    table.add_row("tool load <模板>", "加载预设/用户工具模板")
    table.add_row("tool save <名称>", "保存当前工具声明为模板")
    table.add_row("tool list", "列出所有工具模板")
    table.add_row("tool clear", "清空工具声明")
    table.add_row("tool show", "查看当前工具声明")
    table.add_row("result <文本>", "添加工具调用结果 (自动使用最后一条 tool_call_id)")
    table.add_row("result <id> <文本>", "显式指定 tool_call_id 添加结果")
    table.add_row("show", "查看完整 HTTP 请求 (URL + Headers + Body)")
    table.add_row("edit", "在外部编辑器中编辑请求 JSON")
    table.add_row("send", "以当前模式发送请求")
    table.add_row("stream", "切换流式模式 (开/关)，send 按当前模式发送")
    table.add_row("load <模板名>", "加载模板")
    table.add_row("save <模板名>", "保存当前会话为模板")
    table.add_row("templates", "列出所有模板")
    table.add_row("config", "查看配置文件说明")
    table.add_row("quit / q", "退出")
    return table


def format_config_help() -> str:
    return """[bold]配置文件说明[/bold]

配置文件为项目目录下的 [cyan]config.json[/cyan]，格式如下：

  {
    "api_key": "sk-你的API密钥",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini"
  }

字段说明:
  [cyan]api_key[/cyan]  - API 密钥
  [cyan]base_url[/cyan] - API 端点地址 (支持任意兼容 OpenAI 接口的服务)
  [cyan]model[/cyan]    - 默认模型名称

修改后保存文件即可生效。"""
