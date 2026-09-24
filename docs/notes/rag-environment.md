# RAG 执行环境记录

日期：2026-09-24。使用现有 Conda `TVGuider`，没有创建 `.venv`。

## 实测环境

| 项目 | 结果 |
| --- | --- |
| Python | 3.12.13，`C:/all/environments/anaconda3/envs/TVGuider/python.exe` |
| Conda | 24.9.2 |
| GPU | NVIDIA GeForce RTX 5060 Ti，16311 MiB，compute capability 12.0 |
| 驱动 | 591.86 |
| PyTorch | 2.11.0+cu128，CUDA runtime 12.8 |
| 编码栈 | sentence-transformers 5.1.2、transformers 4.57.6、tokenizers 0.22.2 |
| 索引 | qdrant-client 1.19.1、rank-bm25 0.2.2 |
| 解析 | markdown-it-py 4.2.0、PyYAML 6.0.3、pysbd 0.3.4 |
| 开发工具 | pytest 9.1.1、ruff 0.16.8 |

CUDA 实际运算：`arange(16).reshape(4,4)` 在 GPU 上与其转置相乘，结果元素之和为 `3680.0`。真实 Qwen 编码输出为 1024 维、有限数值、L2 归一化向量，文档与查询使用不同前缀。测试包含编码长度检查、真实 Qdrant 落盘、独立进程重新加载和 CLI/API 对照。

## 依赖与复现

安装前环境只有 packaging 26.0、pip 26.0.1、setuptools 82.0.1、wheel 0.46.3。本次增加项目运行和测试依赖；PyTorch 的依赖约束将 setuptools 调整为 78.1.0。没有修改 Anaconda base 环境。

GPU wheel 使用 [PyTorch 官方 CUDA 12.8 索引](https://download.pytorch.org/whl/cu128)，版本依据 [官方历史版本安装说明](https://pytorch.org/get-started/previous-versions/) 核对，再用本机 GPU 实测。关键安装步骤：

```powershell
conda run -n TVGuider python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
conda run -n TVGuider python -m pip install -r requirements.lock.txt
conda run -n TVGuider python -m pip install --no-deps -e .
conda run -n TVGuider python -m pip check
```

`requirements.lock.txt` 是安装完成后从 TVGuider 导出的精确环境快照，包含安装准备过程留下的额外依赖；`pyproject.toml` 只声明项目直接依赖。快照针对本次 Windows/Python/CUDA 环境，不是跨平台 Conda 环境锁。`pip check` 已通过。

## 固定模型

- 模型：`Qwen/Qwen3-Embedding-0.6B`。
- 本地目录：`C:/all/tools/llm/models/Qwen3-Embedding-0.6B`。
- 模型与 tokenizer revision：`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`。
- 权重文件：1,191,586,416 bytes；源码仓库不包含权重。
- 使用 CUDA、float32、SDPA、batch size 8；没有安装 FlashAttention。
- 文档不加查询指令；查询使用 checkpoint 自带的 `query` prompt，见 [固定版本模型说明](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/tree/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3)。
- 实测 tokenizer 会添加特殊 token；长度由完整 tokenizer 编码计数，不额外手工猜测 EOS 数量。

模型通过以下独立准备命令下载并生成 `rag-model.json` 文件指纹记录：

```powershell
conda run -n TVGuider python scripts/provision_model.py --config configs/rag.yaml
```

正常 build/search 使用 `local_files_only=True`，不会自动联网补模型。加载时核对 receipt、revision 与文件指纹；构建 manifest 记录编码配置、模型文件指纹及关键库版本。调整模型、编码配置或依赖后应重建知识库。`bm25` 查询不加载模型，但仍校验完整知识库的一致性。
