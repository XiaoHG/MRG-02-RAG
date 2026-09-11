# MRG-02-RAG

面向医学报告生成的知识库构建项目。项目从网页、PDF、Markdown、TXT、HTML、
PubMed 摘要等来源获取医学文本，经过分块和 LLM 三元组抽取后，写入可审查、
可检索、可回溯的 LanceDB 知识库，为后续 RAG 报告生成提供证据。

项目不使用 Neo4j。三元组与原文证据统一存储在 LanceDB 的
`knowledge_triples` 表中。

## 目录结构

```text
cli/
├── trafilatura.py              # 网页抓取、DDGS 搜索和 Markdown 保存
├── extract_triples.py          # 文档分块、LLM 三元组抽取
├── local_llm_runner.py         # 本地 Hugging Face 模型 stdin/stdout 适配器
├── build_knowledge_base.py     # 构建或增量更新 LanceDB
└── query_knowledge_base.py     # 向量和结构化条件查询

src/
├── knowledge_extraction/       # 文档读取、Prompt、LLM 和三元组抽取
└── knowledge_base/             # embedding、元数据、LanceDB 存储和入库

prompts/                        # 抽取 Prompt 和本地模型 system Prompt
references/                     # 输入医学资料
output/                         # 抓取结果和抽取运行结果
LanceDB/                        # 项目根目录下的 LanceDB 数据库
tests/                          # 自动化测试
```

## 安装

建议使用项目已有的 conda 环境：

```powershell
conda activate mrg
```

安装基础抽取、PDF、网页和测试依赖：

```powershell
pip install -e ".[test,pdf,web]"
```

使用 LanceDB：

```powershell
pip install -e ".[knowledge-base]"
```

项目默认使用本机的 BGE-M3 embedding 模型
`D:\papers\models\bge-m3`。安装 `sentence-transformers`：

```powershell
pip install -e ".[embedding]"
```

如果模型目录或 Python 环境不是默认配置，请通过 `--embedding-model` 指定模型路径。

## 网页采集

单 URL 抓取：

```powershell
python .\cli\trafilatura.py "https://example.com/article"
```

DDGS 搜索并批量抓取：

```powershell
python .\cli\trafilatura.py `
    --query "dental fluorosis pathogenesis" `
    --region us-en `
    --max-results 20 `
    --delay 1
```

每次运行都会在 `output/trafilatura/` 下创建独立的
`YYYYMMDD_HHMMSS_mmmmmmZ` 子目录。批量模式会同时保存 `ddgs_search.json`，
其中包含搜索 URL、标题、100-200 字以内的摘要、规范化 URL、抓取状态和输出文件。
执行抓取前会扫描所有历史运行目录的 Markdown front matter，已经下载过的规范化
URL 不会再次调用 `fetch_url()`。

## 三元组抽取

仅生成分块和 Prompt，不调用 LLM：

```powershell
python .\cli\extract_triples.py `
    --input-dir ".\references" `
    --write-prompts-only `
    --output-dir ".\output"
```

支持单个或多个文件、单个或多个目录，目录会递归扫描。支持的主要格式：

```text
.pdf .md .txt .html .htm .json .csv .tsv .xml .yaml .yml .rst .log .text
.py .js .ts .jsx .tsx .css .scss .sql .ini .cfg .conf .toml .tex
.c .cpp .h .java .go .rs .vue
```

使用本地模型抽取：

```powershell
$env:LOCAL_LLM_MODEL="D:/models/Qwen2.5-32B-Instruct"

python .\cli\extract_triples.py `
    --input-dir ".\references" `
    --llm-command "python cli/local_llm_runner.py --model-path D:/models/Qwen2.5-32B-Instruct --trust-remote-code" `
    --llm-timeout 3600 `
    --output-dir ".\output"
```

不调用真实模型的冒烟测试：

```powershell
python .\cli\extract_triples.py `
    --text-file ".\references\README.md" `
    --mock-output "head_entity,relation,tail_entity`nCondition,caused_by,Exposure" `
    --output-dir ".\output"
```

