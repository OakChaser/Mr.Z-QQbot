import random
from datetime import date

from nonebot import on_command, on_keyword
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment


def luck_simple(num: int) -> str:
    if num < 18:
        return "大吉"
    elif num < 53:
        return "吉"
    elif num < 58:
        return "半吉"
    elif num < 62:
        return "小吉"
    elif num < 65:
        return "末小吉"
    elif num < 71:
        return "末吉"
    else:
        return "凶"


jrrp = on_command("/jrrp", priority=50)


@jrrp.handle()
async def jrrp_handle(bot: Bot, event: Event):
    rnd = random.Random()
    rnd.seed(int(date.today().strftime("%y%m%d")) + int(event.get_user_id()))
    lucknum = rnd.randint(1, 100)
    at = MessageSegment.at(event.get_user_id())
    await jrrp.finish(
        Message(f'{at}你今日的幸运指数是{lucknum}/100（越低越好），为\u201c{luck_simple(lucknum)}\u201d')
    )


sleep = on_keyword(["碎觉了", "睡觉了", "睡了", "睡去", "觉去了"], priority=60)


@sleep.handle()
async def sleep_handle(event: Event):
    at = MessageSegment.at(event.get_user_id())
    await sleep.finish(Message(f"{at}晚安(￣o￣) . z Z"))
