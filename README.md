# tv-guider

Verilog 时序违例分析与大模型辅助修复项目，目前处于从论文实验实现整理为基础可用版本的阶段。

## 当前目录

| 位置 | 内容 |
| --- | --- |
| [legacy/](C:/Users/anwen/Desktop/tv-guider/legacy/README.md) | 旧版方法实现、实验脚本、输入与结果归档 |
| [docs/notes/](C:/Users/anwen/Desktop/tv-guider/docs/notes/2026-09-24-codegraph-exploration.md) | 项目探索与分析记录 |
| [docs/spec/](C:/Users/anwen/Desktop/tv-guider/docs/spec/method-modules.md) | 方法模块关系与各能力的规格文档 |
| [docs/plans/](C:/Users/anwen/Desktop/tv-guider/docs/plans/rag-knowledge-base.md) | 对应 Spec 的实施任务、验证和交付安排 |
| `.codegraph/` | 当前项目的代码地图索引 |
| `.idea/` | 保留的本地 IDE 配置，尚未针对归档后的路径调整 |

2026-09-24 已将原有业务代码和实验材料整体移入 `legacy/`。新版 RAG 实现在 `src/rag/`，通过 Python API 与 `python -m rag` 使用；旧实验归档不纳入新版 Git 仓库。

从 VioAdvisor 复用的 TVIR 实现已接入 `src/tvir/`。本次仅移植、清理注释和格式化，保留原有运行逻辑；原始功能代码归档在 `legacy2/`。`docs/`、`legacy2/` 和验证产物均不纳入 Git。

建议先阅读 [代码探索记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/2026-09-24-codegraph-exploration.md)，了解已经实现的能力、未完成部分及验证范围。

方法由 TVIR 构建、RAG 知识库构建与检索、根因分析、修复结果生成四个核心模块组成，输入是 RTL 代码与对应的 STA 时序报告。详见 [方法模块与关系](C:/Users/anwen/Desktop/tv-guider/docs/spec/method-modules.md)。基础版覆盖 setup、hold，暂不纳入 CDC；先实现独立的 RAG 知识库构建与检索，后续生成类模型优先使用 DeepSeek。项目术语见 [CONTEXT.md](C:/Users/anwen/Desktop/tv-guider/CONTEXT.md)。

[RAG 知识库构建与独立检索 Spec](C:/Users/anwen/Desktop/tv-guider/docs/spec/rag-knowledge-base.md) 定义英文 Markdown、本地 Qwen3-Embedding-0.6B、Qdrant 与 BM25、RRF 混合检索，以及功能和检索效果验收标准。

[RAG 实现计划](C:/Users/anwen/Desktop/tv-guider/docs/plans/rag-knowledge-base.md) 已执行。实际结果见 [验收记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-validation.md)，安装版本和模型指纹机制见 [环境记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-environment.md)。

## 使用 RAG

使用已有的 Conda `TVGuider` 环境，在项目根目录运行以下命令。模型位于项目外的 `C:/all/tools/llm/models/Qwen3-Embedding-0.6B`，本机已经安装并完成真实编码验证。新机器先按环境记录安装依赖，再运行 `python scripts/provision_model.py` 下载固定版本。

```powershell
conda run -n TVGuider python -m rag build --source knowledge/raw --kb artifacts/rag/kb --config configs/rag.yaml
conda run -n TVGuider python -m rag search --kb artifacts/rag/kb --query "What causes a setup violation on a long combinational path?"
conda run -n TVGuider python -m rag search --kb artifacts/rag/kb --query "Why does a short data path cause a hold violation?" --mode bm25 --top-k 5
```

默认 `hybrid`、`top_k=5`，也支持 `dense`、`bm25`。成功时 stdout 输出 JSON；失败时 stderr 给出错误类别、退出码非零。响应包含 build ID、参数、排名及 `results[].chunk` 中的正文、标题路径、来源和原始正文行范围；它不调用生成模型，也不生成 RTL 修复。

```python
from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import load_config

report = build_knowledge_base("knowledge/raw", "artifacts/rag/kb", load_config("configs/rag.yaml"))
response = search_knowledge_base("artifacts/rag/kb", "How can pipeline registers improve setup timing?")
for hit in response.results:
    print(hit.rank, hit.chunk.document_id, hit.chunk.heading_path, hit.chunk.text)
```

