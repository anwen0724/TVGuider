# RAG 知识库构建与独立检索 Implementation Plan

状态：计划已编写，尚未执行。

日期：2026-09-24。

设计依据：[RAG Spec v1.0](C:/Users/anwen/Desktop/tv-guider/docs/spec/rag-knowledge-base.md)。执行依据：[开发基线](C:/Users/anwen/Desktop/tv-guider/docs/DEVELOPMENT_BASELINE.md)。验收预期只在 Spec 中维护；本文安排实现、测试、资料与验证任务，不增加另一套功能语义。

## 1. 验收项与实施任务对应

| Spec 验收项 | 主要任务 | 补充验证 |
| --- | --- | --- |
| RAG-01 | T02、T03 | T10 真实模型与真实资料闭环 |
| RAG-02 | T02、T04 | T07 旧版本保护 |
| RAG-03、RAG-04 | T04 | T10 实际 tokenizer 与完整资料检查 |
| RAG-05、RAG-06、RAG-07 | T05 | T07 失败保护、T10 真实资料分块 |
| RAG-08 | T02、T03 | T10 独立进程重新加载 |
| RAG-09、RAG-10 | T07 | T10 实际失败后的检索 |
| RAG-11 | T03 | T07 版本校验、T10 固定模型验证 |
| RAG-12 | T02 | T06 与混合检索集成 |
| RAG-13、RAG-14、RAG-15 | T06 | T08 Python／CLI 一致性、T10 实际检索 |
| RAG-16 | T02、T03、T06、T07、T08 | 各失败边界的相邻回归测试 |
| RAG-17 | T08 | T10 三模式命令行与 Python 对照 |
| RAG-E01、RAG-E02、RAG-E03 | T01、T09、T10 | 独立评估集、固定配置与逐题结果 |

T00 是环境与版本准备，不独立证明某项功能通过。T01 准备正式资料和评估输入，不把资料整理混进运行时构建逻辑。每项的通过标准以 Spec 2.6 对应编号为准。

## 2. 已核对的项目基底

- 新版已有 Spec 和设计规范；旧实现位于 `legacy/`。根目录尚无 `src/`、`tests/`、`pyproject.toml` 或现成 Python 测试配置。
- `git rev-parse --show-toplevel` 当前报告不是 Git 仓库；本次编写计划没有初始化 Git、安装依赖或创建模型缓存。
- 用户指定复用已有 Conda 环境 **TVGuider**，已核实其解释器为 `C:/all/environments/anaconda3/envs/TVGuider/python.exe`，Python 3.12.13。当前工具进程未激活该环境，直接执行 `python` 会落到 Anaconda 基础环境，因此计划中的命令显式使用 `conda run -n TVGuider`。
- 已读取 TVGuider 的包元数据，目前未发现 torch、transformers、sentence-transformers、qdrant-client 和 pytest；后续在该环境内补齐依赖，不新建环境，也不向 Anaconda 基础环境安装本项目依赖。
- `nvidia-smi` 读取到 RTX 5060 Ti、16311 MiB 显存、驱动 591.86。GPU 可见不代表 PyTorch CUDA 已验证，T00/T03 必须实际检查。
- 旧代码不作为新版包或测试的运行依赖；本计划不修改 `legacy/`、代码地图数据或 IDE 配置，不调用 DeepSeek、Vivado 或 STA 工具。

## 3. 目标文件与实现组织

以下是本计划执行时新建的目标路径，当前尚不存在；不会在本次写计划时创建代码骨架。路径相对于项目根目录 `C:/Users/anwen/Desktop/tv-guider`。

