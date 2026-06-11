# 05 评测基准

> Agent 综合评测 — 领域知识 + 工具编排 双维度

---

## 评测集

**主文件**：[气固热导Agent综合评测集.md](气固热导Agent综合评测集.md)

| 篇章 | 来源 | 题数 | 满分 | 测什么 |
|------|------|:---:|:---:|------|
| 上篇 G1-G3 | Golden Evaluation (2026-05-11) | 10 | 30 | LLM 领域知识：检索精度 + 推理合成 + 抗幻觉 |
| 下篇 A1-A4 | Agent 评测基准 (2026-06-02) | 18 | 41 | Agent 编排能力：工具选择 + 多步 + 克制 + 鲁棒性 |
| **合计** | | **28** | **71** | |

---

## 评测维度速览

| 维度 | 代号 | 题数 | 满分 | 及格 |
|------|:---:|:---:|:---:|:---:|
| 精确数据提取 | G1 | 3 | 9 | 6 |
| 深度推理合成 | G2 | 4 | 12 | 8 |
| 抗幻觉压力 | G3 | 3 | 9 | 6 |
| 工具选择精度 | A1 | 5 | 10 | 6 |
| 多步任务编排 | A2 | 5 | 15 | 9 |
| 工具滥用防御 | A3 | 4 | 8 | 5 |
| 编排鲁棒性 | A4 | 4 | 8 | 5 |
| **综合** | | **28** | **71** | **46** |

---

## 配置消融矩阵

| 配置 | LLM | RAG | Agent | 工具 | 跑哪些题 |
|:---:|-----|:---:|:---:|------|------|
| C1 | 基座 8B (4-bit) | ❌ | ❌ | ❌ | 上篇 G1-G3 |
| C2 | 基座 8B (4-bit) | ✅ | ❌ | ❌ | 上篇 G1-G3 |
| C3 | 基座 8B (4-bit) | ❌ | ✅ | ✅ 9 tools | 下篇 A1-A4 |
| C4 | 基座 8B (4-bit) | ✅ | ✅ | ✅ 9 tools | 全 28 题 |
| C5 | + LoRA (4-bit) | ✅ | ✅ | ✅ 9 tools | **全 28 题（目标）** |

---

## 当前状态

- [x] 评测集设计完成（28 题 / 6 维度 / 71 分）
- [ ] 自动化评测脚本（`eval_runner.py`）
- [ ] 工具调用精度自动化测试
- [ ] 幻觉自动检测
- [ ] 评测报告模板生成

> 旧版独立评测文件（Golden 10 题 / Agent 18 题）已归档至 `99_archive/20260608_旧评测集归档/`

---

# 05 Evaluation Benchmark

> Comprehensive Agent Evaluation — Domain Knowledge + Tool Orchestration

---

## Evaluation Dataset

**Main file**: [气固热导Agent综合评测集.md](气固热导Agent综合评测集.md)

| Section | Source | Questions | Full Score | What It Tests |
|------|------|:---:|:---:|------|
| Upper: G1-G3 | Golden Evaluation (2026-05-11) | 10 | 30 | LLM Domain Knowledge: Retrieval Precision + Reasoning Synthesis + Anti-Hallucination |
| Lower: A1-A4 | Agent Benchmark (2026-06-02) | 18 | 41 | Agent Orchestration: Tool Selection + Multi-step + Restraint + Robustness |
| **Total** | | **28** | **71** | |

---

## Evaluation Dimensions Overview

| Dimension | Code | Questions | Full Score | Passing |
|------|:---:|:---:|:---:|:---:|
| Precise Data Extraction | G1 | 3 | 9 | 6 |
| Deep Reasoning Synthesis | G2 | 4 | 12 | 8 |
| Anti-Hallucination Stress | G3 | 3 | 9 | 6 |
| Tool Selection Precision | A1 | 5 | 10 | 6 |
| Multi-step Task Orchestration | A2 | 5 | 15 | 9 |
| Tool Misuse Defense | A3 | 4 | 8 | 5 |
| Orchestration Robustness | A4 | 4 | 8 | 5 |
| **Overall** | | **28** | **71** | **46** |

---

## Configuration Ablation Matrix

| Config | LLM | RAG | Agent | Tools | Which Questions |
|:---:|-----|:---:|:---:|------|------|
| C1 | Base 8B (4-bit) | ❌ | ❌ | ❌ | Upper: G1-G3 |
| C2 | Base 8B (4-bit) | ✅ | ❌ | ❌ | Upper: G1-G3 |
| C3 | Base 8B (4-bit) | ❌ | ✅ | ✅ 9 tools | Lower: A1-A4 |
| C4 | Base 8B (4-bit) | ✅ | ✅ | ✅ 9 tools | All 28 questions |
| C5 | + LoRA (4-bit) | ✅ | ✅ | ✅ 9 tools | **All 28 questions (Target)** |

---

## Current Status

- [x] Evaluation dataset design complete (28 questions / 6 dimensions / 71 points)
- [ ] Automated evaluation script (`eval_runner.py`)
- [ ] Automated tool call precision testing
- [ ] Automated hallucination detection
- [ ] Evaluation report template generation

> Legacy standalone evaluation files (Golden 10 questions / Agent 18 questions) archived to `99_archive/20260608_旧评测集归档/`
