from apscheduler.triggers.cron import CronTrigger
from nonebot import get_bots, get_driver, get_plugin_config, require
from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from .config import Config  # noqa: E402

__plugin_meta__ = PluginMetadata(
    name="每日问候",
    description="定时向指定群发送问候语，并在上线/下线时通知",
    usage="在 .env 配置 GREETING_TARGETS 后自动生效",
    type="application",
)

config = get_plugin_config(Config)
driver = get_driver()

MORNING_MSG = "早"
AFTERNOON_MSG = "𝓖𝓸𝓸𝓭 𝓪𝓯𝓽𝓮𝓻𝓷𝓸𝓸𝓷"
EVENING_MSG = "下班！"
ONLINE_MSG = "我上线了"
OFFLINE_MSG = "我下线了"

GREETINGS = [
    (MORNING_MSG, 8, 10),
    (AFTERNOON_MSG, 14, 0),
    (EVENING_MSG, 20, 0),
]


async def send_to_targets(bot, message: str) -> None:
    for target in config.greeting_targets:
        try:
            group_id = int(target)
        except (TypeError, ValueError):
            logger.warning(f"GREETING_TARGETS 中的 {target!r} 不是合法群号，已跳过")
            continue
        try:
            await bot.send_group_msg(group_id=group_id, message=message)
        except Exception:
            logger.opt(exception=True).warning(f"问候消息发送失败 group={group_id}")


async def _send_all(message: str) -> None:
    for bot in get_bots().values():
        await send_to_targets(bot, message)


async def _on_bot_connect(bot: Bot) -> None:
    await send_to_targets(bot, ONLINE_MSG)


async def _send_offline() -> None:
    await _send_all(OFFLINE_MSG)


async def _run_test() -> None:
    await _send_all("测试问候 OK")


if config.greeting_targets:
    for message, hour, minute in GREETINGS:
        scheduler.add_job(
            _send_all,
            CronTrigger(hour=hour, minute=minute),
            args=[message],
            id=f"greeting_{hour:02d}{minute:02d}",
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
else:
    logger.warning("GREETING_TARGETS 未配置，每日问候定时任务未注册")

if config.greeting_test_time:
    try:
        hh, mm, ss = (int(x) for x in config.greeting_test_time.split(":"))
        scheduler.add_job(
            _run_test,
            CronTrigger(hour=hh, minute=mm, second=ss),
            id="greeting_test",
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
        logger.info(f"测试问候任务已注册: {config.greeting_test_time}")
    except (ValueError, AttributeError):
        logger.warning(
            f"GREETING_TEST_TIME 格式非法: {config.greeting_test_time!r}，应为 HH:MM:SS"
        )
else:
    logger.info("GREETING_TEST_TIME 未设置，不注册测试任务")

# driver.on_bot_connect(_on_bot_connect)
# driver.on_shutdown(_send_offline)
