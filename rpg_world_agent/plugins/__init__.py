"""
Plugin System - 插件目录

这个目录包含所有通过插件系统扩展的功能模块。

每个插件应该：
1. 继承自 Plugin 基类
2. 实现必需的生命周期方法（on_load, on_unload）
3. 可以注册命令、LLM工具、事件监听器等
4. 使用 @plugin 装饰器声明元数据
"""

from .magic_system import get_plugin

__all__ = ['get_plugin']