```text
pyproject.toml                         包元数据、依赖、pytest 与 Ruff 配置
requirements.lock.txt                  已实际验证环境的精确依赖版本
.gitignore                             运行产物、环境、模型及历史归档排除规则
configs/rag.yaml                       本地模型路径、固定 revision、编码与检索配置
src/rag/
  __init__.py                          导出 Python 构建与检索入口
  contracts.py                         输入配置、结果类型、可识别错误
  document_loader.py                   Markdown 文档读取、校验、结构解析与来源位置
  chunking.py                          自然边界递归拆分、重叠、结构保护
  embedding.py                         Qwen 编码、token 计数与版本约束
  lexical.py                           BM25 分词、持久化数据与评分适配
  storage.py                           Qdrant、本地构建版本与发布
  retrieval.py                         候选排序、RRF、结果组装
  service.py                           构建与检索流程
  __main__.py                          argparse 命令行入口
  evaluate.py                          独立评估执行与报告
tests/
  conftest.py                          测试配置与外部模型替身
  fixtures/markdown/                   可人工核对的英文最小资料
  test_build_search.py
  test_markdown_chunking.py
  test_structured_chunks.py
  test_embedding_contract.py
  test_retrieval.py
  test_generation_recovery.py
  test_cli.py
  test_evaluation.py
  integration/test_local_model.py
knowledge/raw/                         本次整理的英文原始 Markdown
evaluation/rag/dev.jsonl               开发调参查询与章节标注
evaluation/rag/acceptance.jsonl        独立验收查询与章节标注
evaluation/rag/manifest.json           语料、查询、标签的版本与指纹
docs/notes/rag-source-register.md      资料来源核对与适用条件记录
docs/notes/rag-environment.md          实测环境、固定依赖与模型版本
docs/notes/rag-validation.md           最终执行、效果与未验证边界报告
```

运行产物放入 `artifacts/rag/`；Python 运行环境复用项目目录外已有的 Conda **TVGuider** 环境。运行产物、Conda 环境目录以及模型缓存不进入源码版本。评估集放在 `knowledge/raw/` 之外，不能被资料目录递归扫描入库。

用户指定模型存放根目录为 `C:/all/tools/llm/models`，该目录已存在。本模型使用其下的 `Qwen3-Embedding-0.6B/` 子目录保存完整的权重、tokenizer 和模型配置。后续在 `configs/rag.yaml` 中记录 `model_path: C:/all/tools/llm/models/Qwen3-Embedding-0.6B`，同时保留来源标识 `Qwen/Qwen3-Embedding-0.6B` 与实际固定 revision；构建记录保存这些信息，检索加载对应的本地模型。该路径属于本机部署配置，换机器时可以调整路径，但不能悄悄更换模型版本。

模型下载属于 T03 的环境准备步骤；正常构建与检索显式从该目录加载，不依赖默认 Hugging Face 缓存位置，也不在运行时自动下载其他版本。目录中缺少必要文件时报告模型加载错误。当前只记录位置，尚未下载模型或创建该模型子目录。

目标模块是任务定位，不要求一次性生成全部空文件。某个行为首次需要对应模块时再创建；避免为未来能力预建框架。`contracts.py` 使用 Python 类型与 dataclass 和显式边界校验，不为满足模板单独引入运行时 schema 框架。

`src/` 是源码容器，`rag` 是本次实现的 Python 包，不再套项目同名包。后续模块开发时可以在 `src/` 下并列创建，本次只创建 `src/rag/`。T00 在 `pyproject.toml` 中配置从 `src/` 发现并安装 `rag` 包；通过可编辑安装提供导入路径，不把 `src` 当成包，也不在代码中临时修改 `sys.path`。

### 3.1 依赖落实

| 能力 | 计划采用 | 落实方式 |
| --- | --- | --- |
| Markdown | `markdown-it-py` | 使用结构 token 与源行映射，启用表格规则；正文从原始文本切片恢复，不从 HTML 反向重建 |
| YAML | `PyYAML` | 安全加载文档头与配置；再按 Spec 验证字段类型及值 |
| 英文断句 | `pysbd` | 英文模式、禁用清洗，保留字符位置；用缩写、小数和技术标识样例核对，不直接按句点 split |
| embedding | `sentence-transformers`、`transformers`、`torch` | 固定 Qwen 模型／tokenizer revision；先检查 Windows 与显卡兼容，再记录可重建版本 |
| 向量存储 | `qdrant-client` | 本地 path 模式，实际临时目录集成测试，不启动远程数据库 |
| BM25 | `rank-bm25` 的 `BM25Okapi` | 初始固定 `k1=1.5`、`b=0.75`、`epsilon=0.25`；词项匹配过滤由项目保证，不能按分数是否大于零过滤 |
| CLI、数据落盘 | 标准库 `argparse`、`json`、`pathlib` | CLI 复用 Python 入口，不建立第二套实现 |
| 测试／静态检查 | `pytest`、`ruff` | 配置新包与测试目录，排除 legacy；真实模型测试单独标记 |

