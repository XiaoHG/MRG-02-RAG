# MRG-02-RAG

面向医学报告生成的知识库与知识图谱构建项目。项目从医学 PDF、文本文件和
PubMed 摘要中构造可审查的知识三元组，并支持使用本地 Hugging Face 模型完成
抽取，目标是为报告生成提供可追溯的专业依据，减少 LLM 幻觉。

当前项目保留三条实际可用的命令行入口：

- `cli/extract_triples.py`：准备文档、构造 prompt、调用 LLM 并输出三元组。
- `cli/local_llm_runner.py`：读取 stdin 中的 prompt，调用本地 Hugging Face 模型，
  将结果写到 stdout。
- `cli/trafilatura.py`：抓取单个网页，或通过 DDGS 检索后批量提取网页正文并保存为
  Markdown。

旧版 `crawl.py` 及其配置化爬虫模块已经移除。医学资料采集统一使用
`trafilatura.py`，三元组抽取统一使用 `extract_triples.py`。

## 目录结构

- `src/documents.py`：PDF/文本文件读取、HTML 正文提取和文本分块。
- `src/extractor.py`：prompt 构造、CSV 三元组解析和清洗。
- `src/llm.py`：本地 LLM 命令适配器。
- `src/pipeline.py`：三元组抽取流程和结果写盘。
- `src/prompts.py`：prompt 文件加载。
- `src/pubmed.py`：PubMed 摘要检索、解析和分块。
- `src/schema.py`：文档块、三元组和抽取结果的数据结构。
- `cli/extract_triples.py`：三元组抽取 CLI。
- `cli/local_llm_runner.py`：本地模型推理 CLI。
- `cli/trafilatura.py`：网页正文提取和 DDGS 批量采集 CLI。
- `prompts/`：抽取 prompt 和本地模型 system prompt。
- `references/`：人工整理的医学资料和文献。
- `output/`：运行结果，包括 prompt、模型原始输出和清洗后的三元组。
- `tests/`：自动化测试。

## 整体流程

```text
本地 PDF/文本文件或 PubMed 摘要
    -> 文本读取与分块
    -> prompt 构造
    -> 本地 LLM 抽取
    -> 三元组清洗
    -> CSV/JSONL 审核文件
```

网页资料使用独立的 `trafilatura.py` 采集后，再将生成的 Markdown 文件通过
`extract_triples.py` 批量抽取。

## 环境安装

推荐使用已有 conda 环境：

```powershell
conda activate mrg
```

安装测试、PDF 处理和网页采集依赖：

```powershell
pip install -e .[test,pdf,web]
```

如果需要运行本地 Qwen、DeepSeek 或其他 Hugging Face 模型，再安装：

```powershell
pip install -e .[llm]
```

本地模型是否使用 GPU 取决于当前机器、CUDA、PyTorch 和量化后端。运行前建议确认
`torch.cuda.is_available()`，并确认模型路径或模型 ID 可被 Transformers 识别。

## 三元组抽取

### 只生成 prompt

本地模型尚未准备好时，可以只准备文档分块和 prompt：

```powershell
python cli/extract_triples.py `
    --pdf "references/CNKI/pdf/地方性氟中毒近10年发病机制研究概况_姜爽.pdf" `
    --write-prompts-only `
    --output-dir output
```

也可以处理单个文本文件：

```powershell
python cli/extract_triples.py `
    --text-file "references/CNKI/README.md" `
    --write-prompts-only `
    --output-dir output
```

支持的常见输入格式包括：

```text
.pdf .md .txt .html .htm .json .csv .tsv .xml .yaml .yml .rst .log .text
.py .js .ts .jsx .tsx .css .scss .sql .ini .cfg .conf .toml .tex
.c .cpp .h .java .go .rs .vue
```

可以混合传入多个文件。`--input-file` 可以重复使用；`--input-dir` 也可以重复使用，
每个目录都会递归扫描。目录中的不支持格式会自动跳过，重复传入的同一个文件只会
处理一次：

