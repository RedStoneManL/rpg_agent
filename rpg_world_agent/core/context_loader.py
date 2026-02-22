"""
Context-Aware Loader - 上下文感知加载器

这个系统根据游戏进度、玩家状态和事件历史，智能地决定应该加载或生成哪些内容。
这就像一个智能的DM（Dungeon Master），知道什么时候该引入新内容。

核心功能：
1. 根据玩家行为和位置，判断是否需要加载新内容
2. 基于事件历史，决定剧情走向
3. 动态生成符合当前情境的世界内容
4. 提供给LLM的上下文构建
"""

from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json

from rpg_world_agent.core.event_system import EventSystem, EventData, EventType
from rpg_world_agent.core.map_engine import MapTopologyEngine
from rpg_world_agent.data.llm_client import get_llm_client
from rpg_world_agent.config.settings import AGENT_CONFIG


class LoadTrigger(Enum):
    """加载触发条件类型"""
    LOCATION_BASED = "location"        # 基于位置触发
    EVENT_BASED = "event"            # 基于事件触发
    PLAYER_STATE = "player_state"     # 基于玩家状态触发
    COMBO = "combo"                 # 组合条件触发
    ALWAYS = "always"               # 总是加载
    NEVER = "never"                # 永不加载


class ContentType(Enum):
    """内容类型"""
    LOCATION = "location"     # 地点
    NPC = "npc"            # NPC
    ITEM = "item"          # 物品
    QUEST = "quest"        # 任务
    LORE = "lore"         # 背景故事
    ENCOUNTER = "encounter" # 遭遇
    CUSTOM = "custom"      # 自定义


@dataclass
class LoadCondition:
    """加载条件"""
    trigger_type: LoadTrigger

    # 位置相关
    at_location: Optional[str] = None
    in_region: Optional[str] = None
    visited: Set[str] = field(default_factory=set)

    # 事件相关
    requires_events: List[str] = field(default_factory=list)  # 必须发生的事件ID
    excludes_events: List[str] = field(default_factory=list)   # 不能发生的事件ID
    requires_event_types: List[EventType] = field(default_factory=list)

    # 玩家状态相关
    min_level: int = 1
    max_level: int = 100
    has_tags: List[str] = field(default_factory=list)
    has_items: List[str] = field(default_factory=list)
    state_conditions: Dict[str, Any] = field(default_factory=dict)  # 自定义状态条件

    # 自定义条件函数
    custom_condition: Optional[Callable[[Dict[str, Any], EventSystem], bool]] = None


@dataclass
class LoadableContent:
    """可加载的内容"""
    content_id: str          # 内容ID
    content_type: ContentType   # 内容类型
    name: str               # 内容名称
    description: str         # 描述

    # 加载条件
    condition: LoadCondition

    # 内容数据（当条件满足时使用）
    data: Dict[str, Any] = field(default_factory=dict)

    # 优先级（数字越小越优先）
    priority: int = 10

    # 是否已加载
    loaded: bool = False

    # 是否可以重复加载
    repeatable: bool = False

    # 加载后的事件
    on_load_events: List[str] = field(default_factory=list)

    # 替代或排除其他内容
    excludes: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)


@dataclass
class LoadContext:
    """加载上下文"""
    player_id: str
    current_location: str
    player_state: Dict[str, Any]
    event_system: EventSystem
    map_engine: MapTopologyEngine

    # 缓存的已访问内容
    loaded_content: Set[str] = field(default_factory=set)

    def get_recent_events(self, limit: int = 20) -> List[EventData]:
        """获取最近的事件"""
        return self.event_system.get_all_events(limit=limit)

    def get_events_by_type(self, event_type: EventType) -> List[EventData]:
        """获取指定类型的事件"""
        return self.event_system.get_events_by_type(event_type)

    def has_tag(self, tag: str) -> bool:
        """检查玩家是否有指定标签"""
        tags = self.player_state.get("tags", [])
        return tag in tags

    def has_item(self, item_id: str) -> bool:
        """检查玩家是否有指定物品"""
        inventory = self.player_state.get("inventory", {}).get("items", [])
        for item in inventory:
            if isinstance(item, dict) and item.get("item_id") == item_id:
                return True
            elif isinstance(item, str) and item == item_id:
                return True
        return False

    def get_level(self) -> int:
        """获取玩家等级"""
        return self.player_state.get("level", 1)

    def is_content_loaded(self, content_id: str) -> bool:
        """检查内容是否已加载"""
        return content_id in self.loaded_content

    def mark_content_loaded(self, content_id: str) -> None:
        """标记内容已加载"""
        self.loaded_content.add(content_id)


