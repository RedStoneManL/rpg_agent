"""
Plugin System - 可扩展的插件架构

这个系统允许你动态添加新的游戏功能模块，如：
- 魔法系统
- 战斗系统
- 经济系统
- 任务系统
- 等等...

每个插件都可以：
1. 注册自己的事件监听器
2. 提供新的命令/动作
3. 扩展玩家状态
4. 修改世界生成
5. 添加新的LLM工具
"""

from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import inspect

from rpg_world_agent.core.event_system import EventSystem, EventData, EventType, EventListener
from rpg_world_agent.data.llm_client import get_llm_client

# 为了避免循环导入
if TYPE_CHECKING:
    from core.runtime import RuntimeEngine


class PluginLifecycle(Enum):
    """插件生命周期状态"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    ERROR = "error"


class PluginHookType(Enum):
    """插件钩子点"""
    # 玩家相关
    ON_PLAYER_CREATED = "on_player_created"
    ON_PLAYER_MOVED = "on_player_moved"
    ON_PLAYER_STATE_CHANGED = "on_player_state_changed"

    # 游戏回合相关
    ON_TURN_START = "on_turn_start"
    ON_TURN_END = "on_turn_end"
    ON_BEFORE_ACTION = "on_before_action"
    ON_AFTER_ACTION = "on_after_action"

    # 世界相关
    ON_WORLD_GENERATED = "on_world_generated"
    ON_LOCATION_ENTERED = "on_location_entered"
    ON_LOCATION_EXITED = "on_location_exited"

    # 响应相关
    ON_NARRATION_GENERATED = "on_narration_generated"

    # 存档相关
    ON_SAVE = "on_save"
    ON_LOAD = "on_load"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    author: str
    description: str
    dependencies: List[str] = field(default_factory=list)

    # 插件能力标记
    provides_commands: List[str] = field(default_factory=list)
    provides_state_fields: List[str] = field(default_factory=list)
    provides_llm_tools: List[str] = field(default_factory=list)
    provides_abilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "dependencies": self.dependencies,
            "provides_commands": self.provides_commands,
            "provides_state_fields": self.provides_state_fields,
            "provides_llm_tools": self.provides_llm_tools,
            "provides_abilities": self.provides_abilities
        }


@dataclass
class PluginCommand:
    """插件提供的命令定义"""
    name: str
    description: str
    handler: Callable[[str, 'RuntimeEngine'], str]
    aliases: List[str] = field(default_factory=list)
    requires_params: bool = False


@dataclass
class LLMTool:
    """LLM工具定义"""
    name: str
    description: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    parameters: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """
    插件基类

    所有插件必须继承此类并实现必需的方法。
    插件可以通过钩子、命令、事件监听器等方式与引擎交互。
    """

    # 子类必须定义这些
    metadata: PluginMetadata

    def __init__(self):
        self._lifecycle = PluginLifecycle.UNLOADED
        self._event_listeners: List[EventListener] = []
        self._hooks: Dict[PluginHookType, List[Callable]] = {}
        self._commands: Dict[str, PluginCommand] = {}
        self._llm_tools: Dict[str, LLMTool] = {}

    # =========================================================================
    # 🔗 生命周期方法 - 插件必须实现
    # =========================================================================

    @abstractmethod
    def on_load(self, engine: 'RuntimeEngine') -> None:
        """插件加载时调用，用于初始化插件"""
        pass

    @abstractmethod
    def on_unload(self, engine: 'RuntimeEngine') -> None:
        """插件卸载时调用，用于清理资源"""
        pass

    # =========================================================================
    # ⚙️ 钩子系统 - 插件可以重写这些方法
    # =========================================================================

    def on_player_created(self, player_id: str, location: str) -> None:
        """玩家创建时调用"""
        pass

    def on_player_moved(self, player_id: str, from_loc: str, to_loc: str) -> None:
        """玩家移动时调用"""
        pass

    def on_before_action(
        self,
        user_input: str,
        player_state: Dict[str, Any]
    ) -> Optional[str]:
        """动作执行前调用，返回None继续执行，返回字符串则中止并显示消息"""
        return None

    def on_after_action(
        self,
        user_input: str,
        player_state: Dict[str, Any],
        response: str
    ) -> Optional[str]:
        """动作执行后调用，可以修改响应或返回None"""
        return None

    def on_narration_generated(
        self,
        narrative: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """叙事生成后调用，可以修改叙事内容"""
        return None

    def on_save(self, save_data: Dict[str, Any]) -> Dict[str, Any]:
        """存档时调用，可以添加额外的存档数据"""
        return save_data

    def on_load(self, load_data: Dict[str, Any]) -> None:
        """读档时调用，从存档数据中读取插件数据"""
        pass

    # =========================================================================
    # 🎮 命令系统
    # =========================================================================

    def register_command(self, command: PluginCommand) -> None:
        """注册命令"""
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def get_command(self, name: str) -> Optional[PluginCommand]:
        """获取命令"""
        return self._commands.get(name)

    def get_all_commands(self) -> Dict[str, PluginCommand]:
        """获取所有命令"""
        return self._commands.copy()

    # =========================================================================
    # 🤖 LLM工具系统
    # =========================================================================

    def register_llm_tool(self, tool: LLMTool) -> None:
        """注册LLM工具"""
        self._llm_tools[tool.name] = tool
        self.metadata.provides_llm_tools.append(tool.name)

    def get_llm_tool(self, name: str) -> Optional[LLMTool]:
        """获取LLM工具"""
        return self._llm_tools.get(name)

    def get_all_llm_tools(self) -> Dict[str, LLMTool]:
        """获取所有LLM工具"""
        return self._llm_tools.copy()

    # =========================================================================
    # 👂 事件监听
    # =========================================================================

    def register_event_listener(
        self,
        event_system: EventSystem,
        event_types: List[EventType],
        handler: Callable[[EventData], None]
    ) -> None:
        """注册事件监听器"""
        listener = EventListener(event_types, handler, priority=10)
        event_system.register_listener(listener)
        self._event_listeners.append(listener)

    # =========================================================================
    # 📊 状态管理
    # =========================================================================

    def get_plugin_state(self, player_state: Dict[str, Any]) -> Dict[str, Any]:
        """从玩家状态中获取插件专属数据"""
        plugin_data = player_state.get(f"plugin_{self.metadata.name}", {})
        return plugin_data if isinstance(plugin_data, dict) else {}

    def set_plugin_state(
        self,
        player_state: Dict[str, Any],
        state: Dict[str, Any]
    ) -> None:
        """设置插件专属数据到玩家状态"""
        player_state[f"plugin_{self.metadata.name}"] = state

    # =========================================================================
    # 🔧 工具方法
    # =========================================================================

    @property
    def lifecycle(self) -> PluginLifecycle:
        return self._lifecycle

    def mark_loaded(self) -> None:
        self._lifecycle = PluginLifecycle.LOADED

    def mark_unloading(self) -> None:
        self._lifecycle = PluginLifecycle.UNLOADING

    def mark_unloaded(self) -> None:
        self._lifecycle = PluginLifecycle.UNLOADED

    def mark_error(self) -> None:
        self._lifecycle = PluginLifecycle.ERROR


class PluginManager:
    """
    插件管理器

    负责插件的加载、卸载、调度和管理
    """

    _instance: Optional['PluginManager'] = None

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._enabled_plugins: List[str] = []

    @classmethod
    def get_instance(cls) -> 'PluginManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = PluginManager()
        return cls._instance

    def register_plugin(self, plugin: Plugin) -> None:
        """
        注册插件（但不加载）

        Args:
            plugin: 插件实例
        """
        name = plugin.metadata.name
        if name in self._plugins:
            raise ValueError(f"插件 '{name}' 已经注册")

        self._plugins[name] = plugin

    def load_plugin(
        self,
        plugin_name: str,
        engine: 'RuntimeEngine'
    ) -> bool:
        """
        加载插件

        Args:
            plugin_name: 插件名称
            engine: 游戏引擎实例

        Returns:
            bool: 加载成功返回True
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            print(f"❌ 插件 '{plugin_name}' 未找到")
            return False

        if plugin.lifecycle == PluginLifecycle.LOADED:
            print(f"⚠️ 插件 '{plugin_name}' 已经加载")
            return True

        try:
            print(f"🔌 正在加载插件: {plugin.metadata.name} v{plugin.metadata.version}")
            plugin.on_load(engine)
            plugin.mark_loaded()
            self._enabled_plugins.append(plugin_name)
            print(f"✅ 插件 '{plugin_name}' 加载成功")
            return True
        except Exception as e:
            plugin.mark_error()
            print(f"❌ 插件 '{plugin_name}' 加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_all_plugins(self, engine: 'RuntimeEngine') -> None:
        """加载所有已注册的插件"""
        for name, plugin in self._plugins.items():
            self.load_plugin(name, engine)

    def unload_plugin(
        self,
        plugin_name: str,
        engine: 'RuntimeEngine'
    ) -> bool:
        """
        卸载插件

        Args:
            plugin_name: 插件名称
            engine: 游戏引擎实例

        Returns:
            bool: 卸载成功返回True
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return False

        if plugin.lifecycle != PluginLifecycle.LOADED:
            return False

        try:
            plugin.mark_unloading()
            plugin.on_unload(engine)
            plugin.mark_unloaded()
            if plugin_name in self._enabled_plugins:
                self._enabled_plugins.remove(plugin_name)
            print(f"✅ 插件 '{plugin_name}' 已卸载")
            return True
        except Exception as e:
            print(f"❌ 插件 '{plugin_name}' 卸载失败: {e}")
            return False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """获取插件实例"""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """获取所有插件"""
        return self._plugins.copy()

    def get_enabled_plugins(self) -> List[Plugin]:
        """获取已启用（加载）的插件"""
        return [
            self._plugins[name] for name in self._enabled_plugins
            if name in self._plugins
        ]

    def get_plugin_metadata(self, name: str) -> Optional[PluginMetadata]:
        """获取插件元数据"""
        plugin = self._plugins.get(name)
        return plugin.metadata if plugin else None

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """获取所有插件的元数据"""
        return [
            plugin.metadata.to_dict()
            for plugin in self._plugins.values()
        ]

    # =========================================================================
    # 🎮 命令调度
    # =========================================================================

    def get_command_handler(
        self,
        command_name: str
    ) -> Optional[Callable[[str, 'RuntimeEngine'], str]]:
        """从所有启用的插件中获取命令处理器"""
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin:
                command = plugin.get_command(command_name)
                if command:
                    return command.handler
        return None

    def get_all_commands(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件提供的命令"""
        result = {}
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin:
                for name, cmd in plugin.get_all_commands().items():
                    if name not in result:  # 避免覆盖
                        result[name] = {
                            "description": cmd.description,
                            "plugin": plugin_name,
                            "aliases": cmd.aliases,
                            "requires_params": cmd.requires_params
                        }
        return result

    # =========================================================================
    # 🤖 LLM工具调度
    # =========================================================================

    def execute_llm_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        执行LLM工具

        Args:
            tool_name: 工具名称
            parameters: 参数字典

        Returns:
            工具执行结果，如果工具不存在返回None
        """
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin:
                tool = plugin.get_llm_tool(tool_name)
                if tool:
                    try:
                        return tool.handler(parameters)
                    except Exception as e:
                        return {
                            "success": False,
                            "error": str(e)
                        }
        return None

    def get_all_llm_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用的LLM工具"""
        tools = []
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin:
                for name, tool in plugin.get_all_llm_tools().items():
                    tools.append({
                        "name": f"{plugin_name}.{name}" if hasattr(tool, 'name') else name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "plugin": plugin_name
                    })
        return tools

    # =========================================================================
    # 🔩 钩子调度
    # =========================================================================

    def invoke_hook(
        self,
        hook_type: PluginHookType,
        *args,
        **kwargs
    ) -> List[Any]:
        """
        调用所有启用的插件中的指定钩子

        Args:
            hook_type: 钩子类型
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            List[Any]: 所有插件的返回值列表
        """
        results = []
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin and plugin.lifecycle == PluginLifecycle.LOADED:
                # 获取钩子方法
                method = getattr(plugin, hook_type.value, None)
                if method and callable(method):
                    try:
                        result = method(*args, **kwargs)
                        results.append(result)
                    except Exception as e:
                        print(f"⚠️ 插件 '{plugin_name}' 的钩子 {hook_type.value} 执行失败: {e}")
        return results

    def invoke_hook_first(
        self,
        hook_type: PluginHookType,
        *args,
        **kwargs
    ) -> Any:
        """
        调用钩子并返回第一个非None的值

        用于某些钩子（如on_before_action）需要提前中止的情况
        """
        for plugin_name in self._enabled_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin and plugin.lifecycle == PluginLifecycle.LOADED:
                method = getattr(plugin, hook_type.value, None)
                if method and callable(method):
                    try:
                        result = method(*args, **kwargs)
                        if result is not None:
                            return result
                    except Exception as e:
                        print(f"⚠️ 插件 '{plugin_name}' 的钩子 {hook_type.value} 执行失败: {e}")
        return None


# ============================================================================
# 📦 插件装饰器 - 便捷的插件注册方式
# ============================================================================

def plugin(
    name: str,
    version: str = "1.0.0",
    author: str = "Unknown",
    description: str = ""
):
    """
    插件类装饰器

    用法:
        @plugin(name="MagicSystem", version="1.0.0", author="You")
        class MagicPlugin(Plugin):
            ...
    """
    def decorator(cls: Type[Plugin]) -> Type[Plugin]:
        # 创建元数据并赋值给类
        cls.metadata = PluginMetadata(
            name=name,
            version=version,
            author=author,
            description=description
        )
        return cls
    return decorator


def command(
    name: str,
    description: str,
    aliases: Optional[List[str]] = None,
    requires_params: bool = False
):
    """
    命令方法装饰器

    用法:
        @command("cast", "施放法术", aliases=["c"], requires_params=True)
        def handle_cast(self, params: str, engine: RuntimeEngine) -> str:
            ...
    """
    def decorator(method: Callable) -> Callable:
        if not hasattr(method, "_plugin_commands"):
            method._plugin_commands = []
        method._plugin_commands.append({
            "name": name,
            "description": description,
            "aliases": aliases or [],
            "requires_params": requires_params
        })
        return method
    return decorator


def llm_tool(name: str, description: str):
    """
    LLM工具方法装饰器

    用法:
        @llm_tool("check_mana", "检查法力值")
        def check_mana(self, params: Dict[str, Any]) -> Dict[str, Any]:
            ...
    """
    def decorator(method: Callable) -> Callable:
        if not hasattr(method, "_llm_tools"):
            method._llm_tools = []
        method._llm_tools.append({
            "name": name,
            "description": description,
            "method": method
        })
        return method
    return decorator