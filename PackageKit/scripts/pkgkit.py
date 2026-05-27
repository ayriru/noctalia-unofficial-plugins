#!/usr/bin/env python3
"""
PackageKit 包管理模块
====================
使用 PackageKit GLib 绑定查询软件包信息，可供其他 Python 程序 import 使用。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
架构说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本模块封装了 PackageKit 的 GLib 异步 API，统一使用以下模式调用：

    loop = GLib.MainLoop()        # 1. 创建事件循环
    task = Pk.Task()              # 2. 创建任务对象
    task.xxx_async(               # 3. 发起异步操作
        args...,
        None,                     # cancellable — 不支持取消
        on_progress,              # 进度回调 — 操作进行中多次调用
        (),                       # progress_user_data — 必须为 tuple
        on_done,                  # 完成回调 — 操作结束时调用一次
        (),                       # user_data — 必须为 tuple
    )
    loop.run()                    # 4. 阻塞等待，直到 loop.quit() 被调用

关键约束：
    - user_data 参数必须为 tuple（空元组用 ()），传 None 会报 TypeError
    - on_done 中必须调用 loop.quit()，否则 loop.run() 永不返回
    - on_done 中通过 task.generic_finish(result) 获取 Pk.Results
    - 所有 xxx_async 方法的回调签名一致：(source, result) 或 (progress, type)

使用方式:
    # 命令行
    python pkgkit.py search python            # 搜索包
    python pkgkit.py search python --json     # 搜索（JSON）
    python pkgkit.py resolve bash vim         # 查询指定包信息
    python pkgkit.py resolve bash vim --json  # 查询（JSON）
    python pkgkit.py list-update               # 查看可用更新
    python pkgkit.py list-update --json        # 更新（JSON）

    # 作为模块导入
    from pkgkit import resolve_packages, list_update, packages_to_json

    details = resolve_packages(["bash", "coreutils"])
    json_str = list_update(as_json=True)

依赖:
    - python-gobject (系统包，提供 gi 模块)
    - PackageKitGlib (PackageKit 的 GLib 绑定，包含 PackageKitGlib-1.0.typelib)
    - 运行环境需要系统 Python（虚拟环境可能缺少 gi 模块）

公开 API:
    - resolve_packages(names, as_json=False, verbose=True)
    - list_update(filters=0, as_json=False, verbose=True)
    - search_packages(keyword, filters=0, as_json=False, verbose=True)
    - package_to_dict(pkg)
    - packages_to_json(packages, indent=2)
"""

import gi
# 指定 API 版本，必须在 import gi.repository 之前调用
gi.require_version('PackageKitGlib', '1.0')
from gi.repository import PackageKitGlib as Pk
from gi.repository import GLib
import json
import argparse

