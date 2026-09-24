# RAG 知识库平台调研

调研日期：2026-09-24。范围：RAGFlow、Dify、LlamaIndex、Qdrant 的官方仓库和文档，以及本项目旧实验材料。本文是选型参考，不是已采纳的设计决策；未安装平台、未实测解析或检索效果。官方 `main` 和在线文档会变化，实际采用时需固定版本复核。

项目依据：[方法模块与关系](C:/Users/anwen/Desktop/tv-guider/docs/spec/method-modules.md)。当前方法主链是 RTL + STA → TVIR → 根因分析 → 检索知识 → 生成修复结果，基础版从单个 setup 案例与 DeepSeek 开始。RAG 是否同时辅助根因分析仍待确定。现成平台可以承担入库和检索，项目仍需定义领域知识结构、检索查询与修复约束。

## RAGFlow

- **入库与解析**：支持 PDF、Word、表格、HTML、Markdown 等；Parser 可输出保留层次的结构文本，内置 DeepDoc 处理 PDF，并提供可配置的入库流程。它适合评估论文、手册等复杂材料的解析，具体 Verilog 代码块与公式的保真度仍需用本项目资料测试。[官方 Parser 说明](https://github.com/infiniflow/ragflow/blob/main/docs/guides/agent/ingestion_pipeline/configure_parser_component.md)
- **分块与检索**：有 General、Paper、Manual 等分块方式；支持文档元数据过滤、词项与向量相似度加权、可选 rerank 模型。独立接口 `POST /api/v1/retrieval` 返回片段、文档 ID、分数等，Python 可通过 HTTP 调用。[HTTP API](https://ragflow.io/docs/http_api_reference)
- **Python 接入**：官方提供 `RAGFlow.retrieve(...)`，可以直接取得检索片段，随后由本项目组织修复提示词。[Python API](https://ragflow.io/docs/python_api_reference)
- **部署**：官方 README 列出的最低条件为 4 核 CPU、16 GB RAM、50 GB 磁盘、Docker 24.0.0+、Compose 2.26.1+；默认 Elasticsearch 方案还要求调整 Linux 内核参数 `vm.max_map_count`。README 包含 Windows Docker 入口；在 Windows 上应按 Linux 容器环境评估部署，不能把安装 Python SDK 当作部署了平台。[官方 README](https://github.com/infiniflow/ragflow)
- **服务负担**：Compose 源码包含文档引擎、关系数据库、对象存储、Redis 兼容服务等，具体启用项由配置决定。当前 `main` 中部分底层服务镜像已变化，应以固定版本的 Compose 文件为准。[官方 Compose](https://github.com/infiniflow/ragflow/blob/main/docker/docker-compose-base.yml)
- **许可证**：仓库采用标准 **Apache License 2.0**，分发时涉及保留许可和相关声明、标记修改等条款；本次未见 Dify 式平台附加条件。[LICENSE](https://github.com/infiniflow/ragflow/blob/main/LICENSE)

## Dify

- **入库与解析**：提供本地文件上传，也能通过知识流水线选择文档提取插件；官方文档说明 PDF 内嵌图片等内容需要合适的提取插件，不能预设所有文档内容都由默认导入完整保留。[本地文件入库](https://docs.dify.ai/en/cloud/use-dify/knowledge/create-knowledge/import-text-data/readme)
- **分块**：支持 General 和 Parent-child；后者以小块匹配、返回较大的父块，可用来保留策略的上下文。分隔符、块长度和重叠可配置，知识库创建后分块模式不能直接切换。[分块设置](https://docs.dify.ai/en/cloud/use-dify/knowledge/create-knowledge/chunking-and-cleaning-text)
- **检索**：High Quality 索引支持向量、全文和混合检索，混合检索可调权重或接入 rerank；工作流检索节点支持文档元数据过滤，输出内容、元数据与标题。[检索配置](https://docs.dify.ai/en/cloud/use-dify/knowledge/create-knowledge/setting-indexing-methods)、[官方检索节点文档](https://github.com/langgenius/dify-docs/blob/main/en/cloud/use-dify/nodes/knowledge-retrieval.mdx)
- **Python 接入**：知识接口 `POST /datasets/{dataset_id}/retrieve` 支持生产检索和测试检索，官方提供 Python `requests` 示例；返回片段、来源文档与分数。可只调用此接口，再由本项目调用 DeepSeek。接口使用知识库 API key；当前文档对查询文本列出 250 字符上限，因此应构造简洁领域查询，而非直接塞入整个 TVIR。[检索 API](https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval)
- **Windows 部署**：官方要求启用 WSL 2、Docker Desktop、Compose 2.24.0+；建议将容器挂载的数据放在 Linux 文件系统。通用最低硬件为 2 核、4 GiB，但这不是本项目工作负载下的实测占用。当前部署文档列 7 个核心服务、8 个依赖组件，以及 1 个退出后不常驻的初始化任务。[Docker Compose 部署](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose)
- **许可证**：官方 LICENSE 标题为 **Open Source License**，正文明确为 Dify 的修改版 Apache License 2.0，附加条款包括：未经书面授权不得用源码运营多租户环境（按 workspace 定义租户）；使用其前端时不得移除或修改 console/apps 的 LOGO 和版权信息。不能将其等同标准 Apache-2.0。[LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)

## 可复用的轻量组件

- **LlamaIndex**：Python RAG 框架，提供数据连接、索引、检索和集成能力，采用 MIT 许可证；它是需要编程接入的框架，不是部署后即可管理知识库的完整产品。其 ingestion pipeline 支持转换、缓存和持久化。官方同时提供商业解析服务，不能把这些服务与开源框架混为一谈。[官方仓库](https://github.com/run-llama/llama_index)、[入库流水线](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/)
- **Qdrant**：可作为检索存储组件；Python 客户端支持 `QdrantClient(path="...")` 本地持久化，原型阶段无需单独启动数据库服务。客户端采用 Apache-2.0。它不替代资料审阅、知识整理和完整文档管理平台。[官方客户端](https://github.com/qdrant/qdrant-client)
- Qdrant 提供元数据过滤和 dense/sparse 混合查询能力，但项目仍需配置相应的向量表示、索引和查询逻辑。本地模式适合原型，不能据此推断大规模服务的吞吐量。[过滤](https://qdrant.tech/documentation/search/filtering/)、[混合查询](https://qdrant.tech/documentation/search/hybrid-queries/)

## 针对本项目的判断（推断，待验证）

| 需求 | 更值得评估的方向 | 理由 |
| --- | --- | --- |
| 大量论文 PDF、器件手册、扫描资料，需要界面查看和调整入库效果 | RAGFlow | 复杂文档解析与知识入库是较直接的能力匹配，但有较高部署负担 |
| 希望通过可视化节点快速演示完整应用、调整提示词并管理交互 | Dify | 工作流和应用管理更贴近这一目标；仅为一个 Python 检索模块部署完整平台，收益需权衡 |
| 当前仅有少量人工整理的修复策略，需要可复现、便于消融的 Python 研究实现 | 优先比较轻量自建方案 | 两个平台的管理界面和多服务部署可能超出第一版需求；这是工程取舍判断，不代表它们做不到 |

无论选哪个平台，都应由项目维护可导出的知识源、稳定的知识条目 ID、出处、适用条件和修复限制。知识服务负责返回可追溯片段；TVIR 的构建、领域根因判断与生成 RTL 仍由论文方法模块承担。不能将通用文档问答能力视为已经实现了本项目的方法。

如进入平台验证，建议用同一批人工审阅过的 setup 策略和同一组查询，检查正确策略能否进入前几个结果、代码及适用条件是否完整、错误适用策略是否被排除，再决定采用；本次没有这类实测数据。

## 知识内容与基础版建议

建议采用“自行维护领域知识与检索逻辑，复用成熟检索组件”的路线。初始组合可为 Python、Markdown/JSON 知识源、Qdrant 本地模式；资料格式增多时再评估 LlamaIndex 的导入组件。DeepSeek 继续负责生成任务，embedding 模型单独配置和评估。这些是建议，尚未确定最终依赖。

旧实验的知识散落在提示词里。例如 [setup 知识提示词](C:/Users/anwen/Desktop/tv-guider/legacy/test_0618/repair_prompts/long_comb_chain/llm+knowledge/setup_violation_case1.txt) 主要包含时序概念，[方法提示词](C:/Users/anwen/Desktop/tv-guider/legacy/test_0618/repair_prompts/long_comb_chain/gpt+ours/setup_violation_case1.txt) 包含长组合链诊断、插入流水线和逻辑重构等策略。它们可作为待审阅素材，不能直接标为经过验证的成功修复案例。

建议区分原始资料、整理后的修复策略、经过验证的修复案例。基础版先整理少量 setup 策略，来源可以是工具官方手册、论文、人工总结和经过验证的项目案例。每条知识至少包含：

| 字段 | 目的 |
| --- | --- |
| 稳定 ID、版本、来源及章节/页码 | 能追溯、更新和复现实验 |
| 违例类型、根因标签与现象 | 将 TVIR/诊断结果转为检索条件 |
| 适用条件、不适用条件 | 避免相似但不适用的策略进入修复提示词 |
| 修复动作及必要的 RTL 示例 | 提供可执行的修改指导 |
| 可能影响：周期延迟、吞吐、资源、接口协议 | 说明修改前需要满足的约束 |
| 验证方式及验证状态 | 区分建议、未验证案例和有验证证据的案例 |

例如，“长组合链可考虑插入流水线”必须同时记录其适用条件和周期延迟影响。AMD 文档明确讨论流水线提高运行频率与增加延迟之间的取舍。若具体案例要求保持周期延迟，检索阶段应据此排除不满足约束的策略；不能把禁止改变延迟设为所有案例的默认前提。[AMD Pipelining Considerations](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations)

建议的离线流程：收集材料 → 审阅并整理知识条目 → 按完整策略分块 → 建立元数据与检索索引 → 用固定查询检查检索结果。条件、策略和代码示例尽量作为完整知识单元返回；长资料可分块，但应保留所属策略及来源关联。

建议的在线接口：输入违例类型、根因/路径特征和已知设计约束，返回知识条目、来源、适用条件和检索分数。分数仅用于排序，不等于策略正确概率。TVIR 尚未实现时，可先用人工编写的同类查询独立验证知识模块；之后再接入主流程。

检索实现可先有关键词基线，再比较向量检索与混合检索；是否需要 reranker 由漏检和错排情况决定。基础版检查正确策略是否进入 Top-K、是否违反案例约束、来源与代码上下文是否完整。检索评估与最终 RTL 修复成功率分别记录；评估案例的目标修复答案应与知识构建材料隔离，避免结果泄漏。
