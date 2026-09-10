# MRG-02-RAG

面向医学报告生成的知识库与知识图谱构建项目。当前代码包含三条基础能力：

- 医学资料采集：通过 DDGS 检索公开网页，再使用 Trafilatura 提取正文，保存原始文本和元数据。
- 网页单页抓取：直接抓取指定 URL，并将正文保存为 Markdown。
- 医学知识三元组抽取：从 CNKI PDF、本地文本或 PubMed 摘要中构造 prompt，调用本地 LLM 抽取 CSV 三元组，供人工审核和 Neo4j 导入。

项目目标是为医学报告生成提供可追溯、可审核的专业知识依据，减少 LLM 幻觉。

当前网页资料采集先采用 `DDGS + Trafilatura` 跑通最小闭环，不要求 Docker 或
SearXNG 服务：

```text
检索词 -> DDGS 搜索结果 -> requests/Trafilatura 抓取网页 -> 正文提取 -> Markdown
```

## 目录结构

- `src/`：核心代码，所有模块直接放在 `src` 根目录下，不使用项目名前缀子包。
- `cli/`：命令行入口。
- `prompts/`：LLM 使用的提示词文件，每个提示词单独保存，代码运行时加载。
- `config/`：采集配置文件。
- `references/`：人工整理的医学资料和 PDF 文献。
- `dataset/`：网页采集输出目录。
- `output/`：三元组抽取输出目录。
- `tests/`：自动化测试。
- `versions/`：版本需求、分析和迭代说明。

## 环境

推荐使用已有 conda 环境：

```powershell
conda activate mrg
```

安装测试和 PDF 处理依赖：

```powershell
pip install -e .[test,pdf]
```

如果需要运行本地 Qwen/DeepSeek 模型，再安装 LLM 推理依赖：

```powershell
pip install -e .[llm]
```

如果需要使用网页单页抓取或 DDGS 批量检索，再安装网页采集依赖：

```powershell
pip install -e .[web]
```

也可以单独安装：

```powershell
pip install ddgs trafilatura requests
```

本地模型是否使用 GPU 取决于当前机器、CUDA、PyTorch 和模型量化后端。
运行前应先确认 `torch.cuda.is_available()` 和模型实际加载设备。

## Prompt 管理

所有 LLM 使用的提示词都放在 `prompts/` 目录，不写在源码中：

- `prompts/extraction_triples_v1.md`：文本分块的三元组抽取 prompt。
- `prompts/system_triples_v1.md`：本地模型 runner 使用的 system prompt。

代码通过 `src/prompts.py` 加载提示词文件。运行时生成的完整 prompt 会保存到输出目录的 `prompts.jsonl`，便于审查和回放。

## 三元组抽取

### 只生成 Prompt

本地模型还没有准备好时，先生成文本分块和 prompt：

```powershell
python cli/extract_triples.py --pdf "references/CNKI/pdf/地方性氟中毒近10年发病机制研究概况_姜爽.pdf" --write-prompts-only --output-dir output
```

### 使用本地模型抽取

先确认本地模型目录真实存在，例如：

```powershell
$env:LOCAL_LLM_MODEL="D:/models/Qwen2.5-32B-Instruct"
```

然后运行抽取：

```powershell
python cli/extract_triples.py --pdf "references/CNKI/pdf/地方性氟中毒近10年发病机制研究概况_姜爽.pdf" --llm-command "python cli/local_llm_runner.py --trust-remote-code --model-path D:/papers/medical-report-generation/MRG-02-RAG/models/Qwen2.5-32B-Instruct-GPTQ-Int4/snapshots/master" --output-dir output
```

也可以直接在命令中指定模型路径：

```powershell
python cli/extract_triples.py --pdf "references/CNKI/pdf/地方性氟中毒近10年发病机制研究概况_姜爽.pdf" --llm-command "python cli/local_llm_runner.py --model-path ./models/qwen2.5-3b-int4 --trust-remote-code" --llm-timeout 3600 --output-dir output
```

注意：不要使用 `python path/to/local_llm_runner.py`。这是旧占位示例，不是实际文件。当前真实 runner 是 `cli/local_llm_runner.py`。

### 批量处理 PDF

