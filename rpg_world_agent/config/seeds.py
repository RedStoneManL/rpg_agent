"""
Seed data for procedural world generation.
包含了 JRPG 经典风味的危机种子库，用于激发创世灵感。
"""

CRISIS_SEEDS = [
    # --- 政治/权力类 ---
    "傀儡皇帝与摄政王 (The Puppet King and the Regent) - 王权旁落，幕后黑手操纵着年幼的君主。",
    "教会的血腥清洗 (The Church's Purge) - 圣教军正在以异端的名义清洗所有魔法使用者。",
    "军事政变 (Military Coup) - 边境将军率领魔导装甲军团向王都进发。",
    "边境公爵的叛乱 (Rebellion of the Border Duke) - 掌握资源的公爵宣布脱离王国独立。",
    
    # --- 征服/战争类 ---
    "古代帝国的复辟 (Restoration of the Ancient Empire) - 沉睡千年的古代魔法王朝正在苏醒。",
    "异族的大举入侵 (Invasion from the Barbaric Lands) - 北方冻土的蛮族跨越了长城。",
    "魔导帝国的闪击战 (Blitzkrieg of the Magitek Empire) - 邻国突然展示了跨时代的魔导科技武器。",
    
    # --- 超自然/宿命类 ---
    "魔王封印松动 (The Seal of the Demon King Weakens) - 世界各地的封印石碑开始出现裂痕。",
    "邪神转生仪式 (Ritual of the Dark God's Reincarnation) - 秘密教团正在收集祭品唤醒邪神。",
    "世界树的枯萎 (Withering of the World Tree) - 魔法的源头正在干涸，精灵森林开始腐烂。",
    "天空城的坠落 (Fall of the Sky Fortress) - 悬浮在空中的古都失去了动力，即将撞向地表。",
    "魔法瘟疫爆发 (Outbreak of the Spellplague) - 接触魔法会让人变异成晶体怪物。",
    "星辰错位 (The Stars Are Wrong) - 占星师发现群星的排列预示着维度的崩塌。"
]

# (可选) 如果你希望把 System Prompt 的模板也放回这里管理，可以加回来
# 但目前的架构中，Prompt 逻辑主要在 core/generators.py 里