class ContextLoader:
    """
    上下文感知加载器

    根据当前游戏状态智能决定加载哪些内容
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._loadable_content: Dict[str, LoadableContent] = {}
        self._generator_cache: Dict[str, Any] = {}

    # =========================================================================
    # 📦 内容注册
    # =========================================================================

    def register_content(self, content: LoadableContent) -> None:
        """注册可加载的内容"""
        self._loadable_content[content.content_id] = content

    def register_multiple_content(self, contents: List[LoadableContent]) -> None:
        """批量注册内容"""
        for content in contents:
            self.register_content(content)

    def unregister_content(self, content_id: str) -> None:
        """注销内容"""
        self._loadable_content.pop(content_id, None)

    def get_content(self, content_id: str) -> Optional[LoadableContent]:
        """获取内容"""
        return self._loadable_content.get(content_id)

    def get_content_by_type(self, content_type: ContentType) -> List[LoadableContent]:
        """按类型获取内容"""
        return [
            c for c in self._loadable_content.values()
            if c.content_type == content_type
        ]

    # =========================================================================
    # 🔍 条件检查
    # =========================================================================

    def _check_condition(
        self,
        condition: LoadCondition,
        context: LoadContext
    ) -> bool:
        """
        检查加载条件是否满足

        Args:
            condition: 加载条件
            context: 加载上下文

        Returns:
            bool: 条件满足返回True
        """
        # 总是加载
        if condition.trigger_type == LoadTrigger.ALWAYS:
            return True

        # 永不加载
        if condition.trigger_type == LoadTrigger.NEVER:
            return False

        # 自定义条件函数优先
        if condition.custom_condition:
            if not condition.custom_condition(context.player_state, context.event_system):
                return False

        # 位置条件
        if condition.at_location:
            if context.current_location != condition.at_location:
                return False

        if condition.in_region:
            # 检查是否在指定区域内
            node = context.map_engine.get_node(context.current_location)
            if not node or node.get("region_id") != condition.in_region:
                return False

        # 访问历史条件
        if condition.visited:
            recent_events = context.event_system.get_events_by_type(EventType.DISCOVERY)
            visited_locations = {e.data.get("target", "") for e in recent_events}
            if not condition.visited.issubset(visited_locations):
                return False

        # 事件条件
        if condition.requires_events:
            all_events = {e.event_id for e in context.get_recent_events(100)}
            if not all(event_id in all_events for event_id in condition.requires_events):
                return False

        if condition.excludes_events:
            all_events = {e.event_id for e in context.get_recent_events(100)}
            if any(event_id in all_events for event_id in condition.excludes_events):
                return False

        if condition.requires_event_types:
            recent_events = context.get_recent_events(100)
            event_types = {e.event_type for e in recent_events}
            if not any(et in event_types for et in condition.requires_event_types):
                return False

        # 玩家状态条件
        level = context.get_level()
        if level < condition.min_level or level > condition.max_level:
            return False

        if condition.has_tags:
            if not all(context.has_tag(tag) for tag in condition.has_tags):
                return False

        if condition.has_items:
            if not all(context.has_item(item) for item in condition.has_items):
                return False

        if condition.state_conditions:
            for key, value in condition.state_conditions.items():
                if context.player_state.get(key) != value:
                    return False

        return True

    # =========================================================================
    # 📥 内容加载
    # =========================================================================

    def get_loadable_content(
        self,
        context: LoadContext,
        content_type: Optional[ContentType] = None
    ) -> List[LoadableContent]:
        """
        获取当前上下文下可加载的内容

        Args:
            context: 加载上下文
            content_type: 可选，指定内容类型

        Returns:
            List[LoadableContent]: 满足条件的内容列表（按优先级排序）
        """
        candidates = []

        for content_id, content in self._loadable_content.items():
            # 类型过滤
            if content_type and content.content_type != content_type:
                continue

            # 检查是否已加载
            if not content.repeatable and context.is_content_loaded(content_id):
                continue

            # 检查条件
            if self._check_condition(content.condition, context):
                candidates.append(content)

        # 按优先级排序
        candidates.sort(key=lambda x: x.priority)

        return candidates

    def load_content(
        self,
        content_id: str,
        context: LoadContext
    ) -> bool:
        """
        加载指定的内容

        Args:
            content_id: 内容ID
            context: 加载上下文

        Returns:
            bool: 加载成功返回True
        """
        content = self._loadable_content.get(content_id)
        if not content:
            return False

        # 检查条件
        if not self._check_condition(content.condition, context):
            return False

        # 触发加载事件
        for event_id in content.on_load_events:
            event = context.event_system.get_event(event_id)
            if event and hasattr(event, 'data'):
                # 这里可以复制事件数据并作为新事件触发
                pass

        # 标记为已加载
        context.mark_content_loaded(content_id)
        content.loaded = True

        return True

    def load_all_matching(
        self,
        context: LoadContext,
        content_type: Optional[ContentType] = None,
        limit: Optional[int] = None
    ) -> List[LoadableContent]:
        """
        加载所有匹配的内容

        Args:
            context: 加载上下文
            content_type: 可选，指定内容类型
            limit: 可选，限制加载数量

        Returns:
            List[LoadableContent]: 已加载的内容列表
        """
        candidates = self.get_loadable_content(context, content_type)

        if limit:
            candidates = candidates[:limit]

        loaded = []
        for content in candidates:
            if self.load_content(content.content_id, context):
                loaded.append(content)

        return loaded

    # =========================================================================
    # 🤖 动态内容生成
    # =========================================================================

    def generate_dynamic_content(
        self,
        user_intent: str,
        context: LoadContext
    ) -> Optional[Dict[str, Any]]:
        """
        根据用户意图动态生成内容

        这就像一个智能的DM，当玩家做某事时，动态创建相应的世界内容

        Args:
            user_intent: 用户的意图描述
            context: 加载上下文

        Returns:
            生成的内容，如果失败返回None
        """
        cache_key = f"{context.current_location}:{user_intent}"

        # 检查缓存
        if cache_key in self._generator_cache:
            return self._generator_cache[cache_key]

        # 构建生成prompt
        event_context = context.event_system.get_context_for_narration()
        location = context.map_engine.get_node(context.current_location)

        prompt = f"""
