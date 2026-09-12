from typing import AsyncIterator
from contextlib import asynccontextmanager

from nonebot import get_driver
from nonebot.log import logger

_browser = None
_playwright = None


async def _init_browser(**kwargs):
    global _browser, _playwright
    from playwright.async_api import async_playwright

    _playwright = await async_playwright().start()
    try:
        _browser = await _playwright.chromium.launch(**kwargs)
    except Exception:
        logger.info("Installing Chromium...")
        import sys
        sys.argv = ["", "install", "chromium"]
        try:
            from playwright.__main__ import main
            main()
        except SystemExit:
            pass
        _browser = await _playwright.chromium.launch(**kwargs)
    return _browser


async def get_browser(**kwargs):
    return _browser or await _init_browser(**kwargs)


@asynccontextmanager
async def get_new_page(**kwargs) -> AsyncIterator:
    browser = await get_browser()
    page = await browser.new_page(**kwargs)
    try:
        yield page
    finally:
        await page.close()


driver = get_driver()


@driver.on_startup
async def start_browser():
    await _init_browser()
    logger.info("Browser Started.")


@driver.on_shutdown
async def shutdown_browser():
    global _browser, _playwright
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    logger.info("Browser Stopped.")


__all__ = [
    "get_new_page",
    "get_browser",
    "text_to_pic",
    "md_to_pic",
    "html_to_pic",
    "template_to_pic",
]
