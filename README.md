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

方法由 TVIR 构建、RAG 知识库构建与检索、根因分析、修复结果生成四个核心模块组成，输入是 RTL 代码与对应的 STA 时序报告。详见 [方法模块与关系](C:/Users/anwen/Desktop/tv-guider/docs/spec/method-modules.md)。当前根因分析与修复生成仅覆盖 setup，排除 hold 和 CDC；已建成的独立 RAG 保留原有 setup/hold 资料。生成类模型默认使用 DeepSeek。项目术语见 [CONTEXT.md](C:/Users/anwen/Desktop/tv-guider/CONTEXT.md)。

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

入口是 `tvir.api.build_tvir_dicts_from_vivado_report_and_rtl(report_text, rtl_text)`，接收 Vivado 报告文本和对应 RTL 文本，返回 TVIR 字典列表。默认仅处理负 slack 路径；`only_violations=False` 可包含非违例路径。全流程入口 `src/run_pipeline.py` 调用该接口，然后连接根因分析、RAG 和修复生成。

Python 依赖包含 `pyverilog==1.3.0`，同时要求系统 PATH 可找到 Icarus Verilog 的 `iverilog`。现有 `TVGuider` Conda 环境已完成依赖安装。Pyverilog 会在运行目录生成解析器文件，验证时使用临时工作目录。

已使用 `code_and_xdc` 中三个已有 setup 案例确认迁移前后输出一致，但发现运算链、表达式定位、端口路径建模和缺失报告字段处理的问题；还未完成真实 hold 违例验证，因此当前不代表 TVIR 语义验收通过。输入来源、结果和待修问题见 [TVIR 迁移验证记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/tvir-import-validation.md)。

## 提示词构建

`src/prompts/` 集中管理根因分析和修复建议的提示词，提供 `build_root_cause_prompt(llm_context, language="en")` 与 `build_repair_prompt(llm_context, language="en", allow_custom_strategy=True)` 两个函数，语言等选项为关键字参数。它们接收业务模块准备的可 JSON 序列化上下文并返回字符串，不执行检索或模型调用，也不解析模型响应。

```python
from prompts import build_repair_prompt, build_root_cause_prompt

diagnosis_prompt = build_root_cause_prompt(diagnosis_context)
repair_prompt = build_repair_prompt(repair_context, allow_custom_strategy=False)
```

`src/root_cause/` 和 `src/repair/` 已调用这两个构建函数。模板保留中英文选项，根因标签限定 setup；修复模板接收完整 RTL、设计约束和 RAG 片段，要求返回完整 RTL 候选、修改说明与知识引用。业务模块中不再保存提示词正文。

## 在 PyCharm 中运行完整流程

直接打开 `src/run_pipeline.py`。运行需要填写的配置都在文件开头，包括 `RTL_DIR`、`REPORT_DIR`、`OUTPUT_DIR`、`KB_DIR`、`ENV_FILE`、`LLM_CONFIG`、`DESIGN_CONTEXT`、检索方式、`TOP_K`、`MAX_PATHS` 和 Icarus 路径。输入是目录，不需要指定文件名或填写命令行参数。

