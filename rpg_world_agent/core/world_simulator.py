"""
World Simulator - 世界模拟系统

这个系统让游戏世界在玩家之外也有发展：
1. 模拟时间流逝和世界变化
2. NPC 的自主活动和移动
3. 随机世界事件的触发
4. 危机等级的动态变化

核心功能：
- simulate_tick(): 模拟一段时间内的世界发展
- simulate_npc_activities(): 模拟 NPC 的随机活动
- simulate_world_events(): 模拟世界事件（战争、灾难、发现等）
"""

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set
from enum import Enum

from rpg_world_agent.core.world_state import (
    WorldStateManager,
    NPCState,
    RegionState,
    QuestState,
    CrisisLevel,
    WeatherType
)
from rpg_world_agent.core.event_system import EventSystem, EventData, EventType, EventPriority

if TYPE_CHECKING:
    from rpg_world_agent.core.runtime import RuntimeEngine


class SimulationPhase(Enum):
    """模拟阶段"""
    QUIET = "quiet"           # 平静期，玩家不活跃时
    ACTIVE = "active"         # 活跃期，玩家正在游戏
    TRANSITION = "transition"  # 过渡期，玩家刚离开或刚回来


class WorldEventCategory(Enum):
    """世界事件类别"""
    NATURAL = "natural"       # 自然事件（天气、灾害）
    POLITICAL = "political"   # 政治事件（战争、和平）
    ECONOMIC = "economic"     # 经济事件（贸易、萧条）
    SOCIAL = "social"         # 社会事件（节日、骚乱）
    MYSTICAL = "mystical"     # 神秘事件（魔法、异象）
    CRISIS = "crisis"         # 危机事件（主线相关）


@dataclass
class NPCActivity:
    """NPC 活动记录"""
    npc_id: str
    activity_type: str        # move, work, rest, social, quest
    timestamp: float
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    description: str = ""
    affected_entities: Set[str] = field(default_factory=set)
    impact: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldEvent:
    """世界事件"""
    event_id: str
    category: WorldEventCategory
    name: str
    description: str
    timestamp: float
    duration_minutes: int = 0      # 0 表示瞬时事件
    affected_regions: Set[str] = field(default_factory=set)
    affected_npcs: Set[str] = field(default_factory=set)
    crisis_change: int = 0         # 对危机等级的影响
    world_state_changes: Dict[str, Any] = field(default_factory=dict)
    narrative: str = ""            # 用于叙事的描述


@dataclass
class SimulationConfig:
    """模拟配置"""
    # NPC 活动频率
    npc_activity_chance: float = 0.3      # 每次 tick 每个 NPC 有活动概率
    npc_move_chance: float = 0.15         # NPC 移动概率
    npc_social_chance: float = 0.1        # NPC 社交概率

    # 事件触发概率
    event_base_chance: float = 0.1        # 基础事件概率
    crisis_event_bonus: float = 0.05      # 危机等级加成（每级）

    # 危机变化
    crisis_natural_decay: float = 0.05    # 危机自然衰减概率
    crisis_escalation_chance: float = 0.1  # 危机升级概率

    # 时间推进
    default_tick_minutes: int = 30        # 默认每次 tick 推进的分钟数
    max_tick_minutes: int = 480           # 单次 tick 最大推进分钟数


