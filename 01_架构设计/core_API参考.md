# core/ API 参考

> Agent 核心框架全部公开接口，面向后续开发和调试。
> 版本：v2（2026-06-08），对应 `05_AI_Agent/core/` 全部代码。

---

## 架构关系

```
Agent                          ← 用户唯一直接接触的类
├── LLMInterface + LLMConfig  ← OpenAI 兼容 API 调用
├── Role                       ← 身份/目标/约束/工具注册
│   ├── ActionRegistry        ← 工具注册表
│   ├── Memory                ← 记忆统一接口
│   │   ├── ShortTermMemory   ← 对话滑动窗口
│   │   └── WorkingMemory     ← 研究上下文 KV
│   └── Message               ← 消息体
├── ReActOrchestrator          ← 推理-行动-观察循环
└── PlanExecuteOrchestrator    ← 先规划后执行
```

---

## 1. Agent（顶层入口）

**文件**：`agent.py`
**导出**：`from core import Agent`

用户唯一需要直接接触的类。把 Role + LLM + Orchestrator 组装成可用的 Agent。

### 构造器

```python
Agent(
    llm_config: LLMConfig | None = None,
    name: str = "AeroThermalExpert",
    profile: str = "",
    goal: str = "",
    constraints: list[str] | None = None,
    mode: str = "react",     # "react" | "plan_execute"
    verbose: bool = False,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm_config` | `LLMConfig \| None` | `LLMConfig()` | LLM 连接配置，默认连 `localhost:8000` |
| `name` | `str` | `"AeroThermalExpert"` | Agent 名称，注入 system prompt |
| `profile` | `str` | `""` | 身份描述，如"高超声速气固界面耦合研究专家" |
| `goal` | `str` | `""` | 任务目标 |
| `constraints` | `list[str] \| None` | `None` | 行为约束列表，逐条注入 system prompt |
| `mode` | `str` | `"react"` | 运行模式：`"react"` 或 `"plan_execute"` |
| `verbose` | `bool` | `False` | 开启后打印每步工具调用的名称和结果预览 |

### 方法

#### `equip(action) -> Agent`
装配一个工具（`Action` 子类实例）。返回 `self`，支持链式调用。

```python
agent.equip(LiteratureSearchTool()).equip(AeroThermalComputeTool())
```

#### `equip_many(actions: list) -> Agent`
批量装配工具。

```python
agent.equip_many([LiteratureSearchTool(), AeroThermalComputeTool()])
```

#### `async run(task: str) -> Message`
运行 Agent，处理一个任务。这是**主入口**。

```python
reply = await agent.run("比较 SiO₂ 和 SiC 在 2000K 下的催化复合系数")
print(reply.content)       # Agent 的最终文本回答
print(reply.metadata)      # {"steps": 3, "tool_call_history": [...]}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 用户的问题或指令 |
| 返回值 | `Message` | Agent 最终回答，`role="agent"` |

内部流程：
1. 调用 `role.build_system_prompt()` 构建 system prompt
2. 根据 `mode` 选择 `ReActOrchestrator.run()` 或 `PlanExecuteOrchestrator.run()`
3. 返回最终 Message

#### `run_sync(task: str) -> Message`
同步封装。**不能在已有事件循环的环境中调用**（否则抛出 `RuntimeError`）。

```python
reply = agent.run_sync("什么是 Knudsen 数")
```

#### `describe() -> str`
返回 Agent 当前状态的文本描述（角色、模式、LLM 端点、工具列表）。

```python
print(agent.describe())
# Role: AeroThermalExpert
# Mode: react
# LLM: qwen-plus @ https://dashscope.aliyuncs.com/compatible-mode/v1
# Tools (9): search_literature, web_search, compute_aerothermal, ...
```

#### `async close()`
关闭 httpx 客户端连接。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `registry` | `ActionRegistry` | 工具注册表（快捷引用 `role.registry`） |
| `memory` | `Memory` | 记忆系统（快捷引用 `role.memory`） |

---

## 2. LLMConfig + LLMInterface

**文件**：`llm.py`
**导出**：`from core import LLMConfig, LLMInterface`

### LLMConfig

```python
LLMConfig(
    base_url: str = "http://localhost:8000/v1",
    api_key: str = "not-needed",
    model: str = "aero-thermal-expert",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    timeout: float = 120.0,
)
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_url` | `str` | `"http://localhost:8000/v1"` | OpenAI 兼容 API 地址 |
| `api_key` | `str` | `"not-needed"` | API Key（vLLM 本地不需要） |
| `model` | `str` | `"aero-thermal-expert"` | 模型名，发给 API 的 `model` 字段 |
| `temperature` | `float` | `0.3` | 生成温度，0-2 |
| `max_tokens` | `int` | `2048` | 单次生成最大 token 数 |
| `timeout` | `float` | `120.0` | HTTP 请求超时秒数 |

**预设参考**（来自 `config.py`）：

| 预设 | base_url | model |
|------|----------|-------|
| vllm_local | `http://localhost:8000/v1` | `aero-thermal-expert` |
| bailian | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| ollama | `http://localhost:11434/v1` | `llama3.1:8b` |
| custom | 用户指定 | 用户指定 |

