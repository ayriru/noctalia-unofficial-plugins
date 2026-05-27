import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Widgets
import qs.Services.UI

// ═══════════════════════════════════════════════════════════════════════════════
// PackageKit BarWidget — 状态栏胶囊小部件
//
// 职责：
//   1. 在 Noctalia 状态栏中显示一个胶囊形状的图标+数字
//   2. 数字来自 Main.qml 的 updateCount 属性（通过 pluginApi.mainInstance 引用）
//   3. 点击时调用 UI.openPanel 展开主面板
//
// 生命周期：
//   由 Noctalia 根据 manifest.json 的 entryPoints.barWidget 加载
//   注入 pluginApi、screen、widgetId、section 等属性
//
// 设计约定：
//   - 使用 Noctalia Style API 确保外观与系统主题一致
//   - 通过属性绑定（而非信号）订阅 updateCount，保证实时性
// ═══════════════════════════════════════════════════════════════════════════════

Item {
  id: root

  // ───────────────────────────────────────────────────────────────────
  // Noctalia 注入属性（由框架在加载时设置）
  // ───────────────────────────────────────────────────────────────────

  // 插件 API：通过 .mainInstance 访问 Main.qml 的状态和方法
  property var pluginApi: null

  // 当前屏幕对象，用于多显示器适配
  property ShellScreen screen

  // 小部件标识：widgetId 唯一标识此实例，section 指定其所属的栏区域
  property string widgetId: ""
  property string section: ""

  // 在 section 内的排序位置（0-based）和该 section 中小部件总数
  // 用于处理首尾小部件的圆角等边界样式
  property int sectionWidgetIndex: -1
  property int sectionWidgetsCount: 0

  // ───────────────────────────────────────────────────────────────────
  // 屏幕自适应属性 — 根据当前屏幕动态计算
  // ───────────────────────────────────────────────────────────────────

  // 屏幕名称（如 "eDP-1", "HDMI-1"），用于从 Style/Settings 查询对应配置
  readonly property string screenName: screen?.name ?? ""

  // 栏的位置：top / bottom / left / right
  readonly property string barPosition: Settings.getBarPositionForScreen(screenName)

  // 是否为垂直栏（左侧或右侧），影响布局方向
  readonly property bool isBarVertical: barPosition === "left" || barPosition === "right"

  // 胶囊高度和字体大小：由 Style 根据屏幕 DPI 和用户设置计算
  readonly property real capsuleHeight: Style.getCapsuleHeightForScreen(screenName)
  readonly property real barFontSize: Style.getBarFontSizeForScreen(screenName)

  // ───────────────────────────────────────────────────────────────────
  // 尺寸计算
  // ───────────────────────────────────────────────────────────────────

  // 内容宽度 = 图标+数字的固有宽度 + 左右内边距（marginM × 2）
  readonly property real contentWidth: row.implicitWidth + Style.marginM * 2

  // 内容高度 = 胶囊高度（由系统风格决定）
  readonly property real contentHeight: capsuleHeight

  // 对外声明的尺寸：Noctalia 布局引擎依据这两个值排列小部件
  implicitWidth: contentWidth
  implicitHeight: contentHeight

  // ═══════════════════════════════════════════════════════════════════
  // 视觉层：胶囊背景
  // ═══════════════════════════════════════════════════════════════════

  Rectangle {
    id: visualCapsule

    // 居中：使用 Style.pixelAlignCenter 确保亚像素对齐（避免模糊）
    x: Style.pixelAlignCenter(parent.width, width)
    y: Style.pixelAlignCenter(parent.height, height)
    width: root.contentWidth
    height: root.contentHeight

    // 悬停时使用高亮色，否则使用默认胶囊色
    color: mouseArea.containsMouse ? Color.mHover : Style.capsuleColor

    // 大圆角（radiusL），匹配 Noctalia 胶囊风格
    radius: Style.radiusL

    // 边框：使胶囊与背景面板有视觉分隔
    border.color: Style.capsuleBorderColor
    border.width: Style.capsuleBorderWidth

    // ═══════════════════════════════════════════════════════════════════
    // 内容行：图标 + 更新数量
    // ═══════════════════════════════════════════════════════════════════

    RowLayout {
      id: row
      anchors.centerIn: parent
      spacing: Style.marginS

      // 图标：使用 Noctalia 内置图标字体
      NIcon {
        icon: "numbers"
        color: Color.mPrimary        // 主题主色
      }

      // 更新数量文本
      NText {
        id: updateCountText

        // 通过 pluginApi.mainInstance 跨组件读取 Main.qml 的 updateCount
        // 属性绑定机制：Main.qml 中 updateCount 变化时自动更新此处文本
        // -1 = 加载中，显示 "..."
        // >=0 = 正常显示数量
        text: {
          var count = pluginApi?.mainInstance?.updateCount
          return count >= 0 ? count.toString() : "..."
        }

        color: Color.mOnSurface      // 主题前景色（高对比度）
        pointSize: barFontSize
        font.weight: Font.Bold
      }
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // 交互层：鼠标事件
  // ═══════════════════════════════════════════════════════════════════

  MouseArea {
    id: mouseArea
    anchors.fill: parent

    // 启用悬停检测 → visualCapsule 的悬停变色生效
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor   // 手型光标，暗示可点击

    onClicked: {
      // 点击胶囊 → 打开主面板（Main.qml）
      // ?? 运算符：pluginApi 为 null 时 fallback 到自身
      UI.openPanel(pluginApi?.mainInstance ?? root)
    }
  }
}