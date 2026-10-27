# AIEvalOps

> 基于 RAG 的客服问答系统与 LLM 自动化评测平台

面向电商客服场景构建的 Python AI 应用：将 PDF/Markdown 客服知识库转换为可检索的向量索引，提供带来源引用的 RAG 问答 API，并通过自动化评测、异步任务和质量门禁持续验证检索、生成、安全与性能表现。

## 项目能力

- **RAG 知识问答**：解析 PDF/Markdown，完成 Chunk 切分、Sentence Transformers 向量化、Chroma 持久化索引、Top-K 检索与低相关内容过滤。
- **可信回答与溯源**：API 返回答案、来源文件、PDF 页码、Chunk ID、相关性分数与原文片段；资料不足时转人工。
- **生成与安全控制**：支持 Ollama 和 Mock 两类模型客户端，覆盖模型超时、空响应、无依据回答和 Prompt 注入等场景。
- **自动化评测**：使用 Pytest、Promptfoo 及自定义检索脚本评测 Recall@K、MRR、答案相关性、引用存在性、拒答准确率与延迟。
- **异步评测平台**：通过 FastAPI、PostgreSQL、Redis 与 Celery 管理评测任务、结果、基线和质量门禁。

## 架构

```text
知识库（PDF / Markdown）
        │
        ▼
解析、切分、Embedding
        │
        ▼
Chroma 持久化向量索引
        │
        ▼
FastAPI /api/rag/query
        │
        ├── Top-K 检索与阈值过滤
        ├── Prompt 构建
        └── Ollama / Mock 生成
        │
        ▼
答案 + 来源文件 + 页码 + Chunk + 引用片段

评测请求 → FastAPI → Redis → Celery Worker → PostgreSQL
                                      │
                                      ▼
                         Promptfoo / Pytest / 质量门禁
```

## 实测检索结果

实验使用 `BAAI/bge-small-zh-v1.5`、10 份知识文档、13 个 Chunk、相似度阈值 `0.45`，评测集共 23 条，其中 21 条可回答检索问题、2 条无依据拒答问题。

| 配置 | 来源/证据 Recall | MRR |
| --- | ---: | ---: |
| Chroma，Top-K=3 | 95.24%（20/21） | 0.9048 |
| Chroma，Top-K=4 | **100.00%（21/21）** | **0.9167** |
| Chroma，Top-K=5 | 100.00%（21/21） | 0.9167 |

将 Top-K 从 3 调整至 4 后，来源/证据 Recall 提升 **4.76 个百分点**，MRR 提升 **0.0119**。Top-K=5 未带来额外收益，因此在该评测集上 K=4 是更小的有效候选集。

实验报告位于：

- `output/rag-retrieval-measured.json`：Top-K=3
- `output/rag-retrieval-top4-measured.json`：Top-K=4
- `output/rag-retrieval-top5-measured.json`：Top-K=5
- `output/tfidf-same-corpus-retrieval-baseline.json`：相同文档集合的 TF-IDF 对照

> 当前 `.env.example` 默认 `RAG_TOP_K=3`，K=4 是本次实验推荐值。修改默认配置前，应按本 README 的评测流程重新验证 API 和回归结果。

## 快速开始

### 1. 准备环境

```powershell
git clone https://github.com/z7-11/aievalops.git
cd aievalops
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

编辑 `.env` 中的 `DATABASE_URL`、`POSTGRES_PASSWORD` 等本地配置。默认 `LLM_MOCK_MODE=true`，可先在不启动本地模型的情况下验证 API 逻辑。

### 2. 构建 Chroma 索引

将知识文件放入 `knowledge/`，然后执行：

```powershell
python -m scripts.build_rag_index
```

该命令会递归读取 PDF/Markdown，按配置切分、生成向量并写入 `storage/chroma/`。首次运行会加载或下载 Embedding 模型；若配置 `RAG_EMBEDDING_LOCAL_FILES_ONLY=true`，则需先确保模型已缓存到本地。

### 3. 启动 API

本地开发可使用：

```powershell
alembic upgrade head
python -m uvicorn app.main:app --reload --port 3001
```

访问：

- Swagger API 文档：`http://127.0.0.1:3001/docs`
- 健康检查：`http://127.0.0.1:3001/health`