你是一个智能Dungeon Master。玩家正在进行以下行动：

玩家意图: {user_intent}
当前位置: {location.get('name', 'Unknown')} - {location.get('desc', '')}

【最近事件背景】
{event_context}

【玩家状态】
HP: {context.player_state.get('hp', 100)}/100
SAN: {context.player_state.get('sanity', 100)}/100
标签: {', '.join(context.player_state.get('tags', []))}
等级: {context.get_level()}

请根据玩家的意图和当前情境，动态生成合适的游戏内容。

返回JSON格式：
{{
    "content_type": "location|npc|item|quest|encounter",
    "name": "内容名称",
    "description": "详细描述",
    "data": {{"具体的自定义数据字段": "value"}},
    "requires_action": "是否需要玩家进一步行动",
    "suggested_response": "给玩家的建议性回应"
}}
"""

        try:
            llm = get_llm_client()
            response = llm.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            content = response.choices[0].message.content

            # 解析JSON
            import re
            clean = re.sub(r"```(?:json)?", "", content, flags=re.IGNORECASE).strip()
            start = clean.find('{')
            end = clean.rfind('}')
            if start != -1 and end != -1:
                result = json.loads(clean[start:end+1])
                self._generator_cache[cache_key] = result
                return result

        except Exception as e:
            print(f"⚠️ 动态内容生成失败: {e}")

        return None

    # =========================================================================
    # 📋 上下文构建
    # =========================================================================

    def build_llm_context(
        self,
        user_input: str,
        context: LoadContext
    ) -> str:
        """
        构建用于LLM的完整上下文

        这个上下文包括：
        1. 当前环境描述
        2. 玩家状态
        3. 最近的事件历史
        4. 可用的内容（NPC、物品等）
        5. 用户当前输入

        Args:
            user_input: 用户输入
            context: 加载上下文

        Returns:
            str: 格式化的上下文字符串
        """
        sections = []

        # 1. 当前环境
        location = context.map_engine.get_node(context.current_location)
        if location:
            sections.append("【当前环境】")
            sections.append(f"地点: {location.get('name', 'Unknown')}")
            sections.append(f"描述: {location.get('desc', '')}")
            sections.append(f"特征: {location.get('geo_feature', 'Unknown')}")
            sections.append("")

        # 2. 玩家状态
        sections.append("【玩家状态】")
        sections.append(f"位置: {context.current_location}")
        sections.append(f"HP: {context.player_state.get('hp', 100)}/100")
        sections.append(f"SAN: {context.player_state.get('sanity', 100)}/100")
        sections.append(f"标签: {', '.join(context.player_state.get('tags', []))}")
        sections.append("")

        # 3. 可加载的内容
        available_content = self.get_loadable_content(context)
        if available_content:
            sections.append("【可用内容】")
            for content in available_content[:10]:  # 限制数量
                sections.append(f"- {content.name} ({content.content_type.value})")
            sections.append("")

        # 4. 事件历史
        event_context = context.event_system.get_context_for_narration()
        if event_context:
            sections.append(event_context)
            sections.append("")

        # 5. 用户输入
        sections.append("【玩家行动】")
        sections.append(user_input)

        return "\n".join(sections)

    def get_suggestions(
        self,
        context: LoadContext
    ) -> List[str]:
        """
        根据当前上下文，获取给玩家的建议行动

        Args:
            context: 加载上下文

        Returns:
            List[str]: 建议的行动列表
        """
        suggestions = []

        # 获取可加载的内容，作为建议
        available = self.get_loadable_content(context, limit=5)
        for content in available:
            if content.content_type == ContentType.NPC:
                suggestions.append(f"尝试与 {content.name} 交谈")
            elif content.content_type == ContentType.QUEST:
                suggestions.append(f"查看任务: {content.name}")
            elif content.content_type == ContentType.LOCATION:
                suggestions.append(f"探索 {content.name}")

        # 根据最近事件生成建议
        recent_events = context.get_recent_events(5)
        for event in recent_events:
            if event.event_type == EventType.NPC_MEET:
                npc_name = event.data.get("name", "NPC")
                suggestions.append(f"深入了解 {npc_name} 的故事")
            elif event.event_type == EventType.ITEM_ACQUIRED:
                item = event.data.get("item", "物品")
                suggestions.append(f"尝试使用 {item}")

        return suggestions[:5]  # 返回最多5个建议


# ============================================================================
# 🏭 内容生成器 - 用于批量生成游戏内容
# ============================================================================

class ContentGenerator:
    """
    内容生成器，用于批量创建游戏内容
    """

    @staticmethod
    def create_location(
        location_id: str,
        name: str,
        description: str,
        at_location: Optional[LoadTrigger] = None,
        **kwargs
    ) -> LoadableContent:
        """创建地点内容"""
        condition = LoadCondition(trigger_type=at_location or LoadTrigger.LOCATION_BASED)
        if at_location == LoadTrigger.LOCATION_BASED:
            condition = LoadCondition(
                trigger_type=LoadTrigger.LOCATION_BASED,
                at_location=location_id
            )

        return LoadableContent(
            content_id=f"loc_{location_id}",
            content_type=ContentType.LOCATION,
            name=name,
            description=description,
            condition=condition,
            data=kwargs
        )

    @staticmethod
    def create_npc(
        npc_id: str,
        name: str,
        description: str,
        at_location: str,
        **kwargs
    ) -> LoadableContent:
        """创建NPC内容"""
        condition = LoadCondition(
            trigger_type=LoadTrigger.LOCATION_BASED,
            at_location=at_location
        )

        return LoadableContent(
            content_id=f"npc_{npc_id}",
            content_type=ContentType.NPC,
            name=name,
            description=description,
            condition=condition,
            data={
                "npc_id": npc_id,
                "name": name,
                "description": description,
                **kwargs
            }
        )

    @staticmethod
    def create_item(
        item_id: str,
        name: str,
        description: str,
        requires_event: Optional[str] = None,
        **kwargs
    ) -> LoadableContent:
        """创建物品内容"""
        condition = LoadCondition(
            trigger_type=LoadTrigger.EVENT_BASED
        )
        if requires_event:
            condition.requires_events = [requires_event]

        return LoadableContent(
            content_id=f"item_{item_id}",
            content_type=ContentType.ITEM,
            name=name,
            description=description,
            condition=condition,
            data={
                "item_id": item_id,
                "name": name,
                "description": description,
                **kwargs
            }
        )