```powershell
python cli/extract_triples.py --pdf-dir "references/CNKI/pdf" --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --load-in-8bit --trust-remote-code" --llm-timeout 3600 --output-dir output
```

### 处理 PubMed 摘要

```powershell
python cli/extract_triples.py --pubmed-query "dental fluorosis" --pubmed-max-results 20 --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --load-in-8bit --trust-remote-code" --llm-timeout 3600 --output-dir output
```

### 冒烟测试

不调用真实模型，仅验证流程：

```powershell
python cli/extract_triples.py --text-file "references/CNKI/README.md" --mock-output "head_entity,relation,tail_entity`n地方性氟中毒,caused_by,过量氟" --output-dir output
```

## 抽取输出

每次运行会生成 `output/<run_name>/<timestamp>/`，包含：

- `chunks.jsonl`：文献文本分块。
- `prompts.jsonl`：发送给模型的完整 prompt。
- `raw_outputs.jsonl`：模型原始输出。
- `triples_clean.csv`：清洗后的三元组，包含 `source` 和 `chunk_id`，用于人工审核。
- `triples_for_neo4j.csv`：三列 CSV，用于 Neo4j 导入。
- `manifest.json`：本次运行的统计和文件索引。
- `README.md`：该批次输出说明。

模型输出会经过清洗过滤：非三列 CSV、非法关系、解释性文字、Markdown 包裹和重复三元组会被过滤。

## 医学资料采集

运行默认采集配置：

```powershell
python cli/crawl.py --config config/crawl_config.json --output-dir dataset
```

采集输出会保存到 `dataset/`，包含：

- `README.md`：该批数据说明。
- `manifest.json`：关键词、来源、抓取时间、记录数等元数据。
- `documents.jsonl`：网页文本、URL、访问状态和错误信息。

## 测试

```powershell
pytest -q
```

当前测试覆盖：

- PDF/text 分块。
- prompt 文件加载。
- CSV 三元组解析与过滤。
- PubMed XML 解析。
- 抽取流水线写盘。
- 本地模型 runner 参数校验。
- 网页采集和失败记录。

## 关键模块

- `src/documents.py`：PDF 文本提取和文本分块。
- `src/extractor.py`：prompt 构造、CSV 解析、三元组清洗。
- `src/llm.py`：LLM 命令行适配器。
- `src/pipeline.py`：批量抽取和输出写盘。
- `src/pubmed.py`：PubMed 摘要获取与解析。
- `src/prompts.py`：prompt 文件加载。
- `cli/local_llm_runner.py`：本地 Hugging Face 模型推理脚本。
- `cli/extract_triples.py`：三元组抽取入口。
- `cli/crawl.py`：医学资料采集入口。
- `cli/trafilatura.py`：单网页抓取，以及 DDGS + Trafilatura 批量论文资料采集入口。

## 注意事项

- `mrg` 只是 conda 环境名，不是代码模块名。
- `src/` 下不使用 `mrg` 前缀子目录。
- 本地模型路径必须是真实存在的模型目录，或可由 Hugging Face/Transformers 识别的模型 ID。
- CNKI、万方等资料可能存在权限或格式限制，PDF 文本抽取质量需要人工抽查。

## 网页与论文资料采集

### 工具用途

`cli/trafilatura.py` 用于抓取网页并提取主要正文，适合将公开网页、论文介绍页、
机构页面和医学资料整理为后续 RAG 处理所需的 Markdown 原始文档。

脚本提供两种模式：

- 单网页模式：直接指定一个 URL，抓取并保存该网页正文。
- 批量检索模式：使用 DDGS 检索论文或医学主题，再使用 Trafilatura 逐条提取
  搜索结果正文并保存。

批量模式不会直接绕过数据库权限，也不会保证每条搜索结果都能获取全文。对于
需要登录、验证码、纯 JavaScript 渲染、仅提供 PDF 下载或受权限限制的页面，
脚本会记录失败并继续处理其他结果。

### 安装依赖

在 `mrg` 环境中安装：

```powershell
conda activate mrg
pip install -e .[web]
```

### 单网页抓取

直接运行默认示例网页：

```powershell
python .\cli\trafilatura.py
```

抓取指定网页：

```powershell
python .\cli\trafilatura.py "https://example.com/article"
```

脚本会先调用 `trafilatura.fetch_url()`。如果该方法受到代理、响应状态或下载器
配置影响而返回空结果，则使用 `requests` 作为回退方式抓取网页。

### DDGS 批量检索

为了先跑通“检索 -> 网页抓取 -> 正文提取 -> Markdown 保存”的最小闭环，
当前暂时使用 `ddgs` 作为检索层，不需要部署 Docker 或 SearXNG。

```text
DDGS -> 搜索结果 URL -> requests/Trafilatura -> output/trafilatura/*.md
```

安装依赖：

```powershell
conda activate mrg
pip install -e .[web]
```

DDGS 负责获取搜索结果，Trafilatura 负责访问搜索结果页面并提取正文。
当前 CLI 不要求配置 SearXNG 地址，也不要求本地启动 Docker 或 SearXNG。
后续需要多引擎聚合时，可以再将检索实现替换为 SearXNG，正文提取和输出部分不变。

### 批量论文检索与采集

中文医学主题：

```powershell
python .\cli\trafilatura.py `
    --query "地方性氟中毒 发病机制" `
    --region cn-zh `
    --max-results 20 `
    --delay 1
```

英文医学主题：

```powershell
python .\cli\trafilatura.py `
    --query "dental fluorosis pathogenesis" `
    --region us-en `
    --max-results 50 `
    --timelimit y
```

增加请求间隔，降低对目标网站的访问压力：

```powershell
python .\cli\trafilatura.py `
    --query "fluoride neurotoxicity review" `
    --max-results 30 `
    --delay 1
```

### 命令行参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `url` | 无 | 单网页模式的位置参数。 |
| `--query` / `-q` | 无 | DDGS 检索词。提供后进入批量模式。 |
| `--backend` | `auto` | DDGS 搜索后端，可指定一个或多个后端。 |
| `--max-results` | `20` | 最多处理的搜索结果数量。 |
| `--region` | `cn-zh` | DDGS 搜索区域，例如 `cn-zh` 或 `us-en`。 |
| `--safesearch` | `moderate` | 安全搜索级别：`on`、`moderate` 或 `off`。 |
| `--timelimit` | 无 | 时间限制：`d`、`w`、`m` 或 `y`。 |
| `--timeout` | `30` | 单次 HTTP 请求超时时间，单位为秒。 |
| `--delay` | `0` | 处理结果之间的等待时间，单位为秒。 |

查看完整参数：

```powershell
python .\cli\trafilatura.py --help
```

### 输出目录与文件命名

所有提取结果保存到：

```text
output/trafilatura/
```

文件命名规则如下：

1. 优先使用网页正文中识别到的网页标题。
2. 如果网页没有标题，批量模式使用 DDGS 返回的标题。
3. 如果仍然没有标题，则使用 URL 的路径名或域名。
4. 自动清理 Windows 文件名不允许使用的字符。
5. 文件扩展名为 `.md`。
6. 已存在的文件不会被覆盖，而是自动添加序号，例如：

```text
article.md
article_001.md
article_002.md
```

每个批量采集结果都是独立 Markdown 文件，便于后续人工审核、去重和导入知识库。

### Markdown 文件元数据

批量模式保存的 Markdown 文件会在正文前写入 YAML 风格元数据，例如：

```markdown
---
title: "Article title"
author: "Author name"
date: "2025-01-01"
sitename: "Example Journal"
source_url: "https://example.com/article"
search_query: "fluorosis pathogenesis"
search_title: "Article title"
search_snippet: "Search result summary"
search_published_date: "2025-01-01"
---

Article main text...
```

这些字段用于保留来源和检索上下文，不代表已经完成医学事实审核。

### 批量采集流程

批量模式的处理流程为：

1. 向 DDGS 搜索后端发送检索请求。
2. 根据 URL 去重。
3. 逐条访问搜索结果网页。
4. 使用 Trafilatura 提取主要正文。
5. 保存正文和来源元数据到 `output/trafilatura/`。
6. 对无法访问或无法提取正文的结果输出跳过信息，并继续处理下一条。

建议先使用较小数量验证检索效果：

```powershell
python .\cli\trafilatura.py --query "地方性氟中毒" --max-results 5
```

确认结果质量后，再逐步增加 `--max-results`。大量采集时建议设置
`--delay`，并遵守目标网站的访问规则、版权要求和 robots 约束。
