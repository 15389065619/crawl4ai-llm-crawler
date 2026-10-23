"""
crawl4ai 阶段1:最小可用爬虫
目标:抓取 https://quotes.toscrape.com/js/ (JS 动态渲染页面)

对比回忆:同一个页面,用 Scrapy + scrapy-playwright 需要:
  1. settings.py 注册 DOWNLOAD_HANDLERS
  2. 配置 TWISTED_REACTOR
  3. Spider 里写 meta={"playwright": True}
  4. PageMethod("wait_for_selector", ...) 等元素加载
而 crawl4ai 只需要下面这一个文件 —— 因为它"天生就是浏览器渲染"。

运行方式(注意用全局 python,不是 .venv):
  python crawl4ai_learning/stage1_basic.py
"""
import asyncio  # crawl4ai 是异步库,所有操作都在协程里跑
from crawl4ai import AsyncWebCrawler


async def main():
    """
    主流程:创建爬虫 -> 抓一个页面 -> 读结果
    async with 是"异步上下文管理器":
      进入时启动一个无头浏览器(类似你手动打开 Chrome),
      退出时自动关闭浏览器,释放内存。
      —— 相当于 Scrapy 里整个 Playwright 生命周期的自动化版本。
    """
    async with AsyncWebCrawler() as crawler:
        # arun = "async run",抓一个 URL。
        # 内部做的事:开浏览器标签 -> 加载页面 -> 等 JS 执行完 -> 提取内容
        result = await crawler.arun(url="https://quotes.toscrape.com/js/")

        # result 是 CrawlResult 对象,常用属性:
        #   success  —— 是否成功(True/False)
        #   html     —— 渲染后的完整 HTML(相当于 Scrapy 里的 response.text)
        #   markdown —— 把 HTML 自动转成 Markdown 文本(crawl4ai 的招牌功能)
        #   media    —— 页面里的图片/视频/音频链接
        #   links    —— 页面里的所有链接(分内部/外部)
        print("=" * 50)
        print("抓取成功:", result.success)
        print("渲染后 HTML 长度:", len(result.html))
        print("Markdown 长度:", len(result.markdown))
        print("=" * 50)
        # 打印 Markdown 前 500 字符看看效果
        # 注意:原本 JS 渲染出来的名言,已经变成纯文本了
        print(result.markdown[:500])


# Python 异步程序的固定启动写法:
# asyncio.run() 会创建一个"事件循环"(event loop)——
# 大白话:一个调度器,负责在多个异步任务之间切换执行,
# 让程序在等待网络响应时不傻等,可以去做别的事。
if __name__ == "__main__":
    asyncio.run(main())
