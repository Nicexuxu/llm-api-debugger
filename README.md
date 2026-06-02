# OpenAI Chat API 调试工具

基于 Python TUI 的 OpenAI Chat Completions API 交互式调试工具。支持构建/编辑/发送请求、查看完整 HTTP 请求与响应、多轮对话管理、工具调用（function calling）、DeepSeek 思考模式等。兼容所有 OpenAI 接口格式的大模型服务。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建配置文件 config.json
# 在项目根目录创建，内容见下方「配置文件」章节

# 3. 启动
python main.py
```

## 配置文件

`config.json` 放在项目根目录：

```json
{
  "api_key": "sk-你的API密钥",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat"
}
```

| 字段 | 说明 |
|------|------|
| `api_key` | API 密钥 |
| `base_url` | API 端点地址，支持所有兼容 OpenAI Chat Completions 接口的服务 |
| `model` | 默认模型名称，启动后可在应用内切换 |

常见服务的 `base_url`：

| 服务商 | base_url |
|--------|----------|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

> `config.json` 包含 API 密钥，已加入 `.gitignore`。

## 界面布局

```
┌──────────────────────────────────────────────────┐
│  OpenAI Chat API Debugger                        │
├────────────────────┬─────────────────────────────┤
│ 配置               │  消息列表                    │
│ model: deepseek... │  [1] User: 北京天气怎样？    │
│ base_url: https:// │  [2] Assistant:             │
│ api_key: sk-xxx... │    [思考] 用户想知道北京...   │
│                    │    [工具调用] get_weather()   │
│ 参数               │    [回复] 让我查询一下...     │
│ temperature: 0.7   │                              │
│                    │  响应                        │
│                    │  模型最终回复内容...          │
├────────────────────┴─────────────────────────────┤
│ 消息数: 5 | 工具: 2 | 思考: 开 | 流式: 开        │
├──────────────────────────────────────────────────┤
│ > █                                              │
└──────────────────────────────────────────────────┘
```

- **左上** — 当前配置（model、base_url、api_key 脱敏显示）
- **右上** — 消息列表，每条消息显示角色标签 + 思考/工具调用/回复分段（超 250 字符截断为 3 行）
- **左下** — 当前参数
- **右下** — 最近一次 API 返回的完整响应内容
- **底部** — 状态栏 + 命令输入提示符 `>`

## 命令参考

### 消息管理

| 命令 | 说明 |
|------|------|
| `直接输入文本` | 作为 user 消息追加到对话末尾 |
| `system <文本>` | 设置 system 消息（仅保留一条，重复执行会覆盖） |
| `user <文本>` | 添加 user 消息 |
| `assistant <文本>` | 添加 assistant 消息（手动构造对话历史） |
| `del` | 删除最后一条 user 消息（撤销误输入） |
| `clear` | 清空全部消息、响应和用量信息 |

### 请求发送

| 命令 | 说明 |
|------|------|
| `send` | 按当前模式发送请求（流式/非流式） |
| `stream` | 切换流式模式，默认**开** |
| `show` | 查看完整 HTTP 请求（URL + Headers + JSON Body），含完整 API Key |
| `edit` | 将当前请求 JSON 写入临时文件，用外部编辑器打开，保存后自动同步回会话 |

`edit` 工作流程：构建 payload → 写入临时 JSON → 打开编辑器（默认 notepad，可通过 `EDITOR` 环境变量配置）→ 关闭后读回 → 验证 JSON 格式 → 同步 model、messages、params、tools 到当前会话。

自定义编辑器示例：
```bash
export EDITOR="code --wait"
python main.py
```

### 模型与参数

| 命令 | 说明 |
|------|------|
| `model` | 查看当前模型 |
| `model <模型名>` | 切换模型，同时保存到 config.json |
| `param <key> <value>` | 设置参数，值支持 JSON 解析 |
| `param rm <key>` | 删除参数，恢复默认值 |
| `think` | 切换 DeepSeek 思考模式（开/关），默认**开** |

支持的参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `temperature` | float | 采样温度 0.0-2.0 |
| `max_tokens` | int | 最大输出 token 数 |
| `top_p` | float | 核采样参数 |
| `stop` | string/array | 停止序列 |
| `frequency_penalty` | float | 频率惩罚 -2.0 到 2.0 |
| `presence_penalty` | float | 存在惩罚 -2.0 到 2.0 |
| `seed` | int | 随机种子 |
| `reasoning_effort` | string | 思考强度，DeepSeek 支持 `high` / `max` |

示例：
```
> param temperature 0.7
> param max_tokens 2048
> param stop '["word1","word2"]'
> param rm temperature
```

### 工具调用（Function Calling）

| 命令 | 说明 |
|------|------|
| `tool list` | **交互式多选**工具模板：`[✓]` 标记已激活模板，输入编号切换，回车确认，`q` 取消 |
| `tool load <模板名>` | 加载工具模板并**合并**到当前工具声明（不覆盖，按函数名去重） |
| `tool show` | 查看当前工具声明详情 |
| `tool add <JSON>` | 手动添加工具声明（JSON 对象或数组） |
| `tool save <名称>` | 保存当前工具声明为用户模板 |
| `tool clear` | 清空工具声明 |
| `result` | **逐个交互填写**所有待处理的工具调用结果 |
| `result <文本>` | 快捷方式：自动填入第一个待处理的 tool_call_id |
| `result <id> <文本>` | 显式指定 tool_call_id |

**多工具调用回传**：当模型一次返回多个 tool_calls 时，`result`（无参数）会逐个引导用户填写，显示进度 `(1/3)`、`(2/3)`... ，确保每个 tool_call_id 都有对应的 tool result 消息。输入 `skip` 跳过当前工具，空输入取消剩余填写。

**工具模板合并逻辑**：`tool list` 多选和 `tool load` 均采用累加模式——加载新模板不会覆盖已有工具，按函数名去重。同一函数名的工具只会保留一份。

工具调用完整流程示例：
```
> 北京今天天气怎么样？
> send
  [模型返回 tool_calls: get_weather(location="北京")]
