"""TUI 主循环 + 命令处理。"""

import json
import shlex
import subprocess
import tempfile
import os
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from api.client import OpenAIClient, APIError
from config.settings import Settings
from payload.builder import build_payload, build_full_request
from payload.templates import list_templates, get_template, save_template
from payload.templates import list_tool_templates, get_tool_template, save_tool_template, PRESET_TOOL_TEMPLATES
from . import display
from .screens import render_main

HISTORY_DIR = Path(__file__).parent.parent / "history"


@dataclass
class AppState:
    messages: list[dict] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    thinking_enabled: bool = True
    last_response: dict | None = None
    last_usage: str = ""
    stream_mode: bool = True


class App:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = AppState()
        self.client = OpenAIClient(settings.api_key, settings.base_url)
        # 默认加载 weather 工具
        from payload.templates import get_tool_template
        tmpl = get_tool_template("weather")
        if tmpl:
            self.state.tools = tmpl
        self.console = Console()
        self._running = True
        self._session_dir: Path | None = None

    def run(self) -> None:
        while self._running:
            render_main(self.console, self.state, self.settings)
            try:
                raw = self.console.input("[bold cyan]> [/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                self._running = False
                break

            if not raw.strip():
                continue

            self._handle_command(raw.strip())

        self.client.close()

    def _handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

        handlers = {
            "?": self._cmd_help,
            "help": self._cmd_help,
            "q": self._cmd_quit,
            "quit": self._cmd_quit,
            "system": self._cmd_system,
            "user": self._cmd_user,
            "assistant": self._cmd_assistant,
            "del": self._cmd_del,
            "clear": self._cmd_clear,
            "model": self._cmd_model,
            "param": self._cmd_param,
            "think": self._cmd_think,
            "tool": self._cmd_tool,
            "result": self._cmd_result,
            "show": self._cmd_show,
            "edit": self._cmd_edit,
            "send": self._cmd_send,
            "stream": self._cmd_stream,
            "load": self._cmd_load,
            "save": self._cmd_save,
            "templates": self._cmd_templates,
            "config": self._cmd_config,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            self._cmd_user([raw])

    def _pause(self) -> None:
        try:
            self.console.input("\n[dim]按回车继续...[/dim]")
        except (EOFError, KeyboardInterrupt):
            pass

    def _get_tool_names(self) -> set[str]:
        """获取当前工具声明中的所有函数名。"""
        return {t.get("function", {}).get("name") for t in self.state.tools}

    def _merge_tools(self, new_tools: list[dict]) -> int:
        """合并工具声明，按函数名去重。返回新增数量。"""
        existing = self._get_tool_names()
        added = 0
        for tool in new_tools:
            fn_name = tool.get("function", {}).get("name")
            if fn_name and fn_name not in existing:
                self.state.tools.append(dict(tool))
                existing.add(fn_name)
                added += 1
        return added

    def _remove_tools_by_names(self, names: set[str]) -> int:
        """移除指定函数名的工具声明。返回移除数量。"""
        before = len(self.state.tools)
        self.state.tools = [t for t in self.state.tools
                            if t.get("function", {}).get("name") not in names]
        return before - len(self.state.tools)

    def _toggle_template_tools(self, tpl_tools: list[dict]) -> str:
        """切换模板中的工具：全激活则移除，否则添加。返回 'added' / 'removed' / 'unchanged'。"""
        tpl_names = {t.get("function", {}).get("name") for t in tpl_tools}
        active_names = self._get_tool_names()
        if tpl_names and tpl_names.issubset(active_names):
            self._remove_tools_by_names(tpl_names)
            return "removed"
        else:
            added = self._merge_tools(tpl_tools)
            return "added" if added else "unchanged"

    def _print_tool_selector(self, all_t: dict, template_order: list[str]) -> None:
        """打印交互式工具模板选择器。"""
        active_names = self._get_tool_names()
        preset_keys = set(PRESET_TOOL_TEMPLATES.keys())

        self.console.print("[bold]工具模板 — 输入编号切换勾选，回车确认[/bold]")
        self.console.print()
        for i, name in enumerate(template_order, 1):
            tools = all_t[name]
            tpl_names = {t.get("function", {}).get("name") for t in tools}
            is_active = bool(tpl_names) and tpl_names.issubset(active_names)
            mark = "✓" if is_active else " "
            ttype = "预设" if name in preset_keys else "用户"
            fn_list = ", ".join(sorted(tpl_names))
            self.console.print(f"  [{mark}] {i}. [bold cyan]{name}[/bold cyan] ({ttype}) — {fn_list}")

        self.console.print()
        if active_names:
            self.console.print(f"[dim]当前激活: {', '.join(sorted(active_names))} | 共 {len(active_names)} 个工具[/dim]")
        else:
            self.console.print("[dim]当前无激活工具[/dim]")
        self.console.print()

    # ── command implementations ──

    def _cmd_help(self, args):
        render_main(self.console, self.state, self.settings)
        self.console.print(display.format_help())
        self._pause()

    def _cmd_quit(self, args):
        self._running = False

    def _cmd_system(self, args):
        if not args:
            self.console.print("[red]用法: system <文本>[/red]")
        else:
            text = " ".join(args)
            existing = [m for m in self.state.messages if m["role"] == "system"]
            if existing:
                existing[0]["content"] = text
            else:
                self.state.messages.insert(0, {"role": "system", "content": text})

    def _cmd_user(self, args):
        if not args:
            self.console.print("[red]用法: user <文本>[/red]")
        else:
            text = " ".join(args)
            self.state.messages.append({"role": "user", "content": text})

    def _cmd_assistant(self, args):
        if not args:
            self.console.print("[red]用法: assistant <文本>[/red]")
        else:
            text = " ".join(args)
            self.state.messages.append({"role": "assistant", "content": text})

    def _cmd_del(self, args):
        if not self.state.messages:
            return
        for i in range(len(self.state.messages) - 1, -1, -1):
            if self.state.messages[i]["role"] == "user":
                removed = self.state.messages.pop(i)
                self.console.print(f"[dim]已删除: {removed['content'][:50]}[/dim]")
                return
        removed = self.state.messages.pop()
        self.console.print("[dim]已删除最后一条消息[/dim]")

    def _cmd_clear(self, args):
        self.state.messages.clear()
        self.state.last_response = None
        self.state.last_usage = ""

    def _cmd_model(self, args):
        if not args:
            self.console.print(f"[dim]当前 model: {self.settings.model}[/dim]")
            self._pause()
        else:
            self.settings.model = args[0]
            self.settings.save()

    def _cmd_param(self, args):
        if not args:
            self.console.print("[red]用法: param <key> <value> | param rm <key>[/red]")
        elif len(args) >= 2 and args[0] == "rm":
            self.state.params.pop(args[1], None)
        elif len(args) >= 2:
            key = args[0]
            val_str = " ".join(args[1:])
            try:
                val = json.loads(val_str)
            except json.JSONDecodeError:
                val = val_str
            self.state.params[key] = val
        else:
            self.console.print("[red]用法: param <key> <value> | param rm <key>[/red]")

    def _cmd_think(self, args):
        self.state.thinking_enabled = not self.state.thinking_enabled
        state_text = "开" if self.state.thinking_enabled else "关"
        self.console.print(f"[green]思考模式已切换为: {state_text}[/green]")

    def _cmd_tool(self, args):
        if not args:
            self.console.print("[red]用法: tool add <JSON> | tool load <模板> | tool save <名称> | tool list | tool clear | tool show[/red]")
            return
        sub = args[0].lower()
        if sub == "clear":
            self.state.tools.clear()
            self.console.print("[dim]已清空工具声明[/dim]")
        elif sub == "show":
            render_main(self.console, self.state, self.settings)
            self.console.print(display.format_tools(self.state.tools))
            self._pause()
        elif sub == "list":
            all_t = list_tool_templates()
            if not all_t:
                render_main(self.console, self.state, self.settings)
                self.console.print("[dim]没有工具模板。[/dim]")
                self._pause()
                return

            template_order = list(all_t.keys())
            original_tools = [dict(t) for t in self.state.tools]

            while True:
                render_main(self.console, self.state, self.settings)
                self._print_tool_selector(all_t, template_order)
                raw = self.console.input("[dim]输入编号切换 / 回车确认 / q 取消: [/dim]")
                if not raw.strip():
                    break
                if raw.strip().lower() == 'q':
                    self.state.tools = original_tools
                    break
                try:
                    idx = int(raw.strip()) - 1
                    if 0 <= idx < len(template_order):
                        name = template_order[idx]
                        result = self._toggle_template_tools(all_t[name])
                        if result == "added":
                            self.console.print(f"[green]已添加 '{name}'[/green]")
                        elif result == "removed":
                            self.console.print(f"[dim]已移除 '{name}'[/dim]")
                    else:
                        self.console.print("[red]无效编号[/red]")
                        self._pause()
                except ValueError:
                    self.console.print("[red]请输入编号[/red]")
                    self._pause()

            render_main(self.console, self.state, self.settings)
            self.console.print(f"[green]当前工具声明: {len(self.state.tools)} 个工具[/green]")
            self._pause()
        elif sub == "load":
            if len(args) < 2:
                self.console.print("[red]用法: tool load <模板名>[/red]")
                return
            name = args[1]
            tool_tmpl = get_tool_template(name)
            if tool_tmpl is None:
                self.console.print(f"[red]工具模板 '{name}' 不存在。先用 tool list 查看可用工具模板。[/red]")
                self._pause()
                return
            added = self._merge_tools(tool_tmpl)
            if added:
                self.console.print(f"[green]已添加 {added} 个工具 (来自 '{name}')，当前共 {len(self.state.tools)} 个工具[/green]")
            else:
                self.console.print(f"[dim]工具模板 '{name}' 中的工具已全部存在，无需添加。[/dim]")
            self._pause()
        elif sub == "save":
            if len(args) < 2:
                self.console.print("[red]用法: tool save <名称>[/red]")
                return
            save_tool_template(args[1], self.state.tools)
            self.console.print(f"[green]已保存工具模板 '{args[1]}'[/green]")
        elif sub == "add":
            json_str = " ".join(args[1:])
            try:
                tool = json.loads(json_str)
                if isinstance(tool, dict):
                    tool = [tool]
                if not isinstance(tool, list):
                    self.console.print("[red]工具声明应为对象或数组[/red]")
                    return
                self.state.tools.extend(tool)
                self.console.print(f"[green]已添加 {len(tool)} 个工具声明[/green]")
            except json.JSONDecodeError as e:
                self.console.print(f"[red]JSON 格式错误: {e}[/red]")
        else:
            self.console.print("[red]用法: tool add <JSON> | tool load <模板> | tool save <名称> | tool list | tool clear | tool show[/red]")

    def _cmd_result(self, args):
        """添加工具调用结果消息。无参数时逐个交互填写所有待处理工具调用。"""
        if len(args) > 0:
            # 有参数：文本模式（快捷方式，填第一个待处理的）
            if args[0].startswith("call_") and len(args) >= 2:
                call_id = args[0]
                text = " ".join(args[1:])
            else:
                pending = self._get_pending_tool_infos()
                if not pending:
                    self.console.print("[red]没有待处理的工具调用。[/red]")
                    return
                call_id = pending[0][0]
                text = " ".join(args)
            content = self._parse_result_text(text)
            self._add_tool_result(call_id, content)
            return

        # 无参数：逐个交互填写所有待处理工具调用
        pending = self._get_pending_tool_infos()
        if not pending:
            self.console.print("[red]没有待处理的工具调用。先 send 触发工具调用再使用 result。[/red]")
            return

        total = len(pending)
        for idx, (call_id, fn_name, model_args) in enumerate(pending, 1):
            header = f"工具调用 ({idx}/{total})" if total > 1 else "工具调用"
            self.console.print(f"\n[bold]{header}:[/bold] [cyan]{fn_name}[/cyan]")
            if model_args:
                self.console.print(f"[bold]模型入参:[/bold] [dim]{json.dumps(model_args, ensure_ascii=False)}[/dim]")
            self.console.print(f"[dim]id: {call_id[:40]}...[/dim]")
            self.console.print()
            self.console.print("[dim]请输入工具返回的结果（JSON 或纯文本，输入 skip 跳过）:[/dim]")
            raw = self.console.input("[bold yellow]结果: [/bold yellow]")
            if not raw.strip():
                self.console.print("[dim]已取消剩余填写。[/dim]")
                return
            if raw.strip().lower() == "skip":
                self.console.print(f"[dim]已跳过 {fn_name}。[/dim]")
                continue
            content = self._parse_result_text(raw.strip())
            self._add_tool_result(call_id, content)

    def _add_tool_result(self, call_id: str, content):
        self.state.messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content),
        })
        self.console.print(f"[green]已添加 tool 结果 -> {call_id[:30]}...[/green]")

    def _parse_result_text(self, text: str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _get_pending_tool_infos(self) -> list[tuple[str, str, dict]]:
        """获取所有待处理的工具调用，排除已有 tool result 的。
        返回 [(call_id, function_name, model_args), ...]。"""
        # 收集已有 tool result 的 id
        responded_ids = set()
        for msg in self.state.messages:
            if msg.get("role") == "tool":
                tid = msg.get("tool_call_id")
                if tid:
                    responded_ids.add(tid)

        # 找最后一条有 tool_calls 的 assistant 消息
        for i in range(len(self.state.messages) - 1, -1, -1):
            msg = self.state.messages[i]
            if msg.get("role") == "assistant":
                tcs = msg.get("tool_calls")
                if tcs:
                    result = []
                    for tc in tcs:
                        call_id = tc.get("id", "")
                        if call_id and call_id not in responded_ids:
                            fn_name = tc.get("function", {}).get("name", "")
                            args_str = tc.get("function", {}).get("arguments", "{}") or "{}"
                            try:
                                model_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                            except (json.JSONDecodeError, TypeError):
                                model_args = {}
                            result.append((call_id, fn_name, model_args))
                    return result
        return []

    def _find_tool_def(self, name: str) -> dict | None:
        """从 tools 声明中按函数名查找工具定义。"""
        for t in self.state.tools:
            if t.get("function", {}).get("name") == name:
                return t
        return None

    def _cmd_show(self, args):
        render_main(self.console, self.state, self.settings)
        payload = build_payload(
            self.settings.model, self.state.messages, self.state.params,
            tools=self.state.tools,
            thinking={"type": "enabled"} if self.state.thinking_enabled else None,
        )
        req = build_full_request(self.settings, payload)
        self.console.print(display.format_full_request(req))
        self._pause()

    def _cmd_edit(self, args):
        payload = build_payload(
            self.settings.model, self.state.messages, self.state.params,
            tools=self.state.tools,
            thinking={"type": "enabled"} if self.state.thinking_enabled else None,
        )
        req = build_full_request(self.settings, payload)
        edited = self._edit_payload(req["body"])
        if edited is None:
            return
        self.settings.model = edited.get("model", self.settings.model)
        self.state.messages = edited.get("messages", [])
        self.state.tools = edited.get("tools", [])
        if edited.get("thinking"):
            self.state.thinking_enabled = True
        else:
            self.state.thinking_enabled = False
        params = dict(edited)
        for key in ("model", "messages", "tools", "thinking", "reasoning_effort"):
            params.pop(key, None)
        self.state.params = {k: v for k, v in params.items() if v is not None}

    def _edit_payload(self, payload: dict) -> dict | None:
        payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        editor = os.environ.get("EDITOR", "notepad")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write(payload_json)
            tmp_path = f.name

        try:
            subprocess.run([editor, tmp_path], check=False)
            with open(tmp_path, encoding="utf-8") as f:
                new_json = f.read()
            edited = json.loads(new_json)
            if "messages" not in edited:
                self.console.print("[red]Payload 必须包含 'messages' 字段[/red]")
                self._pause()
                return None
            return edited
        except json.JSONDecodeError as e:
            self.console.print(f"[red]JSON 格式错误: {e}[/red]")
            self._pause()
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _cmd_send(self, args):
        if not self.state.messages:
            self.console.print("[red]没有消息可发送。[/red]")
            return
        if self.state.stream_mode:
            self._do_stream()
        else:
            self._do_send()

    def _build_payload(self) -> dict:
        return build_payload(
            self.settings.model, self.state.messages, self.state.params,
            tools=self.state.tools or None,
            thinking={"type": "enabled"} if self.state.thinking_enabled else None,
        )

    def _init_session(self) -> Path:
        if self._session_dir is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_dir = HISTORY_DIR / ts
        self._session_dir.mkdir(parents=True, exist_ok=True)
        return self._session_dir

    def _save_history(self, payload: dict, response: dict | None, error: dict | None = None) -> None:
        session = self._init_session()
        idx = len(list(session.glob("*.json"))) // 2 + 1
        req = build_full_request(self.settings, payload)
        req["headers"]["Authorization"] = f"Bearer {self.settings.api_key}"
        with open(session / f"{idx:03d}_request.json", "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)
        with open(session / f"{idx:03d}_response.json", "w", encoding="utf-8") as f:
            if error:
                json.dump(error, f, indent=2, ensure_ascii=False)
            elif response:
                json.dump(response, f, indent=2, ensure_ascii=False)

    def _do_send(self):
        payload = self._build_payload()

        self.console.print("[dim]发送中...[/dim]")
        try:
            resp = self.client.chat_completion(payload)
        except APIError as e:
            self.console.print(f"[red]API 错误 ({e.status_code}): {e.message}[/red]")
            if e.body and "error" in e.body:
                detail = e.body["error"]
                if isinstance(detail, dict):
                    self.console.print(f"[dim red]{json.dumps(detail, indent=2, ensure_ascii=False)}[/dim red]")
            self._save_history(payload, None, {"error": {"status": e.status_code, "message": e.message, "body": e.body}})
            self._pause()
            return

        self._save_history(payload, resp)
        self._process_response(resp)

    def _do_stream(self):
        payload = self._build_payload()

        self.console.print("[dim]流式发送中...[/dim]")

        # 保存请求
        self._save_history(payload, None)

        collected_content = ""
        collected_reasoning = ""
        usage_info = {}
        tool_calls_by_idx: dict[int, dict] = {}
        error_info = None

        try:
            reasoning_started = False
            content_started = False
            for chunk in self.client.stream_chat(payload):
                if "usage" in chunk:
                    usage_info = chunk["usage"]
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                reasoning = delta.get("reasoning_content", "")
                content = delta.get("content", "")
                tc_deltas = delta.get("tool_calls") or []

                if reasoning:
                    if not reasoning_started:
                        self.console.print()
                        self.console.print("[bold blue]思考过程:[/bold blue]")
                        reasoning_started = True
                    self.console.print(reasoning, end="", style="dim italic")
                    collected_reasoning += reasoning
                if content:
                    if not content_started:
                        if reasoning_started:
                            self.console.print()
                        self.console.print("[bold magenta]Assistant:[/bold magenta]")
                        content_started = True
                    self.console.print(content, end="", style="magenta")
                    collected_content += content
                # 流式工具调用按 index 拼接（DeepSeek 逐字符分片传输 arguments）
                for tc in tc_deltas:
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_by_idx:
                        tool_calls_by_idx[idx] = {
                            "id": tc.get("id") or "",
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name") or "",
                                "arguments": tc.get("function", {}).get("arguments") or "",
                            },
                        }
                    else:
                        cur = tool_calls_by_idx[idx]
                        if tc.get("id"):
                            cur["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            cur["function"]["name"] += tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            cur["function"]["arguments"] += tc["function"]["arguments"]
            self.console.print()
            tool_calls_buf = list(tool_calls_by_idx.values())
        except APIError as e:
            self.console.print(f"\n[red]API 错误 ({e.status_code}): {e.message}[/red]")
            if e.body:
                self.console.print(f"[dim red]{json.dumps(e.body, indent=2, ensure_ascii=False)}[/dim red]")
            error_info = {"error": {"status": e.status_code, "message": e.message, "body": e.body}}
            self._save_history(payload, None, error_info)
            self._pause()
            return

        # 构建 assistant 消息
        assistant_msg: dict = {"role": "assistant", "content": collected_content}
        if collected_reasoning:
            assistant_msg["reasoning_content"] = collected_reasoning
        if tool_calls_buf:
            assistant_msg["tool_calls"] = tool_calls_buf
        self.state.messages.append(assistant_msg)

        resp = {
            "choices": [{"message": assistant_msg}],
            "usage": usage_info,
        }
        self.state.last_response = resp
        self.state.last_usage = display.format_usage(self.state.last_response)
        self._save_history(payload, resp)

    def _process_response(self, resp: dict) -> None:
        self.state.last_response = resp
        self.state.last_usage = display.format_usage(resp)
        try:
            msg = resp["choices"][0].get("message", {})
            assistant_msg = {
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", ""),
            }
            if msg.get("reasoning_content"):
                assistant_msg["reasoning_content"] = msg["reasoning_content"]
            if msg.get("tool_calls"):
                # 确保每个 tool_call 都有 type 字段
                tcs = []
                for tc in msg["tool_calls"]:
                    if "type" not in tc:
                        tc = dict(tc, type="function")
                    tcs.append(tc)
                assistant_msg["tool_calls"] = tcs
            self.state.messages.append(assistant_msg)
        except (KeyError, IndexError):
            pass

    def _cmd_stream(self, args):
        self.state.stream_mode = not self.state.stream_mode
        state_text = "开" if self.state.stream_mode else "关"
        self.console.print(f"[green]流式模式已切换为: {state_text}[/green]")

    def _cmd_load(self, args):
        if not args:
            self.console.print("[red]用法: load <模板名>[/red]")
            return
        name = args[0]
        # 先尝试对话模板，再尝试工具模板
        conv = get_template(name)
        tool = get_tool_template(name) if conv is None else None
        if conv is None and tool is None:
            self.console.print(f"[red]模板 '{name}' 不存在。[/red]")
            return
        if conv is not None:
            system = conv.pop("system", None)
            params = {k: v for k, v in conv.items() if k != "messages" and k != "tools"}
            self.state.messages.clear()
            self.state.params.update(params)
            if system:
                self.state.messages.append({"role": "system", "content": system})
            if "messages" in conv:
                self.state.messages.extend(conv["messages"])
            if "tools" in conv:
                self._merge_tools(conv["tools"])
            self.console.print(f"[green]已加载对话模板 '{name}'。[/green]")
        else:
            added = self._merge_tools(tool)
            if added:
                self.console.print(f"[green]已添加 {added} 个工具，当前共 {len(self.state.tools)} 个工具[/green]")
            else:
                self.console.print(f"[dim]工具模板 '{name}' 中的工具已全部存在，无需添加。[/dim]")

    def _cmd_save(self, args):
        if not args:
            self.console.print("[red]用法: save <模板名>[/red]")
            return
        name = args[0]
        data = {
            "messages": self.state.messages,
            **self.state.params,
        }
        if self.state.tools:
            data["tools"] = self.state.tools
        save_template(name, data)
        self.console.print(f"[green]已保存模板 '{name}'。[/green]")

    def _cmd_templates(self, args):
        render_main(self.console, self.state, self.settings)
        all_t = list_templates()
        if not all_t:
            self.console.print("[dim]没有模板。[/dim]")
        else:
            from rich.table import Table
            table = Table(title="模板列表", border_style="dim")
            table.add_column("名称", style="bold cyan")
            table.add_column("类型")
            table.add_column("System 消息")
            for name, data in all_t.items():
                is_preset = name in ["translate", "summarize", "coder", "explain"]
                ttype = "预设" if is_preset else "用户"
                system = data.get("system", "")[:50]
                table.add_row(name, ttype, system)
            self.console.print(table)
        self._pause()

    def _cmd_config(self, args):
        render_main(self.console, self.state, self.settings)
        self.console.print(display.format_config_help())
        self._pause()