六份英文资料位于 `knowledge/raw/`，来源和适用条件见 [资料登记](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-source-register.md)。递归扫描 `.md`，每份需要 YAML 字段 `id`、`title`、`topics`、`sources`。新增、修改或删除资料后执行完整 build；失败不会覆盖当前成功版本。

配置在 `configs/rag.yaml`，默认每块最多 1024 tokens，正文重叠最多 128 tokens。模型路径可调整；模型、编码精度、分块或索引依赖变更后重建。CPU 部署可将 `device` 改成 `cpu` 后重建，本次真实验收使用 CUDA/float32。

构建产物位于 `artifacts/rag/kb/generations/`，`current.json` 指向当前成功版本；模型和 `artifacts/` 均不进入 Git。旧的成功版本暂时保留，本版不提供历史版本查询或并发服务。

## 使用 TVIR

入口是 `tvir.api.build_tvir_dicts_from_vivado_report_and_rtl(report_text, rtl_text)`，接收 Vivado 报告文本和对应 RTL 文本，返回 TVIR 字典列表。默认仅处理负 slack 路径；`only_violations=False` 可包含非违例路径。当前没有新增 CLI，也未接入根因分析、RAG 或修复生成。

Python 依赖包含 `pyverilog==1.3.0`，同时要求系统 PATH 可找到 Icarus Verilog 的 `iverilog`。现有 `TVGuider` Conda 环境已完成依赖安装。Pyverilog 会在运行目录生成解析器文件，验证时使用临时工作目录。

已使用 `code_and_xdc` 中三个已有 setup 案例确认迁移前后输出一致，但发现运算链、表达式定位、端口路径建模和缺失报告字段处理的问题；还未完成真实 hold 违例验证，因此当前不代表 TVIR 语义验收通过。输入来源、结果和待修问题见 [TVIR 迁移验证记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/tvir-import-validation.md)。

## 提示词构建

`src/prompts/` 集中管理根因分析和修复建议的提示词，提供 `build_root_cause_prompt(llm_context, language="en")` 与 `build_repair_prompt(llm_context, language="en", allow_custom_strategy=True)` 两个函数，语言等选项为关键字参数。它们接收业务模块准备的可 JSON 序列化上下文并返回字符串，不执行检索或模型调用，也不解析模型响应。

```python
from prompts import build_repair_prompt, build_root_cause_prompt

diagnosis_prompt = build_root_cause_prompt(diagnosis_context)
repair_prompt = build_repair_prompt(repair_context, allow_custom_strategy=False)
```

本次保留旧版中英文模板内容，尚未迁移 `legacy2/root_cause` 和 `legacy2/repair` 的调用方；后续迁移时改为调用上述函数。RAG 上下文接入和完整 RTL 输出要求尚未加入模板，当前 repair 模板仍用于生成修复建议。

## 验证与评估

```powershell
conda run -n TVGuider python -m pytest -q
conda run -n TVGuider python -m pytest -m model -q
conda run -n TVGuider python -m ruff check src tests scripts
conda run -n TVGuider python -m ruff format --check src tests scripts
conda run -n TVGuider python -m rag.evaluate --kb artifacts/rag/kb --dataset evaluation/rag/dev.jsonl --manifest evaluation/rag/manifest.json --output artifacts/rag/evaluation/dev
conda run -n TVGuider python -m rag.evaluate --kb artifacts/rag/kb --dataset evaluation/rag/acceptance.jsonl --manifest evaluation/rag/manifest.json --output artifacts/rag/evaluation/acceptance
```

默认测试不运行模型组；显式 `-m model` 会实际加载本地模型，缺模型会失败。评估输出 `report.json`（逐题 Top-5 和配置）及 `report.md`；验收未达标退出码为 2，输入或运行错误为 1。

TVIR 移植保留了旧代码的 lint 问题，因此上面的全项目 `ruff check` 当前未通过；`ruff check src/rag tests scripts` 与全项目格式检查通过。具体检查结果记录在 TVIR 迁移验证记录中。

开发集 8 问与验收集 20 问分开保存，manifest 固定其用途及 SHA-256。验收要求 hybrid 总体至少 16/20，setup 和 hold 分别至少 8/10。不能使用验收集调参后仍将其作为独立验收；资料变更后的评估需重新审阅标签并显式更新冻结记录。
