"""
crawl4ai 阶段3:结构化提取 —— 把网页变成 JSON 数据
====================================================
阶段1/2拿到的是"一整段 Markdown 文本",适合喂给 AI 看,但不能直接入库。
阶段3学 crawl4ai 的两种提取策略(ExtractionStrategy):

  A. JsonCssExtractionStrategy —— 用 CSS 选择器声明"我要什么字段"
     对标 Scrapy 的:response.css(...) 解析 + Item 组装
     特点:免费、快、结果精确,但页面改版要跟着改选择器

  B. LLMExtractionStrategy —— 用大语言模型"读懂"页面再提取
     特点:不用写选择器、抗改版,但要调 LLM API(花钱、慢)
     crawl4ai 名字的由来,就是为这个场景设计的

运行方式: python crawl4ai_learning/stage3_extract.py
"""
import asyncio
import json
import os

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy


# ========== 演示 A:CSS 声明式提取 ==========
#
# schema(模式) = 一张"字段说明书",告诉爬虫:
#   1. baseSelector:页面里每个"数据卡片"长什么样(一条名言 = 一个 div.quote)
#   2. fields:每张卡片里要抠哪些字段、用什么选择器、抠文本还是属性
#
# 对标 Scrapy 的 parse() 循环:
#   for card in response.css("div.quote"):
#       text = card.css("span.text::text").get()
#       ...
# 区别:Scrapy 是"写代码循环抠",crawl4ai 是"写配置声明要啥",循环由库来做
# 注意!本演示用静态首页 https://quotes.toscrape.com/ 而不是 /js/ 版。
# 原因(调试实录,值得看):
#   /js/ 版的 JS 渲染模板里,标签是 <a class='tag'>change</a>(没有 href),
#   而且压根不渲染作者链接 —— 这是网站模板本身如此,不是爬虫问题。
#   最初 schema 里写了 author_link 字段,结果整个字段"神秘消失"(选不中 → None → 被丢弃)。
#   教训:选择器提取不到数据时,先确认"页面里到底有没有这个结构",再怀疑工具。
#   静态首页的 HTML 是完整的(有作者链接、标签 href、分页),三种字段类型都能演示。
QUOTE_SCHEMA = {
    "name": "Quote",                    # 这组数据的名字(随便起,注释用)
    "baseSelector": "div.quote",        # 每条数据的"容器"选择器
    "fields": [
        # type="text":抠元素的文本内容
        {"name": "text", "selector": "span.text", "type": "text"},
        {"name": "author", "selector": "small.author", "type": "text"},
        # type="attribute":抠元素的某个 HTML 属性(这里抠作者页的 href 链接)
        {"name": "author_link", "selector": "a[href*='/author/']",
         "type": "attribute", "attribute": "href"},
        # type="list":一个字段对应多个元素(一条名言有多个标签)
        # fields 里再声明每个标签抠什么(这里抠文本,起名叫 tag)
        {"name": "tags", "selector": "a.tag", "type": "list",
         "fields": [{"name": "tag", "type": "text"}]},
    ],
}


async def demo_css_extraction():
    # 提取策略挂到 CrawlerRunConfig 上 —— 还记得吗,每次抓取的配置都在 RunConfig 里
    config = CrawlerRunConfig(
        wait_for="css:div.quote",                              # 阶段2学的:等元素渲染完
        extraction_strategy=JsonCssExtractionStrategy(QUOTE_SCHEMA),  # 本阶段主角
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://quotes.toscrape.com/", config=config)

        # 提取结果在 result.extracted_content 里,是 JSON 字符串,转成 Python 列表
        quotes = json.loads(result.extracted_content)
        print(f"【演示A】CSS 提取到 {len(quotes)} 条名言")

        # 清洗一下:tags 从 [{"tag": "change"}, ...] 拍平成 ["change", ...]
        for q in quotes:
            q["tags"] = [t["tag"] for t in q.get("tags", [])]
            # 名言文本两端的装饰性引号去掉(和 Scrapy 项目里做过的清洗一样)
            q["text"] = q["text"].strip("“”\"")

        # 打印第一条看看结构
        print("  第 1 条:", json.dumps(quotes[0], ensure_ascii=False, indent=2))

        # 存成 JSON 文件 —— 对标 Scrapy 的 Pipeline 入库/导出环节
        out_path = os.path.join(os.path.dirname(__file__), "quotes_c4a.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(quotes, f, ensure_ascii=False, indent=2)
        print(f"  已保存到 {out_path}")


# ========== 演示 B:LLM 提取(需要 API Key,没有就自动跳过) ==========
#
# 思路:不写任何选择器,只写一句"人话指令",让 LLM 读页面、按要求返回 JSON。
# 底层:crawl4ai 把页面 Markdown 切片发给 LLM,附上你的指令和返回格式要求。
async def demo_llm_extraction():
    # 支持 openai/ deepseek/ 通义等任何 litellm 兼容的 provider
    # 用法:设置环境变量,如 set OPENAI_API_KEY=sk-xxx
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("【演示B】未检测到 OPENAI_API_KEY / DEEPSEEK_API_KEY,跳过 LLM 提取演示")
        print("  (设置环境变量后重跑即可体验,代码已写好)")
        return

    config = CrawlerRunConfig(
        wait_for="css:div.quote",
        extraction_strategy=LLMExtractionStrategy(
            # provider 格式: "厂商/模型名",走 litellm,主流厂商都支持
            provider="openai/gpt-4o-mini",
            api_token=api_key,
            # instruction:用人话告诉 LLM 要提取什么 —— 注意,一个选择器都没写!
            instruction=(
                "提取页面中所有名言,返回 JSON 数组,每条包含: "
                "text(名言内容)、author(作者)、tags(标签数组)"
            ),
        ),
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://quotes.toscrape.com/js/", config=config)
        quotes = json.loads(result.extracted_content)
        print(f"【演示B】LLM 提取到 {len(quotes)} 条名言")
        print("  第 1 条:", json.dumps(quotes[0], ensure_ascii=False, indent=2))
        # LLM 提取会统计 token 用量(花了多少钱)
        result.extraction_strategy.show_usage()


async def main():
    await demo_css_extraction()
    print()
    await demo_llm_extraction()


if __name__ == "__main__":
    asyncio.run(main())
