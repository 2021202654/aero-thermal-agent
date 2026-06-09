# 02 工具链

## 状态：✅ 9 个工具全部实现

| # | 工具 | 文件 | 功能 |
|---|------|------|------|
| 1 | `LiteratureSearchTool` | `../tools/search.py` | CSV 关键词 + FAISS 语义检索（3,326 篇文献库） |
| 2 | `WebSearchTool` | `../tools/web_search.py` | OpenAlex API 全球学术文献搜索（2.5 亿+ 论文） |
| 3 | `AeroThermalComputeTool` | `../tools/compute.py` | 驻点热流 / Knudsen / 催化系数 / 单位换算 / 边界层厚度 |
| 4 | `CodeExecutionTool` | `../tools/code_exec.py` | Python 子进程沙箱（30s 超时，支持 pip install） |
| 5 | `CitationResolverTool` | `../tools/citation.py` | CrossRef / OpenAlex DOI 解析 + BibTeX 生成 |
| 6 | `PDFAnalysisTool` | `../tools/pdf_parser.py` | PyMuPDF 论文解析（元数据/全文/章节/参数/搜索） |
| 7 | `ReportTool` | `../tools/report.py` | 结构化 Markdown 研究报告生成 |
| 8 | `ExportFindingTool` | `../tools/report.py` | 单条研究发现追加记录 |
| 9 | `PandocExportTool` | `../tools/pandoc_export.py` | Markdown → LaTeX / DOCX / PDF（XeLaTeX + CJK） |

### 工具定义规范

所有工具继承 `core.action.Action`，实现 `async run()` 方法。自动导出 OpenAI function-calling JSON Schema。

```python
from core.action import Action

class MyTool(Action):
    name = "my_tool"
    description = "工具描述"
    parameters = {
        "type": "object",
        "properties": {...},
        "required": [...],
    }

    async def run(self, **kwargs) -> str:
        return "result"
```