### LLMInterface

```python
LLMInterface(config: LLMConfig | None = None)
```

#### `async chat(messages: list[Message]) -> Message`
纯文本对话，不带工具。返回 `Message(role="agent")`，`metadata` 含 `usage`。

```python
reply = await llm.chat([Message.system(sys_prompt), Message.user(question)])
print(reply.content)
print(reply.metadata["usage"])  # {"prompt_tokens": 120, "completion_tokens": 300, ...}
```

#### `async chat_with_tools(messages: list[Message], tools: list[dict]) -> Message`
工具增强对话。返回的 Message 可能含 `tool_calls` 字段。

```python
response = await llm.chat_with_tools(messages, tool_schemas)
if response.tool_calls:
    for tc in response.tool_calls:
        print(tc["function"]["name"], tc["function"]["arguments"])
else:
    print(response.content)  # LLM 直接回答
```

#### `async close()`
关闭 httpx 客户端。

---

## 3. Role

**文件**：`role.py`
**导出**：`from core import Role`

Agent 的身份与行为核心。仿 MetaGPT Role，去掉了多 Agent 通信机制。

### 构造器

```python
Role(
    name: str,
    profile: str = "",
    goal: str = "",
    constraints: list[str] | None = None,
)
```

### 方法

#### `equip(action) -> Role`
装备一个工具。返回 `self`。

#### `equip_many(actions: list) -> Role`
批量装备工具。

#### `build_system_prompt() -> str`
根据 `name/profile/goal/constraints` 构建 system prompt 字符串。
每次 `Agent.run()` 调用时自动执行。如果 system prompt 不满足需求，可以在 Agent 层覆盖 role 的 profile/goal/constraints 参数。

```python
>>> role.build_system_prompt()
你是 AeroThermalExpert，高超声速气固界面耦合研究专家。
你的目标是：辅助研究者进行文献检索、多步推理、证据合成。
你必须遵守以下约束：
- 引用必须可溯源
- 不确定时明确标注
...
```

#### `system_message() -> Message`
返回 `Message.system(build_system_prompt())`。

#### `describe() -> str`
返回角色的文本描述。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 角色名称 |
| `profile` | `str` | 身份描述 |
| `goal` | `str` | 任务目标 |
| `constraints` | `list[str]` | 行为约束 |
| `registry` | `ActionRegistry` | 工具注册表 |
| `memory` | `Memory` | 记忆系统 |

---

## 4. Action + ActionRegistry

**文件**：`action.py`
**导出**：`from core import Action, ActionRegistry`

### Action（抽象基类）

所有工具的父类。继承它，实现 `run()`，就是一个 Agent 可用的工具。

```python
class Action(ABC):
    name: str = ""           # 工具名，OpenAI function name
    description: str = ""    # 工具描述，注入 LLM context
    parameters: dict = {}    # OpenAI function-calling JSON Schema

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """执行工具逻辑。接收 LLM 传入的参数，返回字符串结果。"""
        ...
```

**三个必须覆盖的字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 全局唯一工具名，如 `"search_literature"` |
| `description` | `str` | 给 LLM 看的工具说明，影响工具选择准确率 |
| `parameters` | `dict` | JSON Schema，描述参数名/类型/是否必填 |

**一个必须实现的方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `run()` | `async def run(self, **kwargs) -> str` | 执行逻辑，返回值作为 `tool_result` 注入对话上下文 |

#### `to_openai_schema() -> dict`
导出为 OpenAI function-calling 格式，供 `chat_with_tools()` 使用。无需手动调用。

### ActionRegistry

管理工具集合。提供注册、查询、Schema 导出。

```python
registry = ActionRegistry()
registry.register(SearchAction())
registry.register_many([Action1(), Action2()])
```

#### 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `register(action)` | `(Action) -> None` | 注册单个工具，`name` 为空时抛 `ValueError` |
| `register_many(actions)` | `(list[Action]) -> None` | 批量注册 |
| `get(name)` | `(str) -> Action \| None` | 按名称获取工具 |
| `list_names()` | `() -> list[str]` | 返回所有已注册工具名 |
| `to_openai_schemas()` | `() -> list[dict]` | 导出全部工具的 OpenAI Schema |
| `__len__()` | `() -> int` | 已注册工具数 |