> result
  工具调用 (1/1): get_weather
  模型入参: {"location": "北京"}
  结果: 晴天，25°C
> send
  [模型收到结果，返回最终回复]
```

### 模板管理

| 命令 | 说明 |
|------|------|
| `templates` | 列出所有对话模板（预设 + 用户） |
| `load <模板名>` | 加载对话模板；未找到对话模板时自动尝试加载工具模板 |
| `save <模板名>` | 保存当前会话为对话模板（含消息、参数、工具声明） |

**预设对话模板：**

| 名称 | 说明 | temperature |
|------|------|-------------|
| `translate` | 专业翻译（中译英） | 0.3 |
| `summarize` | 文本摘要 | 0.5 |
| `coder` | 代码编写，简洁风格 | 0.2 |
| `explain` | 概念解释，面向初学者 | 0.7 |

**预设工具模板：**

| 名称 | 包含函数 | 说明 |
|------|---------|------|
| `weather` | get_weather | 天气查询 |
| `date` | get_date | 日期查询 |
| `search` | web_search | 网页搜索 |
| `calculator` | calculate | 数学计算 |
| `weather+date` | get_weather, get_date | 天气+日期组合 |
| `filesystem` | read_file, write_file, list_dir | 文件系统操作 |

示例：
```
> load translate
> user 人工智能正在改变世界
> send

> tool load weather+date
> tool load filesystem
> tool list
  [✓] 1. weather+date (预设) — get_weather, get_date
  [✓] 2. filesystem (预设) — read_file, write_file, list_dir
```

### 其他

| 命令 | 说明 |
|------|------|
| `config` | 查看配置文件格式说明 |
| `?` / `help` | 显示完整命令帮助 |
| `quit` / `q` | 退出程序 |

## 典型使用场景

### 场景一：简单对话

```
> system 你是资深 Python 工程师，回答简洁，只给代码。
> user 写一个读取 CSV 并统计每列平均值的函数
> send
```

### 场景二：多轮对话 + 参数对比

```
> system 你是一个有创意的作家
> user 写一个科幻故事的开头
> param temperature 0.3
> send
  （记录回复）
