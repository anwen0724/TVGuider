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

2026-09-24 已将原有业务代码和实验材料整体移入 `legacy/`，未修改其内容。新版代码目录和运行入口尚未建立。

建议先阅读 [代码探索记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/2026-09-24-codegraph-exploration.md)，了解已经实现的能力、未完成部分及验证范围。

方法由 TVIR 构建、RAG 知识库构建与检索、根因分析、修复结果生成四个核心模块组成，输入是 RTL 代码与对应的 STA 时序报告。详见 [方法模块与关系](C:/Users/anwen/Desktop/tv-guider/docs/spec/method-modules.md)。基础版覆盖 setup、hold，暂不纳入 CDC；先实现独立的 RAG 知识库构建与检索，后续生成类模型优先使用 DeepSeek。项目术语见 [CONTEXT.md](C:/Users/anwen/Desktop/tv-guider/CONTEXT.md)。

[RAG 知识库构建与独立检索 Spec](C:/Users/anwen/Desktop/tv-guider/docs/spec/rag-knowledge-base.md) 已汇总确认：英文 Markdown、本地 Qwen3-Embedding-0.6B、Qdrant 与 BM25、RRF 混合检索，以及功能和检索效果验收标准。当前是设计确认阶段，原始资料、实现和实际评估尚未完成。

[RAG 实现计划](C:/Users/anwen/Desktop/tv-guider/docs/plans/rag-knowledge-base.md) 已编写，覆盖环境准备、英文资料、逐行为 TDD、真实模型集成和独立效果评估；当前尚未执行。