class WorldSimulator:
    """
    世界模拟器

    负责让世界在玩家之外也有发展，包括：
    - 时间流逝和天气变化
    - NPC 的自主行为
    - 随机世界事件
    - 危机等级的动态调整
    """

    def __init__(
        self,
        session_id: str,
        world_state: WorldStateManager,
        event_system: EventSystem,
        runtime: Optional["RuntimeEngine"] = None,
        config: Optional[SimulationConfig] = None
    ):
        self.session_id = session_id
        self.world_state = world_state
        self.event_system = event_system
        self.runtime = runtime
        self.config = config or SimulationConfig()

        # 模拟状态
        self._last_sim_time: float = time.time()
        self._simulation_phase: SimulationPhase = SimulationPhase.ACTIVE
        self._tick_count: int = 0

        # 活动历史
        self._recent_activities: List[NPCActivity] = []
        self._recent_world_events: List[WorldEvent] = []

        # 注册事件处理器
        self._setup_event_handlers()

    # =========================================================================
    # 🎮 公共接口
    # =========================================================================

    def simulate_tick(self, minutes: Optional[int] = None) -> List[WorldEvent]:
        """
        模拟一段时间内的世界发展

        这是主要的公共接口，会依次执行：
        1. 推进世界时间
        2. 模拟 NPC 活动
        3. 触发世界事件
        4. 更新危机等级

        Args:
            minutes: 要模拟的分钟数，None 则使用默认值

        Returns:
            List[WorldEvent]: 触发的世界事件列表
        """
        if minutes is None:
            minutes = self.config.default_tick_minutes

        minutes = min(minutes, self.config.max_tick_minutes)
        self._tick_count += 1

        events: List[WorldEvent] = []

        # 1. 推进世界时间
        self.world_state.advance_time(minutes)

        # 2. 天气变化
        self._simulate_weather_change()

        # 3. NPC 活动
        npc_activities = self.simulate_npc_activities()
        self._recent_activities.extend(npc_activities)

        # 4. 世界事件
        world_events = self.simulate_world_events()
        events.extend(world_events)
        self._recent_world_events.extend(world_events)

        # 5. 危机等级调整
        self._adjust_crisis_level()

        # 6. 清理过期记录
        self._cleanup_history()

        self._last_sim_time = time.time()

        return events

    def simulate_npc_activities(self) -> List[NPCActivity]:
        """
        模拟 NPC 活动

        每个 NPC 可能会：
        - 移动到其他地点
        - 进行日常工作
        - 与其他 NPC 社交
        - 推进任务进度

        Returns:
            List[NPCActivity]: NPC 活动列表
        """
        activities: List[NPCActivity] = []

        for npc_id, npc in self.world_state.npcs.items():
            if not npc.alive:
                continue

            # 判断是否进行活动
            if random.random() > self.config.npc_activity_chance:
                continue

            activity = self._decide_npc_activity(npc)
            if activity:
                activities.append(activity)
                self._apply_npc_activity(activity, npc)

        return activities

    def simulate_world_events(self) -> List[WorldEvent]:
        """
        模拟世界事件

        基于当前世界状态随机触发事件，包括：
        - 自然事件（天气变化、灾害）
        - 政治事件（战争、和平）
        - 经济事件（贸易、萧条）
        - 社会事件（节日、骚乱）
        - 神秘事件（魔法、异象）
        - 危机事件（主线相关）

        Returns:
            List[WorldEvent]: 触发的世界事件列表
        """
        events: List[WorldEvent] = []

        # 基础事件概率 + 危机加成
        crisis_bonus = self.world_state.crisis_level.value * self.config.crisis_event_bonus
        event_chance = self.config.event_base_chance + crisis_bonus

        if random.random() < event_chance:
            event = self._generate_random_event()
            if event:
                events.append(event)
                self._apply_world_event(event)

        return events

    def get_simulation_summary(self) -> Dict[str, Any]:
        """获取模拟状态摘要"""
        return {
            "tick_count": self._tick_count,
            "phase": self._simulation_phase.value,
            "last_sim_time": self._last_sim_time,
            "recent_activities": len(self._recent_activities),
            "recent_events": len(self._recent_world_events),
            "world_time": str(self.world_state.world_time),
            "crisis_level": self.world_state.crisis_level.name
        }

    def get_recent_narrative(self) -> str:
        """获取最近的叙事描述，用于 LLM 上下文"""
        lines = ["【世界动态】"]

        # 最近的世界事件
        if self._recent_world_events:
            lines.append("🌍 近期世界事件:")
            for event in self._recent_world_events[-5:]:
                time_str = time.strftime("%H:%M", time.localtime(event.timestamp))
                lines.append(f"  [{time_str}] {event.name}: {event.description}")

        # 最近的 NPC 活动
        if self._recent_activities:
            lines.append("\n👥 近期NPC活动:")
            for activity in self._recent_activities[-5:]:
                npc = self.world_state.get_npc_state(activity.npc_id)
                if npc:
                    lines.append(f"  {npc.name} - {activity.description}")

        return "\n".join(lines) if len(lines) > 1 else ""

    # =========================================================================
    # 🤖 NPC 活动模拟
    # =========================================================================

    def _decide_npc_activity(self, npc: NPCState) -> Optional[NPCActivity]:
        """决定 NPC 的活动"""
        roll = random.random()

        # 根据概率决定活动类型
        if roll < self.config.npc_move_chance:
            return self._generate_npc_movement(npc)
        elif roll < self.config.npc_move_chance + self.config.npc_social_chance:
            return self._generate_npc_social(npc)
        else:
            return self._generate_npc_routine(npc)

    def _generate_npc_movement(self, npc: NPCState) -> Optional[NPCActivity]:
        """生成 NPC 移动活动"""
        # 获取当前位置的邻近区域
        current_region = self.world_state.get_region_state(npc.current_location)
        if not current_region:
            return None

        # 简单实现：随机选择一个已知区域移动
        available_regions = [
            rid for rid, region in self.world_state.regions.items()
            if rid != npc.current_location and region.discovered
        ]

        if not available_regions:
            return None

        target_region = random.choice(available_regions)

        return NPCActivity(
            npc_id=npc.npc_id,
            activity_type="move",
            timestamp=time.time(),
            from_location=npc.current_location,
            to_location=target_region,
            description=f"{npc.name} 从 {npc.current_location} 前往了 {target_region}",
            impact={"location_change": True}
        )

    def _generate_npc_social(self, npc: NPCState) -> Optional[NPCActivity]:
        """生成 NPC 社交活动"""
        # 查找同一位置的其他 NPC
        nearby_npcs = [
            n for n in self.world_state.npcs.values()
            if n.npc_id != npc.npc_id
            and n.alive
            and n.current_location == npc.current_location
        ]

        if not nearby_npcs:
            return None

        target_npc = random.choice(nearby_npcs)
        social_actions = [
            ("gossip", "与 {target} 闲聊"),
            ("trade", "与 {target} 交易"),
            ("argue", "与 {target} 争论"),
            ("cooperate", "与 {target} 合作")
        ]

        action_type, action_template = random.choice(social_actions)
        description = action_template.format(target=target_npc.name)

        return NPCActivity(
            npc_id=npc.npc_id,
            activity_type="social",
            timestamp=time.time(),
            description=description,
            affected_entities={target_npc.npc_id},
            impact={"relationship_change": True}
        )

    def _generate_npc_routine(self, npc: NPCState) -> Optional[NPCActivity]:
        """生成 NPC 日常活动"""
        # 根据时间决定活动
        hour = self.world_state.world_time.hours

        if 6 <= hour < 12:
            activities = [
                ("work", "正在工作"),
                ("gather", "正在收集资源"),
                ("patrol", "正在巡逻")
            ]
        elif 12 <= hour < 18:
            activities = [
                ("work", "正在工作"),
                ("trade", "正在交易"),
                ("rest", "正在休息")
            ]
        else:
            activities = [
                ("rest", "正在休息"),
                ("socialize", "正在社交"),
                ("guard", "正在守夜")
            ]

        activity_type, description = random.choice(activities)

        return NPCActivity(
            npc_id=npc.npc_id,
            activity_type=activity_type,
            timestamp=time.time(),
            description=f"{npc.name} {description}",
            impact={"routine": True}
        )

    def _apply_npc_activity(self, activity: NPCActivity, npc: NPCState) -> None:
        """应用 NPC 活动的影响"""
        if activity.activity_type == "move" and activity.to_location:
            # 移动 NPC
            self.world_state.move_npc(npc.npc_id, activity.to_location)

        elif activity.activity_type == "social" and activity.affected_entities:
            # 更新 NPC 关系
            for target_id in activity.affected_entities:
                current_rel = self.world_state.get_npc_relationship(npc.npc_id, target_id)
                change = random.randint(-5, 10)  # 社交通常略微正面
                self.world_state.set_npc_relationship(
                    npc.npc_id, target_id, current_rel + change
                )

        # 更新 NPC 当前状态
        npc.current_action = activity.activity_type

        # 触发事件
        self.event_system.emit(
            EventType.CUSTOM,
            f"npc_{npc.npc_id}",
            npc.current_location,
            data={
                "activity": activity.activity_type,
                "description": activity.description
            },
            tags=["npc", "simulation", activity.activity_type]
        )

    # =========================================================================
    # 🌍 世界事件模拟
    # =========================================================================

    def _generate_random_event(self) -> Optional[WorldEvent]:
        """生成随机世界事件"""
        crisis_level = self.world_state.crisis_level.value

        # 根据危机等级调整各类事件概率
        event_weights = {
            WorldEventCategory.NATURAL: 30 - crisis_level * 3,
            WorldEventCategory.POLITICAL: 15,
            WorldEventCategory.ECONOMIC: 15,
            WorldEventCategory.SOCIAL: 20,
            WorldEventCategory.MYSTICAL: 5 + crisis_level * 2,
            WorldEventCategory.CRISIS: 5 + crisis_level * 4
        }

        # 随机选择事件类别
        categories = list(event_weights.keys())
        weights = list(event_weights.values())
        category = random.choices(categories, weights=weights, k=1)[0]

        # 生成该类别的事件
        return self._generate_event_by_category(category)

    def _generate_event_by_category(self, category: WorldEventCategory) -> Optional[WorldEvent]:
        """根据类别生成具体事件"""
        event_templates = self._get_event_templates().get(category, [])
        if not event_templates:
            return None

        template = random.choice(event_templates)

        # 选择受影响的区域
        affected_regions = set()
        discovered_regions = [
            rid for rid, r in self.world_state.regions.items()
            if r.discovered
        ]
        if discovered_regions:
            num_regions = random.randint(1, min(3, len(discovered_regions)))
            affected_regions = set(random.sample(discovered_regions, num_regions))

        event = WorldEvent(
            event_id=f"we_{int(time.time())}_{random.randint(1000, 9999)}",
            category=category,
            name=template["name"],
            description=template["description"],
            timestamp=time.time(),
            duration_minutes=template.get("duration", 0),
            affected_regions=affected_regions,
            crisis_change=template.get("crisis_change", 0),
            narrative=template.get("narrative", template["description"])
        )

        return event

    def _get_event_templates(self) -> Dict[WorldEventCategory, List[Dict]]:
        """获取事件模板"""
        return {
            WorldEventCategory.NATURAL: [
                {
                    "name": "暴风雨来临",
                    "description": "一场突如其来的暴风雨席卷了这片区域",
                    "duration": 120,
                    "crisis_change": 0,
                    "narrative": "乌云密布，雷声隆隆，一场暴风雨正在逼近..."
                },
                {
                    "name": "丰收季节",
                    "description": "风调雨顺，农田迎来了大丰收",
                    "duration": 0,
                    "crisis_change": -1,
                    "narrative": "金黄的麦浪在风中起伏，这是一年中最美好的时节。"
                },
                {
                    "name": "地震",
                    "description": "大地突然剧烈震动",
                    "duration": 30,
                    "crisis_change": 1,
                    "narrative": "地面开始颤抖，远处传来隆隆的声响..."
                }
            ],
            WorldEventCategory.POLITICAL: [
                {
                    "name": "边境冲突",
                    "description": "边境地区发生了小规模冲突",
                    "duration": 0,
                    "crisis_change": 1,
                    "narrative": "有消息传来，边境那边不太平..."
                },
                {
                    "name": "和平协议",
                    "description": "各方达成了暂时的和平协议",
                    "duration": 0,
                    "crisis_change": -1,
                    "narrative": "使者们奔波往来，终于达成了共识。"
                }
            ],
            WorldEventCategory.ECONOMIC: [
                {
                    "name": "商队到达",
                    "description": "一支大型商队抵达，带来了各种奇珍异宝",
                    "duration": 0,
                    "crisis_change": 0,
                    "narrative": "远处的尘土飞扬，一支商队正在靠近..."
                },
                {
                    "name": "物资短缺",
                    "description": "某些物资出现了短缺",
                    "duration": 0,
                    "crisis_change": 0,
                    "narrative": "市场上议论纷纷，有些东西买不到了。"
                }
            ],
            WorldEventCategory.SOCIAL: [
                {
                    "name": "节日庆典",
                    "description": "当地正在举行节日庆典",
                    "duration": 180,
                    "crisis_change": -1,
                    "narrative": "锣鼓喧天，彩旗飘扬，人们正在庆祝节日。"
                },
                {
                    "name": "流言四起",
                    "description": "关于某个神秘事件的流言开始传播",
                    "duration": 0,
                    "crisis_change": 0,
                    "narrative": "人们在角落里窃窃私语，似乎在讨论什么秘密..."
                }
            ],
            WorldEventCategory.MYSTICAL: [
                {
                    "name": "魔法波动",
                    "description": "空气中感受到了不寻常的魔法波动",
                    "duration": 60,
                    "crisis_change": 1,
                    "narrative": "空气中弥漫着一种奇怪的能量，让人不安..."
                },
                {
                    "name": "异象出现",
                    "description": "天空中出现了奇怪的异象",
                    "duration": 0,
                    "crisis_change": 1,
                    "narrative": "天空中的云彩呈现出诡异的形状，似乎在预示着什么..."
                }
            ],
            WorldEventCategory.CRISIS: [
                {
                    "name": "危机加剧",
                    "description": "主线危机有了新的发展",
                    "duration": 0,
                    "crisis_change": 2,
                    "narrative": "远方传来的消息令人担忧，情况正在恶化..."
                },
                {
                    "name": "转机出现",
                    "description": "在危机中看到了一丝希望",
                    "duration": 0,
                    "crisis_change": -1,
                    "narrative": "在黑暗中，似乎有了一线曙光..."
                }
            ]
        }

    def _apply_world_event(self, event: WorldEvent) -> None:
        """应用世界事件的影响"""
        # 更新危机等级
        if event.crisis_change != 0:
            new_level = self.world_state.crisis_level.value + event.crisis_change
            new_level = max(CrisisLevel.CALM.value, min(CrisisLevel.EMERGENCY.value, new_level))
            self.world_state.set_crisis_level(CrisisLevel(new_level))

        # 更新区域状态
        for region_id in event.affected_regions:
            region = self.world_state.get_region_state(region_id)
            if region:
                # 事件影响区域危险等级
                if event.crisis_change > 0:
                    region.danger_level = min(5, region.danger_level + 1)
                elif event.crisis_change < 0:
                    region.danger_level = max(1, region.danger_level - 1)

        # 更新世界状态变量
        for key, value in event.world_state_changes.items():
            self.world_state.set_variable(key, value)

        # 触发事件系统事件
        self.event_system.emit(
            EventType.WORLD_EVENT,
            "world_simulator",
            list(event.affected_regions)[0] if event.affected_regions else "unknown",
            data={
                "event_id": event.event_id,
                "category": event.category.value,
                "name": event.name,
                "description": event.description,
                "crisis_change": event.crisis_change,
                "narrative": event.narrative
            },
            tags=["world_event", "simulation", event.category.value],
            priority=EventPriority.HIGH
        )

    # =========================================================================
    # ⚙️ 内部方法
    # =========================================================================

    def _simulate_weather_change(self) -> None:
        """模拟天气变化"""
        for region_id, region in self.world_state.regions.items():
            # 小概率改变天气
            if random.random() < 0.1:
                weather_options = list(WeatherType)

                # 根据危机等级调整恶劣天气概率
                if self.world_state.crisis_level.value >= CrisisLevel.HIGH.value:
                    # 高危机时更可能出现诡异天气
                    weather_weights = [10, 15, 20, 15, 5, 10, 25]
                else:
                    weather_weights = [30, 25, 15, 5, 5, 10, 10]

                new_weather = random.choices(weather_options, weights=weather_weights, k=1)[0]
                self.world_state.set_region_weather(region_id, new_weather)

    def _adjust_crisis_level(self) -> None:
        """动态调整危机等级"""
        current_level = self.world_state.crisis_level

        # 危机自然衰减（低级别时更容易）
        if current_level.value > CrisisLevel.CALM.value:
            decay_chance = self.config.crisis_natural_decay * (
                CrisisLevel.EMERGENCY.value - current_level.value + 1
            )
            if random.random() < decay_chance:
                new_level = CrisisLevel(current_level.value - 1)
                self.world_state.set_crisis_level(new_level)

        # 危机升级（小概率）
        if current_level.value < CrisisLevel.EMERGENCY.value:
            if random.random() < self.config.crisis_escalation_chance:
                new_level = CrisisLevel(current_level.value + 1)
                self.world_state.set_crisis_level(new_level)

    def _cleanup_history(self) -> None:
        """清理过期记录"""
        max_history = 50

        if len(self._recent_activities) > max_history:
            self._recent_activities = self._recent_activities[-max_history:]

        if len(self._recent_world_events) > max_history:
            self._recent_world_events = self._recent_world_events[-max_history:]

    def _setup_event_handlers(self) -> None:
        """设置事件处理器"""
        # 可以在这里添加对特定事件的响应
        pass

    # =========================================================================
    # 🔗 RuntimeEngine 集成钩子
    # =========================================================================

    def on_player_idle(self, idle_minutes: int) -> List[WorldEvent]:
        """
        玩家空闲时的回调

        当玩家长时间不活跃时，可以加速模拟

        Args:
            idle_minutes: 玩家空闲的分钟数

        Returns:
            List[WorldEvent]: 空闲期间发生的事件
        """
        self._simulation_phase = SimulationPhase.QUIET

        # 空闲时可以加速模拟
        events = []

        # 每 30 分钟模拟一次，最多模拟 24 小时
        max_sim = min(idle_minutes, 24 * 60)
        for _ in range(max_sim // 30):
            tick_events = self.simulate_tick(30)
            events.extend(tick_events)

        return events

    def on_player_return(self) -> str:
        """
        玩家返回时的回调

        返回玩家离开期间发生的摘要

        Returns:
            str: 叙事性的摘要描述
        """
        self._simulation_phase = SimulationPhase.ACTIVE

        narrative = self.get_recent_narrative()

        # 添加时间描述
        time_desc = f"\n⏰ 时间已经流逝，现在是 {self.world_state.get_time_display()}"
        crisis_desc = f"\n⚠️ 当前危机等级: {self.world_state.crisis_level.name}"

        return narrative + time_desc + crisis_desc

    def on_player_action(self, action: str, location: str) -> None:
        """玩家行动时的回调"""
        self._simulation_phase = SimulationPhase.ACTIVE
        self._last_sim_time = time.time()

        # 玩家行动可能影响危机等级
        if "investigate" in action.lower() or "quest" in action.lower():
            # 积极行动可能降低危机
            pass