---

## 5. Message

**文件**：`message.py`
**导出**：`from core import Message`

基于 Pydantic `BaseModel`，Agent 内外部通信的基本单元。

### 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `role` | `str` | `"user"` | `"user"` / `"agent"` / `"system"` / `"tool"` |
| `content` | `str` | `""` | 消息文本内容 |
| `tool_calls` | `list[dict] \| None` | `None` | OpenAI function-calling 格式的工具调用请求 |
| `tool_call_id` | `str \| None` | `None` | 工具调用 ID（tool 消息专用） |
| `tool_name` | `str \| None` | `None` | 工具名（tool 消息专用） |
| `metadata` | `dict` | `{}` | 附加元数据（usage、steps、plan 等） |
| `timestamp` | `str` | 自动生成 | ISO 格式时间戳 |

### 工厂方法

```python
msg_user   = Message.user(content="问题", **meta)        # role="user"
msg_agent  = Message.agent(content="回答", steps=3, ...)  # role="agent"
msg_system = Message.system(content="系统指令")            # role="system"
msg_tool   = Message.tool_result(content="结果",           # role="tool"
                                  tool_call_id="call_1",
                                  tool_name="search")
```

### 实例方法

#### `to_openai() -> dict`
转为 OpenAI Chat Completions API 格式的 dict。内部使用，通常不需要手动调用。

```python
>>> Message.user("你好").to_openai()
{"role": "user", "content": "你好"}
```

---

## 6. Memory 系统

**文件**：`memory.py`
**导出**：`from core import Memory, ShortTermMemory, WorkingMemory`

### Memory（统一接口）

```python
Memory(short_max_tokens: int = 8000)
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `short` | `ShortTermMemory` | 短期记忆（对话窗口） |
| `working` | `WorkingMemory` | 工作记忆（任务状态） |

| 方法 | 说明 |
|------|------|
| `add_message(msg)` | 将消息加入短期记忆并自动截断 |
| `get_conversation()` | 返回短期记忆的全部消息 |
| `clear()` | 清空短期 + 工作记忆 |

### ShortTermMemory

滑动窗口消息队列。自动按估算 token 数截断。

```python
ShortTermMemory(max_tokens: int = 8000)
```

| 方法 | 说明 |
|------|------|
| `add(msg)` | 追加消息，自动触发 `_trim()` |
| `get_all()` | 返回全部消息的副本 |
| `get_recent(n=10)` | 返回最近 n 条消息 |
| `clear(keep_system=True)` | 清空消息，默认保留 system message |

**截断策略**：
- token 估算：`sum(len(m.content)) // 2`（保守估算，中文实际约 1.5 char/token）
- 删除顺序：从最老的非 system 消息开始删
- system message 始终保留

### WorkingMemory

当前研究任务的上下文 KV 存储。存结构化状态，不存对话文本。

```python
WorkingMemory()
```

| 方法 | 签名 | 说明 |
|------|------|------|
| `set(key, value)` | `(str, Any) -> None` | 设置键值 |
| `get(key, default=None)` | `(str, Any) -> Any` | 获取键值 |
| `append(key, value)` | `(str, Any) -> None` | 追加到列表型字段（不存在则自动创建空列表） |
| `snapshot()` | `() -> dict` | 返回摘要：仅含 `search_keywords` / `read_papers` / `intermediate_results` |
| `clear()` | `() -> None` | 清空全部 KV |

**标准 key 约定**：

| Key | 类型 | 说明 |
|------|------|------|
| `search_keywords` | `list[str]` | 本次任务已用的检索词 |
| `read_papers` | `list[str]` | 已阅读/引用的论文 DOI |
| `retrieved_snippets` | `list[str]` | 检索到的文本片段 |
| `intermediate_results` | `list` | 多步推理中间结果 |
| `task_state` | `str` | 当前任务状态机阶段 |
| `tool_calls` | `list[dict]` | 工具调用历史（Orchestrator 自动写入） |
| `plan` | `list[str]` | Plan-Execute 模式的任务分解（Orchestrator 自动写入） |

---

## 7. 编排引擎

**文件**：`orchestrator.py`
**导出**：`from core import ReActOrchestrator, PlanExecuteOrchestrator`

### ReActOrchestrator

推理-行动-观察循环。适合开放式探索任务。

```python
ReActOrchestrator(llm: LLMInterface, max_steps: int = 8)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm` | `LLMInterface` | — | LLM 接口实例 |
| `max_steps` | `int` | `8` | 最大工具调用步数，防止无限循环 |

