# main.py

import random
from astrbot.api.message_components import Node, Plain, Nodes
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# ==================== 游戏配置中心 ====================
GAME_CONFIG = {
    "OWNER_QQ_ID": "12345678",  # !! 请务必修改为你自己的QQ号 !!

    "maps": {"零号大坝": {"display_name": "零号大坝"}},
    "strategies": {
        "猛攻": {"encounter_modifier": 0.20, "win_rate_modifier": 0.0, "loot_range": (1, 5),
                 "quality_modifier": {"史诗": 1.5, "传奇": 2.0}},
        "避战": {"encounter_modifier": -0.20, "win_rate_modifier": -0.20, "loot_range": (0, 3), "quality_modifier": {}}
    },
    "npc": {"base_encounter_chance": 0.70, "base_win_chance": 0.40},
    "shop_weapons": [
        {"name": "水管", "value": 800, "combat_power": 10, "desc": "生锈的铁管，总比赤手空拳要好。"},
        {"name": "PM手枪", "value": 3500, "combat_power": 25, "desc": "可靠的苏式手枪，威力小但胜在常见。"},
        {"name": "双管猎枪", "value": 12000, "combat_power": 55, "desc": "近距离威力巨大，但容错率极低。"},
        {"name": "UZI微冲", "value": 26000, "combat_power": 70, "desc": "射速极快，是室内作战的清道夫。"},
        {"name": "AKM突击步枪", "value": 45000, "combat_power": 95, "desc": "威力强大且可靠，是摸金客最信赖的伙伴。"},
        {"name": "M4A1卡宾枪", "value": 68000, "combat_power": 115, "desc": "性能均衡，后坐力可控，是专业人士的选择。"},
        {"name": "SVD狙击步枪", "value": 95000, "combat_power": 140, "desc": "经典的狙击步枪，能在远处精准解决威胁。"},
        {"name": "MPX冲锋枪", "value": 110000, "combat_power": 165, "desc": "后坐力极低，是近距离战斗中的顶級武器。"},
        {"name": "SCAR-H战斗步枪", "value": 135000, "combat_power": 180, "desc": "大口径战斗步枪，威力巨大，难以驾驭。"},
        {"name": "HK416特战步枪", "value": 150000, "combat_power": 200,
         "desc": "性能完美的特战步枪，是财富和实力的象征。"}
    ],
    "storage": {"weapon_capacity": 10, "junk_capacity": 50}
}

# ==================== 数据库与数据映射 ====================
# 1. 我已经为你填充了完整的杂物数据库
item_database = [
    {"name": "螺丝钉", "value": 20, "rarity": "普通"}, {"name": "能量棒", "value": 50, "rarity": "普通"},
    {"name": "绷带", "value": 80, "rarity": "普通"}, {"name": "香烟", "value": 110, "rarity": "普通"},
    {"name": "绝缘胶带", "value": 130, "rarity": "普通"}, {"name": "多用工具钳", "value": 350, "rarity": "稀有"},
    {"name": "止痛药", "value": 400, "rarity": "稀有"}, {"name": "一捆铜线", "value": 550, "rarity": "稀有"},
    {"name": "小屋钥匙", "value": 600, "rarity": "稀有"}, {"name": "瓶装净水", "value": 700, "rarity": "稀有"},
    {"name": "一盒火药", "value": 900, "rarity": "稀有"}, {"name": "军用急救包", "value": 1500, "rarity": "史诗"},
    {"name": "显卡", "value": 2800, "rarity": "史诗"}, {"name": "工兵铲", "value": 3200, "rarity": "史诗"},
    {"name": "金表", "value": 4500, "rarity": "史诗"}, {"name": "肾上腺素", "value": 5000, "rarity": "史诗"},
    {"name": "一小块黄金", "value": 6500, "rarity": "传奇"}, {"name": "实验室钥匙卡", "value": 7800, "rarity": "传奇"},
    {"name": "军用光纤", "value": 8500, "rarity": "传奇"}, {"name": "加密硬盘", "value": 9800, "rarity": "传奇"}
]
item_map = {item["name"]: item for item in item_database}
weapon_map = {w["name"]: w for w in GAME_CONFIG["shop_weapons"]}

