# RAG 基础版实施与验收记录

日期：2026-09-24。对应 [RAG Spec v1.0](C:/Users/anwen/Desktop/tv-guider/docs/spec/rag-knowledge-base.md) 与 [实施计划](C:/Users/anwen/Desktop/tv-guider/docs/plans/rag-knowledge-base.md)。

## 完成结果

T00～T10 已完成。当前可通过 Python API 或 CLI，独立执行英文 Markdown 资料读取、分块、本地 Qwen 编码、Qdrant/BM25 持久化，以及 dense、bm25、hybrid 检索。默认 hybrid、top_k=5；结果保留正文、来源、完整标题路径、原始正文行范围、构建标识和排名。

六份英文资料已整理并核对官方来源，覆盖 setup 与 hold。来源适用性和限制保留在正文，见 [资料登记](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-source-register.md)。没有将旧版生成结果标注为已经验证的修复案例。

本次验收的成功构建为 `016dd2ea0d074826aa4da57b2201dbcd`：6 份文档、35 个片段，实际编码长度 38～219 tokens，合计 4491 tokens。片段上限 1024 tokens，最大正文重叠 128 tokens。资料较短，因此真实语料中的多数章节无需细分；长正文、长代码、长表格和不可容纳单行另由边界测试覆盖。

模型实际运行于现有 Conda `TVGuider` 环境和 RTX 5060 Ti，采用 CUDA/float32。模型与 tokenizer 固定 revision 为 `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`，权重保存在 `C:/all/tools/llm/models/Qwen3-Embedding-0.6B`。环境版本、安装命令和 CUDA 运算证据见 [环境记录](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-environment.md)。

## 功能验证

| 检查 | 实际结果 |
| --- | --- |
| `python -m pytest -q` | 55 passed，2 个真实模型测试不在默认组 |
| `python -m pytest -m model -q` | 2 passed，55 个普通测试不在模型组 |
| `python -m ruff check src tests scripts` | 通过 |
| `python -m ruff format --check src tests scripts` | 22 个文件已格式化，通过 |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | 通过 |
| CLI 实际全量构建 | 成功发布上述 6 文档、35 片段知识库 |

命令均使用 `C:/all/environments/anaconda3/envs/TVGuider/python.exe`；已核对 `conda run -n TVGuider python` 指向同一解释器。

测试使用真实 Markdown 解析、文件系统和 Qdrant。普通测试只在外部 embedding 边界使用固定向量；真实模型组实际执行 Qwen 文档与查询编码、归一化及长度检查，并通过独立子进程验证 CLI 重新加载、默认 hybrid 参数、API 结果一致性和 CLI 重建。

功能覆盖包括：无效资料/配置拒绝、递归发现、正文自然边界和字符兜底、英文缩写与小数、完整句子重叠、代码/表格整行拆分、嵌套列表内代码保护、来源行范围、稳定 ID、删除资料后全量重建、编码异常、索引不一致、发布失败保留旧版本、未完成目录恢复、BM25 词项匹配、无匹配、稳定排序及 RRF。

开发按行为逐项执行 Red → Green；发现的缩进丢失、长句片段被误当完整句子重叠、嵌套代码被当正文切分，均先用失败用例重现后修复。

## 检索效果

验收语料、20 条英文问题及章节正文标签在首次检索前冻结，并于 Git `7a51ed8` 保存。标签没有根据结果修改。开发集 8 问独立于验收集，没有并入知识资料。检索使用默认配置：top_k=5、两路候选各 20、等权 RRF 常数 60。

| 模式 | 验收总体 HitRate@5 | setup | hold |
| --- | --- | --- | --- |
| dense | 19/20（95%） | 10/10 | 9/10 |
| bm25 | 20/20（100%） | 10/10 | 10/10 |
| hybrid | 20/20（100%） | 10/10 | 10/10 |

RAG-E01、RAG-E02、RAG-E03 均通过：hybrid 总体超过 16/20，两类分别超过 8/10，并记录了三种模式对照。独立验收运行一次，没有依据验收结果调参。

