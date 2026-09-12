import asyncio
import json
from datetime import datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger
from nonebot import get_bots, get_plugin_config, on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, require

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="群消息同步",
    description="发送 /sync，将配置的源群中未同步的新消息以合并转发卡片发送到当前群；每天 09:00 定时同步到配置的群",
    usage="/sync",
    type="application",
)

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

config = get_plugin_config(Config)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "forward"

MAX_FETCH = 200  # 单次最多从源群拉取的消息数
MAX_NODES = 100  # 单个合并转发卡片最多节点数

_state_lock = asyncio.Lock()


def _state_path(source_gid: int, target_gid: int) -> Path:
    return DATA_DIR / f"{source_gid}_{target_gid}.json"


def _load_state(source_gid: int, target_gid: int) -> str | None:
    try:
        data = json.loads(_state_path(source_gid, target_gid).read_text(encoding="utf-8"))
        anchor = str(data.get("last_msg_id") or "").strip()
        return anchor or None
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _save_state(source_gid: int, target_gid: int, anchor: str | None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(source_gid, target_gid).write_text(
        json.dumps(
            {
                "source_group": source_gid,
                "target_group": target_gid,
                "last_msg_id": anchor,
                "last_sync_time": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )


def _group_only(event: GroupMessageEvent) -> bool:
    return isinstance(event, GroupMessageEvent)


def _sender_name(raw_msg: dict) -> str:
    sender = raw_msg.get("sender") or {}
    card = str(sender.get("card") or "").strip()
    nickname = str(sender.get("nickname") or "").strip()
    return card or nickname or str(sender.get("user_id") or raw_msg.get("user_id") or "未知")


def _uin(raw_msg: dict) -> int:
    sender = raw_msg.get("sender") or {}
    uid = sender.get("user_id") or raw_msg.get("user_id")
    try:
        return int(uid)
    except (TypeError, ValueError):
        return 10000


def _text_content(text: str) -> list[dict]:
    return [{"type": "text", "data": {"text": text}}]


def _content_node(uin: int, name: str, content: list[dict]) -> dict:
    return {"type": "node", "data": {"uin": uin, "name": name, "content": content}}


def _msg_id(raw_msg: dict):
    for key in ("message_id", "message_seq", "real_id"):
        v = raw_msg.get(key)
        if v is not None and str(v) not in ("0", ""):
            return v
    return None


def _fallback_content(raw_msg: dict) -> list[dict]:
    segs = raw_msg.get("message")
    if isinstance(segs, str):
        return _text_content(segs) if segs.strip() else _text_content("[不支持解析的消息]")
    if not isinstance(segs, list) or not segs:
        return _text_content("[不支持解析的消息]")
    try:
        return [dict(s) for s in segs]
    except Exception:
        logger.opt(exception=True).warning("解析消息段失败")
        return _text_content("[不支持解析的消息]")


def _count_forward_segs(raw_msg: dict) -> int:
    segs = raw_msg.get("message")
    if not isinstance(segs, list):
        return 0
    return sum(1 for s in segs if isinstance(s, dict) and s.get("type") == "forward")


async def _group_name(bot: Bot, gid: int) -> str:
    try:
        info = await bot.call_api("get_group_info", group_id=gid)
        if isinstance(info, dict):
            return str(info.get("group_name") or gid)
    except Exception:
        pass
    return str(gid)


def _chunk_cards(head: dict, msg_nodes: list[dict]) -> list[list[dict]]:
    cards: list[list[dict]] = []
    current: list[dict] = []
    for node in msg_nodes:
        if len(current) == MAX_NODES:
            cards.append([head, *current])
            current = []
        current.append(node)
    if current:
        cards.append([head, *current])
    return cards


async def _sync_one(bot: Bot, gid: int, target_group: int) -> int:
    anchor = _load_state(gid, target_group)
    logger.info(f"[groupforward] 开始同步 源群={gid} 目标群={target_group} 锚点={anchor}")

    kwargs: dict = {"group_id": gid, "count": MAX_FETCH}
    if anchor:
        kwargs["message_seq"] = anchor
    try:
        resp = await bot.call_api("get_group_msg_history", **kwargs)
    except ActionFailed as e:
        msg = str(getattr(e, "message", "") or getattr(e, "wording", "") or "")
        if anchor and ("不存在" in msg or "not exist" in msg.lower() or "not found" in msg.lower()):
            logger.warning(f"[groupforward] 源群={gid} 锚点 {anchor} 已失效（{msg}），回退为全量拉取最近消息")
            anchor = None
            resp = await bot.call_api("get_group_msg_history", group_id=gid, count=MAX_FETCH)
        else:
            raise
    msgs = resp.get("messages") if isinstance(resp, dict) else (resp or [])
    logger.info(
        f"[groupforward] get_group_msg_history 源群={gid} 锚点={anchor} 返回 {len(msgs) if isinstance(msgs, list) else '?'} 条"
    )
    if isinstance(msgs, list) and msgs:
        first = msgs[0]
        if isinstance(first, dict):
            logger.info(
                f"[groupforward] 首条消息 message_id={first.get('message_id')} message_seq={first.get('message_seq')} "
                f"time={first.get('time')} 分段数={len(first.get('message') or [])}"
            )

    if not isinstance(msgs, list) or not msgs:
        logger.info(f"[groupforward] 源群={gid} 没有新消息")
        return 0

    # 去掉锚点消息本身，过滤系统通知（加群/退群等无实际消息段），按时间升序取其后消息
    anchor_str = str(anchor) if anchor else None
    total_raw = len(msgs) if isinstance(msgs, list) else 0
    new_msgs = [
        m
        for m in msgs
        if isinstance(m, dict)
        and _msg_id(m) is not None
        and str(_msg_id(m)) != anchor_str
        and (m.get("message") or [])
    ]
    new_msgs.sort(key=lambda m: m.get("time") or 0)
    skipped = total_raw - len(new_msgs)
    if skipped > 0:
        logger.info(f"[groupforward] 源群={gid} 已过滤系统通知等不可转发消息 {skipped} 条")
    if not new_msgs:
        logger.info(f"[groupforward] 源群={gid} 没有新消息")
        return 0

    n_forward = sum(_count_forward_segs(m) for m in new_msgs)
    logger.info(f"[groupforward] 源群={gid} 新消息 {len(new_msgs)} 条，其中含合并转发卡片的共 {n_forward} 处")

    gname = await _group_name(bot, gid)
    head = _content_node(
        int(bot.self_id),
        "同步",
        _text_content(f"「{gname}」待同步的消息，共 {len(new_msgs)} 条"),
    )

    msg_nodes: list[dict] = []
    missing_ids = 0
    for m in new_msgs:
        mid = _msg_id(m)
        if mid is not None:
            # 用真实消息 id 引用源消息，让 NapCat 保留内层合并转发的嵌套结构
            msg_nodes.append({"type": "node", "data": {"id": mid}})
        else:
            missing_ids += 1
            msg_nodes.append(_content_node(_uin(m), _sender_name(m), _fallback_content(m)))
    if missing_ids:
        logger.warning(f"[groupforward] 源群={gid} 有 {missing_ids} 条消息缺少 message_id，已改用 content 节点")

    cards = _chunk_cards(head, msg_nodes)
    if not cards:
        logger.warning(f"[groupforward] 源群={gid} 有 {len(new_msgs)} 条新消息但未生成卡片，跳过")
        return 0

    for i, card in enumerate(cards):
        logger.info(
            f"[groupforward] 发送合并转发第 {i + 1}/{len(cards)} 张卡片 源群={gid} 目标群={target_group} "
            f"节点数={len(card)}（ids={[n['data'].get('id') for n in card if 'id' in n.get('data', {})]}）"
        )
        r = await bot.send_forward_msg(group_id=target_group, messages=card)
        if isinstance(r, dict):
            logger.info(f"[groupforward] 发送成功 resp.message_id={r.get('message_id')} resp.res_id={r.get('res_id')}")
        else:
            logger.info(f"[groupforward] 发送成功 resp={r}")

    newest = max(new_msgs, key=lambda m: m.get("time") or 0)
    new_anchor = str(_msg_id(newest))
    _save_state(gid, target_group, new_anchor)
    logger.info(f"[groupforward] 源群={gid} 同步完成 {len(new_msgs)} 条，锚点 {anchor!r} -> {new_anchor!r}")
    return len(new_msgs)


async def _sync_all(bot: Bot, target_group: int) -> None:
    if not config.forward_source_groups:
        await bot.send_group_msg(
            group_id=target_group,
            message="未配置源群（FORWARD_SOURCE_GROUPS 为空）",
        )
        return

    logger.info(f"[groupforward] 触发同步 目标群={target_group} 源群列表={config.forward_source_groups}")

    results: list[tuple[int, int]] = []
    async with _state_lock:
        for item in config.forward_source_groups:
            gid = int(item)
            try:
                count = await _sync_one(bot, gid, target_group)
                results.append((gid, count))
            except Exception:
                logger.opt(exception=True).warning(f"群消息同步失败 group={gid}")
                results.append((gid, -1))

    if all(n <= 0 for _, n in results):
        await bot.send_group_msg(group_id=target_group, message="没有待同步的新消息")
        return

    total = sum(n for _, n in results if n > 0)
    failed = sum(1 for _, n in results if n < 0)
    msg = f"已同步：{total}条"
    if failed:
        msg += f"（{failed} 个源群同步失败）"
    await bot.send_group_msg(group_id=target_group, message=msg)


sync_cmd = on_command(
    "/sync",
    rule=_group_only,
    priority=50,
    block=False,
)


@sync_cmd.handle()
async def handle_sync(bot: Bot, event: GroupMessageEvent):
    await _sync_all(bot, event.group_id)


async def _scheduled_sync() -> None:
    for bot in get_bots().values():
        for gid in config.sync_target_groups:
            try:
                logger.info(f"[groupforward] 定时同步 目标群={gid}")
                await _sync_all(bot, int(gid))
            except Exception:
                logger.opt(exception=True).warning(f"定时同步失败 target_group={gid}")


if config.sync_target_groups:
    scheduler.add_job(
        _scheduled_sync,
        CronTrigger(hour=9, minute=0),
        id="groupforward_daily_sync",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    logger.info(f"定时同步已注册：每天 09:00 同步到群 {config.sync_target_groups}")
else:
    logger.warning("SYNC_TARGET_GROUPS 未配置，定时同步未注册")