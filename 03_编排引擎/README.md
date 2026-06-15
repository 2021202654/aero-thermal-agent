# 03 编排引擎

## 状态：✅ 已实现

### 已实现

| 模式 | 文件 | 说明 |
|------|------|------|
| **ReAct** | `../core/orchestrator.py -> ReActOrchestrator` | 推理-行动-观察循环，适合开放式探索 |
| **Plan-Execute** | `../core/orchestrator.py -> PlanExecuteOrchestrator` | 先规划后执行，适合结构化多步任务 |

### 安全特性

| 特性 | 说明 |
|------|------|
| **JSON 解析异常保护** | 工具参数格式错误不崩溃，返回格式友好的错误提示 |
| **LRU 有界缓存** | `_BoundedCache`（max=100），相同工具+参数去重，防止无限循环和内存耗尽 |
| **max_steps 上限** | 最多 `max_react_steps` 步（默认 15），防止无限循环 |
| **自省循环** | `critique_rounds`（默认 2 轮），初版答案生成后 LLM 自审并修订，提高答案质量 |

### ReAct 循环

```text
User Input -> LLM(think) -> tool_call? --Yes--> execute tool -> observe -> LLM(think)
                               |
                               No -> Self-Critique (N rounds) -> Final Answer
```

- 最多 `max_react_steps` 步（默认 15）防止无限循环
- 每步工具结果自动追加到对话上下文
- **自省循环**（默认 2 轮）：初版答案生成后，LLM 充当审稿人指出弱点 → 修订 → 再审，直至收敛或达到轮数上限；可配置为 `0` 禁用

### Plan-Execute 循环

```text
User Input -> Make Plan -> Step1(miniReAct) -> Step2 -> ... -> Synthesize
```

- 计划阶段：LLM 将任务分解为 <= `max_plan_steps` 步
- 执行阶段：每步是独立的 mini ReAct 循环
- 合成阶段：汇总所有步骤，生成结构化最终回答