```powershell
python cli/extract_triples.py `
    --input-file "references/overview.md" `
    --input-file "references/clinical_notes.txt" `
    --input-dir "references/CNKI" `
    --input-dir "references/guidelines" `
    --write-prompts-only `
    --output-dir output
```

兼容参数仍然保留：

- `--pdf`：单个 PDF 文件，可重复传入。
- `--pdf-dir`：PDF 目录，可重复传入，递归读取其中的 PDF 文件。
- `--text-file`：单个文本文件，可重复传入。
- `--input-file`：任意支持格式的单个文件，可重复传入。
- `--input-dir`：任意支持格式的目录，可重复传入并递归扫描。

对于 HTML 文件，系统会去除 `script`、`style`、`noscript` 和 `template` 内容，
只将可见文本送入分块和抽取流程。显式传入不支持的文件格式时，命令会报错并提示
支持的扩展名。

### 使用本地模型抽取

先设置本地模型目录：

```powershell
$env:LOCAL_LLM_MODEL="D:/models/Qwen2.5-32B-Instruct"
```

然后将 `local_llm_runner.py` 作为 LLM 命令传给抽取入口：

```powershell
python cli/extract_triples.py `
    --pdf "references/CNKI/pdf/地方性氟中毒近10年发病机制研究概况_姜爽.pdf" `
    --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --trust-remote-code" `
    --llm-timeout 3600 `
    --output-dir output
```

也可以处理一个或多个目录中的全部支持格式文件：

```powershell
python cli/extract_triples.py `
    --input-dir "references/CNKI" `
    --input-dir "references/guidelines" `
    --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --load-in-8bit --trust-remote-code" `
    --llm-timeout 3600 `
    --output-dir output
```

默认抽取结果目录为：

```text
output/extraction/<UTC时间戳>/
```

其中 `<UTC时间戳>` 采用 `YYYYMMDD_HHMMSS` 格式。也可以通过 `--run-name` 修改
`extraction` 目录名，例如：

```powershell
python cli/extract_triples.py `
    --input-dir "references" `
    --run-name fluorosis_review `
    --write-prompts-only `
    --output-dir output
```

### 处理 PubMed 摘要

```powershell
python cli/extract_triples.py `
    --pubmed-query "dental fluorosis" `
    --pubmed-max-results 20 `
    --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --load-in-8bit --trust-remote-code" `
    --llm-timeout 3600 `
    --output-dir output
```

### 不调用真实模型的冒烟测试

使用静态 CSV 输出验证完整写盘流程：

```powershell
python cli/extract_triples.py `
    --text-file "references/CNKI/README.md" `
    --mock-output "head_entity,relation,tail_entity`n地方性氟中毒,caused_by,过量氟" `
    --output-dir output
```

### 抽取输出

每次运行会生成 `output/<run_name>/<timestamp>/`，默认就是
`output/extraction/<timestamp>/`，主要文件包括：

- `chunks.jsonl`：文档分块及来源。
- `prompts.jsonl`：发送给模型的完整 prompt。
- `raw_outputs.jsonl`：模型原始输出。
- `triples_clean.csv`：经过清洗、包含来源和分块 ID 的三元组。
- `triples_for_neo4j.csv`：适合导入 Neo4j 的三列 CSV。
- `manifest.json`：运行参数和统计信息。
- `README.md`：本次运行的说明。

清洗流程会过滤格式错误、非法关系、解释性文字和重复三元组。输出仍需经过人工
医学审核，不能直接视为临床诊断结论。

## 网页与论文资料采集

`cli/trafilatura.py` 是项目当前唯一的网页资料采集入口，提供单网页和 DDGS
批量检索两种模式。它负责抓取和正文提取，不负责医学事实审核或三元组抽取。

### 单网页模式

使用默认示例网页：

```powershell
python .\cli\trafilatura.py
```

抓取指定网页：

```powershell
python .\cli\trafilatura.py "https://example.com/article"
```

脚本优先调用 `trafilatura.fetch_url()`，返回空结果时使用 `requests` 回退。结果
默认保存到 `output/trafilatura/<UTC时间戳>/`，例如
`output/trafilatura/20260910_143025_123456Z/`。每次运行都会创建新的时间戳子目录，
文件名优先使用网页标题，并自动避免覆盖同名文件。
抓取前会扫描该目录下已有 Markdown 文件的 `source_url` 元数据，并对 URL 做规范化
处理；如果 URL 已经下载过，则跳过抓取，不会再次调用 `fetch_url()`。

### DDGS 批量检索

中文主题示例：

```powershell
python .\cli\trafilatura.py `
    --query "地方性氟中毒 发病机制" `
    --region cn-zh `
    --max-results 20 `
    --delay 1
