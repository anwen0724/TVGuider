# RAG 原始资料与来源登记

核对日期：2026-09-24。范围：setup、hold；不纳入 CDC。产物是六份英文 Markdown，包含 29 个二级主题章节，位于 `knowledge/raw/`。本记录和评估集不进入知识库。

正文为按主题重新组织的简短释义，不复制手册长段落。每份文档保存来源列表，每个章节就近引用实际依据。方程用于解释，表格是项目审查辅助；没有运行 RTL 综合、布局布线、STA 或形式等价验证，也没有把示例称为已验证修复。

## 来源与适用范围

| 一手来源 | 核对内容和使用位置 | 适用边界 |
| --- | --- | --- |
| [UG906 setup relationship](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Relationship)、[hold relationship](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Relationship) | 基础文档的边沿、arrival、required、slack；hold 文档的降频分析 | 同边沿降频结论是方程推论，不能套用所有时钟关系 |
| [UG906 skew](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Skew-Definition)、[uncertainty](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Clock-Uncertainty) | 基础与 hold 诊断，区分插入延迟差和时钟变化量 | 保留 Vivado dedicated routing 的适用例外 |
| [UG906 max analysis](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Setup/Recovery-Max-Delay-Analysis)、[min checks](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Min-Delay-with-Hold-and-Removal-Checks)、[corner coverage](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Hold/Removal-Min-Delay-Analysis) | setup/hold 诊断和修改后的角落覆盖 | 具体 corner 组合来自 AMD 器件模型，不宣称全部 ASIC 使用相同模型 |
| [UG949 pipeline assessment](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Determine-Whether-Pipelining-is-Needed)、[inferred logic](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Check-Inferred-Logic) | 深逻辑、RAM/算术资源、retiming | 功能与控制语义必须由待修复设计另行验证 |
| [UG906 physical characteristics](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Category-3-Physical)、[UG949 replication](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Replicate-High-Fanout-Net-Drivers) | setup 中的布线、fanout 和约束诊断 | AMD SLR/Pblock/属性属于工具和器件相关建议 |
| [UG949 pipeline considerations](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations)、[planning latency](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Consider-Pipelining-Up-Front)、[unnecessary stages](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Avoid-Unnecessary-Pipelining) | setup 修复与验证，周期延迟和资源代价 | valid/reset/enable 等检查是本项目根据延迟变化推导的审查要求 |
| [UG903 multicycle paths](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Multicycle-Paths) | setup/hold 修复的功能前提 | 不提供脱离边沿关系的通用 N/N-1 约束处方 |
| [UG903 input delay](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Input-Delay)、[UG949 I/O coverage](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/No-Input/Output-Delays-and-Partial-Input/Output-Delays) | hold 输入接口诊断 | 需结合板级和外部器件规格确定实际约束 |
| [UG906 hold-fixing impact, 2024.1](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Determining-if-Hold-Fixing-is-Negatively-Impacting-the-Design) | 布线后 setup 回退、hold detour、异常 multicycle/skew | 保留明确版本链接，工具修复优先级不推广为通用流程规则 |
| [UG949 pre-route hold repair](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Fixing-Large-Hold-Violations-Prior-to-Routing) | LUT1 延迟、受限 negative-edge FF 优化 | 不把工具支持的变换概括为任意 RTL 延迟链或寄存器插入 |
| [OpenROAD resizer](https://openroad.readthedocs.io/en/latest/main/src/rsz/README.html) | ASIC 映射后 setup 优化和 post-CTS hold buffering | 与 Vivado FPGA 实现分开；保留避免新增 setup violation 的默认保护 |
| [OpenSTA README](https://github.com/The-OpenROAD-Project/OpenSTA) | STA 输入与可复现实验上下文 | 说明支持的输入格式，不声称此项目已运行 OpenSTA |
| [UG906 signoff](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/Verifying-Timing-Signoff) | 实现后时序证据 | 功能模拟与时序 signoff 各有职责 |

除显式 2024.1 链接外，AMD 在线正文核对时为 2026.1。在线稳定主题链接可能随发行版变化；本地语料通过 SHA-256 冻结，以实际入库字节为准。OpenROAD/OpenSTA 使用核对当日的官方项目文档。搜索发现后已打开实际正文；没有使用论坛回答作为知识依据。

## 语料与评估冻结

先完成六份语料，再根据正文独立撰写开发查询 8 条（setup 4、hold 4）和验收查询 20 条（setup 10、hold 10）。两组问题没有相同查询文本；它们可以覆盖相同领域概念。相关性由预先选定的文档 ID、完整标题层级和正文行范围表示，行号为包含 YAML 在内的原文件 1-based inclusive 行号，不把标题行作为正文证据。

`evaluation/rag/manifest.json` 记录原文件 bytes 的 SHA-256、查询集用途、数量和冻结版本。标签和查询不是根据检索结果生成，准备期间未执行任何检索。语料修订须重新审核标签和更新冻结记录；若验收集被用于调参，须按 Spec 更换独立验收集。

这是一组人工编写的小规模内部验收题，不是外部盲测基准；其分数只衡量当前语料上的基础检索效果。模型、片段预算、候选数等运行配置由主实现的构建和评估报告记录。本记录不宣称检索指标已经达标。

## 本次资料检查

已通过当前正式 `rag.document_loader.load_documents` 读取六份资料，并对照其源位置检查 28 条查询标签：完整标题层级与正文范围均可对应实际结构块。六份语料和两份查询文件的 SHA-256 均与 manifest 一致。两组查询文本无交集，数量及 setup/hold 分布满足计划。这里只验证资料与标签可回查，真实 tokenizer 分块、模型检索及最终效果由后续集成步骤验证。