不在计划中猜测完整依赖锁定版本或模型提交 SHA。T00 完成实际安装与兼容检查后写入精确版本，T03 固定模型 revision；浮动的 `main`／`latest` 不得作为最终可复现记录。若需要调整所选库而不改变 Spec 行为，更新计划及环境记录；影响功能契约时先回到 Spec。

### 3.2 Python 与 CLI 接线

计划从 `rag` 包导出 `build_knowledge_base(source_dir, kb_dir, config)` 和 `search_knowledge_base(kb_dir, query, mode="hybrid", top_k=5, candidate_k=None, rrf_k=60)`，调用方使用 `from rag import build_knowledge_base, search_knowledge_base`，分别取得类型化的构建摘要与检索响应。配置读取与路径转换属于入口适配，核心服务接收已校验配置。

外部模型通过窄的适配边界接入，提供 token 计数、文档编码、查询编码及版本描述。行为测试可以在此边界注入可预测向量或明确异常，实际 tokenizer 与模型另行验证。不 mock 分块、RRF、文件发布等本项目内部算法来证明它们正确。

命令行在 T08 创建，形态为 `python -m rag build ...` 与 `python -m rag search ...`。标准输出为包含 Spec 结果字段的 JSON，错误写入标准错误并使用非零退出码；诊断信息不得混入成功 JSON。错误类别区分输入校验、超长结构单元、模型、存储及知识库不一致；不增加自动重试、自动翻译或静默检索降级。

### 3.3 持久化与稳定结果

每次构建使用独立生成目录，布局采用：

```text
artifacts/rag/kb/
  current.json                         指向成功构建的 build_id
  generations/<build_id>/
    manifest.json                      文档指纹、配置、revision、格式版本与数量
    chunks.jsonl                       原文片段、位置和元数据
    bm25.json                          有序片段 ID、词项序列、算法与参数
    qdrant/                            该版本的本地向量存储
```

BM25 小规模持久化采用可审阅的 JSON 词项数据，加载时恢复其运行统计，不重新读取原始 Markdown 或运行 embedding；避免持久化依赖私有类布局的 pickle。无词项的片段不伪造词项，全库无词项时 BM25 成功返回空结果，向量能力仍独立工作。

构建在新目录完成并关闭写入句柄后，检查片段 ID、两套索引、数量和 manifest；再将同目录临时指针以 `os.replace` 替换为 `current.json`。指针切换是提交点；此前失败只清理本次未发布目录。成功发布后，清理工作不能删除当前版本，也不能把已发布版本误报为未发布失败。首次构建遵循同样流程。

只使用成功发布版本；启动恢复时识别并清理未完成目录，不做全量目录盲删。Windows 下关闭 Qdrant／文件句柄，任何递归清理前校验解析后的绝对路径位于本次知识库生成目录。并发服务和多写者不在范围内，不绕过 Qdrant 的本地访问限制。

片段 ID 采用稳定散列输入映射为 Qdrant 支持的 UUID：输入包括文档 ID、源范围／结构标识、正文及生效分块配置；不依赖目录枚举次序、绝对机器路径或本次随机 build_id。源文档内容另用 SHA-256 记录。源位置需要保存真实正文跨度；重复标题、围栏和表头与正文跨度区分，以便评估不把标题命中当作相关正文命中。

向量使用归一化表示与 cosine 度量，固定文档／查询编码约定并记录。小规模本地库采用精确评分；为避免 Top-K 截断处同分候选的选择不稳定，先取得完整评分集合，再按分数降序、片段 ID 升序取候选，最后执行 Spec 的 RRF。BM25 同样先按词项命中掩码过滤，再稳定排序。以后改近似检索需重新验证这一排序契约。

## 4. 执行顺序与任务

所有功能任务按“一项可观察行为的失败测试 → 最小实现 → 相关测试通过 → 有收益时重构”执行。下面列出的多个场景是同一任务的后续循环，不是先写完所有测试再集中实现。导入错误、未安装依赖或语法错误不能充当行为测试的 Red。

