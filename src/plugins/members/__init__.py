import json
import io
from pathlib import Path
from datetime import datetime

from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupIncreaseNoticeEvent,
    GroupDecreaseNoticeEvent,
    MessageSegment,
    Message,
)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "member"


def save(data, gid):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fname = DATA_DIR / f"{gid}.json"
    fname.write_text(
        json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )


join = on_notice(priority=5000)


@join.handle()
async def join_handle(bot: Bot, event: GroupIncreaseNoticeEvent):
    gid = event.group_id
    data = await bot.get_group_member_list(group_id=gid)
    save(data, gid)


leave = on_notice(priority=5000)


@leave.handle()
async def leave_handle(bot: Bot, event: GroupDecreaseNoticeEvent):
    gid = event.group_id
    data = await bot.get_group_member_list(group_id=gid)
    save(data, gid)


member_cmd = on_command("/member", priority=5000)


@member_cmd.handle()
async def member_handle(bot: Bot, event: GroupMessageEvent):
    gid = event.group_id
    text = event.get_plaintext().strip()

    if text == "/member update":
        data = await bot.get_group_member_list(group_id=gid)
        save(data, gid)
        await member_cmd.finish("已手动更新群成员列表")

    elif text == "/member show":
        data = await bot.get_group_member_list(group_id=gid)
        save(data, gid)
        md_lines = [
            "| QQ号 | 昵称 | 群名片 | 权限 | 等级 | 加入时间 | 最后发言时间 |",
            "| :----: | :----: | :----: | :----: | :----: | :----: | :----: |",
        ]
        for m in data:
            join_time = datetime.fromtimestamp(m["join_time"]).strftime("%Y-%m-%d %H:%M")
            last_sent = datetime.fromtimestamp(m["last_sent_time"]).strftime("%Y-%m-%d %H:%M")
            md_lines.append(
                f"| {m['user_id']} | {m['nickname']} | {m['card']} | "
                f"{m['role']} | {m['level']} | {join_time} | {last_sent} |"
            )
        doc = "\n".join(md_lines)
        from nonebot.plugin import require

        require("htmlrender")
        from ..htmlrender.data_source import md_to_pic

        pic = await md_to_pic(md=doc, width=1000)
        await member_cmd.finish(MessageSegment.image(pic))

    else:
        await member_cmd.finish(
            "用法：\n/member：显示这条信息\n/member update：手动更新群成员列表\n/member show：显示成员列表"
        )