开发集结果为 dense 8/8、bm25 8/8、hybrid 7/8。开发期间没有修改默认检索参数；因持久化记录与边界实现完善而重新构建后，开发集结果保持相同。保留的开发报告 build ID 为 `efb52844348c4982879cb93e76e22f7e`；最终验收使用上文的新 build ID。两个报告都保存各自完整的配置和身份，未将旧报告当作新构建的验收证据。

完整逐题 Top-5、分数、正文位置和软件配置已纳入 Git：

- [验收结果 JSON](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-acceptance-results.json)
- [开发结果 JSON](C:/Users/anwen/Desktop/tv-guider/docs/notes/rag-development-results.json)

运行时原报告同时位于 `artifacts/rag/evaluation/`，索引位于 `artifacts/rag/kb/`，均按计划忽略，不提交数据库。

### 逐题首次相关片段排名

`miss` 表示前 5 条未命中预标注章节的正文；数字不是修复质量评分。

| Query ID | Topic | dense | bm25 | hybrid |
| --- | --- | --- | --- | --- |
| acceptance-01 | setup | 1 | 1 | 1 |
| acceptance-02 | setup | 1 | 5 | 2 |
| acceptance-03 | setup | 1 | 1 | 1 |
| acceptance-04 | setup | 1 | 1 | 1 |
| acceptance-05 | setup | 1 | 1 | 1 |
| acceptance-06 | setup | 1 | 1 | 1 |
| acceptance-07 | setup | 1 | 1 | 1 |
| acceptance-08 | setup | 1 | 1 | 1 |
| acceptance-09 | setup | 1 | 1 | 1 |
| acceptance-10 | setup | 1 | 1 | 1 |
| acceptance-11 | hold | miss | 1 | 2 |
| acceptance-12 | hold | 2 | 1 | 1 |
| acceptance-13 | hold | 2 | 1 | 1 |
| acceptance-14 | hold | 1 | 1 | 1 |
| acceptance-15 | hold | 1 | 1 | 1 |
| acceptance-16 | hold | 1 | 1 | 1 |
| acceptance-17 | hold | 1 | 1 | 1 |
| acceptance-18 | hold | 1 | 1 | 1 |
| acceptance-19 | hold | 1 | 1 | 1 |
| acceptance-20 | hold | 1 | 1 | 1 |

dense 唯一漏检问题是 `acceptance-11`：两个寄存器直接连接、setup slack 很好但 minimum slack 为负，为什么逻辑少也会有问题。它的 Top-5 为：

1. timing-fundamentals / Setup checks limit late data，正文第 17 行。
2. setup-diagnosis / Routing, fanout, and placement restrictions，第 25 行。
3. timing-fundamentals / Setup checks limit late data，公式第 20～22 行。
4. setup-diagnosis / Dedicated block and inference bottlenecks，第 21 行。
5. repair-tradeoffs-and-validation / Recheck both delay directions and all required corners，第 18 行。

结果表明这条查询的向量排序偏向 setup 相关内容；BM25 在第 1 条、hybrid 在第 2 条命中了预标注正文。这里只记录现象，不据此改写问题或标签。开发集漏检及各模式 Top-5 也完整保留在开发结果 JSON。

## Git 与实施差异

本地仓库分支为 `rag-foundation`，没有配置远程或推送。阶段提交：

- `98f60a9`：已确认的设计与工程基线。
- `7a51ed8`：官方资料整理、冻结语料与评估输入。
- `e1ada59`：持久化、分块、三种检索及基础入口。
- `2778601`：真实 Qwen 接入、冻结输入评估、边界回归和环境记录。
- 本记录、逐题报告和使用说明在最终文档提交中保存。

业务范围、默认参数和验收阈值没有偏离 Spec。执行顺序作了工程调整：CUDA wheel 下载期间先完成使用外部编码替身的确定性功能，再运行真实模型验证。补充 `scripts/provision_model.py` 用于显式下载和记录模型指纹，属于运行环境准备，不是构建时的网络抓取功能。

当前证据来自 6 份资料和固定 20 问，不能推断对任意时序查询都达到 100%。本次没有接入 TVIR、根因分析、DeepSeek 修复生成或 RTL/STA 联合验证，检索验收结果不代表 RTL 修复成功率。