```

英文主题示例：

```powershell
python .\cli\trafilatura.py `
    --query "dental fluorosis pathogenesis" `
    --region us-en `
    --max-results 50 `
    --timelimit y
```

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `url` | 无 | 单网页模式的位置参数。 |
| `--query` / `-q` | 无 | DDGS 检索词，提供后进入批量模式。 |
| `--backend` | `auto` | DDGS 搜索后端。 |
| `--max-results` | `20` | 最多处理的搜索结果数量。 |
| `--region` | `cn-zh` | 搜索区域，例如 `cn-zh` 或 `us-en`。 |
| `--safesearch` | `moderate` | 安全搜索级别。 |
| `--timelimit` | 无 | 时间限制：`d`、`w`、`m` 或 `y`。 |
| `--timeout` | `30` | 单次 HTTP 请求超时时间，单位为秒。 |
| `--delay` | `0` | 处理结果之间的等待时间，单位为秒。 |

批量结果会保存来源 URL、搜索词、搜索标题、摘要和发布时间等元数据。遇到登录、
验证码、JavaScript 页面、PDF 或权限限制时，脚本会记录跳过并继续处理其他结果。
请遵守目标网站的访问规则、版权要求和 robots 约束。

每次 DDGS 搜索都会在本次运行的
`output/trafilatura/<UTC时间戳>/ddgs_search.json` 中保存结果。该文件保存：

- DDGS 搜索词和搜索参数。
- DDGS 返回的 URL、标题、摘要和发布时间。
- 每个 URL 的规范化地址。
- `content` 保存压缩后的搜索摘要，最多 200 字；原始摘要不足 100 字时保留实际内容。
- 抓取状态：`pending`、`saved`、`skipped_existing` 或 `failed`。
- 成功保存的 Markdown 相对路径，或失败原因。

该 JSON 文件是网页采集的中间记录，可用于回溯搜索结果和核对哪些 URL 已经抓取。

## Prompt 管理

提示词保存在 `prompts/`，不直接写在业务代码中：

- `prompts/extraction_triples_v1.md`：三元组抽取 prompt。
- `prompts/system_triples_v1.md`：本地模型 system prompt。

`src/prompts.py` 负责加载提示词。每次抽取运行会在输出目录保存完整 prompt，便于
人工审查和回放。

## 测试

运行全部测试：

```powershell
pytest -q
```

测试覆盖文档分块、prompt 加载、三元组解析与清洗、PubMed XML 解析、抽取流水线、
LLM 命令适配器、本地模型 runner 参数校验和 CLI 行为。

## 重要注意事项

- `mrg` 是 conda 环境名，不是 Python 模块名。
- `extract_triples.py` 调用本地模型时，`--llm-command` 必须指向真实存在的
  `cli/local_llm_runner.py`，或其他兼容 stdin/stdout 协议的 runner。
- `local_llm_runner.py` 从 stdin 读取 prompt，从 stdout 输出模型结果；日志写入
  stderr，不要混入 CSV 输出。
- PDF 文本质量、网页正文质量和模型输出都需要人工抽查。
- CNKI、万方等来源可能存在访问权限、版权和格式限制。
