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

开发集 8 问与验收集 20 问分开保存，manifest 固定其用途及 SHA-256。验收要求 hybrid 总体至少 16/20，setup 和 hold 分别至少 8/10。不能使用验收集调参后仍将其作为独立验收；资料变更后的评估需重新审阅标签并显式更新冻结记录。
