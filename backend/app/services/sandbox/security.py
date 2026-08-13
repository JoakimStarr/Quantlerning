"""练习沙箱静态安全过滤：AST 白名单检查（第一道防线）。

配合子进程隔离（python -I + 资源限制 + 超时）形成纵深防御。
本检查不追求对抗高级逃逸（如利用 pandas 内部对象），面向教学场景：
白名单库 pandas/numpy/math/statistics/random 等 + get_daily 只读数据对象。
"""
import ast

# 允许导入的顶层模块（用户代码只能 import 这些）
ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "random",
    "itertools",
    "functools",
    "collections",
    "datetime",
    "typing",
    "pandas",
    "numpy",
    "matplotlib",
}

# 禁用的内建函数调用
BANNED_BUILTINS = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
    "breakpoint", "help", "exit", "quit",
}

# 禁止访问的属性（经典元类逃逸链）
BANNED_ATTRS = {
    "__subclasses__", "__mro__", "__globals__", "__builtins__",
    "__class__", "__bases__", "__dict__", "__getattribute__", "__setattr__",
    "__reduce__", "__reduce_ex__",
}


def check_code(code: str) -> list[str]:
    """检查练习代码是否触碰安全红线。

    Returns:
        违规原因列表；空列表表示通过。语法错误也归入原因。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"语法错误：{e.msg}（第 {e.lineno} 行）"]

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    errors.append(f"禁止导入模块 {root}（仅允许 {', '.join(sorted(ALLOWED_IMPORTS))}）")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                errors.append("禁止相对导入")
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORTS:
                errors.append(f"禁止导入模块 {root}（仅允许 {', '.join(sorted(ALLOWED_IMPORTS))}）")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_BUILTINS:
                errors.append(f"禁止调用 {node.func.id}()")
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                errors.append(f"禁止访问 {node.attr}")
            if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
                errors.append("禁止访问 __builtins__")

    # 去重保序
    return list(dict.fromkeys(errors))