> param temperature 0.9
> send
  （对比差异）
```

### 场景三：工具调用 + 多工具并行

```
> tool list
  （勾选 weather、date 两个模板）
> user 北京和上海的天气分别怎样？先告诉我今天的日期。
> send
  [模型返回 3 个 tool_calls: get_date, get_weather("北京"), get_weather("上海")]
> result
  工具调用 (1/3): get_date
  结果: 2026-06-02
  工具调用 (2/3): get_weather
  模型入参: {"location": "北京"}
  结果: 晴天，25°C
  工具调用 (3/3): get_weather
  模型入参: {"location": "上海"}
  结果: 多云，28°C
> send
  [模型整合所有结果，返回完整回复]
```

### 场景四：手动编辑 Payload 调试

```
> user hello
> show
  （查看完整 HTTP 请求）
> edit
  （在编辑器中修改 JSON，添加/删除字段，调整参数）
> send
  （发送修改后的请求）
```

### 场景五：思考模式调试

```
> think              （确认思考模式已开启）
> user 解释一下量子纠缠
> send
  [思考过程以斜体暗色实时显示]
  [回复正文以品红色显示]
  [思考内容保存在消息历史中，后续轮次自动回传]
```

## 思考模式（DeepSeek reasoning_content）

- 默认开启，通过 `think` 命令切换
- 思考内容在流式输出中以暗色斜体实时渲染
- 每条 assistant 消息保留 `reasoning_content`，后续请求原样回传
- 工具调用场景下 `reasoning_content` **必须**随消息回传，否则 API 返回 400 — 项目已默认处理
- 关闭思考后请求不再发送 `thinking` 参数

## 历史记录

每次启动自动在 `history/` 下创建会话目录（格式 `YYYYMMDD_HHMMSS`），每次 `send` 保存：

```
history/20260602_223738/
├── 001_request.json
├── 001_response.json
├── 002_request.json
├── 002_response.json
├── ...
```

- `_request.json` — 完整 HTTP 请求（URL + Headers + JSON Body，含完整 API Key）
- `_response.json` — 完整 HTTP 响应

## 项目结构

```
├── main.py                  # 入口
├── config.json              # 配置文件（需自行创建）
├── requirements.txt         # 依赖
│
├── config/
│   └── settings.py          # 配置加载/保存（Settings dataclass）
│
├── api/
│   └── client.py            # HTTP 客户端（httpx 封装、流式 SSE 解析、错误处理）
│
├── payload/
│   ├── builder.py           # 从会话状态构建完整 Chat Completions payload
│   └── templates.py         # 预设/用户模板管理（对话模板 + 工具模板）
│
├── tui/
│   ├── app.py               # TUI 主循环 + 状态管理 + 全部命令实现
│   ├── screens.py           # 主界面布局渲染
│   └── display.py           # rich 渲染辅助（消息列表、响应、帮助等）
│
└── history/                 # 请求/响应历史（自动创建）
```

## 依赖

| 包 | 版本 | 用途 |
|----|------|------|
| `httpx` | >=0.27.0 | HTTP 请求、流式 SSE 解析 |
| `rich` | >=13.0.0 | 终端 UI 渲染（Panel、Syntax、Table 等） |

## 常见问题

**Q: 启动报 "Config file not found"**

需要创建 `config.json`，参考上方「配置文件」章节。

**Q: 工具调用报 400 "missing field 'type'"**

DeepSeek 要求 tool_calls 数组中每个对象包含 `"type": "function"`。项目已在流式合并和非流式路径中自动补齐。

**Q: 多个工具调用报 400 "insufficient tool messages"**

每个 tool_call_id 必须有对应的 tool 结果消息。使用 `result`（无参数）逐个填写所有待处理的工具调用，确保不漏填。

**Q: 思考模式在工具调用时如何回传？**

DeepSeek 要求工具调用场景下 `reasoning_content` 必须随 assistant 消息回传。项目默认保存并回传所有 assistant 消息的 `reasoning_content`，无需手动处理。

**Q: 如何用 VS Code 作为外部编辑器？**

```bash
export EDITOR="code --wait"
python main.py
```
