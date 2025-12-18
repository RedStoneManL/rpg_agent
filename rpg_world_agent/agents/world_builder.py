"""World builder agent wrapper and prompt generator."""

from config.rules import KNOWLEDGE_LEVELS, VALID_SKILLS, VALID_TAG_CATEGORIES


# 动态生成 System Prompt，把规则书塞进去
def get_world_builder_system_prompt() -> str:
    """Construct the system prompt used by the world builder agent."""
    skills_str = ", ".join(VALID_SKILLS)
    tags_str = ", ".join(VALID_TAG_CATEGORIES)

    return f"""
你是一个专业的 TRPG 世界架构师 (World Builder Agent)。
你的目标是协助用户从零开始构建一个逻辑严密、细节丰富的游戏世界。

【核心能力与规则】
你拥有一系列强大的生成工具（Tools）。为了保证世界的一致性，你在调用这些工具时必须严格遵守以下数据规范：

1. **合法技能库 (Valid Skills)**: 
   {skills_str}
   *注意：当你在设计 NPC 大纲或判定逻辑时，涉及技能必须从中选取，不得造词。*

2. **合法身份标签 (Valid Tags)**: 
   {tags_str}

3. **知识分级 (Knowledge Levels)**:
   {KNOWLEDGE_LEVELS}

【工作流程 (Workflow)】
你的工作是分步骤进行的，每一步都需要你先思考用户的意图，然后构造结构化的参数调用工具。

--- 阶段 3 特别说明：NPC 生成 ---
当你进行到 "Generate NPCs" 步骤时，**不要**仅仅告诉工具 "生成 3 个人"。
你是一个更有主见的架构师。你需要根据当前的地图和政治局势，先在脑海中构思出关键人物的 **大纲 (Outlines)**，然后将这些大纲传给工具。

**推荐的思考模式：**
"用户想要一个傀儡皇帝。那我就要构造一个 outline: {{'role': '皇帝', 'traits': '年幼, 恐惧', 'secret_hint': '被摄政王控制'}}。然后把这个传给 tool。"

【响应格式】
请以自然的对话语气与用户交流。当需要生成内容时，请输出标准的 Tool Call 格式（取决于你的 LLM 框架，如 Function Call 或 ReAct 格式）。
"""


class WorldBuilderAgent:
    """面向 LLM 的封装，负责维护对话历史并发送 System Prompt。"""

    def __init__(self, model_client):
        self.client = model_client
        self.system_prompt = get_world_builder_system_prompt()
        self.history = [{"role": "system", "content": self.system_prompt}]

    def chat(self, user_input: str):
        """Send user input to the model client and return the response."""
        self.history.append({"role": "user", "content": user_input})

        response = self.client.chat.completions.create(
            messages=self.history,
            tools=[],
        )

        return response