### T00：建立可复现的执行基底

**依赖**：无。**修改位置**：`pyproject.toml`、`.gitignore`、`requirements.lock.txt`、`configs/rag.yaml`、环境记录，以及最低限度的包入口。

1. 在正式执行本计划时重新检查 Git 状态；当前未启用 Git，计划建立本地仓库并使用 `rag-foundation` 分支，不配置远程或推送。先配置忽略项，再按指定路径纳入新版文档与后续源码，`legacy/` 保持现有归档，不一次性提交整个桌面目录。使用已有 Git 身份；缺失时记录为提交准备事项，不编造作者信息。
2. 复核已有 Conda TVGuider 环境的解释器、Python 版本和依赖清单，记录安装前状态，再配置 `src` 包布局和开发依赖。核对 PyTorch 官方安装方案及 GPU 架构支持，在 TVGuider 内执行一次实际 CUDA 张量运算；不可只依据 `nvidia-smi` 判断成功。
3. 仅补齐本项目缺少或版本不兼容的依赖，不默认重建环境或整体升级已有包。记录 Conda、Python、驱动、torch/CUDA 与库版本、依赖变更及验证过的安装命令，生成精确依赖清单并记录 GPU wheel 来源。默认包导入不得提前加载大型模型。
4. 配置 pytest markers：`model`、`evaluation`；配置 Ruff 与测试发现只覆盖新版。

**验证与完成条件**：TVGuider 环境可导入已选库、包可安装、工具可运行，兼容检查结果和命令已记录。此任务是环境准备，不机械编写无业务意义的测试，也不宣称 RAG 功能已实现。

### T01：准备英文资料与隔离的评估输入

**依赖**：可先于功能代码开展。**对应**：RAG-E01～E03 的数据前置条件。**修改位置**：`knowledge/raw/`、`evaluation/rag/`、来源记录。

1. 检索官方工具手册、公开论文等一手资料，核对实际页面、章节及适用环境；整理英文内容并保留引用。不能以搜索摘要代替阅读，也不将旧模型输出改名为验证案例。
2. 初步按六个主题安排 Markdown：timing fundamentals、setup diagnosis、setup repair、hold diagnosis、hold repair、repair tradeoffs and validation。篇数可随材料调整，范围和文档头遵循 Spec。来源登记放在知识输入目录外，避免说明文档误入库。
3. 审阅 setup／hold 的区分、时钟与数据路径条件、FPGA／ASIC／工具适用性；示例代码说明性质与限制，不宣称未运行的示例已经验证。正文不围绕最终验收题定制答案。
4. 独立准备开发查询与最终验收查询，按 Spec 配置数量、分类和章节标签；先冻结语料，再冻结验收标签。标签记录文档 ID、标题路径与原始正文范围，处理同名标题歧义。
5. 数据 manifest 保存语料与各查询集的指纹及用途；开发调参期间不运行最终验收查询来挑选参数。若最终验收集被用于调参，按 Spec 更换独立验收集并留下版本记录。

**验证与完成条件**：资料有可回查出处，数据集相互独立且位于正确目录，章节标签能人工回查。T02 完成后使用正式解析器检查资料；不另写一套与构建逻辑重复的文档头验证器。

### T02：最小构建—持久化—BM25 检索链路

**依赖**：T00。**对应**：RAG-01、02、08、12、16。**代码**：`contracts.py`、`document_loader.py`、`lexical.py`、`storage.py`、`service.py`。**测试**：`test_build_search.py`、`test_retrieval.py`、`conftest.py` 及最小 Markdown fixture。

- 第一轮 Red：通过服务入口构建一个短章节，结束实例后重新加载并 BM25 查询，观察 Spec 要求的正文与出处。外部 embedding 边界使用固定的 1024 维测试向量；磁盘、Markdown 和 Qdrant 使用真实实现。先有可调用入口，再确认失败原因是行为缺失。
- Green：只实现这一条最小路径，包含真实的本地持久化版本与两套索引，保持源数据不变。
- 后续逐项循环：文档头校验、空正文、重复 ID、递归发现、BM25 大小写／标识符／无词干处理、无匹配与空词项语料、同分稳定排序。每增加一项测试后立即完成相应最小实现。
- Refactor：集中数据和错误契约，避免 CLI 或后续模块复制校验。测试通过公开调用验证结果，不断言内部容器或私有方法。

