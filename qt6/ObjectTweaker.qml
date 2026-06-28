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

    // Active feature ("simplify" | "fillholes").
    property string feature: base.val("Feature", "simplify")

    Column {
        id: items
        spacing: UM.Theme.getSize("default_margin").height

        ComboBox {
            id: featureCombo
            width: UM.Theme.getSize("setting_control").width
            model: ["Simplify", "Fill Holes", "Emboss"]
            currentIndex: base.feature === "emboss" ? 2 : (base.feature === "fillholes" ? 1 : 0)
            onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Feature", currentIndex === 2 ? "emboss" : (currentIndex === 1 ? "fillholes" : "simplify"))
        }

        // ---- Simplify ----
        Column {
            visible: base.feature === "simplify"
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
        }

        // ---- Fill Holes ----
        Column {
            visible: base.feature === "fillholes"
            spacing: UM.Theme.getSize("default_margin").height

            Label {
                text: "Caps all open boundary loops to make the model watertight."
                wrapMode: Text.WordWrap
                width: UM.Theme.getSize("setting_control").width
            }
        }

        // ---- Emboss ----
        Column {
            visible: base.feature === "emboss"
            spacing: UM.Theme.getSize("default_margin").height

            property string shape: base.val("Shape", "circle")

            Label {
                text: "Click the model to place the stamp."
                wrapMode: Text.WordWrap
                width: UM.Theme.getSize("setting_control").width
            }

            ComboBox {
                id: shapeCombo
                width: UM.Theme.getSize("setting_control").width
                model: ["Circle", "Rectangle", "Star"]
                currentIndex: parent.shape === "star" ? 2 : (parent.shape === "rectangle" ? 1 : 0)
                onActivated: if (UM.ActiveTool) UM.ActiveTool.setProperty("Shape", currentIndex === 2 ? "star" : (currentIndex === 1 ? "rectangle" : "circle"))
            }

            RowLayout {
                visible: parent.shape === "circle" || parent.shape === "star"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Diameter " + Math.round(diaSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: diaSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("Diameter", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Diameter", value)
                }
            }
            RowLayout {
                visible: parent.shape === "rectangle"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Width " + Math.round(wSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: wSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("RectWidth", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("RectWidth", value)
                }
            }
            RowLayout {
                visible: parent.shape === "rectangle"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Height " + Math.round(hSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: hSlider
                    from: 1; to: 100; stepSize: 1
                    value: base.val("RectHeight", 10)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("RectHeight", value)
                }
            }
            RowLayout {
                visible: parent.shape === "star"
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Points " + Math.round(ptSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: ptSlider
                    from: 3; to: 12; stepSize: 1
                    value: base.val("StarPoints", 5)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("StarPoints", Math.round(value))
                }
            }

            RowLayout {
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Rotation " + Math.round(rotSlider.value); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: rotSlider
                    from: 0; to: 360; stepSize: 1
                    value: base.val("Rotation", 0)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Rotation", value)
                }
            }
            RowLayout {
                spacing: UM.Theme.getSize("default_margin").width
                Label { text: "Depth " + depthSlider.value.toFixed(1); verticalAlignment: Text.AlignVCenter }
                Slider {
                    id: depthSlider
                    from: 0.2; to: 10; stepSize: 0.2
                    value: base.val("Depth", 1.0)
                    Layout.preferredWidth: UM.Theme.getSize("setting_control").width
                    onPressedChanged: if (!pressed && UM.ActiveTool) UM.ActiveTool.setProperty("Depth", value)
                }
            }
            CheckBox {
                text: "Engrave (recess instead of raise)"
                checked: base.val("EmbossMode", "emboss") === "engrave"
                onClicked: if (UM.ActiveTool) UM.ActiveTool.setProperty("EmbossMode", checked ? "engrave" : "emboss")
            }
        }

        // ---- Shared: stats + actions ----
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
