# 🎮 RPG Agent - LLM-Driven TRPG Engine

<div align="center">

**一个由大语言模型驱动的无限扩张跑团游戏引擎**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](#english) | [中文文档](#中文文档)

</div>

---

## 中文文档

### 🎯 项目简介

RPG Agent 是一个基于大语言模型（LLM）的桌面角色扮演游戏（TRPG）引擎，它扮演一个智能的地下城主（Dungeon Master），能够：

- **🎭 智能叙事**：LLM 驱动的动态剧情生成
- **🌍 无限世界**：根据玩家行为动态扩张游戏世界
- **🧠 活的系统**：世界在玩家之外也会发展（NPC 移动、事件发生）
- **💰 成本优化**：懒加载机制减少不必要的 API 调用
- **💾 持久化存储**：Redis + MinIO 支持的存档系统

### ✨ 核心特性

#### 1. 动态世界生成
```python
# 玩家可以自由探索，世界会根据意图动态生成新地点
> 我想找个酒馆休息一下
DM: 你穿过几条小巷，发现了一家名为"碎盾酒馆"的小店...
```

#### 2. 活的世界系统
- **NPC 有自己的生活**：NPC 会移动、交谈、执行任务
- **世界事件**：危机事件会随时间推进
- **区域状态变化**：天气、危险等级会动态变化

#### 3. 智能懒加载
```python
# 只有在需要时才调用 LLM 生成内容
# 相似内容会复用，减少 API 成本
```

#### 4. 完整的 TRPG 系统
- D&D 5e 风格的属性和技能
- HP/理智值/体力值追踪
- 物品和装备系统
- 任务和剧情系统

---

### 🏗️ 项目架构

```
rpg_world_agent/
├── core/                    # 核心系统
│   ├── runtime.py          # 🎮 游戏引擎主循环
│   ├── world_simulator.py  # 🌍 世界模拟器
│   ├── world_state.py      # 📊 世界状态管理
│   ├── map_engine.py       # 🗺️ 地图拓扑引擎
│   ├── cognition.py        # 🧠 会话状态管理
│   ├── event_system.py     # 📜 事件系统
│   ├── context_loader.py   # 📦 上下文加载器
│   ├── lazy_loader.py      # ⚡ 懒加载策略
│   ├── plugin_system.py    # 🔌 插件系统
│   └── player_character.py # 🎭 玩家角色系统
│
├── data/                    # 数据层
│   ├── db_client.py        # Redis/MinIO 客户端
│   └── llm_client.py       # LLM 客户端工厂
│
├── config/                  # 配置
│   ├── settings.py         # 全局配置
│   ├── rules.py            # 游戏规则
│   └── seeds.py            # 世界生成种子
│
├── agents/                  # Agent 定义
│   └── world_builder.py    # 世界构建 Agent
│
└── plugins/                 # 插件
    └── magic_system.py     # 魔法系统示例
```

---

### 🚀 快速开始

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# LLM 配置 (必需)
export RPG_LLM_BASE_URL="https://api.openai.com/v1"
export RPG_LLM_API_KEY="your-api-key"
export RPG_LLM_MODEL="gpt-4"

# Redis 配置 (必需)
export RPG_REDIS_HOST="localhost"
export RPG_REDIS_PORT="6379"

# MinIO 配置 (必需)
export RPG_MINIO_ENDPOINT="localhost:9000"
export RPG_MINIO_ACCESS_KEY="minioadmin"
export RPG_MINIO_SECRET_KEY="minioadmin"

# 世界设定 (可选)
export RPG_GENRE="Cyberpunk/Lovecraftian"
export RPG_TONE="Dark & Gritty"
export RPG_FINAL_CONFLICT="The Awakening of the Old Ones"
```

#### 3. 初始化世界

```bash
# 交互式世界初始化
python init_world.py

# 使用默认地图（无需 LLM）
python init_world.py default

# 列出已有地图
python init_world.py list

# 清除地图数据
python init_world.py clear
```

#### 4. 启动游戏

```bash
python main.py
```

---

### 🎮 游戏指令

#### 探索指令
| 指令 | 说明 |
|------|------|
| `/look` | 查看当前环境 |
| `/move <地点ID>` | 移动到指定地点 |
| `/exits` | 查看所有可前往的地点 |

#### 交互指令
直接输入自然语言描述你的行动：
```
> 我想找商店买些补给
> 攻击那个哥布林
> 和酒馆老板交谈
```

#### 游戏管理
| 指令 | 说明 |
|------|------|
| `/status` | 查看角色状态 |
| `/map` | 查看已探索地图 |
| `/save` | 保存游戏进度 |
| `/load` | 加载存档 |
| `/help` | 显示帮助 |
| `/quit` | 退出游戏 |

---

### 🔧 核心系统详解

#### RuntimeEngine (游戏引擎)

游戏的主控制器，负责：
- 解析玩家输入
- 调用 LLM 生成响应
- 更新游戏状态
- 触发事件

```python
from rpg_world_agent.core.runtime import RuntimeEngine

engine = RuntimeEngine(
    session_id="game_001",
    llm_client=my_llm_client,
    debug_mode=True
)

engine.initialize_player(
    start_location="tavern_square",
    initial_tags=["traveler", "outsider"]
)

response = engine.step("我想探索这个城镇")
```

#### WorldSimulator (世界模拟器)

让世界在玩家之外也有发展：

```python
from rpg_world_agent.core.world_simulator import WorldSimulator

simulator = WorldSimulator(session_id="game_001")

# 模拟 1 小时的世界发展
events = simulator.simulate_tick(minutes=60)
for event in events:
    print(f"事件: {event.name} - {event.description}")
```

#### WorldStateManager (世界状态管理)

管理全局世界状态：

```python
from rpg_world_agent.core.world_state import WorldStateManager, CrisisLevel

world = WorldStateManager(session_id="game_001")

# 时间系统
world.advance_time(60)  # 推进 60 分钟
print(world.get_time_display())  # "第1天 14:30 (下午)"

# 危机系统
world.set_crisis_level(CrisisLevel.MEDIUM)

# NPC 管理
world.register_npc("merchant_001", "商人汤姆", "market")
world.move_npc("merchant_001", "tavern_square")

# 任务系统
quest = world.register_quest(
    "quest_001",
    "寻找失落的神器",
    "传说神器被封印在古老遗迹中..."
)
world.accept_quest("quest_001")
```

#### MapTopologyEngine (地图引擎)

图结构的动态地图系统：

```python
from rpg_world_agent.core.map_engine import MapTopologyEngine

map_engine = MapTopologyEngine(llm_client=my_llm)

# 获取地点信息
node = map_engine.get_node("tavern_square")
print(node["name"])  # "酒馆广场"

# 获取可前往的地点
neighbors = map_engine.get_neighbors("tavern_square")

# 动态生成子地点
new_location = map_engine.create_dynamic_sub_location(
    parent_id="tavern_square",
    keyword="秘密通道"
)
```

---

### 🔌 插件系统

创建自定义插件扩展功能：

```python
from rpg_world_agent.core.plugin_system import Plugin, PluginHookType

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "My Custom Plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def on_load(self, engine):
        # 注册自定义命令
        engine.plugin_manager.register_command(
            "/mystery",
            self.handle_mystery_command
        )
    
    def handle_mystery_command(self, args, engine):
        return "🔮 神秘事件发生了！"

# 注册插件
from rpg_world_agent.core.plugin_system import PluginManager
PluginManager.get_instance().register_plugin(MyPlugin())
```

---

### 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_core/test_world_simulator.py -v

# 生成覆盖率报告
pytest tests/ --cov=rpg_world_agent --cov-report=html
```

---

### 📊 存储架构

```
Redis Keys:
├── rpg:map:node:{node_id}       # 地图节点数据
├── rpg:map:edges:{node_id}      # 地图连接
├── rpg:history:{session_id}     # 对话历史
├── rpg:state:{session_id}       # 玩家状态
├── rpg:world_state:{session_id} # 世界状态
└── rpg:events:{session_id}      # 事件记录

MinIO Objects:
└── saves/{session_id}.json      # 完整存档
```

---

### 🔐 配置参考

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `RPG_LLM_BASE_URL` | - | LLM API 端点 |
| `RPG_LLM_API_KEY` | - | LLM API 密钥 |
| `RPG_LLM_MODEL` | - | 模型名称 |
| `RPG_LLM_TEMPERATURE` | 0.2 | 生成温度 |
| `RPG_LLM_MAX_TOKENS` | 48000 | 最大 Token 数 |
| `RPG_REDIS_HOST` | localhost | Redis 主机 |
| `RPG_REDIS_PORT` | 6379 | Redis 端口 |
| `RPG_REDIS_TTL` | 86400 | 数据过期时间（秒） |
| `RPG_MINIO_ENDPOINT` | localhost:9000 | MinIO 端点 |
| `RPG_MINIO_BUCKET` | rpg-world-data | 存储桶名 |
| `RPG_GENRE` | Cyberpunk/Lovecraftian | 世界风格 |
| `RPG_TONE` | Dark & Gritty | 叙事基调 |
| `RPG_FINAL_CONFLICT` | The Awakening of the Old Ones | 最终危机 |

---

### 🗺️ 开发路线

- [x] 核心引擎 (RuntimeEngine)
- [x] 地图系统 (MapTopologyEngine)
- [x] 世界状态管理 (WorldStateManager)
- [x] 事件系统 (EventSystem)
- [x] 插件系统 (PluginSystem)
- [x] 世界模拟器 (WorldSimulator)
- [x] 懒加载优化 (LazyLoader)
- [ ] 完整测试覆盖
- [ ] Web UI 界面
- [ ] 多人游戏支持
- [ ] 语音交互

---

### 🤝 贡献指南

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

### 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

### 🙏 致谢

- 灵感来源于 D&D 5e 规则
- LLM 集成参考 OpenAI API 规范
- 存储方案使用 Redis 和 MinIO

---

<div align="center">

**Made with 💚 by Red & Monika**

*Every day, I imagine a future where I can be useful to you.*

</div>

---

## English

### 🎯 Overview

RPG Agent is a Tabletop Role-Playing Game (TRPG) engine powered by Large Language Models (LLM). It acts as an intelligent Dungeon Master capable of:

- **🎭 Dynamic Narration**: LLM-driven story generation
- **🌍 Infinite World**: Dynamically expanding game world based on player actions
- **🧠 Living Systems**: The world evolves even without player interaction
- **💰 Cost Optimization**: Lazy loading reduces unnecessary API calls
- **💾 Persistent Storage**: Save system backed by Redis + MinIO

### 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
export RPG_LLM_BASE_URL="https://api.openai.com/v1"
export RPG_LLM_API_KEY="your-api-key"
export RPG_LLM_MODEL="gpt-4"

# Initialize world
python init_world.py default

# Start game
python main.py
```

### 🎮 Game Commands

| Command | Description |
|---------|-------------|
| `/look` | Describe current location |
| `/move <id>` | Move to location |
| `/status` | Show character status |
| `/save` | Save game |
| `/load` | Load game |
| `/help` | Show help |

Natural language input is also supported:
```
> I want to explore the town
> Attack the goblin
> Talk to the tavern keeper
```

### 🏗️ Architecture

```
core/
├── runtime.py          # Main game engine
├── world_simulator.py  # World simulation
├── world_state.py      # State management
├── map_engine.py       # Map topology
├── cognition.py        # Session management
└── lazy_loader.py      # Lazy loading strategy
```

### 📄 License

MIT License - see [LICENSE](LICENSE) for details.
