## 抓取管线（oscrapers）

- HKEJ 即时新闻（`https://www.hkej.com/instantnews`）
- ETNet China 专栏列表（`https://column.etnetchina.cn/list/article-latest`）

系统目标：给定入口列表页 → 发现候选文章 → 语义筛选（关键词/向量）→ 抽取正文 → 统一导出（TXT），并输出每条相似度分数与是否命中。

---

### 目录结构（关键文件）

- `main.py`：命令行入口（异步）
- `semantic_stream_pipeline.py`：统一管线编排
- `crawler.py`：ETNet/G 站点通用爬虫 + 语义筛选
- `newspaper_scraper.py`：HKEJ 基于 newspaper3k 的抽取
- `bypass.py`：反反爬与多策略回退（Playwright/Requests/可读代理）
- `.env` / `.env.example`：运行时配置
- `.cache/`：针对 ETNet 列表页的本地缓存（加速/缓解反爬）

---

### 快速开始

1) 准备 Python 环境（建议 Python 3.10+）并安装依赖：

```bash
pip install -r requirements.txt  # 若无，请按项目依赖手动安装：
# fastapi uvicorn playwright trafilatura newspaper3k sentence-transformers python-dotenv beautifulsoup4 requests
# 以及 Playwright 浏览器内核（首次）：
playwright install chromium
```

2) 配置 `.env`（可参考 `.env.example`）：

```dotenv
# 入口列表页（二选一）
CRAWL_URL=https://www.hkej.com/instantnews
# CRAWL_URL=https://column.etnetchina.cn/list/article-latest

# 最大文章数量
MAX_ARTICLES=20

# 语义阈值（0~1，余弦相似度）
SEMANTIC_THRESHOLD=0.35

# 目标关键词（JSON 数组或逗号分隔）
KEYWORDS=["中國","財經","經濟","金融","投資"]

# 反爬/渲染参数（可选）
HEADLESS=true
MAX_RENDER_MS=8000
STRATEGY_HARD_TIMEOUT_MS=7000
```

3) 运行：

```bash
# 读取 .env 中的 CRAWL_URL
python old/scrapers/main.py

# 或直接指定 URL
python old/scrapers/main.py https://www.hkej.com/instantnews
```

运行完成后，结果会导出到当前目录下：

```
old/scrapers/hkex_pipeline_results_YYYYMMDD_HHMMSS.txt
old/scrapers/etnet_pipeline_results_YYYYMMDD_HHMMSS.txt
```

---

### 工作流程（Pipeline）

1) 发现（Discover）
- HKEJ：使用 newspaper3k 的解析策略直接发现列表页上的文章链接。
- ETNet：优先 `requests` 获取列表页；若遇反爬返回骨架页，回退至：
  - 本地缓存 `.cache/etnet_list.html`（若已存在完整 DOM 缓存）
  - 轻量 Playwright 捕获一次完整 DOM 并写入缓存
  - 可读代理（只作兜底，不含链接结构时不使用）

2) 语义筛选（Filter）
- 关键词正则 + Sentence-Transformers（`all-MiniLM-L6-v2`）向量相似度。
- 输出 `similarity`（0~1）、`matched` 布尔与 `matched_keywords`。

3) 正文抽取（Extract）
- Trafilatura → 多 CSS 选择器兜底 → 可读代理兜底。
- 对 ETNet 详情页，若标题为空，则从 `og:title`/`<title>`/一级标题推断。

4) 导出（Export）
- 统一 TXT，包含每条：标题、URL、是否命中、相似度、关键词、正文长度与前 4k 预览。

---

### 反反爬策略（bypass.py 摘要）

- Playwright（Chromium）：
  - 关闭自动化指纹标记、随机 UA、视口/语言/时区、Referer 伪装。
  - 资源拦截分层（严格/宽松）、最小化人机模拟（列表页一次性捕获）。
- Requests：
  - 桌面/移动 UA 切换、Referer、超时与降级。
- 可读代理（`r.jina.ai`）：
  - 用于正文兜底（纯文本）与少量列表兜底（如无链接结构时不依赖）。
- 缓存：
  - ETNet 列表页完整 DOM 本地缓存，缓解频繁触发反爬导致的“骨架页”。

专业建议：
- 在 CI/批量部署时，优先启用缓存；Playwright 仅在缓存失效时触发一次捕获。
- 代理池可显著提升稳定性（见环境变量 `PROXY_URLS` 等，若在项目中启用）。

---

### 重要环境变量

- `CRAWL_URL`：入口列表页。
- `MAX_ARTICLES`：最大文章数量（建议分批，避免长时间运行）。
- `SEMANTIC_THRESHOLD`：语义命中阈值（默认 0.35）。
- `KEYWORDS`：关键词列表（JSON 数组或逗号分隔）。
- `HEADLESS`：Playwright 无头模式（默认 `true`）。
- `MAX_RENDER_MS`：单次渲染超时（毫秒）。
- `STRATEGY_HARD_TIMEOUT_MS`：单策略硬超时（毫秒）。

可选代理：

```dotenv
PROXY_URLS=http://user:pass@host:port,http://host2:port2
PROXY_ROTATION=per_request  # or per_domain
PROXY_USERNAME=...
PROXY_PASSWORD=...
```

---

### 参数调优建议

- ETNet：
  - 保持 `HEADLESS=true`、`MAX_RENDER_MS≈7~10s`、`STRATEGY_HARD_TIMEOUT_MS≈6~9s`。
  - 首次跑通后优先使用缓存，减少 Playwright 触发次数。
  - 若只要高质量结果，限制为 `/content/` 详情链接（在 `crawler.py` 的发现阶段可严格过滤）。

- HKEJ：
  - 抽取稳定，`MAX_ARTICLES` 可适当增大。

---

### 故障排查（Troubleshooting）

- “列表为空/仅 2KB 骨架页”：
  - 查看日志是否命中缓存或 Playwright 列表捕获（应见 `playwright list capture len≈6w`）。
  - 若没有，手动在浏览器打开列表页并保存源码到 `.cache/etnet_list.html` 再次运行。

- “标题为空”：
  - 详情页通常可从 `og:title` 或 `<title>` 推断，确认日志是否走到 `fetch_article_detail` 分支。

- “Playwright 提示需安装浏览器”：
  - 运行 `playwright install chromium`（如需 Firefox，单独 `playwright install firefox`）。

- “语义相似度恒 0/1”：
  - 确认 `KEYWORDS` 是否解析为空；建议使用 JSON 数组格式。

---

### 已知限制

- 无代理池环境下，ETNet 会出现间歇性反爬：
  - 我们通过缓存 + 轻量 Playwright 捕获缓解，但并不等价于完整绕过。
  - 若需要 7×24 稳定，请配合代理池/更长间隔/分时段运行。

---

### 示例命令

```bash
# HKEJ（20 篇）
export MAX_ARTICLES=20; python old/scrapers/main.py https://www.hkej.com/instantnews

# ETNet（20 篇，启用严格超时）
export MAX_ARTICLES=20 HEADLESS=true MAX_RENDER_MS=8000 STRATEGY_HARD_TIMEOUT_MS=7000; \
python old/scrapers/main.py https://column.etnetchina.cn/list/article-latest
```

---

如需只抓取 `/content/` 详情页或插入站点特定过滤，请在 `crawler.py` 的发现阶段调整过滤规则；如需更强反爬能力，请在 `bypass.py` 中开启更多策略或引入代理池。