#### `async run(task, role_context, memory, registry) -> Message`

**内部流程**：

```
User Input
  → LLM(think)
    → 返回 content → 任务完成，返回最终回答
    → 返回 tool_calls → 逐一执行工具
      → 结果注入对话历史
      → 回到 LLM(think)，steps++
      → 达到 max_steps → 截断，返回部分结果 + 状态快照
```

**返回的 Message.metadata**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `steps` | `int` | 实际执行的工具调用步数 |
| `tool_call_history` | `list[dict]` | 工具调用历史 |

### PlanExecuteOrchestrator

先规划后执行。适合结构化多步任务。

```python
PlanExecuteOrchestrator(llm: LLMInterface, max_plan_steps: int = 6, max_react_steps: int = 4)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm` | `LLMInterface` | — | LLM 接口实例 |
| `max_plan_steps` | `int` | `6` | 最大计划步骤数 |
| `max_react_steps` | `int` | `4` | 每个子步骤内的最大 ReAct 步数 |

**内部流程**：

```
Phase 1: Plan
  User task → LLM 分解为 ≤ max_plan_steps 步

Phase 2: Execute（每步独立 mini ReAct）
  Step 1 → ReActOrchestrator(max_steps=max_react_steps) → result_1
  Step 2 → ReActOrchestrator(max_steps=max_react_steps) → result_2
  ...

Phase 3: Synthesize
  汇总 step_results → LLM 综合 → 最终回答
```

**返回的 Message.metadata**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `plan` | `list[str]` | 任务分解的步骤列表 |
| `step_results` | `list[dict]` | 每步的 `{"step": str, "result": str}` |

---

## 8. 典型用法汇总

### 最小示例

```python
from core import Agent, LLMConfig

agent = Agent(
    llm_config=LLMConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-xxx",
        model="qwen-plus",
    ),
    name="AeroThermalExpert",
    profile="高超声速气固界面耦合研究专家",
    mode="react",
    verbose=True,
)

reply = await agent.run("计算马赫数15、高度55km下的驻点热流密度")
print(reply.content)
await agent.close()
```

### 完整装配

```python
from core import Agent, LLMConfig
from tools import (
    LiteratureSearchTool, WebSearchTool, AeroThermalComputeTool,
    CodeExecutionTool, CitationResolverTool, PDFAnalysisTool,
    ReportTool, ExportFindingTool, PandocExportTool,
)

agent = Agent(
    llm_config=LLMConfig(model="qwen-plus", base_url="...", api_key="..."),
    profile="高超声速气固界面耦合研究专家",
    constraints=[
        "所有引用必须可溯源到具体文献",
        "不确定的数值必须明确标注",
        "编造文献等于学术不端，严格禁止",
    ],
    mode="react",
)

agent.equip_many([
    LiteratureSearchTool(),
    WebSearchTool(),
    AeroThermalComputeTool(),
    CodeExecutionTool(),
    CitationResolverTool(),
    PDFAnalysisTool(),
    ReportTool(),
    ExportFindingTool(),
    PandocExportTool(),
])

reply = await agent.run(
    "评估气固界面催化模型在跨尺度条件下的适用性，检索相关文献，"
    "对比 SiO₂ 和 SiC 在 2000K 下的催化系数，生成研究报告"
)
print(reply.content)
```

### Plan-Execute 模式

```python
agent = Agent(mode="plan_execute", ...)
# 同样装配工具...

reply = await agent.run(
    "系统性地比较 5 种 TPS 材料（SiO₂, SiC, Al₂O₃, C-Phenolic, RCG）"
    "的催化复合系数，并评估其在火星再入条件下的热防护性能排名"
)
# Agent 会自动：
# 1. 制定计划（分解为 N 步）
# 2. 逐步执行（每步独立 ReAct）
# 3. 综合回答
```

### 新增自定义工具

```python
from core import Action

class UnitConverterTool(Action):
    name = "convert_units"
    description = "转换物理量单位。支持热流(W/cm²↔kW/m²↔MW/m²)、温度(K↔°C↔°F)、压力(Pa↔atm↔bar)"
    parameters = {
        "type": "object",
        "properties": {
            "value": {"type": "number", "description": "数值"},
            "from_unit": {"type": "string", "description": "源单位"},
            "to_unit": {"type": "string", "description": "目标单位"},
        },
        "required": ["value", "from_unit", "to_unit"],
    }

    async def run(self, value, from_unit, to_unit):
        # 实现转换逻辑
        result = self._convert(value, from_unit, to_unit)
        return f"{value} {from_unit} = {result} {to_unit}"

# 装配到 Agent
agent.equip(UnitConverterTool())
```
