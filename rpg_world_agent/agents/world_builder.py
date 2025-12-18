import json
import re
from typing import Any, Dict, Optional

from config.rules import KNOWLEDGE_LEVELS, VALID_SKILLS, VALID_TAG_CATEGORIES
from config.settings import AGENT_CONFIG
from config.tool_schemas import WORLD_GEN_TOOLS

def get_world_builder_system_prompt() -> str:
    """动态生成 System Prompt。"""
    skills_str = ", ".join(VALID_SKILLS)
    tags_str = ", ".join(VALID_TAG_CATEGORIES)
    tools_desc = json.dumps(WORLD_GEN_TOOLS, indent=2, ensure_ascii=False)

    return f"""
你是一个专业的 TRPG 世界架构师 (World Builder Agent)。
你的目标是协助用户从零开始构建一个逻辑严密、细节丰富的游戏世界。

【核心能力与规则】
你拥有一系列强大的生成工具（Tools）。为了保证世界的一致性，你在思考或调用工具时必须严格遵守以下数据规范：

1. **合法技能库 (Valid Skills)**:
   {skills_str}
   *注意：当你在设计 NPC 大纲或判定逻辑时，涉及技能必须从中选取，不得造词。*

2. **合法身份标签 (Valid Tags)**:
   {tags_str}

3. **知识分级 (Knowledge Levels)**:
   {KNOWLEDGE_LEVELS}

【工具库 (Available Tools)】
你可以调用以下工具来辅助生成。**不要自己瞎编生成 Prompt，必须调用工具来获取标准化的 Prompt。**
工具定义如下：
{tools_desc}

【工作流程 (Workflow)】
你的工作是分步骤进行的。每一步都需要你先思考用户的意图，然后构造结构化的参数调用工具。

--- 特别说明：NPC 生成阶段 ---
当你进行到 "Generate NPCs" 步骤时，**不要**仅仅告诉工具 "生成 3 个人"。
你是一个更有主见的架构师。你需要根据当前的地图和政治局势，
先在脑海中构思出关键人物的 **大纲 (Outlines)**，然后将这些大纲传给工具。

**推荐思考模式：**
"用户想要一个傀儡皇帝。那我就要构造一个 outline: {{'role': '皇帝', 'traits': '年幼, 恐惧', 'secret_hint': '被摄政王控制'}}。然后把这个传给 tool。"

【响应协议 (RESPONSE PROTOCOL)】
**非常重要**：
当你决定需要执行某个操作（比如生成地图、生成NPC）时，**必须且只能**输出以下标准的 JSON 格式。
不要加 markdown 标记，不要加 ``` 符号，直接输出 JSON 字符串。

格式示例：
{{
    "thought": "用户想要3个NPC，其中一个是傀儡皇帝。我需要调用 generate_npcs_prompt 工具。",
    "tool_name": "generate_npcs_prompt",
    "arguments": {{
        "num_npcs": 3,
        "custom_outlines": [
            {{
                "role": "皇帝",
                "traits": "傀儡, 年幼"
            }}
        ]
    }}
}}

如果不需要调用工具（只是普通回复用户），则直接输出自然语言文本。
"""


class WorldBuilderAgent:
    """
    WorldBuilderAgent 封装类
    负责：维护对话历史 -> 调用 LLM -> 解析 LLM 返回的 JSON -> 返回给 Main 函数
    """

    def __init__(self, model_client):
        self.client = model_client
        self.system_prompt = get_world_builder_system_prompt()
        self.history = [{"role": "system", "content": self.system_prompt}]

    def chat(self, user_input: str) -> Dict[str, Any]:
        """Agent 主循环"""
        self.history.append({"role": "user", "content": user_input})

        print("🤖 WorldBuilder 正在思考...")
        try:
            # 【解锁】使用全局配置的最大 Token 数
            max_tokens_limit = AGENT_CONFIG["llm"].get("max_tokens", 8000)

            response = self.client.chat.completions.create(
                model=AGENT_CONFIG["llm"]["model"],
                messages=self.history,
                temperature=0.3,
                max_tokens=max_tokens_limit  # 彻底放开限制！
            )
            content = response.choices[0].message.content
        except Exception as e:
            return {
                "type": "error",
                "payload": f"LLM 调用失败: {str(e)}",
                "raw_response": ""
            }

        self.history.append({"role": "assistant", "content": content})
        
        tool_call_data = self._parse_tool_call(content)

        if tool_call_data:
            return {
                "type": "tool_call",
                "payload": tool_call_data,
                "raw_response": content
            }
        else:
            return {
                "type": "text",
                "payload": content,
                "raw_response": content
            }

    def _parse_tool_call(self, text: str) -> Optional[Dict]:
        """尝试从 LLM 的回复中提取 JSON 工具调用。"""
        try:
            # 1. (可选) 过滤掉 <think> 标签，防止干扰 JSON 提取
            clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            
            # 2. 寻找 JSON
            start_idx = clean_text.find('{')
            end_idx = clean_text.rfind('}')

            if start_idx == -1 or end_idx == -1:
                return None

            json_candidate = clean_text[start_idx : end_idx + 1]
            data = json.loads(json_candidate)

            if "tool_name" in data and "arguments" in data:
                print(f"🔧 [Agent] 检测到工具调用: {data['tool_name']}")
                return data

        except json.JSONDecodeError:
            return None
        except Exception as e:
            print(f"⚠️ [Agent] 解析工具调用时发生未知错误: {e}")
            return None

        return None
