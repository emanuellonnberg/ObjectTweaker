// Copyright (c) 2026 Emanuel Lönnberg.
// This tool is released under the terms of the LGPLv3 or higher.
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import UM 1.5 as UM
import Cura 1.0 as Cura

Item {
    id: base
    width: childrenRect.width
    height: childrenRect.height

    // Safe property read: returns fallback before the tool is fully active.
    function val(name, fallback) {
        return UM.ActiveTool ? UM.ActiveTool.properties.getValue(name) : fallback
    }

    Column {
        id: items
        spacing: UM.Theme.getSize("default_margin").height

        CheckBox {
            id: decimateCheck
            text: "Decimate (reduce triangles)"
            checked: base.val("DoDecimate", true)
            onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoDecimate", checked)
        }
        RowLayout {
            visible: decimateCheck.checked
            spacing: UM.Theme.getSize("default_margin").width
            Label {
                text: "Keep " + Math.round(decimateSlider.value) + "%"
                verticalAlignment: Text.AlignVCenter
            }
            Slider {
                id: decimateSlider
                from: 1; to: 100; stepSize: 1
                value: base.val("DecimatePercent", 50)
                Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("DecimatePercent", value)
            }
        }

        CheckBox {
            id: smoothCheck
            text: "Smooth surface"
            checked: base.val("DoSmooth", false)
            onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoSmooth", checked)
        }
        RowLayout {
            visible: smoothCheck.checked
            spacing: UM.Theme.getSize("default_margin").width
            Label {
                text: "Iterations " + Math.round(smoothSlider.value)
                verticalAlignment: Text.AlignVCenter
            }
            Slider {
                id: smoothSlider
                from: 1; to: 50; stepSize: 1
                value: base.val("SmoothIterations", 10)
                Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("SmoothIterations", Math.round(value))
            }
        }

        CheckBox {
            id: cleanupCheck
            text: "Remove small parts"
            checked: base.val("DoRemoveSmall", false)
            onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("DoRemoveSmall", checked)
        }
        CheckBox {
            visible: cleanupCheck.checked
            text: "Keep largest only"
            checked: base.val("KeepLargestOnly", false)
            onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("KeepLargestOnly", checked)
        }

        Label {
            text: base.val("StatsText", "")
            visible: text.length > 0
            wrapMode: Text.WordWrap
        }

        RowLayout {
            width: parent.width
            spacing: UM.Theme.getSize("default_margin").width

            Button {
                text: "Preview"
                enabled: base.val("SelectionValid", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerPreview", true)
            }
            Button {
                text: "Apply"
                enabled: base.val("HasPreview", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerApply", true)
            }
            Button {
                text: "Reset"
                enabled: base.val("HasPreview", false) && !base.val("Busy", false)
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("TriggerReset", true)
            }
        }
    }
}
