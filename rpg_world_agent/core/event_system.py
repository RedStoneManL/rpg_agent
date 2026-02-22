"""
Event System - 追踪游戏进度和剧情点

这个系统允许你定义和触发游戏事件，这些事件可以：
1. 记录玩家的关键行动和选择
2. 触发世界状态的改变
3. 用于后续的上下文感知加载
"""

import json
from typing import Any, Callable, Dict, List, Optional, TypedDict
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from rpg_world_agent.data.db_client import DBClient
from rpg_world_agent.config.settings import AGENT_CONFIG


class EventType(Enum):
    """事件类型枚举"""
    # 探索相关
    DISCOVERY = "discovery"           # 发现新地点
    EXPLORATION_COMPLETE = "exploration_complete"  # 完成区域探索
    HIDDEN_REVEALED = "hidden_revealed"  # 隐藏内容被揭示

    # 交互相关
    NPC_MEET = "npc_meet"           # 遇到新NPC
    NPC_CONVERSATION = "npc_conversation"  # 与NPC对话
    RELATIONSHIP_CHANGE = "relationship_change"  # 关系改变
    ALLIANCE_FORMED = "alliance_formed"  # 结盟

    # 行动相关
    COMBAT_START = "combat_start"     # 战斗开始
    COMBAT_END = "combat_end"        # 战斗结束
    QUEST_ACCEPTED = "quest_accepted"  # 接受任务
    QUEST_COMPLETED = "quest_completed"  # 完成任务
    QUEST_FAILED = "quest_failed"     # 任务失败
    ITEM_ACQUIRED = "item_acquired"  # 获得物品
    ITEM_USED = "item_used"          # 使用物品

    # 世界相关
    WORLD_EVENT = "world_event"       # 世界级事件
    CRISIS_TRIGGERED = "crisis_triggered"  # 危机触发
    TIME_PASS = "time_pass"          # 时间流逝

    # 自定义
    CUSTOM = "custom"                # 自定义事件


class EventPriority(Enum):
    """事件优先级，影响事件排序和处理顺序"""
    CRITICAL = 0    # 关键事件，必须处理
    HIGH = 1        # 高优先级
    MEDIUM = 2      # 中优先级
    LOW = 3         # 低优先级


@dataclass
class EventData:
    """事件数据结构"""
    event_type: EventType
    event_id: str
    timestamp: float
    player_id: str
    session_id: str
    location: str
    priority: EventPriority = EventPriority.MEDIUM

    # 事件的具体数据
    data: Dict[str, Any] = field(default_factory=dict)

    # 事件的标签，用于分类和查询
    tags: List[str] = field(default_factory=list)

    # 事件是否已处理
    processed: bool = False

    # 相关事件ID（用于事件链）
    related_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "player_id": self.player_id,
            "session_id": self.session_id,
            "location": self.location,
            "priority": self.priority.value,
            "data": self.data,
            "tags": self.tags,
            "processed": self.processed,
            "related_events": self.related_events
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventData':
        """从字典反序列化"""
        return cls(
            event_type=EventType(data["event_type"]),
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            player_id=data["player_id"],
            session_id=data["session_id"],
            location=data["location"],
            priority=EventPriority(data["priority"]),
            data=data.get("data", {}),
            tags=data.get("tags", []),
            processed=data.get("processed", False),
            related_events=data.get("related_events", [])
        )


# 事件处理器类型
EventHandler = Callable[[EventData], None]
EventCondition = Callable[[EventData, Dict[str, Any]], bool]


class EventListener:
    """事件监听器，可以监听特定类型的事件"""

    def __init__(
        self,
        event_types: List[EventType],
        handler: EventHandler,
        condition: Optional[EventCondition] = None,
        priority: int = 0
    ):
        self.event_types = event_types
        self.handler = handler
        self.condition = condition
        self.priority = priority  # 越高越先执行

    def can_handle(self, event: EventData, context: Dict[str, Any]) -> bool:
        """检查是否可以处理此事件"""
        if event.event_type not in self.event_types:
            return False
        if self.condition and not self.condition(event, context):
            return False
        return True

    def handle(self, event: EventData) -> None:
        """处理事件"""
        self.handler(event)


