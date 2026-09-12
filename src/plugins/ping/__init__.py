from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment

mc = on_command("/mc", priority=5)


def parse_sub_command(text: str) -> tuple[str, str]:
    text = text.removeprefix("/mc").strip()
    sub = ""
    for s in ("motd", "ping", "player", "status"):
        if text.startswith(s):
            sub = s
            text = text[len(s) :].strip()
            break
    return sub, text


@mc.handle()
async def mc_handle(bot: Bot, event: Event):
    sub, host = parse_sub_command(event.get_plaintext().strip())
    at = MessageSegment.at(event.get_user_id())

    if not host:
        await mc.finish(f"用法：\n/mc <服务器地址>\n/mc motd/ping/player/status <服务器地址>")

    try:
        from mcstatus import JavaServer

        server = JavaServer.lookup(host)
        status = server.status()

        if sub == "motd":
            msg = f"{at}\nMOTD：\n{status.description}"
        elif sub == "ping":
            msg = f"{at}\n延迟：{round(status.latency * 1000, 2)}ms"
        elif sub == "player":
            msg = f"{at}\n在线：{status.players.online}人"
        elif sub == "status":
            msg = f"{at}\n状态：活着"
        else:
            msg = (
                f"{at}\n"
                f"在线：{status.players.online}人\n"
                f"延迟：{round(status.latency * 1000, 2)}ms\n"
                f"状态：活着\n"
                f"MOTD：\n{status.description}"
            )
    except Exception:
        msg = "查询失败，看看服务器地址对不对，或者服务器是不是死了"

    await mc.finish(Message(msg))
