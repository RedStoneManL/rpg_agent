"""Common rule sets for RPG world building agents."""

# 系统支持的技能列表 (用于权限判定)
VALID_SKILLS = [
    "arcana",
    "history",
    "nature",
    "religion",
    "investigation",
    "insight",
    "perception",
    "persuasion",
    "deception",
    "intimidation",
    "street_wise",
    "survival",
    "medicine",
]

# 系统支持的身份标签类别 (示例)
VALID_TAG_CATEGORIES = [
    "noble",
    "commoner",
    "criminal",
    "scholar",
    "soldier",
    "merchant",
    "outsider",
    "cultist",
]

# 知识等级定义 (用于 Prompt 指导)
KNOWLEDGE_LEVELS = {
    1: "Public (路人皆知)",
    2: "Social (圈内传闻/需要打听)",
    3: "Secret (组织机密/只有核心成员知道)",
    4: "Forbidden (禁忌知识/可能导致san值狂掉)",
}
