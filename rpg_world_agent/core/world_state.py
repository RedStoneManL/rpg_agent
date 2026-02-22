"""
World State Manager - 世界状态管理器

这个系统管理整个游戏世界的状态，包括：
1. 全局世界状态（时间、天气、危机等级等）
2. 区域状态（每个区域的特殊状态、NPC行动等）
3. NPC状态（位置、关系、任务等）
4. 任务状态（任务进度、完成条件等）
5. 状态查询和更新接口
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import uuid

from rpg_world_agent.data.db_client import DBClient
from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.core.event_system import EventSystem, EventData, EventType


class WeatherType(Enum):
    """天气类型"""
    CLEAR = "clear"           # 晴朗
    CLOUDY = "cloudy"       # 多云
    RAIN = "rain"            # 下雨
    STORM = "storm"          # 暴风雨
    SNOW = "snow"            # 下雪
    FOG = "fog"             # 大雾
    HAUNTED = "haunted"     # 诡异的天气（通常伴随危机）


class CrisisLevel(Enum):
    """危机等级"""
    CALM = 0          # 平静
    LOW = 1           # 低危机
    MEDIUM = 2        # 中等危机
    HIGH = 3          # 高危机
    CRITICAL = 4       # 严重危机
    EMERGENCY = 5      # 紧急


class WorldTime:
    """世界时间系统"""
    def __init__(self, days: int = 0, hours: int = 8, minutes: int = 0):
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self._total_minutes = days * 24 * 60 + hours * 60 + minutes

    @property
    def total_minutes(self) -> int:
        return self._total_minutes

    def advance(self, minutes: int) -> None:
        """推进时间"""
        self._total_minutes += minutes
        self._update_from_total()

    def _update_from_total(self) -> None:
        """从总分钟数更新天、时、分"""
        self.days = self._total_minutes // (24 * 60)
        remaining = self._total_minutes % (24 * 60)
        self.hours = remaining // 60
        self.minutes = remaining % 60

    def get_period_of_day(self) -> str:
        """获取一天中的时段"""
        if 5 <= self.hours < 8:
            return "黎明"
        elif 8 <= self.hours < 12:
            return "早晨"
        elif 12 <= self.hours < 14:
            return "正午"
        elif 14 <= self.hours < 17:
            return "下午"
        elif 17 <= self.hours < 20:
            return "傍晚"
        elif 20 <= self.hours < 23:
            return "夜晚"
        elif 23 <= self.hours or self.hours < 5:
            return "深夜"

    @property
    def is_day(self) -> bool:
        return 6 <= self.hours < 20

    @property
    def is_night(self) -> bool:
        return not self.is_day

    def to_dict(self) -> Dict[str, Any]:
        return {
            "days": self.days,
            "hours": self.hours,
            "minutes": self.minutes,
            "total_minutes": self._total_minutes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldTime':
        return cls(
            days=data.get("days", 0),
            hours=data.get("hours", 8),
            minutes=data.get("minutes", 0)
        )

    def __str__(self) -> str:
        return f"第{self.days}天 {self.hours:02d}:{self.minutes:02d} ({self.get_period_of_day()})"


@dataclass
class RegionState:
    """区域状态"""
    region_id: str
    name: str

    # 区域特有状态
    weather: WeatherType = WeatherType.CLEAR
    danger_level: int = 1  # 1-5
    npc_count: int = 0
    special_status: Dict[str, Any] = field(default_factory=dict)  # 自定义状态

    # 探索状态
    discovered: bool = False
    fully_explored: bool = False
    discovery_points: Set[str] = field(default_factory=set)

    # 时间戳
    last_updated: float = field(default_factory=lambda: __import__('time').time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "name": self.name,
            "weather": self.weather.value,
            "danger_level": self.danger_level,
            "npc_count": self.npc_count,
            "special_status": self.special_status,
            "discovered": self.discovered,
            "fully_explored": self.fully_explored,
            "discovery_points": list(self.discovery_points),
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionState':
        return cls(
            region_id=data["region_id"],
            name=data["name"],
            weather=WeatherType(data.get("weather", "clear")),
            danger_level=data.get("danger_level", 1),
            npc_count=data.get("npc_count", 0),
            special_status=data.get("special_status", {}),
            discovered=data.get("discovered", False),
            fully_explored=data.get("fully_explored", False),
            discovery_points=set(data.get("discovery_points", [])),
            last_updated=data.get("last_updated", 0)
        )


@dataclass
class NPCState:
    """NPC状态"""
    npc_id: str
    name: str

    # 位置
    current_location: str
    home_location: str

    # 关系
    relationships: Dict[str, int] = field(default_factory=dict)  # npc_id: relationship_value (-100 to 100)

    # 状态
    alive: bool = True
    health: int = 100
    mood: str = "neutral"  # happy, angry, sad, neutral, etc.

    # 可用性
    available: bool = True
    current_action: str = "idle"

    # 任务相关
    active_quests: List[str] = field(default_factory=list)  # quest_id列表
    dialogue_state: Dict[str, Any] = field(default_factory=dict)

    # 时间戳
    last_interacted: float = field(default_factory=lambda: __import__('time').time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "current_location": self.current_location,
            "home_location": self.home_location,
            "relationships": self.relationships,
            "alive": self.alive,
            "health": self.health,
            "mood": self.mood,
            "available": self.available,
            "current_action": self.current_action,
            "active_quests": self.active_quests,
            "dialogue_state": self.dialogue_state,
            "last_interacted": self.last_interacted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPCState':
        return cls(
            npc_id=data["npc_id"],
            name=data["name"],
            current_location=data["current_location"],
            home_location=data["home_location"],
            relationships=data.get("relationships", {}),
            alive=data.get("alive", True),
            health=data.get("health", 100),
            mood=data.get("mood", "neutral"),
            available=data.get("available", True),
            current_action=data.get("current_action", "idle"),
            active_quests=data.get("active_quests", []),
            dialogue_state=data.get("dialogue_state", {}),
            last_interacted=data.get("last_interacted", 0)
        )


@dataclass
class QuestState:
    """任务状态"""
    quest_id: str
    name: str
    description: str

    # 任务阶段
    stage: int = 0
    max_stage: int = 1
    stage_descriptions: List[str] = field(default_factory=list)

    # 任务状态
    status: str = "available"  # available, active, completed, failed, abandoned
    progress: int = 0  # 0-100
    max_progress: int = 100

    # 奖励
    rewards: Dict[str, Any] = field(default_factory=dict)

    # 完成条件
    objectives: Dict[str, bool] = field(default_factory=dict)  # {"objective_id": completed}
    completed_objectives: Set[str] = field(default_factory=set)

    # 时间
    accepted_time: Optional[float] = None
    completed_time: Optional[float] = None
    deadline: Optional[float] = None

    # 相关实体
    giver_npc_id: Optional[str] = None
    target_location: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "name": self.name,
            "description": self.description,
            "stage": self.stage,
            "max_stage": self.max_stage,
            "stage_descriptions": self.stage_descriptions,
            "status": self.status,
            "progress": self.progress,
            "max_progress": self.max_progress,
            "rewards": self.rewards,
            "objectives": self.objectives,
            "completed_objectives": list(self.completed_objectives),
            "accepted_time": self.accepted_time,
            "completed_time": self.completed_time,
            "deadline": self.deadline,
            "giver_npc_id": self.giver_npc_id,
            "target_location": self.target_location
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestState':
        return cls(
            quest_id=data["quest_id"],
            name=data["name"],
            description=data["description"],
            stage=data.get("stage", 0),
            max_stage=data.get("max_stage", 1),
            stage_descriptions=data.get("stage_descriptions", []),
            status=data.get("status", "available"),
            progress=data.get("progress", 0),
            max_progress=data.get("max_progress", 100),
            rewards=data.get("rewards", {}),
            objectives=data.get("objectives", []),
            completed_objectives=set(data.get("completed_objectives", [])),
            accepted_time=data.get("accepted_time"),
            completed_time=data.get("completed_time"),
            deadline=data.get("deadline"),
            giver_npc_id=data.get("giver_npc_id"),
            target_location=data.get("target_location")
        )


class WorldStateManager:
    """
    世界状态管理器

    管理游戏世界的全局状态、区域状态、NPC状态和任务状态
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis = DBClient.get_redis()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]

        # 全局状态
        self.world_time = WorldTime()
        self.crisis_level = CrisisLevel.CALM
        self.global_flags: Dict[str, bool] = {}
        self.global_variables: Dict[str, Any] = {}

        # 区域状态
        self.regions: Dict[str, RegionState] = {}

        # NPC状态
        self.npcs: Dict[str, NPCState] = {}

        # 任务状态
        self.quests: Dict[str, QuestState] = {}

        # Redis Key 前缀
        self.key_root = f"rpg:world_state:{session_id}"
        self.key_regions = f"{self.key_root}:regions"
        self.key_npcs = f"{self.key_root}:npcs"
        self.key_quests = f"{self.key_root}:quests"
        self.key_global = f"{self.key_root}:global"

        # 状态变更监听器
        self._state_change_listeners: List[Callable] = []

    # =========================================================================
    # ⏰ 时间系统
    # =========================================================================

    def advance_time(self, minutes: int) -> None:
        """推进世界时间"""
        self.world_time.advance(minutes)
        self._notify_state_change("time", self.world_time)

    def get_time_display(self) -> str:
        """获取时间显示字符串"""
        return str(self.world_time)

    def get_period_of_day(self) -> str:
        """获取当前时段"""
        return self.world_time.get_period_of_day()

    def is_day(self) -> bool:
        """是否是白天"""
        return self.world_time.is_day

    def is_night(self) -> bool:
        """是否是夜晚"""
        return self.world_time.is_night

    # =========================================================================
    # 🌡️ 全局状态
    # =========================================================================

    def set_crisis_level(self, level: CrisisLevel) -> None:
        """设置危机等级"""
        if self.crisis_level != level:
            self.crisis_level = level
            self._notify_state_change("crisis_level", level)

    def get_crisis_level(self) -> CrisisLevel:
        """获取危机等级"""
        return self.crisis_level

    def set_flag(self, flag: str, value: bool = True) -> None:
        """设置全局标志"""
        self.global_flags[flag] = value

    def has_flag(self, flag: str) -> bool:
        """检查是否设置了标志"""
        return self.global_flags.get(flag, False)

    def set_variable(self, key: str, value: Any) -> None:
        """设置全局变量"""
        self.global_variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取全局变量"""
        return self.global_variables.get(key, default)

    # =========================================================================
    # 🗺️ 区域状态管理
    # =========================================================================

    def register_region(self, region_id: str, name: str) -> RegionState:
        """注册一个新区域"""
        region = RegionState(region_id=region_id, name=name)
        self.regions[region_id] = region
        return region

    def get_region_state(self, region_id: str) -> Optional[RegionState]:
        """获取区域状态"""
        return self.regions.get(region_id)

    def set_region_weather(self, region_id: str, weather: WeatherType) -> None:
        """设置区域天气"""
        region = self.regions.get(region_id)
        if region:
            region.weather = weather

    def discover_region(self, region_id: str) -> None:
        """发现一个区域"""
        region = self.regions.get(region_id)
        if region:
            region.discovered = True

    def add_discovery_point(self, region_id: str, point_id: str) -> None:
        """添加探索点"""
        region = self.regions.get(region_id)
        if region:
            region.discovery_points.add(point_id)

    def set_region_danger_level(self, region_id: str, level: int) -> None:
        """设置区域危险等级（1-5）"""
        region = self.regions.get(region_id)
        if region:
            region.danger_level = max(1, min(5, level))

    # =========================================================================
    # 👥 NPC状态管理
    # =========================================================================

    def register_npc(self, npc_id: str, name: str, location: str) -> NPCState:
        """注册一个新NPC"""
        npc = NPCState(
            npc_id=npc_id,
            name=name,
            current_location=location,
            home_location=location
        )
        self.npcs[npc_id] = npc
        return npc

    def get_npc_state(self, npc_id: str) -> Optional[NPCState]:
        """获取NPC状态"""
        return self.npcs.get(npc_id)

    def move_npc(self, npc_id: str, new_location: str) -> bool:
        """移动NPC到新位置"""
        npc = self.npcs.get(npc_id)
        if npc and npc.alive:
            npc.current_location = new_location
            return True
        return False

    def set_npc_mood(self, npc_id: str, mood: str) -> None:
        """设置NPC心情"""
        npc = self.npcs.get(npc_id)
        if npc:
            npc.mood = mood

    def set_npc_relationship(self, npc_id: str, target_npc_id: str, value: int) -> None:
        """
        设置NPC与另一个NPC的关系值

        Args:
            npc_id: 主NPC的ID
            target_npc_id: 目标NPC的ID
            value: 关系值 (-100 敌对 到 100 亲密，0为中性)
        """
        npc = self.npcs.get(npc_id)
        if npc:
            npc.relationships[target_npc_id] = max(-100, min(100, value))

    def get_npc_relationship(self, npc_id: str, target_npc_id: str) -> int:
        """获取NPC关系值"""
        npc = self.npcs.get(npc_id)
        if npc:
            return npc.relationships.get(target_npc_id, 0)
        return 0

    def set_npc_available(self, npc_id: str, available: bool) -> None:
        """设置NPC是否可用（能否交互）"""
        npc = self.npcs.get(npc_id)
        if npc:
            npc.available = available

    def kill_npc(self, npc_id: str) -> None:
        """Kill an NPC"""
        npc = self.npcs.get(npc_id)
        if npc:
            npc.alive = False
            npc.health = 0
            npc.available = False

    # =========================================================================
    # 📋 任务状态管理
    # =========================================================================

    def register_quest(
        self,
        quest_id: str,
        name: str,
        description: str
    ) -> QuestState:
        """注册一个新任务"""
        quest = QuestState(quest_id=quest_id, name=name, description=description)
        self.quests[quest_id] = quest
        return quest

    def get_quest_state(self, quest_id: str) -> Optional[QuestState]:
        """获取任务状态"""
        return self.quests.get(quest_id)

    def accept_quest(self, quest_id: str) -> bool:
        """接受任务"""
        quest = self.quests.get(quest_id)
        if quest and quest.status == "available":
            import time
            quest.status = "active"
            quest.accepted_time = time.time()
            return True
        return False

    def complete_quest(self, quest_id: str) -> bool:
        """完成任务"""
        quest = self.quests.get(quest_id)
        if quest and quest.status == "active":
            import time
            quest.status = "completed"
            quest.completed_time = time.time()
            return True
        return False

    def fail_quest(self, quest_id: str) -> bool:
        """任务失败"""
        quest = self.quests.get(quest_id)
        if quest and quest.status == "active":
            quest.status = "failed"
            return True
        return False

    def update_quest_progress(self, quest_id: str, progress: int) -> None:
        """更新任务进度"""
        quest = self.quests.get(quest_id)
        if quest:
            quest.progress = max(0, min(quest.max_progress, progress))

    def complete_objective(self, quest_id: str, objective: str) -> None:
        """完成任务目标"""
        quest = self.quests.get(quest_id)
        if quest and objective in quest.objectives:
            quest.completed_objectives.add(objective)

    def get_available_quests_at_location(self, location: str) -> List[QuestState]:
        """获取指定位置可接受的任务"""
        result = []
        for quest in self.quests.values():
            if quest.status == "available" and quest.giver_npc_id:
                # 检查giver是否在当前位置
                npc = self.npcs.get(quest.giver_npc_id)
                if npc and npc.current_location == location:
                    result.append(quest)
        return result

    def get_active_quests(self) -> List[QuestState]:
        """获取所有活跃的任务"""
        return [q for q in self.quests.values() if q.status == "active"]

    # =========================================================================
    # 📊 状态查询和摘要
    # =========================================================================

    def get_world_summary(self) -> Dict[str, Any]:
        """获取世界状态摘要"""
        return {
            "time": str(self.world_time),
            "crisis_level": self.crisis_level.value,
            "crisis_level_name": self.crisis_level.name,
            "regions_count": len(self.regions),
            "discovered_regions": sum(1 for r in self.regions.values() if r.discovered),
            "npcs_count": len(self.npcs),
            "alive_npcs": sum(1 for n in self.npcs.values() if n.alive),
            "quests_count": len(self.quests),
            "active_quests": len(self.get_active_quests()),
            "global_flags": list(self.global_flags.keys())
        }

    def get_location_summary(self, location: str) -> Dict[str, Any]:
        """获取指定位置的状态摘要"""
        region = self.regions.get(location)
        if not region:
            return {}

        # 获取在当前位置的NPC
        npcs_here = [
            npc for npc in self.npcs.values()
            if npc.current_location == location and npc.alive
        ]

        return {
            "location": region.name,
            "weather": region.weather.value,
            "danger_level": region.danger_level,
            "discovered": region.discovered,
            "npcs_present": [npc.name for npc in npcs_here],
            "available_quests": len(self.get_available_quests_at_location(location))
        }

    def get_context_for_llm(self) -> str:
        """获取用于LLM的世界状态上下文"""
        lines = []

        # 时间和危机
        lines.append("【世界状态】")
        lines.append(f"时间: {self.get_time_display()}")
        lines.append(f"危机等级: {self.crisis_level.name} ({self.crisis_level.value})")
        lines.append(f"时段: {self.get_period_of_day()}")
        if self.is_night():
            lines.append(f"现在是夜晚，能见度较低")
        lines.append("")

        # 危机描述
        crisis_descriptions = {
            CrisisLevel.CALM: "世界平静，没有异常迹象",
            CrisisLevel.LOW: "有些不寻常的传闻，但基本安全",
            CrisisLevel.MEDIUM: "危机正在酝酿，各地出现异常",
            CrisisLevel.HIGH: "危机已经显现，危险在增加",
            CrisisLevel.CRITICAL: "世界处于崩溃边缘，非常危险",
            CrisisLevel.EMERGENCY: "紧急情况！需要立即行动"
        }
        lines.append(f"局势: {crisis_descriptions.get(self.crisis_level, '未知')}")
        lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # 💾 持久化
    # =========================================================================

    def save(self) -> None:
        """保存世界状态到Redis"""
        # 保存全局状态
        global_data = {
            "time": self.world_time.to_dict(),
            "crisis_level": self.crisis_level.value,
            "flags": self.global_flags,
            "variables": self.global_variables
        }
        self.redis.setex(
            self.key_global,
            self.ttl,
            json.dumps(global_data, ensure_ascii=False)
        )

        # 保存区域状态
        for region_id, region in self.regions.items():
            key = f"{self.key_regions}:{region_id}"
            self.redis.setex(key, self.ttl, json.dumps(region.to_dict(), ensure_ascii=False))

        # 保存NPC状态
        for npc_id, npc in self.npcs.items():
            key = f"{self.key_npcs}:{npc_id}"
            self.redis.setex(key, self.ttl, json.dumps(npc.to_dict(), ensure_ascii=False))

        # 保存任务状态
        for quest_id, quest in self.quests.items():
            key = f"{self.key_quests}:{quest_id}"
            self.redis.setex(key, self.ttl, json.dumps(quest.to_dict(), ensure_ascii=False))

    def load(self) -> bool:
        """从Redis加载世界状态"""
        try:
            # 加载全局状态
            global_data = self.redis.get(self.key_global)
            if global_data:
                data = json.loads(global_data)
                self.world_time = WorldTime.from_dict(data["time"])
                self.crisis_level = CrisisLevel(data["crisis_level"])
                self.global_flags = data.get("flags", {})
                self.global_variables = data.get("variables", {})

            # 加载区域状态
            region_keys = self.redis.keys(f"{self.key_regions}:*")
            for key in region_keys:
                region_data = json.loads(self.redis.get(key) or "{}")
                region = RegionState.from_dict(region_data)
                self.regions[region.region_id] = region

            # 加载NPC状态
            npc_keys = self.redis.keys(f"{self.key_npcs}:*")
            for key in npc_keys:
                npc_data = json.loads(self.redis.get(key) or "{}")
                npc = NPCState.from_dict(npc_data)
                self.npcs[npc.npc_id] = npc

            # 加载任务状态
            quest_keys = self.redis.keys(f"{self.key_quests}:*")
            for key in quest_keys:
                quest_data = json.loads(self.redis.get(key) or "{}")
                quest = QuestState.from_dict(quest_data)
                self.quests[quest.quest_id] = quest

            return True

        except Exception as e:
            print(f"❌ 加载世界状态失败: {e}")
            return False

    def clear(self) -> None:
        """清除所有世界状态"""
        keys = self.redis.keys(f"{self.key_root}*")
        if keys:
            self.redis.delete(*keys)
        self.regions.clear()
        self.npcs.clear()
        self.quests.clear()
        self.global_flags.clear()
        self.global_variables.clear()

    # =========================================================================
    # 🔔 状态变化监听
    # =========================================================================

    def register_state_change_listener(self, listener: Callable) -> None:
        """注册状态变化监听器"""
        self._state_change_listeners.append(listener)

    def _notify_state_change(self, change_type: str, value: Any) -> None:
        """通知所有监听器状态已变化"""
        for listener in self._state_change_listeners:
            try:
                listener(change_type, value)
            except Exception as e:
                print(f"⚠️ 状态变化监听器错误: {e}")

    # =========================================================================
    # 🎭 与事件系统集成
    # =========================================================================

    def handle_event(self, event: EventData) -> None:
        """处理事件, 更新世界状态"""
        import time

        if event.event_type == EventType.DISCOVERY:
            location = event.data.get("target")
            if location:
                self.discover_region(location)

        elif event.event_type == EventType.QUEST_ACCEPTED:
            self.accept_quest(event.data.get("quest_id", ""))

        elif event.event_type == EventType.QUEST_COMPLETED:
            self.complete_quest(event.data.get("quest_id", ""))
            # 完成任务可能降低危机等级
            if self.crisis_level.value > CrisisLevel.LOW.value:
                self.set_crisis_level(
                    CrisisLevel(self.crisis_level.value - 1)
                )

        elif event.event_type == EventType.WORLD_EVENT:
            # 世界事件可能影响危机等级
            crisis_change = event.data.get("crisis_change", 0)
            new_level = CrisisLevel(
                max(CrisisLevel.CALM.value,
                    min(CrisisLevel.EMERGENCY.value,
                        self.crisis_level.value + crisis_change))
            )
            self.set_crisis_level(new_level)

        elif event.event_type == EventType.TIME_PASS:
            minutes = event.data.get("minutes", 10)
            self.advance_time(minutes)