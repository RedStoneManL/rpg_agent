import ast
import json
import random
import re
from typing import Any, Dict, List

from config.settings import AGENT_CONFIG
from core.cognition import CognitionSystem
from core.map_engine import MapTopologyEngine


class RuntimeEngine:
    """
    游戏运行时引擎 (The Dungeon Master).
    集成记忆上下文、AI Director 逻辑和 Debug 模式。
    """

    def __init__(self, session_id: str, llm_client=None, debug_mode: bool = False):
        self.session_id = session_id
        self.llm_client = llm_client
        self.debug_mode = debug_mode
        self.map_engine = MapTopologyEngine(llm_client)
        self.cognition = CognitionSystem(session_id)

    def _log_debug(self, title: str, content: Any) -> None:
        if self.debug_mode:
            print(f"\n🐛 [DEBUG: {title}]")
            print(str(content))
            print("-" * 40)

    def _normalize_state_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return value

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    parsed = None

            if isinstance(parsed, list):
                return parsed

            return [value]

        return []

    def initialize_player(self, start_location_id: str, initial_tags: List[str] | None = None) -> None:
        default_state = {
            "hp": 100,
            "sanity": 100,
            "location": start_location_id,
            "tags": initial_tags or ["traveler"],
            "skills": ["observation"],
        }
        self.cognition.update_player_state(default_state)
        self.cognition.add_message("system", f"玩家出生于 {start_location_id}")
        print(f"🎮 玩家已出生于: {start_location_id}")

    def step(self, user_input: str) -> str:
        self.cognition.add_message("user", user_input)

        state = self.cognition.get_player_state()
        curr_loc = state.get("location")

        history = self.cognition.get_recent_history(limit=6)
        history_str = self._format_history(history)

        response = ""
        if user_input.startswith("/move"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                response = "🚫 DM: 请输入要前往的目的地 ID。"
            else:
                target_id = parts[1]
                response = self._handle_move(curr_loc, target_id)
        elif user_input.startswith("/look"):
            response = self._handle_look(curr_loc)
        else:
            response = self._handle_natural_language(user_input, state, history_str)

        self.cognition.add_message("assistant", response)
        return response

    def _format_history(self, messages: List[Dict[str, str]]) -> str:
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

    # =========================================================================
    # 🕹️ 基础指令 (Handlers)
    # =========================================================================

    def _handle_move(self, curr_loc: str, target_id: str) -> str:
        if not curr_loc:
            return "🚫 DM: 当前没有有效位置，无法移动。"

        neighbors = self.map_engine.get_neighbors(curr_loc)
        route_payload = None
        for field_key, payload_str in neighbors.items():
            if field_key == f"Travel:{target_id}":
                route_payload = json.loads(payload_str)
                break

        if not route_payload:
            return f"🚫 DM: 前方无路。你无法直接从 {curr_loc} 前往 {target_id}。"

        self.cognition.update_player_state({"location": target_id})
        route_info = route_payload.get("route_info", {})
        route_name = route_info.get("route_name", "通道")
        description = route_info.get("description", "")

        return (
            f"🚶 你穿过【{route_name}】前往 {target_id}。\n"
            f"环境：{description}\n"
            f"...\n"
            f"经过跋涉，你到达了目的地。"
        )

    def _handle_look(self, curr_loc: str) -> str:
        if not curr_loc:
            return "❌ 当前位置未定义，无法观察。"

        node_data = self.map_engine.get_node(curr_loc)
        if not node_data:
            return "❌ 这里的空间似乎崩塌了 (Location Data Missing)。"

        player_state = self.cognition.get_player_state()
        player_tags = self._normalize_state_list(player_state.get("tags"))
        player_skills = self._normalize_state_list(player_state.get("skills"))

        layers = node_data.get("layers") if isinstance(node_data.get("layers"), dict) else {}
        base_desc = node_data.get("desc")
        if not base_desc and isinstance(layers.get("public"), dict):
            base_desc = layers["public"].get("desc")

        revealed_layers: List[str] = []
        for layer_name, layer_data in layers.items():
            if layer_name == "public" or not isinstance(layer_data, dict):
                continue

            access_req = layer_data.get("access_req")
            access_req = access_req if isinstance(access_req, dict) else {}
            required_tags = self._normalize_state_list(access_req.get("tags"))
            required_skills = self._normalize_state_list(access_req.get("skills"))
            logic = str(access_req.get("logic", "OR")).upper()

            if logic == "AND":
                has_access = all(tag in player_tags for tag in required_tags) and all(
                    skill in player_skills for skill in required_skills
                )
            else:
                has_access = any(tag in player_tags for tag in required_tags) or any(
                    skill in player_skills for skill in required_skills
                )

            if has_access and layer_data.get("desc"):
                revealed_layers.append(f"🕵️ Insight ({layer_name}): {layer_data.get('desc')}")

        neighbors = self.map_engine.get_neighbors(curr_loc)
        exits = [key.split(":", 1)[1] for key in neighbors.keys() if ":" in key]

        observation_lines = [
            f"📍 地点: {node_data.get('name')}",
            f"👁️ 观察: {base_desc or '这里暂时没有可见的描述。'}",
            f"🌟 特征: {node_data.get('geo_feature')}",
        ]

        if revealed_layers:
            observation_lines.extend(revealed_layers)

        observation_lines.append(f"🚪 出口: {', '.join(exits)}")

        return "\n".join(observation_lines)

    # =========================================================================
    # 🧠 智能中枢 (带记忆版)
    # =========================================================================

    def _analyze_intent(self, user_input: str, curr_loc_info: Dict, history_str: str) -> Dict:
        loc_name = curr_loc_info.get("name", "未知区域")

        prompt = f"""
你是一个游戏指令解析器。
玩家位置: {loc_name}

【最近对话历史】
{history_str}
----------------
当前输入: "{user_input}"

请判断玩家意图：
1. **EXPLORE**: 玩家想去一个不在地图上的具体地点 (如"找个商店", "去山洞", "进那个门")。
   - 注意：如果玩家之前的动作是"砸门"且成功了，现在的输入是"进去"，这属于 EXPLORE。
2. **ACTION**: 玩家试图改变现状 (如"攻击", "逃跑", "砸门", "黑入").
3. **CHAT**: 闲聊、观察。

返回JSON:
{{
    "intent": "EXPLORE" | "ACTION" | "CHAT",
    "keyword": "地点名(EXPLORE) / 动作词(ACTION)"
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
            clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            self._log_debug("Intent Analysis Raw", clean)

            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1:
                return json.loads(clean[start : end + 1])
        except Exception as exc:  # noqa: BLE001
            self._log_debug("Intent Error", exc)
        return {"intent": "CHAT"}

    def _handle_natural_language(self, user_input: str, player_state: Dict, history_str: str) -> str:
        if not self.llm_client:
            return f"DM (离线): {user_input}"

        curr_loc = player_state.get("location")
        loc_info = self.map_engine.get_node(curr_loc) or {}

        analysis = self._analyze_intent(user_input, loc_info, history_str)
        intent = analysis.get("intent")
        keyword = analysis.get("keyword")

        self._log_debug("Intent Result", f"Type: {intent}, Keyword: {keyword}")

        if intent == "EXPLORE":
            print(f"🔍 [Runtime] 探索意图: {keyword}")
            try:
                new_node_id = self.map_engine.create_dynamic_sub_location(curr_loc, keyword)
                if new_node_id:
                    return self._handle_move(curr_loc, new_node_id)
                self._log_debug("MapGen", "未能生成新节点，回退到叙事")
            except AttributeError:
                self._log_debug("MapGen", "动态造地未实现，回退到叙事")

        elif intent == "ACTION":
            print(f"⚡ [Runtime] 动作结算: {keyword}")
            return self._handle_action_resolution(user_input, player_state, loc_info, history_str)

        return self._handle_chat_narrative(user_input, player_state, loc_info, history_str)

    # =========================================================================
    # 🎲 AI 导演系统 (Probabilistic Director)
    # =========================================================================

    def _roll_for_crisis(self, risk_level: int) -> bool:
        if not risk_level:
            risk_level = 1
        threshold = risk_level * 0.1
        if risk_level >= 5:
            threshold = 0.5

        roll = random.random()
        return roll < threshold

    def _handle_action_resolution(
        self,
        user_input: str,
        player_state: Dict,
        loc_info: Dict,
        history_str: str,
    ) -> str:
        world_genre = AGENT_CONFIG.get("genre", "RPG")
        world_crisis = AGENT_CONFIG.get("final_conflict", "未知威胁")

        prompt = f"""
你是一个严厉的 TRPG 裁判 (Referee)。
世界观: {world_genre}
当前危机背景: {world_crisis}
场景: {loc_info.get('name')}
玩家状态: HP {player_state.get('hp')} | SAN {player_state.get('sanity')}

【前情提要】
{history_str}
----------------
玩家动作: "{user_input}"

请执行 **动作判定 (Action Resolution)**。必须遵守以下规则：

1. **后果优先 (Consequence Driven)**: 不要只描述过程，必须判定结果 (成功 / 失败 / 代价高昂的成功)。
2. **状态改变**: 动作必须导致环境或状态变化，例如获得信息、受到伤害或触发警报。
3. **结合历史**: 如果玩家在重复尝试同一动作，这一次必须给出决定性结果。
4. **逻辑一致性**: 按照 {world_genre} 的物理或魔法规则判定不可能的行动，并给出惩罚。
5. **风格**: 冷硬、客观、紧凑。限制在 150 字以内，禁止输出 <think>。
"""
        return self._call_dm_llm(prompt)

    def _handle_chat_narrative(
        self,
        user_input: str,
        player_state: Dict,
        loc_info: Dict,
        history_str: str,
    ) -> str:
        world_genre = AGENT_CONFIG.get("genre", "RPG")
        world_tone = AGENT_CONFIG.get("tone", "中性")
        world_crisis = AGENT_CONFIG.get("final_conflict", "未知威胁")

        risk_level = loc_info.get("risk_level", 1)
        trigger_crisis = self._roll_for_crisis(int(risk_level))

        if trigger_crisis:
            director_instruction = (
                f"**【AI Director 指令】**: 此处必须隐晦地暗示【{world_crisis}】的迹象"
                f"（如异常的声音、阴影的蠕动），营造紧张感。"
            )
        else:
            director_instruction = (
                "**【AI Director 指令】**: 专注描写当前的物理环境氛围，"
                "保持平静或神秘，不要刻意制造恐慌。"
            )

        prompt = f"""
你是一个专业TRPG游戏的 **沉浸式模拟引擎**。
世界题材: {world_genre}
整体基调: {world_tone}
当前地点: {loc_info.get('name')} - {loc_info.get('desc')}
玩家输入: "{user_input}"

【上下文】
{history_str}
----------------
{director_instruction}

请基于上述信息生成回应，必须严格遵守以下 **通用叙事原则**：

1. **物理锚点 (Physical Grounding)**: 描述必须基于场景中客观存在的物体、光影、声音或气味，拒绝空洞比喻。
2. **逻辑一致性 (Logical Consistency)**: 回应必须是玩家行为的直接结果，必要时根据 {world_genre} 的常识克制推演。
3. **风格适配 (Style Adaptation)**: 严格保持 {world_tone} 的语调。
4. **形式约束**: 限制在 150 字以内，使用第二人称，绝对禁止输出 <think> 标签。
"""
        return self._call_dm_llm(prompt)

    def _call_dm_llm(self, prompt: str) -> str:
        try:
            self._log_debug("LLM Request Prompt", prompt)

            max_tokens = AGENT_CONFIG["llm"].get("max_tokens", 8000)
            res = self.llm_client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            content = res.choices[0].message.content
            clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            self._log_debug("LLM Response", clean)

            return f"DM: {clean}"
        except Exception as exc:  # noqa: BLE001
            return f"DM Error: {exc}"
