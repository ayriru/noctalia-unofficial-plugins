# Noctalia Unofficial Plugins

Noctalia 桌面环境的非官方插件集合。

## 插件列表

| 插件 | 说明 | 版本 |
|------|------|------|
| PackageKit | 系统包管理工具 — 搜索、查询和更新系统软件包 | 0.0.2 |

## PackageKit 插件

### 功能

- 🔍 **搜索软件包** — 按关键词搜索可用包
- 📋 **查询详情** — 解析包名获取版本、架构、描述等信息
- 🔄 **检查更新** — 列出系统可用更新
- 🖥️ **托盘组件** — 状态栏图标显示更新数量，支持点击展开面板

### 目录结构

```
PackageKit/
├── manifest.json          # 插件清单
├── Main.qml               # 主面板 UI
├── BarWidget.qml           # 托盘组件 UI
├── i18n/
│   ├── en.json             # 英文翻译
│   └── zh-CN.json          # 中文翻译
└── scripts/
    ├── pkgkit.py           # Python 命令行工具 & 模块
    └── pkg.lua             # Lua 模块 (供 QML 调用)
```

### 使用方式 (CLI)

```bash
# 搜索包
python PackageKit/scripts/pkgkit.py search python

# 查询包详情
python PackageKit/scripts/pkgkit.py resolve bash vim

# 查看可用更新
python PackageKit/scripts/pkgkit.py list-update

# JSON 格式输出
python PackageKit/scripts/pkgkit.py --json search python
python PackageKit/scripts/pkgkit.py --compact --json list-update

# 使用过滤器
python PackageKit/scripts/pkgkit.py --filter=installed,newest search firefox
```

### 作为 Python 模块使用

```python
from PackageKit.scripts.pkgkit import search_packages, resolve_packages, list_update

# 搜索
packages = search_packages("python", verbose=False)

# 查询
details = resolve_packages(["bash", "coreutils"], as_json=True)

# 更新列表
updates = list_update(as_json=True)
```

## 许可证

MIT
