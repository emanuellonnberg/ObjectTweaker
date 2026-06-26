// Copyright (c) 2026 Emanuel Lönnberg.
// This tool is released under the terms of the LGPLv3 or higher.
import QtQuick 2.10
import QtQuick.Controls 2.15

import UM 1.6 as UM
import Cura 1.0 as Cura

Item {
    id: base
    width: childrenRect.width
    height: childrenRect.height

    property bool selectionValid: UM.ActiveTool.properties.getValue("SelectionValid")
    property bool busy: UM.ActiveTool.properties.getValue("Busy")
    property bool hasPreview: UM.ActiveTool.properties.getValue("HasPreview")

    Column {
        id: items
        spacing: UM.Theme.getSize("default_margin").height

        UM.CheckBox {
            id: decimateCheck
            text: "Decimate (reduce triangles)"
            checked: UM.ActiveTool.properties.getValue("DoDecimate")
            onClicked: UM.ActiveTool.setProperty("DoDecimate", checked)
        }
        Row {
            spacing: UM.Theme.getSize("default_margin").width
            visible: decimateCheck.checked
            UM.Label { text: "Keep %" }
            UM.Slider {
                id: decimateSlider
                width: UM.Theme.getSize("setting_control").width
                from: 1; to: 100
                value: UM.ActiveTool.properties.getValue("DecimatePercent")
                onPressedChanged: if (!pressed) UM.ActiveTool.setProperty("DecimatePercent", value)
            }
            UM.Label { text: Math.round(decimateSlider.value) + "%" }
        }

        UM.CheckBox {
            id: smoothCheck
            text: "Smooth surface"
            checked: UM.ActiveTool.properties.getValue("DoSmooth")
            onClicked: UM.ActiveTool.setProperty("DoSmooth", checked)
        }
        Row {
            spacing: UM.Theme.getSize("default_margin").width
            visible: smoothCheck.checked
            UM.Label { text: "Iterations" }
            UM.Slider {
                id: smoothSlider
                width: UM.Theme.getSize("setting_control").width
                from: 1; to: 50
                value: UM.ActiveTool.properties.getValue("SmoothIterations")
                onPressedChanged: if (!pressed) UM.ActiveTool.setProperty("SmoothIterations", Math.round(value))
            }
            UM.Label { text: Math.round(smoothSlider.value) }
        }

        UM.CheckBox {
            id: cleanupCheck
            text: "Remove small parts"
            checked: UM.ActiveTool.properties.getValue("DoRemoveSmall")
            onClicked: UM.ActiveTool.setProperty("DoRemoveSmall", checked)
        }
        UM.CheckBox {
            visible: cleanupCheck.checked
            text: "Keep largest only"
            checked: UM.ActiveTool.properties.getValue("KeepLargestOnly")
            onClicked: UM.ActiveTool.setProperty("KeepLargestOnly", checked)
        }

        UM.Label {
            text: UM.ActiveTool.properties.getValue("StatsText")
            visible: text.length > 0
        }

        Row {
            spacing: UM.Theme.getSize("default_margin").width
            Cura.SecondaryButton {
                text: "Preview"
                enabled: base.selectionValid && !base.busy
                onClicked: UM.ActiveTool.triggerAction("preview")
            }
            Cura.PrimaryButton {
                text: "Apply"
                enabled: base.hasPreview && !base.busy
                onClicked: UM.ActiveTool.triggerAction("apply")
            }
            Cura.SecondaryButton {
                text: "Reset"
                enabled: base.hasPreview && !base.busy
                onClicked: UM.ActiveTool.triggerAction("reset")
            }
        }
    }
}
