"""
Magic System Plugin - 魔法系统插件

这是一个完整的魔法系统实现示例，展示了如何使用插件系统：
1. 定义新的玩家状态字段（法力、魔法等级）
2. 注册新的游戏命令（/cast, /learn, /spells）
3. 提供LLM工具（check_mana, cast_spell）
4. 监听游戏事件，实现魔法相关的逻辑
5. 扩展世界生成（添加魔法地点、NPC等）
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from core.plugin_system import (
    Plugin, PluginMetadata, PluginCommand, LLMTool,
    PluginLifecycle, PluginHookType, EventListener
)
from core.event_system import EventSystem, EventData, EventType
from core.context_loader import LoadableContent, ContentType, LoadCondition, LoadTrigger, ContentGenerator
import json
import uuid


class MagicSchool(Enum):
    """魔法派系"""
    ELEMENTAL = "elemental"    # 元素魔法
    ARCANE = "arcane"          # 奥术魔法
    NATURE = "nature"           # 自然魔法
    DARK = "dark"              # 黑暗魔法
    LIGHT = "light"            # 光明魔法
    TIME = "time"             # 时间魔法
    MIND = "mind"             # 精神魔法


class SpellDifficulty(Enum):
    """法术难度"""
    CANTRIP = 0    # 戏法
    EASY = 1        # 简单
    NORMAL = 2       # 普通
    HARD = 3         # 困难
    MASTER = 4       # 大师
    LEGENDARY = 5    # 传说


@dataclass
class Spell:
    """法术定义"""
    spell_id: str
    name: str
    description: str
    school: MagicSchool
    difficulty: SpellDifficulty
    mana_cost: int
    cooldown: int = 0  # 冷却时间（回合数）
    effects: Dict[str, Any] = field(default_factory=dict)  # 法术效果
    requirements: Dict[str, Any] = field(default_factory=dict)  # 施放要求

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "name": self.name,
            "description": self.description,
            "school": self.school.value,
            "difficulty": self.difficulty.value,
            "mana_cost": self.mana_cost,
            "cooldown": self.cooldown,
            "effects": self.effects,
            "requirements": self.requirements
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Spell':
        return cls(
            spell_id=data["spell_id"],
            name=data["name"],
            description=data["description"],
            school=MagicSchool(data["school"]),
            difficulty=SpellDifficulty(data["difficulty"]),
            mana_cost=data["mana_cost"],
            cooldown=data.get("cooldown", 0),
            effects=data.get("effects", {}),
            requirements=data.get("requirements", {})
        )


@dataclass
class MagicItem:
    """魔法物品"""
    item_id: str
    name: str
    description: str
    item_type: str  # wand, staff, scroll, potion, etc.
    enchantments: List[str] = field(default_factory=list)  # 魔法效果列表
    mana_bonus: int = 0
    spell_power: int = 0
    durability: int = 100
    max_durability: int = 100


# 内置法术库
BUILTIN_SPELLS = {
    "fireball": Spell(
        spell_id="fireball",
        name="火球术",
        description="发射一团火焰对目标造成魔法伤害",
        school=MagicSchool.ELEMENTAL,
        difficulty=SpellDifficulty.NORMAL,
        mana_cost=20,
        effects={"damage": 30, "damage_type": "fire", "aoe": 3},
        requirements={"magic_level": 3}
    ),
    "heal": Spell(
        spell_id="heal",
        name="治疗术",
        description="用魔法治愈目标的伤口，恢复生命值",
        school=MagicSchool.LIGHT,
        difficulty=SpellDifficulty.EASY,
        mana_cost=15,
        effects={"heal": 25, "target": "ally"},
        requirements={"magic_level": 1}
    ),
    "shield": Spell(
        spell_id="shield",
        name="魔法护盾",
        description="在周身创造一个魔法护盾，暂时提高防御力",
        school=MagicSchool.ARCANE,
        difficulty=SpellDifficulty.EASY,
        mana_cost=10,
        effects={"defense_bonus": 20, "duration": 3},
        requirements={"magic_level": 2}
    ),
    "invisibility": Spell(
        spell_id="invisibility",
        name="隐身术",
        description="使施术者变得隐形，一段时间内无法被察觉",
        school=MagicSchool.ARCANE,
        difficulty=SpellDifficulty.HARD,
        mana_cost=30,
        effects={"invisible": True, "duration": 5},
        requirements={"magic_level": 4}
    ),
    "light": Spell(
        spell_id="light",
        name="照明术",
        description="创造一个光球，照亮周围区域",
        school=MagicSchool.LIGHT,
        difficulty=SpellDifficulty.CANTRIP,
        mana_cost=1,
        effects={"light_radius": 10, "duration": 60},
        requirements={"magic_level": 0}
    ),
    "teleport": Spell(
        spell_id="teleport",
        name="传送术",
        description="瞬间将施术者传送到指定位置",
        school=MagicSchool.ARCANE,
        difficulty=SpellDifficulty.MASTER,
        mana_cost=50,
        effects={"teleport": True, "range": 100},
        requirements={"magic_level": 5, "requires_foci": True}
    ),
    "mind_control": Spell(
        spell_id="mind_control",
        name="精神控制",
        description="控制目标的思想，使其听从你的指令",
        school=MagicSchool.MIND,
        difficulty=SpellDifficulty.LEGENDARY,
        mana_cost=100,
        effects={"control": True, "duration": 10},
        requirements={"magic_level": 6, "forbidden": True}
    ),
    "summon_familiar": Spell(
        spell_id="summon_familiar",
        name="召唤使魔",
        description="召唤一个魔法使魔来协助你",
        school=MagicSchool.NATURE,
        difficulty=SpellDifficulty.NORMAL,
        mana_cost=25,
        effects={"summon": "familiar", "duration": 300},
        requirements={"magic_level": 3}
    )
}


@plugin(
    name="MagicSystem",
    version="1.0.0",
    author="RPG Engine Team",
    description="完整的魔法系统，支持法术学习、施放、魔法物品和法力管理"
)
class MagicSystemPlugin(Plugin):
    """
    魔法系统插件

    提供功能：
    - 法力值管理
    - 魔法等级系统
    - 法术学习
    - 法术施放
    - 魔法物品
    - 魔法相关事件
    """

    def __init__(self):
        super().__init__()
        # 初始化元数据
        self.metadata = type(self).__dict__['metadata']

        # 法术库
        self.spells: Dict[str, Spell] = BUILTIN_SPELLS.copy()

        # 玩家法术冷却追踪 {player_id: {spell_id: remaining_cooldown}}
        self._spell_cooldowns: Dict[str, Dict[str, int]] = {}

    def on_load(self, engine) -> None:
        """插件加载时调用"""
        print("🔮 魔法系统插件加载中...")

        # 注册事件监听器
        event_system = engine.cognition  # 假设event_system在engine中
        self.register_event_listener(
            event_system,
            [EventType.PLAYER_STATE_CHANGED, EventType.ITEM_ACQUIRED],
            self._handle_magic_events
        )

        # 注册命令
        self._setup_commands()

        # 注册LLM工具
        self._setup_llm_tools()

        print("✅ 魔法系统插件加载完成")

    def on_unload(self, engine) -> None:
        """插件卸载时调用"""
        print("🔮 魔法系统插件卸载中...")
        self._spell_cooldowns.clear()
        print("✅ 魔法系统插件卸载完成")

    # =========================================================================
    # 🎮 命令系统
    # =========================================================================

    def _setup_commands(self) -> None:
        """设置魔法命令"""
        # 施放法术命令
        self.register_command(PluginCommand(
            name="cast",
            description="施放法术。用法: /cast <法术名> [目标]",
            handler=self._handle_cast_command,
            aliases=["c", "施法", "施放"],
            requires_params=True
        ))

        # 学习法术命令
        self.register_command(PluginCommand(
            name="learn",
            description="学习新法术。用法: /learn <法术名>",
            handler=self._handle_learn_command,
            aliases=["l", "学习"],
            requires_params=True
        ))

        # 查看法术列表命令
        self.register_command(PluginCommand(
            name="spells",
            description="查看已学会的法术列表",
            handler=self._handle_spells_command,
            aliases=["法术", "法术列表", "grimoire"],
            requires_params=False
        ))

        # 查看法力值命令
        self.register_command(PluginCommand(
            name="mana",
            description="查看当前法力值",
            handler=self._handle_mana_command,
            aliases=["法力", "mp"],
            requires_params=False
        ))

        # 恢复法力命令
        self.register_command(PluginCommand(
            name="meditate",
            description="冥想恢复法力值",
            handler=self._handle_meditate_command,
            aliases=["冥想", "打坐"],
            requires_params=False
        ))

    # =========================================================================
    # 🤖 LLM工具系统
    # =========================================================================

    def _setup_llm_tools(self) -> None:
        """设置LLM工具"""
        # 检查法力值工具
        self.register_llm_tool(LLMTool(
            name="check_mana",
            description="检查玩家的法力值和魔法等级",
            handler=self._llm_check_mana,
            parameters={}
        ))

        # 施放法术工具
        self.register_llm_tool(LLMTool(
            name="cast_spell",
            description="施放指定的法术",
            handler=self._llm_cast_spell,
            parameters={
                "spell_name": {"type": "string", "description": "法术名称"},
                "target": {"type": "string", "description": "目标（可选）", "required": False}
            }
        ))

        # 获取可用法术工具
        self.register_llm_tool(LLMTool(
            name="get_available_spells",
            description="获取玩家当前可用的法术列表",
            handler=self._llm_get_available_spells,
            parameters={}
        ))

    def _llm_check_mana(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM工具：检查法力值"""
        # 这里需要从引擎获取玩家状态
        # 返回示例数据
        return {
            "success": True,
            "current_mana": 80,
            "max_mana": 100,
            "magic_level": 3,
            "regeneration_rate": 5
        }

    def _llm_cast_spell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM工具：施放法术"""
        spell_name = params.get("spell_name", "")
        target = params.get("target", None)

        spell = self.spells.get(spell_name)
        if not spell:
            return {
                "success": False,
                "error": f"未找到法术: {spell_name}"
            }

        # 模拟法术施放
        return {
            "success": True,
            "spell": spell.name,
            "cast_by": "玩家",
            "target": target,
            "effects": spell.effects,
            "mana_cost": spell.mana_cost
        }

    def _llm_get_available_spells(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM工具：获取可用法术"""
        # 这里需要从玩家状态中获取已学习的法术
        return {
            "success": True,
            "spells": [
                {"name": s.name, "cost": s.mana_cost, "school": s.school.value}
                for s in self.spells.values()
                if s.difficulty.value <= 3  # 假设玩家学会了所有简单到困难的法术
            ]
        }

    # =========================================================================
    # ⚔️ 命令处理器
    # =========================================================================

    def _handle_cast_command(self, params: str, engine) -> str:
        """处理施法命令"""
        parts = params.strip().split(maxsplit=1)
        if not parts:
            return "请指定要施放的法术。用法: /cast <法术名>"

        spell_name = parts[0].strip().lower()
        target = parts[1].strip() if len(parts) > 1 else None

        spell = self.spells.get(spell_name)
        if not spell:
            # 模糊匹配
            matches = [s for s in self.spells.values() if spell_name in s.name.lower()]
            if matches:
                return f"未找到法术 '{spell_name}'。你是想说: {', '.join(s.name for s in matches)} 吗？"
            return f"❌ 未找到法术: {spell_name}"

        # 检查是否已学习
        player_state = engine.cognition.get_player_state()
        known_spells = player_state.get("spells", [])

        if spell.spell_id not in known_spells:
            return f"❌ 你还没有学会 {spell.name}。可以用 /learn 来学习它。"

        # 检查法力值
        current_mana = player_state.get("mana", 0)
        max_mana = player_state.get("max_mana", 100)

        if current_mana < spell.mana_cost:
            return f"❌ 法力不足！需要 {spell.mana_cost} 法力，当前只有 {current_mana}。"

        # 检查魔法等级
        magic_level = player_state.get("magic_level", 0)
        required_level = spell.requirements.get("magic_level", 0)
        if magic_level < required_level:
            return f"❌ 魔法等级不足！需要等级 {required_level}，当前等级 {magic_level}。"

        # 检查冷却
        player_id = "player"  # 这里应该从玩家状态获取
        cooldowns = self._spell_cooldowns.get(player_id, {})
        remaining_cooldown = cooldowns.get(spell.spell_id, 0)
        if remaining_cooldown > 0:
            return f"❌ {spell.name} 还在冷却中，还需 {remaining_cooldown} 回合。"

        # 施放法术
        # 扣除法力值
        new_mana = current_mana - spell.mana_cost
        engine.cognition.update_player_state({"mana": new_mana})

        # 设置冷却
        if spell.cooldown > 0:
            cooldowns[spell.spell_id] = spell.cooldown
            self._spell_cooldowns[player_id] = cooldowns

        # 生成法术效果描述
        effect_desc = self._generate_spell_effect_description(spell, target)

        # 触发法术施放事件
        engine.event_system.emit(
            EventType.ACTION,
            "player",
            player_state.get("location", "Unknown"),
            data={
                "description": f"施放了法术 {spell.name}",
                "spell_id": spell.spell_id,
                "target": target,
                "result": "success"
            },
            tags=["magic", "spell_cast"]
        )

        return f"✨ {effect_desc}\n\n🔮 法力消耗: {spell.mana_cost}/{max_mana}"

    def _handle_learn_command(self, params: str, engine) -> str:
        """处理学习法术命令"""
        spell_name = params.strip().lower()

        # 查找法术
        spell = None
        for s in self.spells.values():
            if spell_name in s.name.lower() or spell_name == s.spell_id:
                spell = s
                break

        if not spell:
            return f"❌ 未找到法术: {spell_name}"

        # 检查是否已学会
        player_state = engine.cognition.get_player_state()
        known_spells = player_state.get("spells", [])

        if spell.spell_id in known_spells:
            return f"⚠️ 你已经学会了 {spell.name}。"

        # 检查魔法等级
        magic_level = player_state.get("magic_level", 0)
        required_level = spell.requirements.get("magic_level", 0)
        if magic_level < required_level:
            return f"❌ 魔法等级不足！需要等级 {required_level}，当前等级 {magic_level}。"

        # 学习法术
        known_spells.append(spell.spell_id)
        engine.cognition.update_player_state({"spells": known_spells})

        # 触发学习事件
        engine.event_system.emit(
            EventType.ACTION,
            "player",
            player_state.get("location", "Unknown"),
            data={
                "description": f"学会了法术 {spell.name}",
                "spell_id": spell.spell_id,
                "result": "success"
            },
            tags=["magic", "learn_spell"]
        )

        return f"📖 你学会了 {spell.name}！\n" \
               f"   派系: {spell.school.value}\n" \
               f"   法力消耗: {spell.mana_cost}\n" \
               f"   {spell.description}"

    def _handle_spells_command(self, params: str, engine) -> str:
        """处理查看法术列表命令"""
        player_state = engine.cognition.get_player_state()
        known_spells = player_state.get("spells", [])

        if not known_spells:
            return "你还没有学会任何法术。使用 /learn <法术名> 来学习新法术。"

        lines = ["📜 已学会的法术:", "=" * 40]
        for spell_id in known_spells:
            spell = self.spells.get(spell_id)
            if spell:
                # 检查冷却
                player_id = "player"
                cooldown = self._spell_cooldowns.get(player_id, {}).get(spell_id, 0)
                cooldown_str = f" (冷却: {cooldown})" if cooldown > 0 else ""

                mana_affordable = "✓" if player_state.get("mana", 0) >= spell.mana_cost else "✗"

                lines.append(f"{mana_affordable} {spell.name:20s} | {spell.mana_cost:3d}法力 | {spell.school.value[:8]}{cooldown_str}")

        current_mana = player_state.get("mana", 0)
        max_mana = player_state.get("max_mana", 100)
        lines.append("\n" + "=" * 40)
        lines.append(f"🔮 法力: {current_mana}/{max_mana}")

        return "\n".join(lines)

    def _handle_mana_command(self, params: str, engine) -> str:
        """处理查看法力值命令"""
        player_state = engine.cognition.get_player_state()
        current_mana = player_state.get("mana", 0)
        max_mana = player_state.get("max_mana", 100)
        magic_level = player_state.get("magic_level", 0)

        return f"🔮 法力值: {current_mana}/{max_mana}\n\n" \
               f"   魔法等级: {magic_level}\n" \
               f"   已学习法术: {len(player_state.get('spells', []))} 个"

    def _handle_meditate_command(self, params: str, engine) -> str:
        """处理冥想命令"""
        player_state = engine.cognition.get_player_state()
        current_mana = player_state.get("mana", 0)
        max_mana = player_state.get("max_mana", 100)

        if current_mana >= max_mana:
            return "🧘 你的法力已经满了，不需要冥想。"

        # 冥想恢复法力
        recovery = min(20, max_mana - current_mana)
        new_mana = current_mana + recovery
        engine.cognition.update_player_state({"mana": new_mana})

        # 魔法等级越高，恢复越多
        magic_level = player_state.get("magic_level", 0)
        extra_recovery = magic_level * 2
        new_mana = min(max_mana, new_mana + extra_recovery)
        engine.cognition.update_player_state({"mana": new_mana})

        final_mana = player_state.get("mana", 0)
        return f"🧘 你进入冥想状态，感受着周围魔力的流动...\n\n" \
               f"   法力恢复: {final_mana - current_mana}\n" \
               f"   当前法力: {final_mana}/{max_mana}"

    # =========================================================================
    # 🔧 辅助方法
    # =========================================================================

    def _generate_spell_effect_description(self, spell: Spell, target: Optional[str]) -> str:
        """生成法术效果描述"""
        effect_name = spell.name
        target_str = f"对 {target}" if target else "施放"

        if spell.school == MagicSchool.ELEMENTAL:
            action = self._get_elemental_action(spell)
            return f"{action}，{target_str}施放了 {spell.name}！"
        elif spell.school == MagicSchool.LIGHT:
            return f"柔和的光芒汇聚，{target_str}施放了 {spell.name}！"
        elif spell.school == MagicSchool.DARK:
            return f"诡异的暗影从你周围涌出，{target_str}施放了 {spell.name}！"
        elif spell.school == MagicSchool.ARCANE:
            return f"奥术的符文在空中浮现，{target_str} 精准地施放了 {spell.name}！"
        else:
            return f"你集中精神，{target_str} 施放了 {spell.name}！"

    def _get_elemental_action(self, spell: Spell) -> str:
        """获取元素法术的描述性动作"""
        if "fire" in spell.spell_id or "flame" in spell.spell_id:
            return "炽热的火焰从你掌心喷涌而出"
        elif "ice" in spell.spell_id or "frost" in spell.spell_id:
            return "冰晶的碎片在你周围凝聚"
        elif "lightning" in spell.spell_id or "thunder" in spell.spell_id:
            return "电弧在你指尖跳跃"
        elif "earth" in spell.spell_id or "stone" in spell.spell_id:
            return "大地震颤，岩石从地下升起"
        else:
            return "元素的力量在你体内涌动"

    def _handle_magic_events(self, event: EventData) -> None:
        """处理魔法相关事件"""
        if event.event_type == EventType.ITEM_ACQUIRED:
            item_id = event.data.get("item_id", "")
            # 检查是否是魔法物品
            if item_id.startswith("magic_"):
                # 触发发现魔法物品事件
                pass

    # =========================================================================
    # 🌍 世界内容扩展
    # =========================================================================

    def get_magic_locations(self) -> List[LoadableContent]:
        """获取魔法系统提供的地点内容"""
        return [
            LoadableContent(
                content_id="magic_shop",
                content_type=ContentType.LOCATION,
                name="神秘法师塔",
                description="一座高耸入云的法师塔，塔顶闪烁着奥术的光芒",
                condition=LoadCondition(
                    trigger_type=LoadTrigger.EVENT_BASED,
                    custom_condition=lambda state, events: state.get("magic_level", 0) >= 1
                ),
                data={
                    "shop_type": "magic",
                    "available_spells": ["light", "shield", "heal"],
                    "npcs": ["archmage_vincent"]
                }
            ),
            LoadableContent(
                content_id="mana_spring",
                content_type=ContentType.LOCATION,
                name="魔力之泉",
                description="一池散发着微弱蓝光的泉水，饮用后可以恢复大量法力值",
                condition=LoadCondition(
                    trigger_type=LoadTrigger.LOCATION_BASED,
                    has_tags=["traveler", "outsider"]
                ),
                data={
                    "effect": "restore_mana",
                    "mana_restore": 50,
                    "one_time_use": True
                }
            )
        ]

    def get_magic_npcs(self) -> List[Dict[str, Any]]:
        """获取魔法系统提供的NPC"""
        return [
            {
                "npc_id": "archmage_vincent",
                "name": "大法师文森特",
                "description": "一位年迈但智慧的大法师，精通所有派系的魔法",
                "location": "magic_shop",
                "special": True,
                "dialogue_trees": {
                    "magic_tutorial": [
                        "年轻人，你对魔法有兴趣吗？",
                        "魔法是我们与世界沟通的桥梁，也是对抗黑暗的力量",
                        "要学魔法，首先要学会感受周围的魔力流动"
                    ]
                }
            },
            {
                "npc_id": "hedge_mage_eldora",
                "name": "树篱法师艾尔朵拉",
                "description": "一位居住在森林中的自然派法师，与动物和谐相处",
                "location": "forest_entrance",
                "special": True,
                "teaches_spells": ["summon_familiar", "nature_gift"]
            }
        ]


# ============================================================================
# 导出插件实例
# ============================================================================

def get_plugin() -> MagicSystemPlugin:
    """获取魔法系统插件实例"""
    return MagicSystemPlugin()