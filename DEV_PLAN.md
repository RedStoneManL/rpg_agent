# RPG Agent 开发计划

## 项目目标
完成一个基于 LLM 的 DM（Dungeon Master）跑团游戏引擎，能够：
1. 跑一局完整的游戏
2. 动态扩张世界
3. 使用懒加载机制节省 API 成本
4. 整个世界是"活的"——玩家之外也有发展

---

## 当前状态分析

### ✅ 已有功能
- 地图系统 (MapTopologyEngine) - 图结构地图，支持动态子位置
- 玩家状态管理 (CognitionSystem) - HP/SAN/位置/标签/技能
- 世界状态管理 (WorldStateManager) - 时间/危机等级/区域状态/NPC状态/任务状态
- 事件系统 (EventSystem) - 事件记录和查询
- 插件系统 (PluginSystem) - 可扩展的插件架构
- 上下文加载器 (ContextLoader) - 基于条件的内容加载
- LLM 驱动的 DM 响应 - 意图分析/动作判定/叙事生成
- 存档/读档功能 - Redis + MinIO

### ❌ 缺失功能
1. **世界模拟系统** - 让世界在玩家之外也有发展（NPC移动、事件发生）
2. **懒加载策略** - ContextLoader 存在但没有真正的懒加载策略实现
3. **完整测试覆盖** - 现有测试约 2000 行，覆盖率不足
4. **完整游戏流程验证** - 需要端到端测试确保能跑完一局游戏

---

## 开发任务

### Phase 1: 世界模拟系统 (World Simulation)
**目标**: 让世界在玩家之外也有发展

#### 1.1 WorldSimulator 类
```python
# rpg_world_agent/core/world_simulator.py
class WorldSimulator:
    """世界模拟器 - 在玩家不活动时推进世界发展"""
    
    def simulate_tick(self, minutes: int) -> List[WorldEvent]:
        """模拟一段时间内的世界发展"""
        events = []
        # NPC 移动
        # 事件发生
        # 危机等级变化
        return events
    
    def simulate_npc_activities(self) -> List[NPCActivity]:
        """模拟 NPC 活动"""
        pass
    
    def simulate_world_events(self) -> List[WorldEvent]:
        """模拟世界事件（战争、灾难、发现等）"""
        pass
```

#### 1.2 NPC AI 系统
```python
# rpg_world_agent/core/npc_ai.py
class NPCAI:
    """NPC AI - 让 NPC 有自己的目标和行为"""
    
    def decide_action(self, npc: NPCState, world_context: Dict) -> NPCAction:
        """决定 NPC 的下一个行动"""
        pass
    
    def execute_action(self, action: NPCAction) -> ActionResult:
        """执行 NPC 行动"""
        pass
```

#### 1.3 世界事件生成器
```python
# rpg_world_agent/core/world_events.py
class WorldEventGenerator:
    """生成玩家之外的世界事件"""
    
    def generate_random_event(self, world_state: Dict) -> Optional[WorldEvent]:
        """基于当前世界状态生成随机事件"""
        pass
    
    def generate_crisis_progression(self) -> Optional[CrisisEvent]:
        """推进危机事件"""
        pass
```

### Phase 2: 懒加载优化
**目标**: 减少不必要的 LLM 调用

#### 2.1 LazyLoadingStrategy 类
```python
# rpg_world_agent/core/lazy_loader.py
class LazyLoadingStrategy:
    """懒加载策略"""
    
    def should_generate_content(self, context: LoadContext) -> bool:
        """判断是否应该生成新内容"""
        # 检查缓存
        # 检查相似内容
        # 检查 API 调用频率
        pass
    
    def get_cached_or_generate(self, key: str, generator: Callable) -> Any:
        """获取缓存或生成新内容"""
        pass
```

#### 2.2 内容缓存系统
```python
# rpg_world_agent/core/content_cache.py
class ContentCache:
    """内容缓存 - 存储生成的地点/NPC/物品"""
    
    def get_similar_content(self, query: str, threshold: float = 0.8) -> Optional[Dict]:
        """查找相似内容"""
        pass
    
    def store_content(self, content: Dict) -> str:
        """存储生成的内容"""
        pass
```

### Phase 3: 测试覆盖
**目标**: Extensive tests

#### 3.1 单元测试
- [ ] WorldSimulator 测试
- [ ] NPCAI 测试
- [ ] WorldEventGenerator 测试
- [ ] LazyLoadingStrategy 测试
- [ ] ContentCache 测试

#### 3.2 集成测试
- [ ] 完整游戏流程测试
- [ ] 世界模拟集成测试
- [ ] 懒加载集成测试

#### 3.3 端到端测试
- [ ] 完整游戏会话测试（从创建到结束）

### Phase 4: 游戏流程优化
**目标**: 确保能跑一局完整游戏

#### 4.1 游戏结束条件
- 玩家死亡 (HP <= 0)
- 玩家发疯 (SAN <= 0)
- 主线任务完成
- 特定危机解决

#### 4.2 游戏进度跟踪
- 任务进度
- 危机进度
- 世界状态变化历史

---

## 文件结构

```
rpg_world_agent/
├── core/
│   ├── runtime.py          # 主引擎 (已有)
│   ├── world_simulator.py  # 🆕 世界模拟器
│   ├── npc_ai.py           # 🆕 NPC AI
│   ├── world_events.py     # 🆕 世界事件生成
│   ├── lazy_loader.py      # 🆕 懒加载策略
│   ├── content_cache.py    # 🆕 内容缓存
│   └── ... (其他已有模块)
├── tests/
│   ├── test_core/
│   │   ├── test_world_simulator.py  # 🆕
│   │   ├── test_npc_ai.py           # 🆕
│   │   ├── test_world_events.py     # 🆕
│   │   ├── test_lazy_loader.py      # 🆕
│   │   └── test_game_flow.py        # 🆕 端到端测试
│   └── ... (其他已有测试)
```

---

## 实现优先级

1. **P0 - 必须完成**
   - [ ] 世界模拟系统基础
   - [ ] 完整游戏流程测试
   - [ ] 基础懒加载

2. **P1 - 重要**
   - [ ] NPC AI 系统
   - [ ] 内容缓存
   - [ ] 更多测试

3. **P2 - 可选**
   - [ ] 高级懒加载策略
   - [ ] 性能优化
   - [ ] 更多世界事件类型

---

## 成功标准

1. ✅ 能跑一局完整的游戏（从创建角色到游戏结束）
2. ✅ 世界在玩家之外也有发展（NPC 移动、事件发生）
3. ✅ 懒加载机制减少不必要的 API 调用
4. ✅ 测试覆盖率 > 60%
