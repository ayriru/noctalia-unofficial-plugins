import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Widgets

Rectangle {
  id: root

  // Plugin API (injected by PluginService)
  property var pluginApi: null

  // Required properties for bar widgets
  property ShellScreen screen
  property string widgetId: ""
  property string section: ""
  property int sectionWidgetIndex: -1
  property int sectionWidgetsCount: 0

  implicitWidth: row.implicitWidth + Style.marginM * 2
  implicitHeight: Style.barHeight

  color: Style.capsuleColor
  radius: Style.radiusM

  RowLayout {
    id: row
    anchors.centerIn: parent
    spacing: Style.marginS

    NIcon {
      icon: "heart"
      color: Color.mPrimary
    }

    NText {
      text: "My Plugin"
      color: Color.mOnSurface
      pointSize: Style.fontSizeS
    }
  }
  MouseArea {
    anchors.fill: parent
    onClicked: {
      if (pluginApi) {
        pluginApi.openPanel(root.screen, root)
      }
    }
  }
}