1. 在 PyCharm 的 Python Interpreter 设置中选择已有 Conda `TVGuider` 环境，解释器路径为 `C:/all/environments/anaconda3/envs/TVGuider/python.exe`。无需新建虚拟环境。[JetBrains 官方说明](https://www.jetbrains.com/help/pycharm/conda-support-creating-conda-virtual-environment.html)
2. 检查 `src/run_pipeline.py` 开头的目录和模型配置。代码和报告默认指向此前使用的 VioAdvisor `code_and_xdc/all_code/s3_code`、`code_and_xdc/all_reports/s3_reports`；输出默认为项目下 `artifacts/pipeline`，知识库为 `artifacts/rag/kb`。
3. 项目根目录 `.env` 配置 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`。现有 Conda 环境已安装依赖；新环境需安装 `python -m pip install -e ".[llm]"`。
4. 在编辑器中右键 `run_pipeline.py`，选择 **Run 'run_pipeline'**。[JetBrains 官方说明](https://www.jetbrains.com/help/pycharm/running-applications.html)

运行配置的 Parameters 留空。所有相对路径以项目目录为基准；脚本默认从项目根目录读取 `.env`，不依赖 PyCharm 的 Working directory。也可以在项目根目录执行 `python src/run_pipeline.py`。

入口递归扫描 `.v` 代码和 `.txt`/`.rpt` 报告，按相对目录和文件主名配对，例如 `group/design.v` 对应 `group/design.txt`。此规则针对当前一份 RTL 对应一份报告的独立案例。不会将一个多文件设计的所有 RTL 自动拼接，也不会根据不一致的名称猜测对应关系；缺失配对或重复报告会列出问题。默认 `MAX_PATHS=1` 处理每份报告的第一条负 slack 路径；设为 `None` 可处理所有负 slack 路径，存在多条路径时增加 `path-001` 等输出子目录。

执行顺序：RTL/STA → TVIR → 规则根因分析 → 模型根因分析 → 保存根因结果 → RAG 检索 → 修复策略 → 模型修复生成 → 保存修复结果。规则保留 S1–S4；没有新增接口/拍数限制、hold/不同时钟名称拦截，也没有新增 hold/CDC 专用算法。默认检索 `hybrid`、`top_k=5`。

每个案例只保存两个文件：

```text
artifacts/pipeline/
  design/
    root_cause.json
    repair_result.json
```

`root_cause.json` 内部使用 `rule_analysis`、`model_raw_response`、`model_analysis` 区分规则判断、模型原始响应、解析后的根因。原始响应收到后立即写入此文件，解析完更新同一个文件；根因阶段结束就已保存，不等待修复完成。

`repair_result.json` 内部为 `retrieval`、`model_raw_response`、`model_result`。模型返回的 RTL 文本保留在 JSON 中，不提取 `.v` 文件。原始响应包含 SDK 返回内容及可用的模型名、结束原因和 token 用量；空正文、截断内容和解析失败都保存。程序的 `validation_status="not_run"` 不随模型自行声称通过而改变；功能与时序评估属于后续工作。

已有结果不覆盖，重复运行时修改 `OUTPUT_DIR` 指向新目录。单个案例运行失败会在控制台指出，并继续后续案例；已保存的文件保留。全部完成退出 0，存在运行失败退出 1。没有单独的响应文件、重复汇总文件、保存回调或记录器。

主入口默认 `deepseek-flash`，`max_tokens=32768`，可在开头的 `LLM_CONFIG` 调整。RAG 的 1024-token 分块参数不变。独立客户端配置：Qwen 32768；GPT-4o 16384（[官方上限](https://developers.openai.com/api/docs/models/gpt-4o)）。旧 Claude 与 Together CodeLlama 仍保留原模型和预算；这些旧模型的状态见 [Claude](https://platform.claude.com/docs/en/about-claude/model-deprecations) 和 [Together](https://docs.together.ai/docs/deprecations) 下线记录。

旧 `repair/service.py`、`repair/__main__.py` 和 `llm_clients/responses.py` 已删除。根因分析和修复模块分别提供 `build_prompt()`、`parse_response()`，入口直接调用现有客户端的 `generate_response()`，直接写入对应阶段文件。

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

TVIR 仍保留旧代码的 lint 问题，因此上面的全项目 `ruff check` 当前未通过。本次范围可运行 `ruff check src/run_pipeline.py src/root_cause src/repair src/prompts src/llm_clients src/rag tests scripts`；旧 TVIR 的检查结果见其迁移验证记录。

开发集 8 问与验收集 20 问分开保存，manifest 固定其用途及 SHA-256。验收要求 hybrid 总体至少 16/20，setup 和 hold 分别至少 8/10。不能使用验收集调参后仍将其作为独立验收；资料变更后的评估需重新审阅标签并显式更新冻结记录。
