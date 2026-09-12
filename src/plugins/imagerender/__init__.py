import asyncio
import io

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from nonebot.plugin import require

require("htmlrender")
from ..htmlrender.data_source import text_to_pic, md_to_pic, template_to_pic, get_new_page


text2pic = on_command("text2pic")


@text2pic.handle()
async def _text2pic(bot: Bot, event: MessageEvent):
    msg = str(event.get_message())
    pic = await text_to_pic(text=msg)
    await text2pic.finish(MessageSegment.image(pic))


html2pic = on_command("html2pic")

HTML2PIC_VIEWPORT_WIDTH = 1500
MAX_PAGE_HEIGHT = 30000
GOTO_TIMEOUT = 15000
NAV_TIMEOUT = 30000


@html2pic.handle()
async def _html2pic(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    url = args.extract_plain_text().strip()
    if not url:
        await html2pic.finish("用法：html2pic <url>，例如 html2pic https://example.com")
    if "://" not in url:
        url = "https://" + url
    try:
        async def _shot():
            async with get_new_page(
                viewport={"width": HTML2PIC_VIEWPORT_WIDTH, "height": 1800}
            ) as page:
                await page.goto(url, wait_until="load", timeout=GOTO_TIMEOUT)
                await page.wait_for_timeout(1000)
                height = await page.evaluate(
                    "() => document.body.scrollHeight"
                )
                if height > MAX_PAGE_HEIGHT:
                    return await page.screenshot(
                        clip={
                            "x": 0,
                            "y": 0,
                            "width": HTML2PIC_VIEWPORT_WIDTH,
                            "height": MAX_PAGE_HEIGHT,
                        },
                    )
                return await page.screenshot(full_page=True, scale="css")

        pic = await asyncio.wait_for(_shot(), timeout=NAV_TIMEOUT)
    except asyncio.TimeoutError:
        await html2pic.finish(f"截图超时（{NAV_TIMEOUT}s）：{url}")
    except Exception as e:
        await html2pic.finish(f"截图失败：{type(e).__name__}: {e}")
    await html2pic.finish(MessageSegment.image(pic))


md2pic_cmd = on_command("md2pic")


@md2pic_cmd.handle()
async def _md2pic(bot: Bot, event: MessageEvent):
    from pathlib import Path

    doc_path = Path(__file__).parent.parent.parent.parent / "doc" / "rule.md"
    if doc_path.is_file():
        doc = doc_path.read_text(encoding="utf-8")
    else:
        doc = "# Rule\nNo rule file found."
    pic = await md_to_pic(md=doc, width=1000)
    await md2pic_cmd.finish(MessageSegment.image(pic))
