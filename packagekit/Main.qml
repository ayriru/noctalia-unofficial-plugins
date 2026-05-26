import QtQuick
import Quickshell
import qs.Commons

Item {
  id: root
  property var pluginApi: null

  readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")

}