class EventSystem:
    """
    事件系统核心类

    功能：
    1. 发布事件
    2. 注册/注销监听器
    3. 事件持久化（Redis）
    4. 事件查询和过滤
    5. 事件链追踪
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis = DBClient.get_redis()
        self.ttl = AGENT_CONFIG["redis"]["ttl"]

        # 监听器列表
        self._listeners: List[EventListener] = []

        # Redis Key 前缀
        self.key_events = f"rpg:events:{session_id}"
        self.key_event_index = f"rpg:events:index:{session_id}"
        self.key_tags = f"rpg:events:tags:{session_id}"

    def _get_event_key(self, event_id: str) -> str:
        return f"{self.key_events}:{event_id}"

    # =========================================================================
    # 📢 事件发布
    # =========================================================================

    def emit(
        self,
        event_type: EventType,
        player_id: str,
        location: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        priority: EventPriority = EventPriority.MEDIUM,
        related_events: Optional[List[str]] = None
    ) -> EventData:
        """
        发布一个新事件

        Args:
            event_type: 事件类型
            player_id: 玩家ID
            location: 事件发生地点
            data: 事件的具体数据
            tags: 事件标签
            priority: 事件优先级
            related_events: 相关事件ID列表

        Returns:
            EventData: 创建的事件对象
        """
        import time
        import uuid

        event = EventData(
            event_type=event_type,
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            player_id=player_id,
            session_id=self.session_id,
            location=location,
            data=data or {},
            tags=tags or [],
            priority=priority,
            related_events=related_events or []
        )

        # 持久化到Redis
        self._persist_event(event)

        # 调用监听器
        self._notify_listeners(event)

        return event

    def _persist_event(self, event: EventData) -> None:
        """将事件持久化到Redis"""
        # 存储事件详情
        event_key = self._get_event_key(event.event_id)
        self.redis.setex(
            event_key,
            self.ttl,
            json.dumps(event.to_dict(), ensure_ascii=False)
        )

        # 添加到时间索引
        self.redis.zadd(self.key_event_index, {event.event_id: event.timestamp})

        # 更新标签索引
        for tag in event.tags:
            self.redis.sadd(f"{self.key_tags}:{tag}", event.event_id)

    # =========================================================================
    # 👂 监听器管理
    # =========================================================================

    def register_listener(
        self,
        listener: EventListener
    ) -> None:
        """
        注册事件监听器

        Args:
            listener: 事件监听器对象
        """
        self._listeners.append(listener)
        # 按优先级排序
        self._listeners.sort(key=lambda x: x.priority, reverse=True)

    def register_handler(
        self,
        event_types: List[EventType],
        handler: EventHandler,
        condition: Optional[EventCondition] = None,
        priority: int = 0
    ) -> EventListener:
        """
        便捷方法：注册事件处理器

        Args:
            event_types: 要监听的事件类型列表
            handler: 处理函数
            condition: 额外的条件检查函数
            priority: 优先级

        Returns:
            EventListener: 创建的监听器对象
        """
        listener = EventListener(event_types, handler, condition, priority)
        self.register_listener(listener)
        return listener

    def _notify_listeners(self, event: EventData) -> None:
        """通知所有相关监听器"""
        context = {"session_id": self.session_id}
        for listener in self._listeners:
            if listener.can_handle(event, context):
                try:
                    listener.handle(event)
                    event.processed = True
                    # 更新处理状态
                    self._update_event_processed_status(event)
                except Exception as e:
                    print(f"⚠️ Event handler error: {e}")

    def _update_event_processed_status(self, event: EventData) -> None:
        """更新事件处理状态"""
        event_key = self._get_event_key(event.event_id)
        event_data = json.loads(self.redis.get(event_key) or "{}")
        event_data["processed"] = True
        self.redis.setex(
            event_key,
            self.ttl,
            json.dumps(event_data, ensure_ascii=False)
        )

    # =========================================================================
    # 🔍 事件查询
    # =========================================================================

    def get_event(self, event_id: str) -> Optional[EventData]:
        """获取单个事件"""
        event_key = self._get_event_key(event_id)
        data = self.redis.get(event_key)
        if data:
            return EventData.from_dict(json.loads(data))
        return None

    def get_events_by_type(
        self,
        event_type: EventType,
        limit: int = 100
    ) -> List[EventData]:
        """按类型获取事件"""
        events = self.get_all_events(limit=limit)
        return [e for e in events if e.event_type == event_type]

    def get_events_by_tag(
        self,
        tag: str,
        limit: int = 100
    ) -> List[EventData]:
        """按标签获取事件"""
        tag_key = f"{self.key_tags}:{tag}"
        event_ids = self.redis.smembers(tag_key)
        events = []
        for event_id in list(event_ids)[:limit]:
            event = self.get_event(event_id)
            if event:
                events.append(event)
        return events

    def get_events_by_location(
        self,
        location: str,
        limit: int = 100
    ) -> List[EventData]:
        """按地点获取事件"""
        events = self.get_all_events(limit=limit)
        return [e for e in events if e.location == location]

    def get_events_in_range(
        self,
        start_time: float,
        end_time: float,
        limit: int = 100
    ) -> List[EventData]:
        """获取时间范围内的事件"""
        # 使用有序集合获取时间范围内的事件ID
        event_ids = self.redis.zrevrangebyscore(
            self.key_event_index,
            end_time,
            start_time,
            start=0, num=limit
        )
        events = []
        for event_id in event_ids:
            event = self.get_event(event_id)
            if event:
                events.append(event)
        return events

    def get_all_events(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[EventData]:
        """获取所有事件（按时间倒序）"""
        event_ids = self.redis.zrevrange(
            self.key_event_index,
            start=offset,
            end=offset + limit - 1
        )
        events = []
        for event_id in event_ids:
            event = self.get_event(event_id)
            if event:
                events.append(event)
        return events

    def get_related_events(
        self,
        event_id: str,
        depth: int = 1
    ) -> List[EventData]:
        """
        获取相关事件（事件链）

        Args:
            event_id: 起始事件ID
            depth: 追踪深度

        Returns:
            List[EventData]: 相关事件列表
        """
        all_events = self.get_all_events(limit=1000)
        event_map = {e.event_id: e for e in all_events}

        result = []
        visited = {event_id}
        queue = [event_id]

        for _ in range(depth):
            if not queue:
                break
            current = queue.pop(0)
            event = event_map.get(current)
            if event:
                for rel_id in event.related_events:
                    if rel_id not in visited:
                        visited.add(rel_id)
                        queue.append(rel_id)
                        rel_event = event_map.get(rel_id)
                        if rel_event:
                            result.append(rel_event)

        return result

    # =========================================================================
    # 📊 事件统计和摘要
    # =========================================================================

    def get_event_summary(self) -> Dict[str, Any]:
        """获取事件统计摘要"""
        all_events = self.get_all_events(limit=1000)

        # 按类型统计
        type_counts = {}
        for event in all_events:
            type_name = event.event_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 探索相关事件

        # 按地点统计
        location_counts = {}
        for event in all_events:
            loc = event.location
            location_counts[loc] = location_counts.get(loc, 0) + 1

        # 按标签统计
        tag_counts = {}
        for event in all_events:
            for tag in event.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_events": len(all_events),
            "event_types": type_counts,
            "locations": location_counts,
            "tags": tag_counts,
            "last_event_time": all_events[0].timestamp if all_events else None
        }

    def get_recent_context(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取最近的事件上下文，用于LLM推理

        Returns:
            格式化的事件列表，便于注入到prompt中
        """
        events = self.get_all_events(limit=limit)
        context = []

        for event in events:
            context.append({
                "type": event.event_type.value,
                "location": event.location,
                "data": event.data,
                "timestamp": datetime.fromtimestamp(event.timestamp).isoformat()
            })

        return context

    # =========================================================================
    # 🗑️ 清理
    # =========================================================================

    def clear_all_events(self) -> None:
        """清除所有事件数据"""
        events = self.get_all_events(limit=1000)
        for event in events:
            self.redis.delete(self._get_event_key(event.event_id))

        # 清除索引
        self.redis.delete(self.key_event_index)

        # 清除标签索引
        keys = self.redis.keys(f"{self.key_tags}:*")
        if keys:
            self.redis.delete(*keys)

    def get_context_for_narration(self) -> str:
        """
        获取用于叙事的上下文字符串

        将事件历史格式化为自然的叙事文本，供LLM使用
        """
        events = self.get_all_events(limit=15)
        if not events:
            return "（暂无重大事件记录）"

        lines = []
        lines.append("【最近发生的重要事件】")
        lines.append("=" * 50)

        for event in events:
            time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
            type_str = event.event_type.value.replace("_", " ").title()
            location_str = event.location

            # 构建事件描述
            data_desc = []
            if event.data.get("description"):
                data_desc.append(event.data["description"])
            if event.data.get("target"):
                data_desc.append(f'目标: {event.data["target"]}')
            if event.data.get("result"):
                data_desc.append(f'结果: {event.data["result"]}')

            desc = " | ".join(data_desc) if data_desc else ""

            lines.append(f"[{time_str}] {type_str} @ {location_str}")
            if desc:
                lines.append(f"  └─ {desc}")

        return "\n".join(lines)