**完成条件**：对应场景在最小输入上通过；明确当前 embedding 是测试替身，不能称真实模型链路已通过。

### T03：接入实际 tokenizer、Qwen 编码与 dense 检索

**依赖**：T02。**对应**：RAG-01、08、11、13、16。**代码**：`embedding.py`、`retrieval.py`、服务接线与配置。**测试**：`test_embedding_contract.py`、`integration/test_local_model.py`。

- 按单个行为循环验证：文档和查询使用匹配 revision、查询指令与文档格式不同、输出维数／有限数值、模型错误向调用方传播、实际长度检查防止静默截断。
- 依据官方模型用法，用 Sentence Transformers 实现查询／文档分别编码，固定查询 prompt、L2 归一化与 cosine；采用普通 PyTorch 可用的 attention 路径，不把 FlashAttention 当成基础版前置条件。
- token 计数覆盖真正送入模型的标题、正文及自动特殊 token，不能只对未包装的正文计数。检查 tokenizer 和模型运行配置不会把合法片段二次缩短；对过长查询明确报错，不悄悄截断。
- 固定实际模型／tokenizer 的提交 revision，将所需文件下载到 `C:/all/tools/llm/models/Qwen3-Embedding-0.6B/`，核对完整性并配置本地加载；在 RTX 5060 Ti 上先用短文本小批量实测，再确定 dtype 和 batch size 并记录，不预设显存一定足够。
- 真实集成验证使用少量英文 setup／hold 文本，运行实际构建与 dense 查询，并重新打开 Qdrant 后检索。运行时间与峰值显存作为观测数据，不临时增加 Spec 未要求的性能门槛。

**完成条件**：模型契约测试通过，实际模型 smoke test 成功并记录环境；真实依赖不可用时不能把跳过标记当作通过。

### T04：完成正文结构解析、递归分块与重叠

**依赖**：T03 的真实 tokenizer；T01 资料可作为样本。**对应**：RAG-02、03、04、11。**代码**：`document_loader.py`、`chunking.py`、服务接线。**测试**：`test_markdown_chunking.py`。

- 依次循环：标题路径与原始位置、章节边界、段落装箱、超长段落断句、长句按词拆分、无边界文本字符兜底、正文重叠、无法推进时错误。
- 用 markdown-it 源行映射与原始字符范围恢复正文，解析后的行号加回 YAML 文档头偏移，避免来源位置错位。列表按正文处理但保留原始标记与顺序。
- 用手工构造的缩写、小数、标识符样本验证 pySBD；保留未清洗文本的偏移，避免断句时改写原文。
- 以真实 Qwen tokenizer 验证实际片段预算及重叠预算；不能假定字符数等于 token 数，或简单相加子串 token 数就等于拼接后的 token 数。每次加入标题／重叠后重新核验。
- 重叠需要同时留出新正文的空间；没有满足自然边界的后缀时取零。字符兜底基于原始 Unicode 字符位置推进，不通过截断 token ID 再 decode 改写文本。

**完成条件**：对应场景通过；可用原始范围核对非重叠正文完整覆盖，构建输出没有静默遗漏、跨章节正文混入或无限递归。测试断言行为和内容保留，不复制生产分块算法计算预期。

### T05：完成代码与表格的结构拆分

**依赖**：T04。**对应**：RAG-05、06、07。**代码**：`document_loader.py`、`chunking.py`。**测试**：`test_structured_chunks.py`。

- 按循环分别实现：可容纳完整块、整体移入下一片段、超长代码按完整行拆分、超长表格按完整数据行拆分、单行超限报错。
- 代码测试包含围栏内看似标题的文本、不同围栏长度、缩进与行号，确认实际编码内容中没有注入额外 RTL。未给语言标记时不猜测。
- 表格测试包含对齐分隔行、单元格中的转义竖线和行内代码，使用解析结果识别结构，不用简单 `split('|')` 重建表格。
- 对真实 tokenizer 构造临界输入，覆盖标题／围栏／重复表头使片段刚好可容纳和无法容纳的两种边界。用原始数据行集合及位置验证完整覆盖，不把重复表头算成重复数据。

