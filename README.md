# MRG-02-RAG

面向医学报告生成的知识库采集与整理项目。当前版本重点完成医学知识数据的网络爬取、配置化关键词管理、数据落盘和基础测试。

## 运行环境

- 操作系统：Windows / Linux / macOS
- Python：3.10 及以上，建议 3.13
- Shell：PowerShell 或兼容终端
- 依赖：当前运行时仅使用 Python 标准库；测试需要 `pytest`

## 环境配置

创建虚拟环境：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.venv\Scripts\Activate.ps1
```

安装项目与测试依赖：

```powershell
pip install -e .[test]
```

## 目标

- 建立医学知识库前置数据层，减少后续 LLM 幻觉。
- 支持围绕 `氟斑牙`、`氟骨症`、`氟中毒` 等关键词持续扩展采集。
- 保留来源、时间和目录说明，便于后续检索、清洗和追溯。

## Demo

运行默认配置：

```powershell
python cli/crawl.py --output-dir dataset
```

使用自定义配置：

```powershell
python cli/crawl.py --config config/crawl_config.json --output-dir dataset
```

运行测试：

```powershell
pytest -q
```

## 配置说明

关键词和抓取 URL 模板由 `config/crawl_config.json` 管理，可直接手动增删。

- `keywords`：抓取关键词列表。
- `url_templates`：搜索入口模板，支持 `{keyword}` 占位符，关键词会自动做 URL 编码。

## 项目结构

- `src/mrg02_rag/`：核心实现。
- `cli/`：demo 入口脚本。
- `config/`：可编辑配置文件。
- `dataset/`：抓取后的原始数据输出目录。
- `output/`：后续处理结果目录，预留给清洗结果、索引、报告导出等产物。
- `tests/`：自动化测试。
- `versions/`：版本说明与分析文档。

## 输出目录说明

### `dataset/`

保存爬取后的原始医学资料，按关键词和抓取时间分目录存放。每个子目录通常包含：

- `README.md`：该批数据说明。
- `manifest.json`：元数据，包括关键词、抓取时间、记录数等。
- `documents.jsonl`：抓取到的文档记录。

### `output/`

预留给后续处理结果，例如：

- 清洗后的结构化数据。
- 检索索引或向量库导出文件。
- 报告生成结果。

## 版本说明

当前 `v1` 以数据采集和工程骨架为主，后续迭代重点是：

- 数据清洗与去重。
- 结构化抽取与字段标准化。
- 采集日志与异常处理。
- 更完整的单元测试与回归测试。
