import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

// ═══════════════════════════════════════════════════════════════════════════════
// PackageKit — 系统包管理面板（插件入口）
//
// 职责：
//   1. 定期通过 PackageKit 查询系统可用更新数量
//   2. 将 updateCount 暴露给 BarWidget 显示在状态栏
//   3. 作为插件主实例，被 BarWidget 通过 pluginApi.mainInstance 引用
//
// 数据流：
//   Timer 触发 → Process 执行 pkgkit.py list-update --count
//   → StdioCollector 收集 stdout → parseInt 解析整数
//   → 写入 root.updateCount → BarWidget 通过属性绑定自动读取
//
// 依赖：
//   - Quickshell.Io.Process / StdioCollector（子进程管理）
//   - PackageKit/scripts/pkgkit.py（Python 后端脚本）
// ═══════════════════════════════════════════════════════════════════════════════

Item {
  id: root

  // ───────────────────────────────────────────────────────────────────
  // Plugin API — Noctalia 运行时注入
  // ───────────────────────────────────────────────────────────────────

  // Noctalia 在加载插件时注入此对象，提供以下方法：
  //   - getPluginDir:  返回插件目录的绝对路径
  //   - getPluginVersion: 返回 manifest.json 中的版本号
  //   - mainInstance:  指向此 Main.qml 根 Item，供 BarWidget 引用
  // 开发模式下 pluginApi 为 null，使用 fallback 路径
  property var pluginApi: null

  // ───────────────────────────────────────────────────────────────────
  // 路径 — 运行时动态解析，兼容开发与部署环境
  // ───────────────────────────────────────────────────────────────────

  // XDG_CONFIG_HOME，通常为 ~/.config
  readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME")
                                      || (Quickshell.env("HOME") + "/.config")

  // 插件目录：优先使用 pluginApi 提供的路径，否则 fallback 到标准位置
  readonly property string pluginDir: pluginApi?.getPluginDir
                                      || configHome + "/noctalia/plugins/PackageKit"

  // 脚本目录：所有后端脚本（pkgkit.py, pkg.lua 等）的存放位置
  readonly property string scriptsDir: pluginDir + "/scripts".toString()


  // ───────────────────────────────────────────────────────────────────
  // 状态
  // ───────────────────────────────────────────────────────────────────

  // 可用更新数量。约定：-1 = 加载中 / 查询失败，>=0 = 实际数量
  // 由 StdioCollector.onStreamFinished 异步写入
  // 被 BarWidget.updateCountText 通过属性绑定自动订阅
  property int updateCount: -1

  // ───────────────────────────────────────────────────────────────────
  // 子进程：调用 Python 脚本查询更新
  // ───────────────────────────────────────────────────────────────────

  Process {
    id: updateCountProcess

    // running 由 Timer 控制：设为 true 时启动子进程
    running: false

    // 命令：直接执行 pkgkit.py（依赖 shebang #!/usr/bin/env python3）
    // --count 参数让脚本仅输出整数，减少 I/O 开销
    command: [ scriptsDir + "/pkgkit.py", "list-update", "--count" ]

    // StdioCollector：将子进程 stdout 收集为字符串
    // onStreamFinished 在进程退出 + stdout 关闭后触发
    stdout: StdioCollector {
      onStreamFinished: {
        // 解析输出为整数；解析失败则保持 -1（加载失败状态）
        var count = parseInt(this.text.trim())
        root.updateCount = isNaN(count) ? -1 : count
      }
    }
  }

  // ───────────────────────────────────────────────────────────────────
  // 定时器：控制刷新节奏
  // ───────────────────────────────────────────────────────────────────

  Timer {
    id: refreshTimer

    // 首次触发：启动后 500ms（给 Noctalia 初始化留缓冲时间）
    interval: 500
    running: true
    repeat: true

    onTriggered: {
      // 启动子进程查询更新
      updateCountProcess.running = true

      // 首次触发后，将间隔改为 10 分钟（600,000ms）
      // 避免频繁 DBus 调用消耗系统资源
      interval = 600000
    }
  }
}