--[[
  main.lua — PackageKit Lua 后端入口 / 示例
  ══════════════════════════════════════════════════════════
  用途:
    - 作为独立脚本运行，测试 pkg.lua 模块是否正常工作
    - 演示 pkg.lua 的 list_updates() API 用法

  运行:
    lua main.lua

  注意:
    需要系统安装 lgi 包（Lua GObject Introspection 绑定）
    以及 PackageKitGlib-1.0.typelib（PackageKit GLib 类型信息）
--]]

-- 加载同目录下的 pkg 模块（pkg.lua）
local pkg = require("./pkg")

-- 查询系统可用更新列表
-- 底层通过 GLib MainLoop + PackageKit DBus 通信
local updates = pkg.list_updates()

-- 输出结果
for _, update in ipairs(updates) do
    print(string.format("%s %s (%s) - %s", update.name, update.version, update.arch, update.summary))
end