# 抽奖池现在在全局作用域创建一次即可
rarity_weights_map = {"普通": 100, "稀有": 30, "史诗": 5, "传奇": 1}
loot_pool = list(item_map.values())
base_loot_weights = [rarity_weights_map[item["rarity"]] for item in loot_pool] if loot_pool else []

# ==================== 游戏数据存储 ====================
player_data = {}


# ==================== 插件核心代码 ====================
@register("astrabot_plugin_deltaforce", "Huanghun", "将三角洲的摸金玩法搬到了astrbot中", "v1.0",
          "https://github.com/Huanghun542/astrabot_plugin_deltaforce")
class TarkovPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    # --- 核心辅助函数 ---
    def get_player(self, user_id: str):
        if user_id not in player_data:
            player_data[user_id] = {"shibi": 0, "weapons": [], "junk": {}}
        return player_data[user_id]

    def create_forwarded_message(self, bot_id: int, content_text: str, name: str):
        node = Node(uin=int(bot_id), name=name, content=[Plain(content_text)])
        return Nodes(nodes=[node])

    def _get_junk_count(self, player: dict) -> int:
        return sum(player["junk"].values())

    # 2. 加入了安全检查
    def _calculate_and_apply_loot(self, player: dict, strategy_config: dict) -> (str, str):
        if not base_loot_weights:
            logger.error("物品数据库为空！无法生成战利品。请检查配置。")
            return "错误:物品数据库为空", ""

        min_loot, max_loot = strategy_config["loot_range"]
        num_items_found = random.randint(min_loot, max_loot)
        if num_items_found == 0: return "", ""

        temp_loot_weights = list(base_loot_weights)
        quality_mod = strategy_config["quality_modifier"]
        if quality_mod:
            for i, item in enumerate(loot_pool):
                if item["rarity"] in quality_mod:
                    temp_loot_weights[i] *= quality_mod[item["rarity"]]

        found_items = random.choices(loot_pool, weights=temp_loot_weights, k=num_items_found)

        loot_summary, discarded_summary = [], []
        junk_limit = GAME_CONFIG["storage"]["junk_capacity"]
        for item in found_items:
            if self._get_junk_count(player) < junk_limit:
                player["junk"][item["name"]] = player["junk"].get(item["name"], 0) + 1
                loot_summary.append(f"【{item['rarity']}】 {item['name']}")
            else:
                discarded_summary.append(item['name'])

        loot_str = "\n" + "\n".join(loot_summary) if loot_summary else ""
        discarded_str = "\n" + "\n".join(
            f"- {name} (仓库已满)" for name in discarded_summary) if discarded_summary else ""
        return loot_str, discarded_str

    # --- 游戏指令 (后续指令与上一版完全相同，为简洁省略) ---
    # ... (此处省略所有指令代码，请直接使用上一版中完整的、未报错的指令部分) ...
    # 为了防止再次出错，下面依然提供完整的代码
    @filter.command("汐币管理")
    async def gm_set_shibi(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id != GAME_CONFIG["OWNER_QQ_ID"]:
            yield event.plain_result("你没有权限使用此指令。")
            return
        parts = event.message_str.split()
        if len(parts) != 2:
            yield event.plain_result("格式错误！正确格式: /汐币管理 [数量]")
            return
        try:
            amount = int(parts[1])
            player = self.get_player(user_id)
            player['shibi'] = amount
            yield event.plain_result(f"操作成功！你的汐币已设置为 {amount}。")
        except ValueError:
            yield event.plain_result("数量必须是一个有效的整数！")

    @filter.command("进入地图")
    async def enter_map(self, event: AstrMessageEvent):
        user_id, user_name = event.get_sender_id(), event.get_sender_name()
        player, bot_id = self.get_player(user_id), event.get_self_id()
        parts = event.message_str.split()
        if len(parts) != 3 or parts[1] not in GAME_CONFIG["maps"] or parts[2] not in GAME_CONFIG["strategies"]:
            maps = "、".join(GAME_CONFIG["maps"].keys())
            strats = "、".join(GAME_CONFIG["strategies"].keys())
            reply_text = f"指令格式错误！\n正确格式: 进入地图 [地图名] [策略]\n可用地图: {maps}\n可用策略: {strats}"
            yield event.chain_result([self.create_forwarded_message(bot_id, reply_text, name="战局播报员 汐汐")])
            return
        map_name, strategy_name = parts[1], parts[2]
        map_config, strategy_config, npc_config = GAME_CONFIG["maps"][map_name], GAME_CONFIG["strategies"][
            strategy_name], GAME_CONFIG["npc"]
        report_text = f"PMC {user_name}，你选择了 **{strategy_name}** 策略进入 **{map_config['display_name']}**...\n\n"
        final_encounter_chance = npc_config["base_encounter_chance"] + strategy_config["encounter_modifier"]
        is_encounter = random.random() < final_encounter_chance
        if not is_encounter:
            final_loot_str, final_discarded_str = self._calculate_and_apply_loot(player, strategy_config)
            report_text += "你一路潜行，未遇到任何抵抗，顺利撤离。\n\n🎉 **安全撤离** 🎉"
            if final_loot_str: report_text += "\n\n本次收获:" + final_loot_str
            if final_discarded_str: report_text += "\n\n部分物品因仓库已满被丢弃:" + final_discarded_str
        else:
            npc_strategy = random.choice(list(GAME_CONFIG["strategies"].keys()))
            report_text += f"你与一名NPC拾荒者不期而遇！对方采取了 **{npc_strategy}** 策略。\n\n"
            if strategy_name == "避战" and npc_strategy == "避戦":
                final_loot_str, final_discarded_str = self._calculate_and_apply_loot(player, strategy_config)
                report_text += "你们互相提防，最终和平避让。\n\n🎉 **和平撤离** 🎉"
                if final_loot_str: report_text += "\n\n你在该区域的其他地方有所斩获:" + final_loot_str
                if final_discarded_str: report_text += "\n\n部分物品因仓库已满被丢弃:" + final_discarded_str
            else:
                final_win_chance = npc_config["base_win_chance"] + strategy_config["win_rate_modifier"]
                is_victory = random.random() < final_win_chance
                if is_victory:
                    final_loot_str, final_discarded_str = self._calculate_and_apply_loot(player, strategy_config)
                    report_text += "战斗爆发！你成功击败了对方！\n\n🏆 **战斗胜利** 🏆"
                    if final_loot_str: report_text += "\n\n你从这片区域搜刮到了战利品:" + final_loot_str
                    if final_discarded_str: report_text += "\n\n部分物品因仓库已满被丢弃:" + final_discarded_str
                else:
                    report_text += "战斗爆发！不幸的是，你倒在了敌人的枪下。\n\n💀 **战斗失败** 💀"
        yield event.chain_result([self.create_forwarded_message(bot_id, report_text, name="战局播报员 汐汐")])

    @filter.command("商店")
    async def show_shop(self, event: AstrMessageEvent):
        bot_id = event.get_self_id()
        reply_text = "欢迎来到汐汐的黑市军火商店！\n使用 /购买 [武器名] 进行交易\n--------------------\n"
        for weapon in GAME_CONFIG["shop_weapons"]:
            reply_text += (f"{weapon['name']} 价格: {weapon['value']} 汐币 | 战力: {weapon['combat_power']}\n"
                           f"——{weapon['desc']}\n\n")
        yield event.chain_result([self.create_forwarded_message(bot_id, reply_text, name="黑市商人 汐汐")])

    @filter.command("我的仓库")
    async def my_stash(self, event: AstrMessageEvent):
        user_id, user_name = event.get_sender_id(), event.get_sender_name()
        player = self.get_player(user_id)
        weapon_limit, junk_limit = GAME_CONFIG["storage"]["weapon_capacity"], GAME_CONFIG["storage"]["junk_capacity"]
        reply_text = f"💰 {user_name}的资产\n汐币: {player['shibi']}\n"
        reply_text += f"\n--- 武器 ({len(player['weapons'])}/{weapon_limit}) ---\n"
        if not player['weapons']:
            reply_text += "空空如也\n"
        else:
            for weapon_name in player['weapons']:
                w_details = weapon_map[weapon_name]
                reply_text += f"· {w_details['name']} (战力: {w_details['combat_power']})\n"
        junk_count = self._get_junk_count(player)
        reply_text += f"\n--- 杂物 ({junk_count}/{junk_limit}) ---\n"
        if not player['junk']:
            reply_text += "空空如也\n"
        else:
            total_junk_value = 0
            for item_name, count in player["junk"].items():
                i_details = item_map[item_name]
                total_junk_value += i_details['value'] * count
                reply_text += f"· {item_name} * {count}\n"
            reply_text += f"杂物总价值: {total_junk_value} 汐币\n"
        yield event.plain_result(reply_text)

    @filter.command("购买")
    async def buy_weapon(self, event: AstrMessageEvent):
        user_id, player, bot_id = event.get_sender_id(), self.get_player(event.get_sender_id()), event.get_self_id()
        parts = event.message_str.split()
        if len(parts) != 2:
            reply_text = "指令格式错误！正确格式: /购买 [武器名]"
        else:
            weapon_name_to_buy = parts[1]
            if weapon_name_to_buy not in weapon_map:
                reply_text = f"商店里没有名为“{weapon_name_to_buy}”的武器。"
            else:
                weapon_details = weapon_map[weapon_name_to_buy]
                if player['shibi'] < weapon_details['value']:
                    reply_text = f"汐币不足！\n你需要 {weapon_details['value']} 汐币，但你只有 {player['shibi']}。"
                else:
                    player['shibi'] -= weapon_details['value']
                    player['weapons'].append(weapon_name_to_buy)
                    reply_text = f"✅ 购买成功！\n你花费了 {weapon_details['value']} 汐币，获得了 [{weapon_name_to_buy}]。"
                    weapon_limit = GAME_CONFIG["storage"]["weapon_capacity"]
                    if len(player['weapons']) > weapon_limit:
                        sold_weapon_name = player['weapons'].pop(0)
                        sold_weapon_value = weapon_map[sold_weapon_name]['value']
                        player['shibi'] += sold_weapon_value
                        reply_text += f"\n\n⚠️ 武器仓库已满！\n已自动出售最旧的武器 [{sold_weapon_name}]，获得 {sold_weapon_value} 汐币。"
        yield event.plain_result(reply_text)

    @filter.command("出售")
    async def sell_item(self, event: AstrMessageEvent):
        user_id, player = event.get_sender_id(), self.get_player(event.get_sender_id())
        parts, reply_text = event.message_str.split(), ""
        if len(parts) > 1 and parts[1] in weapon_map:
            reply_text = "不能在此出售武器！武器超限时会自动出售。"
        elif len(parts) != 3:
            reply_text = "指令格式错误！\n正确格式：出售 [杂物名称] [数量]"
        else:
            item_name_to_sell = parts[1]
            quantity_to_sell_str = parts[2]
            try:
                quantity_to_sell = int(quantity_to_sell_str)
                if quantity_to_sell <= 0:
                    reply_text = "出售数量必须是大于0的整数！"
                elif item_name_to_sell not in player['junk']:
                    reply_text = f"你的杂物仓库中没有“{item_name_to_sell}”。"
                elif player['junk'][item_name_to_sell] < quantity_to_sell:
                    reply_text = f"你的“{item_name_to_sell}”数量不足！\n你只有 {player['junk'][item_name_to_sell]} 个。"
                else:
                    earnings = item_map[item_name_to_sell]['value'] * quantity_to_sell
                    player['shibi'] += earnings
                    player['junk'][item_name_to_sell] -= quantity_to_sell
                    if player['junk'][item_name_to_sell] == 0:
                        del player['junk'][item_name_to_sell]
                    reply_text = f"✅ 成功出售 {quantity_to_sell} 个“{item_name_to_sell}”，获得 {earnings} 汐币。"
            except ValueError:
                reply_text = "数量必须是一个有效的数字！"
        yield event.plain_result(reply_text)

    @filter.command("全部出售")
    async def sell_all_items(self, event: AstrMessageEvent):
        user_id, player = event.get_sender_id(), self.get_player(event.get_sender_id())
        if not player['junk']:
            reply_text = "你的杂物仓库是空的，没什么可以卖的。"
        else:
            total_earnings, items_sold_count = 0, 0
            for item_name, count in player["junk"].items():
                total_earnings += item_map[item_name]['value'] * count
                items_sold_count += count
            player['shibi'] += total_earnings
            player['junk'].clear()
            reply_text = f"一键清仓完成！你卖掉了所有杂物，共获得了 {total_earnings} 汐币。"
        yield event.plain_result(reply_text)

    async def terminate(self):
        logger.info("搜打撤插件已停用。")
