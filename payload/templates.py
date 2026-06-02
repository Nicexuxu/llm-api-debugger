"""
预设模板 + 用户模板 + 工具模板的保存/加载。

用户模板保存在 templates.json，工具模板保存在 tool_templates.json 中。
"""

import json
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent.parent
_TEMPLATES_FILE = _TEMPLATES_DIR / "templates.json"
_TOOL_TEMPLATES_FILE = _TEMPLATES_DIR / "tool_templates.json"


# ── 对话模板 ──

PRESET_TEMPLATES: dict[str, dict] = {
    "translate": {
        "system": "You are a professional translator. Translate the user's input to English accurately and naturally.",
        "temperature": 0.3,
    },
    "summarize": {
        "system": "You are a summarization expert. Summarize the user's input concisely while keeping all key points.",
        "temperature": 0.5,
    },
    "coder": {
        "system": "You are a senior software engineer. Write clean, efficient code with minimal comments. Prefer simplicity over abstraction.",
        "temperature": 0.2,
    },
    "explain": {
        "system": "Explain the following concept clearly and thoroughly, as if teaching a beginner.",
        "temperature": 0.7,
    },
}


# ── 工具模板 ──

PRESET_TOOL_TEMPLATES: dict[str, list[dict]] = {
    "weather": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市在指定日期的天气情况",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称，如 Beijing"},
                        "date": {"type": "string", "description": "日期，格式 YYYY-mm-dd"},
                    },
                    "required": ["location", "date"],
                },
            },
        }
    ],
    "date": [
        {
            "type": "function",
            "function": {
                "name": "get_date",
                "description": "获取当前日期",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ],
    "search": [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索网页获取实时信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "num_results": {"type": "integer", "description": "返回结果数量，默认 5"},
                    },
                    "required": ["query"],
                },
            },
        }
    ],
    "calculator": [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "执行数学计算",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "数学表达式，如 '2 + 3 * 4'"},
                    },
                    "required": ["expression"],
                },
            },
        }
    ],
    "weather+date": [
        {
            "type": "function",
            "function": {
                "name": "get_date",
                "description": "获取当前日期",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市在指定日期的天气情况",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称，如 Beijing"},
                        "date": {"type": "string", "description": "日期，格式 YYYY-mm-dd"},
                    },
                    "required": ["location", "date"],
                },
            },
        }
    ],
    "filesystem": [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "写入文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "文件内容"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出目录中的文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "目录路径"},
                    },
                    "required": ["path"],
                },
            },
        }
    ],
}


# ── 对话模板 ──

def list_templates() -> dict[str, dict]:
    all_templates = dict(PRESET_TEMPLATES)
    all_templates.update(_load_user_templates())
    return all_templates


def get_template(name: str) -> dict | None:
    if name in PRESET_TEMPLATES:
        return dict(PRESET_TEMPLATES[name])
    user = _load_user_templates()
    if name in user:
        return dict(user[name])
    return None


def save_template(name: str, data: dict) -> None:
    user = _load_user_templates()
    user[name] = data
    _TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(user, f, indent=2, ensure_ascii=False)


def delete_template(name: str) -> bool:
    if name in PRESET_TEMPLATES:
        return False
    user = _load_user_templates()
    if name in user:
        del user[name]
        with open(_TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(user, f, indent=2, ensure_ascii=False)
        return True
    return False


def _load_user_templates() -> dict[str, dict]:
    if _TEMPLATES_FILE.exists():
        with open(_TEMPLATES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── 工具模板 ──

def list_tool_templates() -> dict[str, list[dict]]:
    all_t = dict(PRESET_TOOL_TEMPLATES)
    all_t.update(_load_user_tool_templates())
    return all_t


def get_tool_template(name: str) -> list[dict] | None:
    if name in PRESET_TOOL_TEMPLATES:
        return [dict(t) for t in PRESET_TOOL_TEMPLATES[name]]
    user = _load_user_tool_templates()
    if name in user:
        return [dict(t) for t in user[name]]
    return None


def save_tool_template(name: str, tools: list[dict]) -> None:
    user = _load_user_tool_templates()
    user[name] = tools
    _TOOL_TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_TOOL_TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(user, f, indent=2, ensure_ascii=False)


def _load_user_tool_templates() -> dict[str, list[dict]]:
    if _TOOL_TEMPLATES_FILE.exists():
        with open(_TOOL_TEMPLATES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}