**完成条件**：结构测试通过；异常可定位文件、行号与 token 数；不对每个代码碎片运行编译来冒充本任务验收。

### T06：完成三模式检索与 RRF 融合

**依赖**：T03；全链路回归使用 T04/T05。**对应**：RAG-12～16。**代码**：`lexical.py`、`retrieval.py`、`service.py`。**测试**：`test_retrieval.py`。

- 依次循环：默认模式与 top_k、候选数与覆盖 top_k 的校验、两路交集与独有候选、RRF 融合、片段去重、同分与截断边界、BM25 空结果、一路抛错。
- 排序测试使用人工可推导的少量固定向量和词项资料；用独立手算的排名／分数样例断言，不把生产 RRF 函数再调用一遍作为预期值。
- 向量与 BM25 本地索引采用真实组件；测试只在模型依赖边界提供固定向量。验证返回排名来自各路最终候选列表，缺席排名为空，不能用排名零代替。
- 覆盖 `top_k` 大于默认候选数和全库片段数的情况，以及所有片段同分时仍按 ID 截取；不得因底层默认排序破坏稳定性。

**完成条件**：Spec 对应模式、融合和失败语义在服务入口通过；真实模型另由 T10 验收，不把固定向量结果当领域效果。

### T07：完善全量重建、版本一致性与失败恢复

**依赖**：T02～T06。**对应**：RAG-08～11、16。**代码**：`storage.py`、`service.py`。**测试**：`test_generation_recovery.py`。

- 逐项循环：资料新增／修改／删除后的重建、重复构建不累积、索引 ID 缺失或版本错配、模型失败、存储写入失败、指针发布失败、进程中断、下一次加载恢复。
- 用临时目录和真实 Qdrant 验证磁盘状态变化。故障注入只针对模型 SDK、文件系统写入／替换等外部边界；通过后续公开检索行为验证 A 仍可用，不以私有状态断言替代恢复验收。
- 中断测试使用受控子进程和同步事件，在发布前终止，避免靠固定睡眠猜测时点。分别验证发布前中断和发布后重新启动，关闭本地数据库句柄后进行目录处理。
- manifest 记录配置／版本和数据指纹；读取时检查两套索引与片段的一致关系，不能仅验证文件是否存在。

**完成条件**：对应失败和恢复场景通过；当前有效版本不会被清理，半成品不会成为成功版本。测试产物清理限于已验证的临时根目录。

### T08：交付 Python 公共入口与命令行

**依赖**：T06、T07。**对应**：RAG-13、16、17。**代码**：`__init__.py`、`__main__.py`、`contracts.py`、README。**测试**：`test_cli.py`。

- 逐项循环：build 参数传递、search 参数传递、默认值、JSON 成功输出、可读错误及退出码、空结果、同配置的 Python／CLI 对照。
- CLI 只负责解析／输出，不复制分块、索引或检索规则。避免 argparse 与 Python 边界对 `top_k` 等参数接受范围不同。
- 子进程测试覆盖真正的命令入口；涉及实际 embedding 的 CLI 对照归入 model 集成组，不能把测试替身开关暴露为生产用户选项。

**完成条件**：两个入口通过同一契约；README 给出准确的安装、构建、检索示例与模型准备要求。

### T09：实现独立效果评估与报告

**依赖**：T01、T08。**对应**：RAG-E01～E03 的评估机制。**代码**：`evaluate.py`。**测试**：`test_evaluation.py`。**输入**：开发集与冻结验收集。

- 先用人工构造的检索结果验证命中计算、分类汇总、Top-K 截断、同名章节辨别和“只有重复标题不算命中”，逐行为 TDD 实现。
- 评估通过公共检索接口执行三种模式，输出机器可读 JSON 与 Markdown 摘要；报告含逐题结果、正文／来源、分类指标、总指标与实际配置。
- 原始正文跨度负责关联章节标签；不能仅按文档名命中，更不能用运行时 LLM 判断替代预先冻结的相关性标签。
- 缺失／过期标签、样本分类数量不符合 Spec、数据指纹变化或运行失败时，评估报告明确不完整，不能按成功样本缩小分母后宣布通过。