默认结果目录为 `output/extraction/<timestamp>/`，包括：

- `chunks.jsonl`：分块文本及来源。
- `prompts.jsonl`：发送给模型的完整 Prompt。
- `raw_outputs.jsonl`：模型原始输出。
- `triples_clean.csv`：包含来源和 `chunk_id` 的审核文件。
- `triples_structured.csv`：三列结构化三元组文件。
- `manifest.json`：运行统计和文件清单。

## 构建 LanceDB

先运行网页采集或准备本地文本，再执行：

```powershell
python .\cli\build_knowledge_base.py
```

默认读取：

```text
output/trafilatura/      # Markdown 原文
output/extraction/       # triples_clean.csv 和 chunks.jsonl
```

数据库固定默认创建在项目根目录 `LanceDB/`。可指定路径和 embedding：

```powershell
python .\cli\build_knowledge_base.py `
    --input-dir ".\output\trafilatura" `
    --extraction-dir ".\output\extraction" `
    --lancedb-dir ".\LanceDB" `
    --embedding-model "D:\papers\models\bge-m3" `
    --device auto `
    --batch-size 32
```

BGE-M3 是本项目当前使用的本地语义 embedding 模型，模型向量维度由模型自动读取，
不需要手工填写。`--device auto` 会让 `sentence-transformers` 使用可用的 CUDA，
没有 CUDA 时使用 CPU；显存不足时可将 `--batch-size` 调小到 `8` 或 `16`。
写入是增量的：
文本块按 `content_hash + embedding_model` 去重，三元组按
`head_entity + relation + tail_entity + chunk_id` 去重，重复运行不会增加重复记录。

`hash-v1` 仍保留为无需模型下载的确定性测试基线，但不具备语义理解能力，仅可通过
显式传入 `--embedding-model hash-v1` 使用。BGE-M3 写入和查询必须使用同一个模型，
不能将 `hash-v1` 与 BGE-M3 混用在同一知识库中。

LanceDB 包含两张表：

- `knowledge_chunks`：文本块、embedding、URL、标题、来源类型、文件路径、
  `document_id`、`chunk_id`、哈希和元数据。
- `knowledge_triples`：头实体、关系、尾实体、三元组 embedding、原文证据、
  `document_id`、`chunk_id`、来源、标题、置信度和 `review_status`。

未经过人工审核的三元组默认为 `pending`，不能直接视为临床结论。

## 查询 LanceDB

查询文本块：

```powershell
python .\cli\query_knowledge_base.py `
    "dental fluorosis causes" `
    --table chunks `
    --embedding-model "D:\papers\models\bge-m3" `
    --device auto `
    --limit 5
```

查询已经审核通过的三元组：

```powershell
python .\cli\query_knowledge_base.py `
    "dental fluorosis caused by fluoride exposure" `
    --table triples `
    --embedding-model "D:\papers\models\bge-m3" `
    --relation caused_by `
    --review-status approved `
    --limit 10
```

查询结果包含 `_distance`、原文 `content`、来源、标题、`document_id` 和
`chunk_id`，可以回溯到原始 Markdown 或抽取运行文件。查询结果不会完整打印到
控制台，而是自动保存到 `output/lancedb_result/`，例如：

```text
chunks_dental_fluorosis_causes_20260911_143000_123456Z.json
```

每次查询都会创建新文件。也可以通过 `--output-dir` 指定其他保存目录。

## 测试

```powershell
pytest -q
```

测试覆盖文档读取、HTML 正文提取、Prompt、三元组清洗、PubMed 解析、LLM
命令适配器、网页采集行为，以及 LanceDB 表初始化、增量去重、向量查询、
结构化过滤和证据回溯。

## 医学使用边界

该项目负责资料采集、文本处理、结构化抽取和证据检索，不替代医学专家审核。
网页、论文和模型输出仍可能存在访问限制、版权限制、解析错误或事实错误；
知识库中的三元组必须经过人工医学审核后，才能作为报告生成的高可信证据。
