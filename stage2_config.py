"""
crawl4ai 阶段2:CrawlerRunConfig —— 精确控制抓取行为
====================================================
阶段1我们用的是 crawl4ai 的"自动挡":啥都不配,它自己判断页面加载完成。
阶段2学"手动挡":CrawlerRunConfig,一次抓取的所有开关都在这里。

对标 Scrapy 理解:
  Scrapy 里每个请求的控制项写在 Request(meta={...}) 里
  crawl4ai 里每次 arun() 的控制项写在 CrawlerRunConfig 里

本阶段学 4 个核心参数:
  1. wait_for   —— 明确告诉爬虫"等到什么出现才算加载完"(对标 wait_for_selector)
  2. js_code    —— 抓取前在页面里执行一段 JS(滚动、点击等)
  3. js_only    —— "别重新打开页面,只在当前页面上执行 JS"(配合下面这个)
  4. session_id —— 会话 ID,相同 ID 的多次 arun 复用同一个浏览器标签页

演示页面:https://quotes.toscrape.com/scroll
  这个页面是"无限滚动"——滚到底部才加载下一批名言,没有翻页按钮。
  传统 requests/Scrapy 纯 HTTP 只能拿到前 10 条,剩下的必须模拟滚动。

运行方式: python crawl4ai_learning/stage2_config.py
"""
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig


def count_quotes(markdown: str) -> int:
    """
    从 Markdown 结果里数有多少条名言
    规律:每条名言都以中文引号 “ 开头一行
    (用 Markdown 数而不是解析 HTML,阶段3会教正经的结构化提取)
    """
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("“"))


async def main():
    async with AsyncWebCrawler() as crawler:

        # ========== 演示 A:wait_for 显式等待 ==========
        # 阶段1的"自动判断加载完成"其实内部也有默认等待逻辑,
        # 但遇到加载慢的页面,显式指定更稳:
        #   "css:div.quote" = 等 CSS 选择器 div.quote 匹配到元素后再提取内容
        config_a = CrawlerRunConfig(
            wait_for="css:div.quote",  # 对标 scrapy-playwright 的 PageMethod("wait_for_selector", "div.quote")
        )
        result = await crawler.arun(url="https://quotes.toscrape.com/js/", config=config_a)
        print("【演示A】显式等待 div.quote 出现")
        print(f"  抓到名言数: {count_quotes(result.markdown)}")
        print()

        # ========== 演示 B:js_code + session_id 模拟无限滚动 ==========
        # 第 1 步:正常打开页面(此时只有前 10 条)
        #   session_id 给这个浏览器标签页起个名字,后面还要回来找它
        config_b1 = CrawlerRunConfig(
            session_id="scroll_demo",      # 给标签页挂牌子:"scroll_demo"
            wait_for="css:div.quote",
        )
        result = await crawler.arun(url="https://quotes.toscrape.com/scroll", config=config_b1)
        print("【演示B】无限滚动页面")
        print(f"  初始加载: {count_quotes(result.markdown)} 条名言")

        # 第 2 步:在同一个标签页里滚动 2 次,每次多加载 10 条
        for round_no in range(1, 3):
            expected = 10 + round_no * 10  # 滚完后应有的总条数:20、30
            config_scroll = CrawlerRunConfig(
                session_id="scroll_demo",    # 关键!同一个 ID → 回到刚才那个标签页
                js_only=True,                # 关键!不重新加载页面,只执行 JS
                # 注意!这里必须用 js_code_before_wait,不能用 js_code:
                #   crawl4ai 的执行顺序是 js_code_before_wait → wait_for → js_code
                #   "先滚动触发加载,再等待新内容出现" → 滚动必须放在 before_wait
                #   (如果放 js_code 里,wait_for 会先干等 60 秒超时,滚动还没执行)
                js_code_before_wait="window.scrollTo(0, document.body.scrollHeight);",
                # wait_for 支持 JS 表达式("js:" 前缀):
                #   等"名言元素数量 >= expected"成立,说明新一批真的加载出来了
                #   —— 比"傻等 2 秒"可靠:加载快就不多等,加载慢也不会提前截胡
                wait_for=f"js:() => document.querySelectorAll('div.quote').length >= {expected}",
            )
            # 注意:js_only 模式下 url 参数只是"占位",不会真的重新访问
            result = await crawler.arun(url="https://quotes.toscrape.com/scroll", config=config_scroll)
            print(f"  滚动第 {round_no} 次后: {count_quotes(result.markdown)} 条名言")

        # 0.9+ 版本会话自动回收,不用手动 kill_session
        # (async with 退出时会关闭整个浏览器)


if __name__ == "__main__":
    asyncio.run(main())


"""
【补充:登录墙场景怎么破 —— 了解即可,需要真实账号才能跑】

之前京东项目,我们在 Scrapy 里把 Cookie 解析后注入 Playwright 上下文。
crawl4ai 里等价的写法是 BrowserConfig(注意:是浏览器级配置,不是 RunConfig):

    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    browser_config = BrowserConfig(
        cookies=[
            {"name": "thor", "value": "你的cookie值", "domain": ".jd.com", "path": "/"},
            # ... 其他 cookie
        ],
        # 或者用 Playwright 的 storage_state 文件(浏览器导出登录态,下次直接复用):
        # storage_state="jd_login_state.json",
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url="https://search.jd.com/...", config=CrawlerRunConfig(...))

思路完全一致:Cookie 注入浏览器上下文 → 带着登录态访问。
区别:crawl4ai 把它收敛成了 BrowserConfig 的一个参数,不用自己写解析/注入逻辑。
"""
