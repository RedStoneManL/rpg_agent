"""
Runtime Engine - Enhanced with Event System, Plugin System, and Context-Aware Loading

This is the refactored game engine that integrates:
1. Event System - for tracking game progress and story beats
2. Plugin System - for extensible modular features
3. Context-Aware Loader - for intelligent content loading
4. World State Manager - for managing game world state

The engine acts as an intelligent Dungeon Master that:
- Tracks player actions and their consequences
- Dynamically loads content based on game progress
- Allows plugins to extend functionality
- Maintains consistent world state
"""

import json
import random
import re
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from rpg_world_agent.config.settings import AGENT_CONFIG
from rpg_world_agent.core.cognition import CognitionSystem
from rpg_world_agent.core.map_engine import MapTopologyEngine
from rpg_world_agent.core.event_system import EventSystem, EventData, EventType, EventListener, EventPriority
from rpg_world_agent.core.plugin_system import PluginManager, PluginHookType
from rpg_world_agent.core.context_loader import ContextLoader, LoadContext, LoadableContent, ContentType
from rpg_world_agent.core.world_state import WorldStateManager, CrisisLevel, WorldTime

# Import for type checking
if TYPE_CHECKING:
    pass


class RuntimeEngine:
    """
    Enhanced Game Runtime Engine (The Dungeon Master)

    Integrates multiple subsystems:
    - Event System: Tracks notable game events
    - Plugin System: Allows modular feature extensions
    - Context-Aware Loader: Intelligently loads content based on game state
    - World State Manager: Manages persistent world state
    """

    def __init__(
        self,
        session_id: str,
        llm_client=None,
        debug_mode: bool = False
    ):
        self.session_id = session_id
        self.llm_client = llm_client
        self.debug_mode = debug_mode

        # ============ Core Subsystems ============
        self.map_engine = MapTopologyEngine(llm_client)
        self.cognition = CognitionSystem(session_id)
        self.event_system = EventSystem(session_id)
        self.world_state = WorldStateManager(session_id)
        self.context_loader = ContextLoader(session_id)

        # Plugin Manager
        self.plugin_manager = PluginManager.get_instance()

        # Player state shortcuts
        self.player_id = f"player_{session_id}"

        # Turn tracking
        self._turn_count = 0
        self._last_turn_time = 0

        # Setup event listener for world state synchronization
        self._setup_world_state_sync()

        # Debug logging
        if self.debug_mode:
            print("🐛 [DEBUG] RuntimeEngine initialized with enhanced subsystems")

    # =========================================================================
    # 🔧 Setup and Initialization
    # =========================================================================

    def _setup_world_state_sync(self) -> None:
        """Setup event listener to sync events with world state"""
        def on_event(event: EventData) -> None:
            self.world_state.handle_event(event)

        self.event_system.register_listener(EventListener(
            event_types=list(EventType),
            handler=on_event,
            priority=5
        ))

    def initialize_player(
        self,
        start_location_id: str,
        initial_tags: Optional[List[str]] = None
    ) -> None:
        """
        Initialize player character

        This method:
        1. Creates default player state
        2. Registers the starting location
        3. Triggers player creation hooks in plugins
        4. Emits player creation event
        """
        default_state = {
            "hp": 100,
            "max_hp": 100,
            "sanity": 100,
            "max_sanity": 100,
            "location": start_location_id,
            "tags": initial_tags or ["traveler", "outsider"],
            "skills": ["observation"],
            "level": 1,
            "exp": 0,
            "gold": 100
        }
        self.cognition.update_player_state(default_state)

        # Register starting region in world state
        region_name = "Starting Location"
        node = self.map_engine.get_node(start_location_id)
        if node:
            region_name = node.get("name", region_name)
        self.world_state.register_region(start_location_id, region_name)

        # Trigger plugin hooks
        self.plugin_manager.invoke_hook(
            PluginHookType.ON_PLAYER_CREATED,
            self.player_id,
            start_location_id
        )

        # Emit creation event
        self.event_system.emit(
            EventType.CUSTOM,
            self.player_id,
            start_location_id,
            data={
                "description": "玩家角色创建",
                "event_type": "player_created"
            },
            tags=["player", "character_creation"]
        )

        print(f"🎮 Player initialized at: {start_location_id}")

    def load_plugins(self) -> None:
        """Load all registered plugins"""
        print("🔌 Loading plugins...")
        self.plugin_manager.load_all_plugins(self)
        print(f"✅ {len(self.plugin_manager.get_enabled_plugins())} plugins loaded")

    # =========================================================================
    # 🎮 Main Game Loop
    # =========================================================================

    def step(self, user_input: str) -> str:
        """
        Execute one game step

        This is the main entry point for the game loop:
        1. Add input to conversation history
        2. Trigger turn start hooks
        3. Parse and handle command
        4. Check for content to load
        5. Update world state
        6. Trigger turn end hooks
        7. Return response
        """
        self._turn_count += 1

        # Add to history
        self.cognition.add_message("user", user_input)

        # Get current state
        state = self.cognition.get_player_state()
        curr_loc = state.get("location", "Unknown")

        # Trigger turn start hooks
        self.plugin_manager.invoke_hook(PluginHookType.ON_TURN_START, self._turn_count)

        # Trigger before action hooks
        hook_result = self.plugin_manager.invoke_hook_first(
            PluginHookType.ON_BEFORE_ACTION,
            user_input,
            state
        )
        if hook_result is not None:
            # Plugin handled the action
            response = str(hook_result)
        else:
            # Process the command
            response = self._process_command(user_input, state, curr_loc)

        # Add response to history
        self.cognition.add_message("assistant", response)

        # Trigger narrative generated hooks
        self.plugin_manager.invoke_hook(
            PluginHookType.ON_Narration_GENERATED,
            response,
            {"user_input": user_input, "location": curr_loc}
        )

        # Check for loadable content
        self._check_and_load_content(state, curr_loc)

        # Save world state (every few turns)
        if self._turn_count % 10 == 0:
            self.world_state.save()

        # Trigger turn end hooks
        self.plugin_manager.invoke_hook(
            PluginHookType.ON_TURN_END,
            self._turn_count
        )

        return response

    # =========================================================================
    # ⌨️ Command Processing
    # =========================================================================

    def _process_command(
        self,
        user_input: str,
        state: Dict[str, Any],
        curr_loc: str
    ) -> str:
        """Process user input and route to appropriate handler"""

        # Check for plugin commands first
        plugin_handler = self.plugin_manager.get_command_handler(user_input.split()[0])
        if plugin_handler:
            return plugin_handler(user_input, self)

        # Built-in commands
        if user_input.startswith("/move"):
            return self._handle_move_command(curr_loc, user_input)
        elif user_input.startswith("/look"):
            return self._handle_look_command(curr_loc)
        elif user_input.startswith("/status"):
            return self._handle_status_command(state)
        elif user_input.startswith("/events"):
            return self._handle_events_command()
        elif user_input.startswith("/world"):
            return self._handle_world_command()
        elif user_input.startswith("/plugins"):
            return self._handle_plugins_command()
        else:
            # Natural language input
            return self._handle_natural_language(
                user_input,
                state,
                curr_loc
            )

    def _handle_move_command(self, curr_loc: str, user_input: str) -> str:
        """Handle movement command"""
        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            return "🚫 DM: 请输入要前往的目的地 ID。"

        target_id = parts[1]
        neighbors = self.map_engine.get_neighbors(curr_loc)

        # Find the travel route
        route_payload = None
        for field_key, payload_str in neighbors.items():
            if field_key == f"Travel:{target_id}":
                route_payload = json.loads(payload_str)
                break

        if not route_payload:
            return f"🚫 DM: 前方无路。无法从 {curr_loc} 前往 {target_id}。"

        old_loc = curr_loc

        # Update player location
        self.cognition.update_player_state({"location": target_id})
        route_info = route_payload.get("route_info", {})
        route_name = route_info.get("route_name", "通道")
        description = route_info.get("description", "")

        # Trigger location change hooks
        self.plugin_manager.invoke_hook(
            PluginHookType.ON_PLAYER_MOVED,
            self.player_id,
            old_loc,
            target_id
        )

        # Emit movement event
        self.event_system.emit(
            EventType.CUSTOM,
            self.player_id,
            target_id,
            data={
                "description": f"从 {old_loc} 移动到 {target_id}",
                "from_location": old_loc,
                "to_location": target_id,
                "route": route_name
            },
            tags=["movement", "location_change", "player"]
        )

        response = (
            f"🚶 你穿过【{route_name}】前往 {target_id}。\n"
            f"环境：{description}\n"
            f"...经过跋涉，你到达了目的地。"
        )

        # Trigger after action hooks
        hook_result = self.plugin_manager.invoke_hook_first(
            PluginHookType.ON_AFTER_ACTION,
            user_input,
            self.cognition.get_player_state(),
            response
        )
        if hook_result is not None:
            response = str(hook_result)

        return response

    def _handle_look_command(self, curr_loc: str) -> str:
        """Handle look command"""
        if not curr_loc:
            return "❌ 当前位置未定义，无法观察。"

        node_data = self.map_engine.get_node(curr_loc)
        if not node_data:
            return "❌ 这里的空间似乎崩塌了。"

        neighbors = self.map_engine.get_neighbors(curr_loc)
        exits = [key.split(":", 1)[1] for key in neighbors.keys() if ":" in key]

        # Get world state for this location
        location_summary = self.world_state.get_location_summary(curr_loc)

        response = (
            f"📍 地点: {node_data.get('name')}\n"
            f"👁️ 观察: {node_data.get('desc')}\n"
            f"🌟 特征: {node_data.get('geo_feature')}\n"
        )

        # Add world state info
        if location_summary:
            response += f"\n🌡️ 天气: {location_summary.get('weather', '晴朗')}\n"
            if location_summary.get('npcs_present'):
                response += f"👥 在场的人: {', '.join(location_summary['npcs_present'])}\n"

        response += f"\n🚪 出口: {', '.join(exits) if exits else '无'}"

        # Emit discovery event if first time
        if not self.world_state.get_region_state(curr_loc) or \
           not self.world_state.get_region_state(curr_loc).discovered:
            self.event_system.emit(
                EventType.DISCOVERY,
                self.player_id,
                curr_loc,
                data={
                    "description": f"发现了地点 {node_data.get('name')}",
                    "target": curr_loc
                },
                tags=["discovery", "location"]
            )

        return response

    def _handle_status_command(self, state: Dict[str, Any]) -> str:
        """Handle status command"""
        world_summary = self.world_state.get_world_summary()

        lines = [
            "🎭 玩家状态",
            "=" * 40,
            f"❤️ HP: {state.get('hp', 100)}/{state.get('max_hp', 100)}",
            f"🧠 SAN: {state.get('sanity', 100)}/{state.get('max_sanity', 100)}",
            f"📍 位置: {state.get('location', 'Unknown')}",
            f"🏷️ 等级: {state.get('level', 1)} | ✨ EXP: {state.get('exp', 0)}",
            f"💰 金币: {state.get('gold', 0)}",
            f"🏷️ 标签: {', '.join(state.get('tags', []))}",
            "",
            "🌍 世界状态",
            "=" * 40,
            f"⏰ 时间: {world_summary['time']}",
            f"⚠️ 危机等级: {world_summary['crisis_level_name']} ({world_summary['crisis_level']})",
            f"🗺️ 已发现区域: {world_summary['discovered_regions']}/{world_summary['regions_count']}",
            f"👥 存活NPC: {world_summary['alive_npcs']}/{world_summary['npcs_count']}",
            f"📜 活跃任务: {world_summary['active_quests']}"
        ]

        return "\n".join(lines)

    def _handle_events_command(self) -> str:
        """Handle events command - show recent events"""
        summary = self.event_system.get_event_summary()
        context = self.event_system.get_context_for_narration()

        return f"""📜 事件统计
{'=' * 40}
总事件数: {summary['total_events']}
最近事件:

{context}
"""

    def _handle_world_command(self) -> str:
        """Handle world command - show world state"""
        summary = self.world_state.get_world_summary()
        context = self.world_state.get_context_for_llm()

        return f"""🌍 世界概览
{'=' * 40}{context}
"""

    def _handle_plugins_command(self) -> str:
        """Handle plugins command - show loaded plugins"""
        plugins = self.plugin_manager.get_all_metadata()
        commands = self.plugin_manager.get_all_commands()

        lines = ["🔌 已加载的插件", "=" * 40]

        for plugin in plugins:
            lines.append(f"\n• {plugin['name']} v{plugin['version']}")
            lines.append(f"  作者: {plugin['author']}")
            lines.append(f"  {plugin['description']}")
            if plugin['provides_commands']:
                pc = [k for k in commands.keys() if commands[k]['plugin'] == plugin['name']]
                if pc:
                    lines.append(f"  命令: {', '.join(pc)}")

        lines.append("\n" + "=" * 40)
        lines.append(f"📋 可用命令: {', '.join(commands.keys())[:10]}...")

        return "\n".join(lines)

    # =========================================================================
    # 🧠 Natural Language Processing
    # =========================================================================

    def _handle_natural_language(
        self,
        user_input: str,
        state: Dict[str, Any],
        curr_loc: str
    ) -> str:
        """Handle natural language input using LLM intent analysis"""
        if not self.llm_client:
            return f"DM (离线): {user_input}"

        loc_info = self.map_engine.get_node(curr_loc) or {}

        # Get event context
        event_context = self.event_system.get_context_for_narration()
        history = self.cognition.get_recent_history(limit=6)
        history_str = self._format_history(history)

        # Analyze intent
        analysis = self._analyze_intent(user_input, loc_info, history_str, event_context)
        intent = analysis.get("intent", "CHAT")
        keyword = analysis.get("keyword", "")

        if intent == "EXPLORE":
            print(f"🔍 [Runtime] 探索意图: {keyword}")
            # Try to load or generate content
            load_context = LoadContext(
                player_id=self.player_id,
                current_location=curr_loc,
                player_state=state,
                event_system=self.event_system,
                map_engine=self.map_engine
            )
            dynamic_content = self.context_loader.generate_dynamic_content(
                keyword,
                load_context
            )
            if dynamic_content:
                return self._format_dynamic_content(dynamic_content)
            else:
                # Fall back to generating new location
                return self._handle_explore(curr_loc, keyword, user_input, state)

        elif intent == "ACTION":
            print(f"⚡ [Runtime] 动作结算: {keyword}")
            return self._handle_action_resolution(
                user_input, state, loc_info, history_str, event_context
            )

        # CHAT - narrative response
        return self._handle_chat_narrative(
            user_input, state, loc_info, history_str, event_context
        )

    def _handle_explore(
        self,
        curr_loc: str,
        keyword: str,
        user_input: str,
        state: Dict[str, Any]
    ) -> str:
        """Handle explore intent - try to create new location"""
        try:
            new_node_id = self.map_engine.create_dynamic_sub_location(curr_loc, keyword)
            if new_node_id:
                return self._handle_move_command(curr_loc, f"/move {new_node_id}")
        except Exception as e:
            self._log_debug("Explore Error", str(e))

        # Fall back to chat叙事
        return self._handle_chat_narrative(
            user_input, state,
            self.map_engine.get_node(curr_loc) or {},
            self.cognition.get_recent_history(limit=6),
            self.event_system.get_context_for_narration()
        )

    # =========================================================================
    # 🎲 LLM Integration
    # =========================================================================

    def _analyze_intent(
        self,
        user_input: str,
        loc_info: Dict,
        history_str: str,
        event_context: str
    ) -> Dict:
        """Analyze user intent using LLM"""
        loc_name = loc_info.get("name", "未知区域")

        prompt = f"""你是一个游戏指令解析器，判断玩家意图。

玩家位置: {loc_name}

【最近对话历史】
{history_str}

【最近事件】
{event_context}
----------------
当前输入: "{user_input}"

请判断玩家意图：
1. **EXPLORE**: 玩家想去一个不在地图上的具体地点 (如"找个商店"、"去山洞"、"进那个门")、查看发现的新内容
2. **ACTION**: 玩家试图改变现状 (如"攻击"、"逃跑"、"砸门"、"使用技能")
3. **CHAT**: 闲聊、观察、询问信息

返回JSON格式:
{{
    "intent": "EXPLORE" | "ACTION" | "CHAT",
    "keyword": "地点名(EXPLORE) / 动作词(ACTION) / 关键词(CHAT)"
}}
"""

        try:
            response = self.llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            clean = re.sub(r"```(?:json)?", "", content, flags=re.IGNORECASE).strip()

            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1:
                return json.loads(clean[start:end+1])

        except Exception as exc:
            self._log_debug("Intent Error", exc)

        return {"intent": "CHAT", "keyword": user_input}

    def _handle_action_resolution(
        self,
        user_input: str,
        player_state: Dict,
        loc_info: Dict,
        history_str: str,
        event_context: str
    ) -> str:
        """Handle action resolution using LLM as referee"""
        world_genre = AGENT_CONFIG.get("genre", "RPG")
        world_crisis = AGENT_CONFIG.get("final_conflict", "未知威胁")
        crisis_level = self.world_state.get_crisis_level().name

        prompt = f"""你是一个严厉的 TRPG 裁判。

世界观: {world_genre}
当前危机: {world_crisis} (等级: {crisis_level})
场景: {loc_info.get('name', 'Unknown')}
玩家状态: HP {player_state.get('hp', 100)}/100 | SAN {player_state.get('sanity', 100)}/100

【最近对话】
{history_str}

【最近事件】
{event_context}
----------------
玩家动作: "{user_input}"

请执行 **动作判定**，遵守以下规则：

1. **后果优先**: 必须判定结果 (成功/失败/部分成功) 和代价
2. **状态改变**: 动作必须导致环境或状态变化
3. **逻辑一致**: 根据 {world_genre} 的规则判定
4. **结合历史**: 考虑玩家之前的行为和事件
5. **风格**: 冷硬、客观、紧凑。150字以内，禁止输出 ```json

返回叙事描述。
"""

        response = self._call_dm_llm(prompt)

        # Emit action event
        self.event_system.emit(
            EventType.CUSTOM,
            self.player_id,
            player_state.get("location", "Unknown"),
            data={
                "description": f"执行了动作: {user_input[:30]}...",
                "action": user_input
            },
            tags=["action", "player"]
        )

        return response

    def _handle_chat_narrative(
        self,
        user_input: str,
        player_state: Dict,
        loc_info: Dict,
        history_str: str,
        event_context: str
    ) -> str:
        """Handle chat/narrative response"""
        world_genre = AGENT_CONFIG.get("genre", "RPG")
        world_tone = AGENT_CONFIG.get("tone", "中性")
        world_crisis = AGENT_CONFIG.get("final_conflict", "未知威胁")
        crisis_level = self.world_state.get_crisis_level().value

        risk_level = loc_info.get("risk_level", 1)
        trigger_crisis = self._roll_for_crisis(int(risk_level), crisis_level)

        if trigger_crisis:
            director_instruction = (
                f"**【AI Director】**: 此处必须隐晦地暗示【{world_crisis}】的迹象"
                f"（如异常声音、阴影蠕动），营造紧张感。"
            )
        else:
            director_instruction = (
                "**【AI Director】**: 专注描写当前物理环境，"
                "保持平静或神秘，不要刻意制造恐慌。"
            )

        prompt = f"""你是一个专业 TRPG 的沉浸式游戏引擎。

世界题材: {world_genre}
整体基调: {world_tone}
当前地点: {loc_info.get('name', 'Unknown')} - {loc_info.get('desc', '')}
玩家输入: "{user_input}"

【世界状态】
{self.world_state.get_context_for_llm()}

【对话历史】
{history_str}

【最近事件】
{event_context}
----------------
{director_instruction}

请基于以上信息生成回应，遵守以下规则：

1. **物理锚点**: 描述基于场景中客观存在的物体、光影、声音、气味
2. **逻辑一致**: 回应是玩家行为的直接结果，符合 {world_genre} 的常识
3. **风格适配**: 保持 {world_tone} 的语调
4. **形式约束**: 150字以内，第二人称，禁止使用 ```json 标签

返回叙事描述。
"""

        response = self._call_dm_llm(prompt)

        # Trigger after action hooks
        hook_result = self.plugin_manager.invoke_hook_first(
            PluginHookType.ON_AFTER_ACTION,
            user_input,
            player_state,
            response
        )
        if hook_result is not None:
            response = str(hook_result)

        return response

    def _call_dm_llm(self, prompt: str) -> str:
        """Call LLM for DM response"""
        try:
            self._log_debug("LLM Request", prompt[:500] + "...")

            max_tokens = AGENT_CONFIG["llm"].get("max_tokens", 8000)
            res = self.llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            content = res.choices[0].message.content
            clean = re.sub(r"```(?:json)?", "", content, flags=re.DOTALL).strip()

            self._log_debug("LLM Response", clean)
            return f"DM: {clean}"

        except Exception as exc:
            return f"DM Error: {exc}"

    # =========================================================================
    # 🔍 Content Loading and Generation
    # =========================================================================

    def _check_and_load_content(
        self,
        state: Dict[str, Any],
        curr_loc: str
    ) -> None:
        """Check for and load content based on current context"""
        load_context = LoadContext(
            player_id=self.player_id,
            current_location=curr_loc,
            player_state=state,
            event_system=self.event_system,
            map_engine=self.map_engine
        )

        # Load matching content
        loaded = self.context_loader.load_all_matching(
            load_context,
            limit=3
        )

        if loaded:
            for content in loaded:
                print(f"📦 [Loader] Loaded content: {content.name} ({content.content_type.value})")

    def _format_dynamic_content(self, content: Dict[str, Any]) -> str:
        """Format dynamically generated content into narrative response"""
        content_type = content.get("content_type", "custom")
        name = content.get("name", "Unknown")
        description = content.get("description", "")

        if content_type == "location":
            return f"🗺️ 你发现了一个新地方：{name}\n{description}"
        elif content_type == "npc":
            return f"👥 你遇到了{name}：{description}"
        elif content_type == "item":
            return f"🎒 你发现了物品：{name}\n{description}"
        elif content_type == "quest":
            return f"📜 新任务 - {name}：{description}"
        else:
            return f"✨ {description}"

    # =========================================================================
    # 🎲 AI Director System
    # =========================================================================

    def _roll_for_crisis(self, risk_level: int, crisis_level: int) -> bool:
        """Roll for crisis trigger based on location risk and global crisis level"""
        if not risk_level:
            risk_level = 1

        # Crisis level affects trigger probability
        base_threshold = risk_level * 0.1
        crisis_modifier = crisis_level * 0.05
        threshold = min(0.7, base_threshold + crisis_modifier)

        roll = random.random()
        return roll < threshold

    # =========================================================================
    # 💰 Save/Load System
    # =========================================================================

    def save_game(self) -> bool:
        """Save complete game state"""
        try:
            # Get cognition save data
            save_data = {
                "session_id": self.session_id,
                "turn_count": self._turn_count,
                "cognition_data": self.cognition.get_player_state(),
                "world_state": {
                    "time": self.world_state.world_time.to_dict(),
                    "crisis_level": self.world_state.crisis_level.value,
                    "global_flags": self.world_state.global_flags,
                    "global_variables": self.world_state.global_variables
                }
            }

            # Add plugin save data
            plugin_data = self.plugin_manager.invoke_hook(
                PluginHookType.ON_SAVE, save_data
            )
            if plugin_data:
                for plugin_input in plugin_data:
                    if plugin_input is not None and isinstance(plugin_input, dict):
                        save_data = plugin_input

            # Save to MinIO
            self.cognition.update_player_state({"hp": save_data["cognition_data"]["hp"]})
            object_name = self.cognition.archive_session()
            self.world_state.save()

            print(f"✅ Game saved: {object_name}")
            return True

        except Exception as e:
            print(f"❌ Save failed: {e}")
            return False

    def load_game(self) -> bool:
        """Load game state"""
        try:
            # Load from MinIO
            success = self.cognition.load_session()
            if not success:
                return False

            # Load world state
            self.world_state.load()

            # Trigger plugin load hooks
            player_state = self.cognition.get_player_state()
            self.plugin_manager.invoke_hook(PluginHookType.ON_LOAD, player_state)

            print(f"✅ Game loaded: {self.session_id}")
            return True

        except Exception as e:
            print(f"❌ Load failed: {e}")
            return False

    # =========================================================================
    # 🛠️ Utilities
    # =========================================================================

    def _log_debug(self, title: str, content: Any) -> None:
        """Log debug information"""
        if self.debug_mode:
            print(f"\n🐛 [DEBUG: {title}]")
            print(str(content))
            print("-" * 40)

    def _format_history(self, messages: List[Dict[str, str]]) -> str:
        """Format message history for LLM context"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"Player: {content}")
            elif role == "assistant":
                lines.append(f"DM: {content}")
            elif role == "system":
                lines.append(f"[System]: {content}")
        return "\n".join(lines)

    def get_suggestions(self) -> List[str]:
        """Get suggested actions for the player"""
        state = self.cognition.get_player_state()
        curr_loc = state.get("location", "Unknown")

        load_context = LoadContext(
            player_id=self.player_id,
            current_location=curr_loc,
            player_state=state,
            event_system=self.event_system,
            map_engine=self.map_engine
        )

        return self.context_loader.get_suggestions(load_context)