**完成条件**：评估器测试通过，可运行开发集；此时只证明指标计算正确，不宣称最终验收达标。

### T10：真实资料集成、最终评估与交付

**依赖**：T00～T09。**对应**：全部验收项，重点 RAG-E01～E03。**修改位置**：运行产物、验证记录、README；必要的缺陷修复回到对应任务。

1. 使用真实 Qwen 模型和正式英文资料全量构建，检查所有片段实际 token 数、来源和结构拆分结果；结束进程后重新加载并检索。
2. 运行开发查询检查问题，在开发集上完成修复和参数选择；所有改动保持 Spec 语义，修改参数需重建并记录。
3. 固定代码／依赖／模型／语料／评估集版本及配置，运行验收集三模式评估，按 Spec 的总体与分类门槛判断。没有通过就记录未通过；不得降低门槛或把失败问题移出集合。
4. 完成真实路径的 Python／CLI 对照与失败保护检查；不在生产知识源上破坏性修改，以独立临时语料和知识库执行故障场景。
5. 更新验证报告，分别列行为测试、真实模型集成、效果评估、未完成的主链联合验收。清理本次不再使用的临时产物，保留复现所需资料、配置和评估报告。

**完成条件**：所有对应功能检查及效果标准通过才可宣称本 Spec 交付；否则保留明确失败或阻塞项，不以代码存在、pytest 默认组通过或模拟结果代替。

## 5. 验证命令与执行时点

所有命令从项目根目录运行，并显式指定已有 Conda TVGuider 环境，不依赖当前 shell 是否已执行激活。下面是执行计划时的命令，不是在编写计划时已经运行的验证；相关模块、配置、测试和脚本必须先由指定任务创建，不跳过任务直接运行不存在的入口。

### 5.1 T00：环境准备

```powershell
conda run -n TVGuider python --version
conda run -n TVGuider python -c "import sys; print(sys.executable)"
conda list -n TVGuider
```

T00 根据官方安装信息确定 GPU 兼容的 torch 安装命令并写入环境记录，安装命令同样显式指定 TVGuider；创建 pyproject 后再安装本包和开发依赖。以下命令以已处理好 GPU 依赖为前提，不要求预先升级 pip：

```powershell
conda run -n TVGuider python -m pip install -e '.[dev]'
conda run -n TVGuider python -m pip check
conda run -n TVGuider python -m pip freeze --exclude-editable | Set-Content -LiteralPath requirements.lock.txt -Encoding utf8
```

依赖快照必须来自 TVGuider，不能从 Anaconda 基础环境导出。`pyproject.toml` 只声明本项目实际使用的依赖；环境中的其他已有包不因此变成本项目的必需依赖。环境记录同时保留 Conda／Python 版本、安装前后变化、GPU wheel 来源和模型 revision；pip 精确清单本身不包含完整的 Conda 环境信息，也不能替代 CUDA 兼容验证。

### 5.2 T02～T09：逐任务与回归检查

在每个 TDD 循环中，先运行当前新增场景的单个测试，观察行为失败，再实现；Green 后运行该任务文件及受影响回归。以下示例测试文件分别由对应任务创建：

```powershell
conda run -n TVGuider python -m pytest tests/test_build_search.py -q
conda run -n TVGuider python -m pytest tests/test_markdown_chunking.py tests/test_structured_chunks.py -q
conda run -n TVGuider python -m pytest tests/test_retrieval.py tests/test_generation_recovery.py -q
conda run -n TVGuider python -m pytest tests/test_cli.py tests/test_evaluation.py -q
```

各测试文件存在且相关实现完成后，执行汇总检查：

```powershell
conda run -n TVGuider python -m ruff check src tests
conda run -n TVGuider python -m ruff format --check src tests
conda run -n TVGuider python -m pytest -m 'not model and not evaluation' -q
conda run -n TVGuider python -m pytest -m model -q
git diff --check
```

Git 命令以 T00 已建立仓库为前提。真实模型集成测试若缺少依赖，开发默认组可以独立运行，但最终交付记录必须说明未完成的 model 验证，不能把 skipped 当通过。模型资源准备完成后，最终显式 model 运行缺资源应失败。

### 5.3 T08～T10：实际构建与检索

