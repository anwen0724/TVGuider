# TV-Guider

## 核心目录

```text
src/
  run_pipeline.py   # RTL 与 STA 报告目录的全流程入口
  tvir/             # RTL 与时序报告解析、TVIR 构建
  root_cause/       # 根因分析
  rag/              # 知识库构建与检索
  repair/           # 修复策略与结果生成
  prompts/          # 提示词构建
  llm_clients/      # 大模型接口
knowledge/raw/      # Markdown 知识资料
configs/            # 运行配置
scripts/            # 模型下载脚本
evaluation/rag/     # 检索评估数据
tests/              # 测试
```

## 运行命令

```powershell
# 在项目根目录执行，使用 Python 3.12+
python -m pip install -e ".[llm,dev]"

# 将 .env.example 复制为 .env 并填写 API Key
# 配置 configs/rag.yaml 和 src/run_pipeline.py 开头的参数
# 安装 Icarus Verilog，将其加入 PATH 或配置 IVERILOG_DIR

# 下载嵌入模型
python scripts/provision_model.py --config configs/rag.yaml

# 构建知识库
python -m rag build --source knowledge/raw --kb artifacts/rag/kb --config configs/rag.yaml

# 独立检索
python -m rag search --kb artifacts/rag/kb --query "How can pipeline registers improve setup timing?" --mode hybrid --top-k 5

# 运行完整流程
python src/run_pipeline.py

# 测试
python -m pytest -q

# 检索评估
python -m rag.evaluate --kb artifacts/rag/kb --dataset evaluation/rag/acceptance.jsonl --manifest evaluation/rag/manifest.json --output artifacts/rag/evaluation/acceptance
```
