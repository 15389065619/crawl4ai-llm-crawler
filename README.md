# crawl4ai LLM 友好型网页采集示例

基于 [crawl4ai](https://github.com/unclecode/crawl4ai) 0.9.5 的三个渐进式示例，演示如何用极少的代码完成 **JS 动态页面抓取 → 抓取行为精确控制 → 结构化提取**。

crawl4ai 的定位：**为 LLM 准备数据的爬虫工具**。它内置 Playwright 浏览器渲染，无需额外配置，并可直接把页面转成干净的 Markdown。

## 三个阶段

| 脚本 | 主题 | 核心 API |
|---|---|---|
| `stage1_basic.py` | 最小可用爬虫 | `AsyncWebCrawler` + `arun()` |
| `stage2_config.py` | 精确控制抓取行为 | `CrawlerRunConfig`：`wait_for` / `js_code_before_wait` / `js_only` / `session_id` |
| `stage3_extract.py` | 结构化提取为 JSON | `JsonCssExtractionStrategy` / `LLMExtractionStrategy` |

## 快速开始

```bash
pip install -r requirements.txt
crawl4ai-setup          # 安装/校验 Playwright 浏览器依赖

python stage1_basic.py
python stage2_config.py
python stage3_extract.py
```

`stage3_extract.py` 中的 LLM 提取演示需要 API Key，未设置时会自动跳过：

```bash
set OPENAI_API_KEY=sk-xxx        # Windows
export OPENAI_API_KEY=sk-xxx     # macOS / Linux
```

## 各阶段要点

### 阶段 1：三行代码抓 JS 页面

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url="https://quotes.toscrape.com/js/")
    print(result.markdown)
```

浏览器**自动启动、自动渲染、自动回收**，输出同时提供 `result.html`（渲染后 DOM）与 `result.markdown`（清洗后的 Markdown）。

### 阶段 2：控制抓取行为

对标 Scrapy 中写在 `Request(meta={...})` 里的控制项，crawl4ai 统一收敛到 `CrawlerRunConfig`：

```python
CrawlerRunConfig(
    session_id="scroll_demo",                   # 复用同一个浏览器标签页
    js_only=True,                               # 不重新加载页面，只在当前页操作
    js_code_before_wait="window.scrollTo(0, document.body.scrollHeight);",
    wait_for="js:() => document.querySelectorAll('div.quote').length >= 20",
)
```

演示目标为无限滚动页面 `quotes.toscrape.com/scroll`，滚动两轮后数据由 10 条增至 30 条。

**关键坑点**：crawl4ai 的执行顺序固定为 `js_code_before_wait` → `wait_for` → `js_code`。用于「触发加载」的脚本必须放在 `js_code_before_wait`，否则 `wait_for` 会等待一个尚未发生的事件，直接超时。

**登录态注入**（浏览器级配置）：

```python
BrowserConfig(cookies=[{"name": "...", "value": "...", "domain": ".example.com", "path": "/"}])
```

### 阶段 3：声明式 / LLM 提取

`JsonCssExtractionStrategy` 用 schema 描述「要什么」，由库自动循环提取，支持三种字段类型：

| type | 含义 |
|---|---|
| `text` | 提取元素文本 |
| `attribute` | 提取 HTML 属性（如 `href`） |
| `list` | 一对多子元素（如标签数组） |

`LLMExtractionStrategy` 则用一句自然语言指令替代所有选择器，代价是需要调用 LLM API（有费用、速度较慢），优势是抗页面改版。

## 与 Scrapy + scrapy-playwright 的差异

| 维度 | Scrapy + scrapy-playwright | crawl4ai |
|---|---|---|
| 定位 | 工业级爬虫框架 | 轻量单页抓取工具 |
| 浏览器渲染 | 装插件、注册 handler、meta 标记 | 默认内置，零配置 |
| 输出 | 原始 HTML，需自行解析 | HTML + Markdown + JSON |
| 工程化能力 | 调度、并发、去重、管道、限速、重试 | 需自行实现 |
| 翻页 | 解析下一页 URL 发新请求 | `session_id` 复用标签页，适合无限滚动 |
| 适用规模 | 成千上万页面、长期运行 | 几十到几百页、快速验证、AI 数据准备 |

## 调试经验

**「字段神秘消失」排查**：`JsonCssExtractionStrategy` 对值为 `None` 的字段会静默丢弃，不报错。当提取结果缺少字段时，排查顺序应为：

1. 确认页面里是否真的存在该结构（直接查看渲染后 DOM）
2. 再检查选择器写法
3. 最后才怀疑工具

本仓库阶段 3 因此改用静态首页演示 `attribute` 提取 —— `quotes.toscrape.com/js/` 的 JS 模板本身不渲染作者链接与标签 `href`。

## 目标站点

本项目仅访问 [quotes.toscrape.com](https://quotes.toscrape.com)，为官方公开的爬虫练习站点。