T03 写好固定模型配置，T01 准备资料，T08 建立 CLI 后执行：

```powershell
conda run -n TVGuider python -m rag build --source knowledge/raw --kb artifacts/rag/kb --config configs/rag.yaml
conda run -n TVGuider python -m rag search --kb artifacts/rag/kb --query 'What can cause a setup violation on a long combinational path?' --mode hybrid --top-k 5
conda run -n TVGuider python -m rag search --kb artifacts/rag/kb --query 'Why can a short data path cause a hold violation?' --mode bm25 --top-k 5
```

命令行省略模式时的默认行为也必须由 T08 测试验证。dense 同样通过 `--mode dense` 运行；索引加载以其 manifest 为准，不另传可能冲突的编码配置。

### 5.4 T09～T10：开发与最终评估

`evaluate.py` 及数据集建立后使用：

```powershell
conda run -n TVGuider python -m rag.evaluate --kb artifacts/rag/kb --dataset evaluation/rag/dev.jsonl --manifest evaluation/rag/manifest.json --output artifacts/rag/evaluation/dev
conda run -n TVGuider python -m rag.evaluate --kb artifacts/rag/kb --dataset evaluation/rag/acceptance.jsonl --manifest evaluation/rag/manifest.json --output artifacts/rag/evaluation/acceptance
```

评估入口依次执行三种模式；只有 manifest 标记为验收用途的数据集执行 Spec 的分类数量和通过门槛判定，开发集用于观测。第二条命令只在调参结束并冻结输入后执行。模型／语料／参数改变后不能继续引用旧报告证明新配置达标。

## 6. 提交与收尾安排

Git 在 T00 准备后，按可审查的阶段提交，不要求每个 task 一个 commit：

| 阶段 | 内容 | 提交前验证 |
| --- | --- | --- |
| 环境与资料基底 | T00、T01 的环境配置、源文档与评估输入 | 实际环境记录、资料来源和数据隔离检查 |
| 最小真实闭环 | T02、T03 | 最小行为回归及真实模型 smoke |
| 分块与检索 | T04～T06 | 对应功能回归与真实 tokenizer 样本 |
| 稳定构建与入口 | T07、T08 | 故障恢复、持久化和 CLI 契约验证 |
| 评估与交付 | T09、T10 | 完整功能检查、真实模型集成与最终效果报告 |

原始资料和标签若因实际执行修订，单独记录原因与版本，不能在提交中隐藏验收集用途变化。不要提交虚拟环境、模型权重、Qdrant 数据库、临时文件或日志；保留可重建配置和必要的精简评估结果。

最终报告列出已完成任务、实际提交、验证命令与结果、效果指标和 Spec 偏离项。主链的 TVIR／根因分析／修复生成联合验证明确列为后续工作，不在本任务中宣称通过。计划完成不等于实施完成。

## 7. 依赖依据与需实测事项

- [markdown-it-py 官方用法](https://markdown-it-py.readthedocs.io/en/latest/using.html)提供结构 token、源行映射与表格规则；计划在其上保留原始切片，不采用 HTML 渲染后再转文本的方式。
- [pySBD 官方仓库](https://github.com/nipunsadvilkar/pySBD)与[Segmenter 源码](https://github.com/nipunsadvilkar/pySBD/blob/master/pysbd/segmenter.py)支持英文断句及位置相关配置；对时序资料中的缩写仍需测试。
- [rank-bm25 官方源码](https://raw.githubusercontent.com/dorianbrown/rank_bm25/master/rank_bm25.py)给出 BM25Okapi 默认参数和全量评分接口；计划补充词项命中过滤与稳定排序，不直接使用其默认 Top-N 顺序。
- [Qwen 模型说明](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)提供 Sentence Transformers 的查询／文档编码方式；Windows GPU 兼容、特殊 token 计数和显存占用仍需 T00/T03 实测。
- [Qdrant 客户端](https://github.com/qdrant/qdrant-client)支持本地持久化；本项目的整体版本发布、损坏检测和恢复语义由 T07 实现，不假设数据库自动替我们管理另一套 BM25 数据。

以上是落实 Spec 的依赖选择和工程安排，不构成已经安装、运行或通过验收的证据。
