import random

from nonebot import on_notice
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupIncreaseNoticeEvent,
    MessageSegment,
    Message,
)

WELCOME_TEXTS = [
    "这个服又多了一个成员！怎么想都是 {at} 的错",
    "万众瞩目的 {at} 终于来了，让我们用掌声和热情激烈的欢迎他！",
    "{at} 进入了群 过度的索取终究会带来灭亡...",
    "{at} 来了 快上车！没时间解释了！",
    "新成员揭开了神秘的面具，原来他是 {at}",
    "欢迎 {at} 进入群 但是我们已经没有多余的僵立停了...",
    "有请新加入的 {at} 给大家整活儿",
    "{at} 来支援我们了！他肯定不会让这条战线垮掉的！",
    "{at} 进入了群！是新的朋友！是新的好兄弟！",
    "是谁？有那广阔的胸怀？是谁？站在那高耸的山峰上？是 {at}",
    "我不演了，我摊牌了，{at} 就是我们新的一员",
    "{at} 发出了耀眼的光芒！他进化成了......什么也没有",
    "你以为他在第一层，但其实 {at} 在第五层",
    "{at} 来了，简直就像...就像...我编不下去了",
    "天才玩家 {at} 进入了群，这把我们有救辣！",
    "{at} 加入了我们！Level UP！",
    "{at} 进入了群，但事态远没有他想的那么简单",
    "来了个新人，{at}，大家快来欺负他！",
    "狂风呼啸 站在你面前的是 {at}，一个真正的勇士",
    "快看，这是一种叫做 {at} 的地球生物",
    "{at}！你tnd意大利炮呢？给他来一炮！",
    "电闪雷鸣风雨交加，{at} 降临了！",
    "热烈欢迎 {at}！你是电~你是光~你是唯一的神话~",
    "{at} 曾经也是个勇者，直到他的膝盖中了一箭",
    "我轻轻的走了，正如 {at} 轻轻的来",
    "{at} 吃掉了你的脑子！",
    "三年二班 {at} 同学！你妈妈拿了两罐BTL牛奶！要给你！",
    "你选择红色药丸还是蓝色药丸？{at}",
    "{at} 刚从5000年的长眠中醒来，该让这些人知道谁才是他们皇帝了",
    "{at} 来到了群，将其裹上蛋液面包糠，炸至金黄...",
]

welcome = on_notice()


@welcome.handle()
async def welcome_handle(bot: Bot, event: GroupIncreaseNoticeEvent):
    uid = event.get_user_id()
    at = MessageSegment.at(uid)
    text = random.choice(WELCOME_TEXTS).format(at=at)
    await welcome.finish(Message(text))
