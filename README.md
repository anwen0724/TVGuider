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

入口是 `tvir.api.build_tvir_dicts_from_vivado_report_and_rtl(report_text, rtl_text)`，接收 Vivado 报告文本和对应 RTL 文本，返回 TVIR 字典列表。默认仅处理负 slack 路径；`only_violations=False` 可包含非违例路径。下述修复 CLI 可调用该入口，然后连接根因分析、RAG 和修复生成。

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

## Setup 根因分析与修复

流程为：TVIR → 规则特征与评分 → LLM 根因解释 → 英文查询 → RAG 混合检索 → LLM 修复候选。默认 `hybrid`、`top_k=5`，五条知识片段与最多三条旧规则候选策略分别传入模型。规则保留 S1 组合路径、S2 扇出、S3 算术流水线和 S4 跨层次类别。不按违例类型或时钟名称拦截输入；未新增 hold 或 CDC 专用规则与策略。

已有 Conda `TVGuider` 环境已安装 LLM 依赖；新环境执行 `python -m pip install -e ".[llm]"`。在项目根目录 `.env` 填写 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_BASE_URL`，模板见 `.env.example`。运行示例（将案例路径替换为实际文件）：

```powershell
conda run -n TVGuider python -X utf8 -m repair --rtl path/to/design.v --report path/to/timing.txt --kb artifacts/rag/kb --output artifacts/repair/case-001 --max-tokens 32768
```

CLI 处理报告中的第一条负 slack 路径。也可以用 `--tvir path/to/tvir.json` 替代 `--report`，输入单条 TVIR 对象。`--design-context path/to/design.xdc` 可附加约束文本；模型默认跟随 `DeepSeekClientConfig`，也可通过 `--model` 显式指定。

生成预算默认跟随客户端配置，可用 `--max-tokens` 覆盖单次调用预算。DeepSeek、Qwen 默认 32768；GPT-4o 默认 16384（[官方输出上限](https://developers.openai.com/api/docs/models/gpt-4o)）。旧 Claude 配置的模型已在 [Anthropic 下线记录](https://platform.claude.com/docs/en/about-claude/model-deprecations) 中停用，Together 的 CodeLlama 70B 也在 [下线记录](https://docs.together.ai/docs/deprecations) 中；这两个遗留客户端的预算分别保留 8192、1200，没有擅自更换模型。RAG 的 1024-token 分块配置不变。

`--output` 为必填目录参数，没有默认目录。每次模型返回后、业务解析之前，立即写入 `root_cause_response.json` 或 `repair_response.json`，保存正文、返回模型、结束原因、token 用量及完整 SDK 响应。SDK 未提供的字段保存为 null。只实现 `generate(prompt)` 的第三方客户端仍可使用，记录其返回文本，无法取得的元数据为 null。

`result.json` 保存规则结果、整理后的根因、检索证据、模型响应和修复解析结果。修复返回的 JSON 对象按原样保留，不删除或替换模型字段；缺少字段、引用异常、声明增加拍数都不会阻止保存。空正文、截断内容和非法 JSON 记录 `parse_status="failed"` 与 `parse_error`，原始响应照常保留。根因解析失败仍沿用规则回退，并记录解析状态。`validation_status="not_run"` 是程序层状态，和模型自行声明的状态分开。

能从 JSON 的 `repaired_rtl`、Verilog 代码围栏或以 module/常用编译指令起始的纯 RTL 文本中提取代码时，另存 `repaired.v`；无可提取代码时不生成此文件。提取不检查语法、功能或时序。后续检索或处理失败时，先前已收到的响应文件仍然保留。已有同名文件不覆盖，原始 RTL 不修改。

```python
from repair import RepairConstraints, repair_from_tvir

result = repair_from_tvir(
    tvir, original_rtl, kb_dir="artifacts/rag/kb", llm_client=client,
    constraints=RepairConstraints(design_context=xdc_text),
)
raw_response = result["responses"]["repair"]
repaired_rtl = result["repair"]["repaired_rtl"]  # None when no RTL is extractable
```

Python API 默认只返回内存中的字典，不创建结果目录。需要边调用边保存时，可传入 `on_response(stage, response)` 回调；CLI 使用此回调立即落盘。根因分析与修复生成各调用一次模型，接口与拍数没有新增的强制保持条件。功能、等价性、实际延迟和 STA 留给后续验证。修改记录见 [输出保留调整](C:/Users/anwen/Desktop/tv-guider/docs/notes/output-preservation.md)。

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

TVIR 仍保留旧代码的 lint 问题，因此上面的全项目 `ruff check` 当前未通过。本次范围可运行 `ruff check src/root_cause src/repair src/prompts src/llm_clients src/rag tests scripts`；旧 TVIR 的检查结果见其迁移验证记录。

开发集 8 问与验收集 20 问分开保存，manifest 固定其用途及 SHA-256。验收要求 hybrid 总体至少 16/20，setup 和 hold 分别至少 8/10。不能使用验收集调参后仍将其作为独立验收；资料变更后的评估需重新审阅标签并显式更新冻结记录。