调用 RAG API：

```powershell
$body = @{
  question = "商品签收后多久可以申请退款？"
  top_k = 4
  prompt_version = "v2"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:3001/api/rag/query" `
  -Method Post -ContentType "application/json" -Body $body
```

### 4. 使用 Ollama（可选）

将 `.env` 中的配置改为：

```dotenv
LLM_MOCK_MODE=false
LLM_BASE_URL=http://localhost:11434/v1/
LLM_MODEL=qwen3:4b
```

确保 Ollama 已启动且对应模型已下载。Mock 适合验证接口和异常分支；真实模型的回答效果、延迟和安全表现需要单独评测。

## 评测与测试

### RAG 检索评测

```powershell
python -m scripts.evaluate_retrieval `
  --dataset evals/evals/datasets/rag_cases.csv `
  --top-k 4 `
  --output output/rag-retrieval-top4.json
```

### RAG 相关单元测试

```powershell
pytest tests/unit/test_rag_llm_client.py `
  tests/unit/test_rag_retriever.py `
  tests/unit/test_rag_quality_gate.py `
  tests/unit/test_evaluate_retrieval.py `
  tests/unit/test_prepare_rag_gate_report.py `
  tests/unit/test_rag_promptfoo_config.py
```

本次实验对应的 RAG 相关测试为 **43/43 通过**。

### Promptfoo 评测

API 启动在端口 `3001` 后：

```powershell
npx promptfoo@0.122.2 eval -c evals/vector_rag_promptfooconfig.yaml
```

配置包含退款、物流、无依据拒答与 Prompt 注入等用例。请注意：Mock 模式的通过结果用于验证程序流程，不能替代真实模型质量结论。

### RAG 质量门禁

`rag-quality-gate.yaml` 定义检索召回、MRR、回答相关性、引用、拒答、安全失败数和 P95 延迟等阈值。质量门禁会拒绝缺失或无效指标，避免将“没有数据”误判为通过。

## Docker Compose

```powershell
docker compose --env-file .env up --build
```

该编排启动：

- `api`：FastAPI 服务，暴露 `8000` 端口；
- `worker`：Celery 后台评测任务；
- `db`：PostgreSQL，持久化项目、用例、任务、结果与基线；
- `redis`：Celery Broker 和结果后端。

容器首次运行仍需构建 Chroma 索引；可在 API 容器中执行 `python -m scripts.build_rag_index`。

## 目录说明

```text
app/                 FastAPI API、RAG、数据模型、服务和 Celery Worker
knowledge/           客服知识库 PDF/Markdown
storage/chroma/      本地 Chroma 持久化索引（通常不提交）
evals/               Promptfoo 配置与 RAG 评测集
scripts/             索引构建、检索评测和质量门禁脚本
tests/               单元、API、集成与端到端测试
output/              生成的评测配置与可复现实验报告
compose.yaml         FastAPI、Celery、PostgreSQL、Redis 编排
```

## 当前边界与后续方向

当前核心是**预定义路径的 RAG Workflow**：后端固定执行检索、过滤、Prompt 构建和生成；模型不自主选择工具，也没有多步工具执行反馈循环。

后续可将知识检索、订单查询、退货资格校验和人工工单创建封装为受控工具，并补充服务端鉴权、参数校验、幂等控制、最大步数和人工确认，将系统扩展为客服 Agent 应用。

## 技术栈

Python · FastAPI · Sentence Transformers · Chroma · Ollama · PostgreSQL · Redis · Celery · Pytest · Promptfoo · Docker Compose
