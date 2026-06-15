# 06 部署集成

> Agent 全栈部署方案 — DSW vLLM + Gradio

---

## 部署架构

```text
DSW 实例（V100 16GB / A10 24GB）
├── vLLM API Server (localhost:8000)  ← 加载微调模型 aero-thermal-8b
├── Agent Framework                   ← OpenAI 兼容客户端，10 个工具
└── Gradio UI (0.0.0.0:7860)          ← DSW 自动提供公网代理 URL
```

---

## 部署入口

| 入口 | 文件 | 用途 |
|------|------|------|
| CLI | `run_agent.py` | 交互 / 单次问答，`--llm` 选择后端 |
| Gradio | `app.py` | Web UI，`--llm custom` 连 vLLM |

### CLI 示例

```bash
cd 05_AI_Agent

# 百炼 API（即开即用，默认 qwen-plus，支持 Responses API）
python run_agent.py --llm bailian

# DSW vLLM
python run_agent.py --llm custom --base-url http://localhost:8000/v1

# Plan-Execute 模式
python run_agent.py --llm custom --mode plan_execute --task "Evaluate cross-scale applicability of gas-solid interface catalytic model"

# 自省迭代（默认 2 轮，设为 0 可禁用）+ 最大步数上限
python run_agent.py --llm bailian --critique-rounds 2 --max-react-steps 20 -t "Compare catalytic recombination coefficients of SiO2, SiC, RCG at 1500K-3000K"

# Policy Routing + 自动降级（需用户确认）
python run_agent.py --llm bailian --auto-route -t "Identify research gaps in catalytic coefficient modeling and generate hypotheses"
```

### Gradio Web UI

```bash
# DSW 部署（自动获取公网链接）
python app.py --llm custom --port 7860

# 本地开发用百炼
python app.py --llm bailian
```

---

## DSW 部署流程

按 `04_LLM微调线/04_推理部署/` 下 4 个 notebook 顺序执行：

| 步骤 | Notebook | 内容 |
|------|----------|------|
| 0 | `0_DSW环境部署.ipynb` | pip 镜像 + PyTorch CUDA + LLaMA-Factory + vLLM + Pandoc + 中文字体 |
| 1 | `1_模型下载与数据注册.ipynb` | ModelScope 下载 Llama-3.1-8B + 数据集注册 + 校验 |
| 2 | `2_训练与导出.ipynb` | QLoRA 4-bit 训练 + LoRA 合并导出 |
| 3 | `3_推理与Agent部署.ipynb` | vLLM 启动 + Agent 配置 + Gradio UI 上线 |

---

## LLM 后端

| 后端 | 配置 | 适用场景 |
|------|------|----------|
| vLLM (DSW) | `localhost:8000/v1` | 微调模型推理 |
| 百炼 API（qwen-plus） | `dashscope.aliyuncs.com` | Chat Completions API，兼容 function calling |
| 百炼 API（qwen3.5-plus） | `dashscope.aliyuncs.com` | 开发/调试/QA 生成，Responses API |
| 硅基流动（DeepSeek-V3） | `api.siliconflow.cn` | 高性价比推理，1+2 ¥/M tokens |
| Ollama | `localhost:11434/v1` | 本地快速验证 |

`config.py` 提供 5 套预设：`vllm_local` / `bailian` / `siliconflow` / `ollama` / `custom`

> 注意：`bailian` 预设当前使用 `qwen-plus`（Chat Completions + function calling）。如需 Responses API，换用 `qwen3.5-plus`。