# 声明模块公开的 API，方便 IDE 补全和 from pkgkit import *
__all__ = [
    "resolve_packages",
    "list_update",
    "search_packages",
    "package_to_dict",
    "packages_to_json",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════


def package_to_dict(pkg):
    """
    将 Pk.Package 对象转换为字典，包含所有关键字段。

    转换的字段:
        id              — 完整包标识符 (name;version;arch;repo)
        name            — 包名
        version         — 版本号
        arch            — 架构 (x86_64 / any 等)
        summary         — 简要描述
        info            — 包状态枚举名称 (INSTALLED / AVAILABLE / UPDATING 等)
        update_severity — 更新严重级别枚举名称 (NONE / LOW / NORMAL / IMPORTANT / CRITICAL 等)

    参数:
        pkg: Pk.Package 对象

    返回:
        dict: 包含包信息的字典
    """
    return {
        "id": pkg.get_id(),
        "name": pkg.get_name(),
        "version": pkg.get_version(),
        "arch": pkg.get_arch(),
        "summary": pkg.get_summary() or "",
        # GObject 枚举的 .value_nick 返回蛇形命名（如 "installed", "normal"）
        # 与 .value_name（大写下划线）不同，更适合 JSON 输出
        "info": pkg.get_info().value_nick if pkg.get_info() else "UNKNOWN",
        "update_severity": pkg.get_update_severity().value_nick if pkg.get_update_severity() else "NONE",
    }


def packages_to_json(packages, indent=2):
    """
    将 Package 对象列表转换为格式化的 JSON 字符串。

    参数:
        packages: list[Pk.Package] 包对象列表
        indent: JSON 缩进空格数，None 表示紧凑输出

    返回:
        str: JSON 字符串
    """
    return json.dumps(
        [package_to_dict(p) for p in packages],
        ensure_ascii=False,
        indent=indent,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 包查询函数 — 三个函数共享相同的 GLib 异步回调模式
#
# 模式要点:
#   ┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
#   │ loop.run()   │ ──→ │ PackageKit 守护进程 │ ──→ │ on_progress()   │
#   │ (阻塞等待)    │ ←── │ (DBus 通信)        │ ←── │ (多次调用)       │
#   └─────────────┘     └──────────────────┘     └─────────────────┘
#          ↑                                              │
#          │         ┌──────────────────┐                 │
#          └──────── │  on_done()       │ ←───────────────┘
#    loop.quit()     │  (调用一次)       │
#                    └──────────────────┘
#
# 关于 packages 变量的双重收集:
#   on_progress 通过 .append() 收集中间结果（某些操作会触发 PACKAGE 事件）
#   on_done     通过 = 赋值覆盖（最终结果以 get_package_array() 为准）
#   因此 on_done 中使用 nonlocal packages 直接替换整个列表
# ═══════════════════════════════════════════════════════════════════════════════

import signal
from typing import Any, Callable, Optional


def _collect_packages_sync(
    async_starter: Callable[[Pk.Task, Callable, Callable], None],
    *,
    verbose: bool = False,
    progress_label: str = "",
    done_message: str = "",
    timeout_ms: int = 30000,
) -> list[Any]:
    """
    通用的 PackageKit 异步操作封装器。

    封装 GLib 异步调用模式：创建 MainLoop → 发起 async 操作 →
    等待完成 → 收集结果。三个主函数（resolve_packages, list_update,
    search_packages）通过此辅助函数复用相同的回调逻辑。

    参数:
        async_starter: 接收 (task, progress_cb, done_cb) 并调用对应
                       xxx_async 方法的函数
        verbose: 是否打印进度信息
        progress_label: verbose 模式下进度的前缀标签
        done_message: verbose 模式下完成时的提示信息
        timeout_ms: 超时时间（毫秒），默认 30 秒

    返回:
        list[Pk.Package]: 收集到的 Package 对象列表
    """
    loop = GLib.MainLoop()
    task = Pk.Task()
    packages: list[Any] = []
    timed_out = False

    def on_progress(progress: Any, progress_type: Any, *user_data: Any) -> None:
        """进度回调：收集每个 PACKAGE 类型的中间结果"""
        nonlocal packages
        if progress_type == Pk.ProgressType.PACKAGE:
            pkg = progress.get_package()
            if pkg:
                packages.append(pkg)

    def on_done(source: Any, result: Any, *user_data: Any) -> None:
        """完成回调：提取最终结果并退出事件循环"""
        nonlocal packages
        try:
            final = task.generic_finish(result)
            code = final.get_exit_code()
            if code is not None and code != Pk.ExitEnum.SUCCESS:
                print(f"{progress_label}结束，退出码: {code}")
            result_packages = list(final.get_package_array())
            if result_packages:
                packages = result_packages
            if verbose and done_message:
                print(done_message.format(count=len(packages)))
        except Exception as e:
            print(f"{progress_label}出错: {e}")
        finally:
            loop.quit()

    # 超时保护：防止 DBus 无响应导致进程挂起
    def _on_timeout():
        nonlocal timed_out
        timed_out = True
        _cancel(loop, task)
        return False

    timeout_id = GLib.timeout_add(timeout_ms, _on_timeout)

    try:
        async_starter(task, on_progress, on_done)
        loop.run()
    finally:
        # 清理超时定时器（如果事件循环已正常退出）
        if not timed_out:
            GLib.source_remove(timeout_id)

    return packages


def _cancel(loop: GLib.MainLoop, task: Pk.Task) -> None:
    """超时时的清理操作：取消任务并退出事件循环"""
    try:
        task.cancel()
    except Exception:
        pass
    try:
        loop.quit()
    except Exception:
        pass


def resolve_packages(
    package_names: list[str],
    as_json: bool = False,
    verbose: bool = True,
) -> list[Any] | str:
    """
    根据包名列表，查询并返回包的详细信息。

    参数:
        package_names: 包名列表，如 ["bash", "coreutils"]
        as_json:       True 返回 JSON 字符串，False 返回 list[Pk.Package]
        verbose:       True 时打印进度信息（导入为模块时建议设为 False）

    返回:
        list[Pk.Package] 或 str: Package 对象列表，或 JSON 字符串
    """
    if verbose:
        print(f"正在解析包: {', '.join(package_names)}")

    packages = _collect_packages_sync(
        lambda task, on_progress, on_done: task.resolve_async(
            0,
            list(package_names),
            None,
            on_progress,
            (),
            on_done,
            (),
        ),
        verbose=verbose,
        progress_label="解析",
        done_message="成功获取 {count} 个包的详细信息",
    )
    return packages_to_json(packages) if as_json else packages


def list_update(
    filters: int = 0,
    as_json: bool = False,
    verbose: bool = True,
) -> list[Any] | str:
    """
    获取所有可用更新的包列表。

    参数:
        filters: 位掩码过滤标志，0 表示不过滤（获取所有更新）
        as_json: True 返回 JSON 字符串，False 返回 list[Pk.Package]
        verbose: True 时打印进度信息（导入为模块时建议设为 False）

    返回:
        list[Pk.Package] 或 str: 可更新的包对象列表，或 JSON 字符串
    """
    if verbose:
        print("正在查询可用更新...")

    packages = _collect_packages_sync(
        lambda task, on_progress, on_done: task.get_updates_async(
            filters,
            None,
            on_progress,
            (),
            on_done,
            (),
        ),
        verbose=verbose,
        progress_label="更新查询",
        done_message="共 {count} 个可用更新",
    )
    return packages_to_json(packages) if as_json else packages


def search_packages(
    keyword: str,
    filters: int = 0,
    as_json: bool = False,
    verbose: bool = True,
) -> list[Any] | str:
    """
    按关键词搜索包。

    参数:
        keyword: 搜索关键词
        filters: 位掩码过滤标志，0 表示不过滤
        as_json: True 返回 JSON 字符串，False 返回 list[Pk.Package]
        verbose: True 时打印进度信息

    返回:
        list[Pk.Package] 或 str
    """
    if verbose:
        print(f"搜索关键词: {keyword}")

    packages = _collect_packages_sync(
        lambda task, on_progress, on_done: task.search_names_async(
            filters,
            [keyword],
            None,
            on_progress,
            (),
            on_done,
            (),
        ),
        verbose=verbose,
        progress_label="搜索",
        done_message="搜索到 {count} 个包",
    )
    return packages_to_json(packages) if as_json else packages


# ═══════════════════════════════════════════════════════════════════════════════
# 命令行接口 — argparse 子命令模式
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="PackageKit 包管理工具 —— 查询包信息和可用更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 子命令: 必须指定 search / detail / updates 之一
    sub = parser.add_subparsers(dest="command", help="子命令")

    # 全局选项（在子命令之前），适用于所有子命令
    parser.add_argument(
        "--help-filter", action="store_true",
        help="显示过滤器参考（--filter 可用值列表）",
    )
    # 详细说明见 --help-filter
    parser.add_argument(
        "--filter", dest="filter_str", default="none",

        help="包过滤器（默认为 none ） ，使用逗号分隔（如 installed,newest），前缀 ~ 取反；见 --help-filter"
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON 格式输出")
    parser.add_argument("--compact", action="store_true", help="紧凑 JSON（配合 --json）")


    # ---- search ----
    p_search = sub.add_parser("search", help="按关键词搜索包")
    p_search.add_argument("keyword", nargs="?", help="搜索关键词")

    # ---- resolve ----
    p_resolve = sub.add_parser("resolve", help="解析软件包名")
    p_resolve.add_argument("packages", nargs="*", help="包名（可多个），如 bash vim")

    # ---- list-update ----
    p_updates = sub.add_parser("list-update", help="查询可用更新列表")
    p_updates.add_argument("--count", action="store_true",
                           help="仅显示更新数量，不列出具体包")

    # 解析参数，无子命令时显示帮助
    args = parser.parse_args()

    if args.help_filter:
        print("""\
Filter 位掩码参考
================

  PackageKit 使用位掩码过滤结果，多个过滤器用逗号组合。
  前缀 ~ 表示取反，也支持 0x 十六进制位掩码。

  用法示例:
    --filter installed               仅已安装
    --filter ~installed              仅未安装
    --filter installed,newest        已安装且最新版
    --filter installed,free,gui      已安装的自由 GUI 应用
    --filter ~devel,~source,arch     排除开发包和源码包
    --filter 0x3                     十六进制 (installed|~installed)

  --------------------------------------------------------
  none          0x01       无过滤（默认），等价于不指定 --filter
  installed     0x02       仅已安装的包
  ~installed    0x04       仅未安装的包
  newest        0x10000    仅每个包的最新版本
  ~newest       0x20000    显示所有版本（含旧版）
  arch          0x40000    仅匹配当前 CPU 架构 (x86_64 / any)
  ~arch         0x80000    不限制架构
  devel         0x10       仅开发包 (*.so, *.a, -dev 等)
  ~devel        0x20       排除开发包
  gui           0x40       仅 GUI 应用（含 .desktop 文件）
  ~gui          0x80       排除 GUI 应用
  free          0x100      仅自由/开源软件 (FSF/OSI 认证)
  ~free         0x200      仅非自由软件
  visible       0x400      仅可见（非隐藏）的包
  ~visible      0x800      仅隐藏的包
  supported     0x1000     仅受发行版官方支持的包
  ~supported    0x2000     仅社区维护 / AUR 等
  basename      0x4000     仅按包名精确匹配
  ~basename     0x8000     模糊匹配（默认行为）
  source        0x100000   仅源码包
  ~source       0x200000   排除源码包
  collections   0x400000   仅集合/元包 (package groups)
  ~collections  0x800000   排除集合/元包
  application   0x1000000  仅应用程序 (.desktop)
  ~application  0x2000000  排除应用程序
  downloaded    0x4000000  仅已下载（缓存中存在）
  ~downloaded   0x8000000  仅未下载的包
  --------------------------------------------------------""")
        exit(0)

    if args.command is None:
        parser.print_help()
        exit(0)

    # ── 解析 --filter 字符串 → 位掩码整数 ──
    # Pk.filter_bitfield_from_string() 将 "installed,newest" 按位或为 0x10002
    # 同时支持十六进制 (0x3) 或十进制 (3) 数字字面量
    # ~ 前缀转换为 NOT_ 枚举: ~installed → NOT_INSTALLED (0x04)
    filter_str = args.filter_str
    try:
        if filter_str.startswith("0x") or filter_str.startswith("0X"):
            filters = int(filter_str, 16)          # 十六进制位掩码
        elif filter_str.isdigit() or (filter_str.startswith("-") and filter_str[1:].isdigit()):
            filters = int(filter_str)              # 十进制位掩码
        else:
            filters = Pk.filter_bitfield_from_string(filter_str)  # 名称 → 位掩码
    except Exception:
        print(f"无效的过滤器: {filter_str}")
        exit(1)

    # ── JSON 缩进 ──
    json_indent = None if args.compact else 2

    # verbose 策略: JSON 输出时静默，可读模式时打印进度
    is_verbose = not args.json_output

    if args.command == "search":
        if not args.keyword:
            print("错误: 缺少搜索关键词")
            print("用法: pkgkit.py [全局选项] search <关键词>")
            print("示例: pkgkit.py search python")
            print("      pkgkit.py --filter=installed search firefox")
            exit(1)
        pkgs = search_packages(args.keyword, filters=filters, verbose=is_verbose)
        if args.json_output:
            print(packages_to_json(pkgs, indent=json_indent))
        elif pkgs:
            print(f"\n搜索到 {len(pkgs)} 个包:")
            for pkg in pkgs:
                print(f"  {pkg.get_name():30s} {pkg.get_version():20s} [{pkg.get_arch()}]")
                s = pkg.get_summary()
                if s:
                    print(f"    {s}")
        else:
            print("未找到匹配的包")

    elif args.command == "resolve":
        if not args.packages:
            print("错误: 缺少包名")
            print("用法: pkgkit.py [全局选项] resolve [包名 ...]")
            print("示例: pkgkit.py resolve bash")
            print("      pkgkit.py resolve vim git")
            exit(1)
        pkgs = resolve_packages(args.packages, verbose=is_verbose)
        if args.json_output:
            print(packages_to_json(pkgs, indent=json_indent))
        elif pkgs:
            print(f"\n找到 {len(pkgs)} 个包:")
            for pkg in pkgs:
                print(f"  {pkg.get_name():30s} {pkg.get_version():20s} [{pkg.get_arch()}]")
                s = pkg.get_summary()
                if s:
                    print(f"    {s}")
        else:
            print("未找到匹配的包")

    elif args.command == "list-update":
        pkgs = list_update(filters=filters, verbose=is_verbose and not args.count)
        if args.json_output:
            print(packages_to_json(pkgs, indent=json_indent))
        elif args.count:
            print(len(pkgs))
        elif pkgs:
            print(f"\n共 {len(pkgs)} 个可用更新:")
            for pkg in pkgs:
                print(f"  {pkg.get_name():30s} {pkg.get_version()}")
        else:
            print("没有可用更新")
    

