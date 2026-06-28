# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
"""Cura Tool adapter for ObjectTweaker's Simplify feature."""
import os
import threading
from typing import Optional

import numpy

from UM.Logger import Logger
from UM.Application import Application
from UM.Tool import Tool
from UM.Mesh.MeshData import MeshData
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Scene.Selection import Selection
from UM.Operations.Operation import Operation

from cura.CuraApplication import CuraApplication
from cura.Scene.CuraSceneNode import CuraSceneNode

from UM.Event import Event, MouseEvent
from cura.PickingPass import PickingPass

from .core.mesh_io import to_trimesh, from_trimesh
from .core.pipeline import SimplifyOptions, run
from .core.fillholes import fill_holes
from .core.stamp import shape_outline
from .core.emboss import emboss, nearest_face_normal

_COMPUTE_TIMEOUT_S = 30.0


class _SetMeshDataOperation(Operation):
    """Undoable in-place replacement of a node's MeshData."""

    def __init__(self, node: CuraSceneNode, old_mesh: MeshData, new_mesh: MeshData) -> None:
        super().__init__()
        self._node = node
        self._old_mesh = old_mesh
        self._new_mesh = new_mesh

    def undo(self) -> None:
        self._node.setMeshData(self._old_mesh)

    def redo(self) -> None:
        self._node.setMeshData(self._new_mesh)


class ObjectTweaker(Tool):
    def __init__(self) -> None:
        super().__init__()

        self._do_remove_small = False
        self._min_pct = 1.0
        self._keep_largest_only = False
        self._do_decimate = True
        self._decimate_percent = 50.0   # UI percent (keep 50%)
        self._do_smooth = False
        self._smooth_iterations = 10
        self._feature = "simplify"   # "simplify" | "fillholes" | "emboss"
        self._shape = "circle"           # "circle" | "rectangle" | "star"
        self._diameter = 10.0
        self._rect_width = 10.0
        self._rect_height = 10.0
        self._star_points = 5
        self._star_inner_ratio = 0.5
        self._rotation = 0.0
        self._depth = 1.0
        self._emboss_mode = "emboss"     # "emboss" | "engrave"
        self._pick_point = None
        self._has_pick = False
        self._controller = self.getController()

        self._busy = False
        self._stats_text = ""
        self._has_preview = False

        # Preview state.
        self._target_node: Optional[CuraSceneNode] = None
        self._original_mesh: Optional[MeshData] = None
        self._preview_mesh: Optional[MeshData] = None

        self.setExposedProperties(
            "Feature",
            "Shape", "Diameter", "RectWidth", "RectHeight",
            "StarPoints", "StarInnerRatio", "Rotation", "Depth", "EmbossMode",
            "DoRemoveSmall", "MinPct", "KeepLargestOnly",
            "DoDecimate", "DecimatePercent",
            "DoSmooth", "SmoothIterations",
            "Busy", "StatsText", "HasPreview", "SelectionValid",
            "TriggerPreview", "TriggerApply", "TriggerReset",
        )

        Selection.selectionChanged.connect(self._onSelectionChanged)

    # ---- selection -----------------------------------------------------
    def _onSelectionChanged(self) -> None:
        # Drop any uncommitted preview when the selection changes.
        self._revertPreview()
        self._has_pick = False
        self._pick_point = None
        self._stats_text = ""
        self._has_preview = False
        self.propertyChanged.emit()

    def _selectedMeshNode(self) -> Optional[CuraSceneNode]:
        if Selection.getCount() != 1:
            return None
        node = Selection.getSelectedObject(0)
        if node is None or node.getMeshData() is None:
            return None
        return node

    def getSelectionValid(self) -> bool:
        return self._selectedMeshNode() is not None

    # ---- exposed scalar properties ------------------------------------
    def getFeature(self) -> str:
        return self._feature

    def setFeature(self, value: str) -> None:
        if value != self._feature:
            self._feature = value
            self._has_pick = False
            self._pick_point = None
            self.propertyChanged.emit()

    def getShape(self) -> str:
        return self._shape

    def setShape(self, value: str) -> None:
        if value != self._shape:
            self._shape = value
            self.propertyChanged.emit()

    def getDiameter(self) -> float:
        return self._diameter

    def setDiameter(self, value: float) -> None:
        value = float(value)
        if value != self._diameter:
            self._diameter = value
            self.propertyChanged.emit()

    def getRectWidth(self) -> float:
        return self._rect_width

    def setRectWidth(self, value: float) -> None:
        value = float(value)
        if value != self._rect_width:
            self._rect_width = value
            self.propertyChanged.emit()

    def getRectHeight(self) -> float:
        return self._rect_height

    def setRectHeight(self, value: float) -> None:
        value = float(value)
        if value != self._rect_height:
            self._rect_height = value
            self.propertyChanged.emit()

    def getStarPoints(self) -> int:
        return self._star_points

    def setStarPoints(self, value: int) -> None:
        value = int(value)
        if value != self._star_points:
            self._star_points = value
            self.propertyChanged.emit()

    def getStarInnerRatio(self) -> float:
        return self._star_inner_ratio

    def setStarInnerRatio(self, value: float) -> None:
        value = float(value)
        if value != self._star_inner_ratio:
            self._star_inner_ratio = value
            self.propertyChanged.emit()

    def getRotation(self) -> float:
        return self._rotation

    def setRotation(self, value: float) -> None:
        value = float(value)
        if value != self._rotation:
            self._rotation = value
            self.propertyChanged.emit()

    def getDepth(self) -> float:
        return self._depth

    def setDepth(self, value: float) -> None:
        value = float(value)
        if value != self._depth:
            self._depth = value
            self.propertyChanged.emit()

    def getEmbossMode(self) -> str:
        return self._emboss_mode

    def setEmbossMode(self, value: str) -> None:
        if value != self._emboss_mode:
            self._emboss_mode = value
            self.propertyChanged.emit()

    def getDoRemoveSmall(self) -> bool:
        return self._do_remove_small

    def setDoRemoveSmall(self, value: bool) -> None:
        if value != self._do_remove_small:
            self._do_remove_small = value
            self.propertyChanged.emit()

    def getMinPct(self) -> float:
        return self._min_pct

    def setMinPct(self, value: float) -> None:
        value = float(value)
        if value != self._min_pct:
            self._min_pct = value
            self.propertyChanged.emit()

    def getKeepLargestOnly(self) -> bool:
        return self._keep_largest_only

    def setKeepLargestOnly(self, value: bool) -> None:
        if value != self._keep_largest_only:
            self._keep_largest_only = value
            self.propertyChanged.emit()

    def getDoDecimate(self) -> bool:
        return self._do_decimate

    def setDoDecimate(self, value: bool) -> None:
        if value != self._do_decimate:
            self._do_decimate = value
            self.propertyChanged.emit()

    def getDecimatePercent(self) -> float:
        return self._decimate_percent

    def setDecimatePercent(self, value: float) -> None:
        value = float(value)
        if value != self._decimate_percent:
            self._decimate_percent = value
            self.propertyChanged.emit()

    def getDoSmooth(self) -> bool:
        return self._do_smooth

    def setDoSmooth(self, value: bool) -> None:
        if value != self._do_smooth:
            self._do_smooth = value
            self.propertyChanged.emit()

    def getSmoothIterations(self) -> int:
        return self._smooth_iterations

    def setSmoothIterations(self, value: int) -> None:
        value = int(value)
        if value != self._smooth_iterations:
            self._smooth_iterations = value
            self.propertyChanged.emit()

    def getBusy(self) -> bool:
        return self._busy

    def getStatsText(self) -> str:
        return self._stats_text

    def getHasPreview(self) -> bool:
        return self._has_preview

    # ---- write-only action triggers (set from QML buttons) ------------
    def getTriggerPreview(self) -> bool:
        return False

    def setTriggerPreview(self, value: bool) -> None:
        if value:
            self.preview()

    def getTriggerApply(self) -> bool:
        return False

    def setTriggerApply(self, value: bool) -> None:
        if value:
            self.apply()

    def getTriggerReset(self) -> bool:
        return False

    def setTriggerReset(self, value: bool) -> None:
        if value:
            self.reset()

    # ---- mesh extraction / build (Cura <-> ndarray) -------------------
    def _extractLocal(self, node: CuraSceneNode):
        mesh_data = node.getMeshData()
        vertices = numpy.asarray(mesh_data.getVertices(), dtype=numpy.float64)
        if vertices.ndim == 1:
            vertices = vertices.reshape(-1, 3)
        indices = mesh_data.getIndices()
        if indices is None:
            faces = numpy.arange(len(vertices), dtype=numpy.int32).reshape(-1, 3)
        else:
            faces = numpy.asarray(indices, dtype=numpy.int32)
            if faces.ndim == 1:
                faces = faces.reshape(-1, 3)
        return to_trimesh(vertices, faces)

    def _buildMeshData(self, mesh) -> MeshData:
        verts, faces, normals = from_trimesh(mesh)
        if normals.shape == verts.shape:
            return MeshData(vertices=verts, indices=faces, normals=normals)
        builder = MeshBuilder()
        builder.setVertices(verts)
        builder.setIndices(faces)
        builder.calculateNormals()
        return builder.build()

    def _currentOptions(self) -> SimplifyOptions:
        return SimplifyOptions(
            do_remove_small=self._do_remove_small,
            min_pct=self._min_pct,
            keep_largest_only=self._keep_largest_only,
            do_decimate=self._do_decimate,
            decimate_percent=max(0.01, min(1.0, self._decimate_percent / 100.0)),
            do_smooth=self._do_smooth,
            smooth_iterations=self._smooth_iterations,
            smooth_method="taubin",
        )

    def event(self, event) -> bool:
        result = super().event(event)
        if self._feature != "emboss":
            return result
        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons:
            node = self._selectedMeshNode()
            if node is None:
                return result
            camera = self._controller.getScene().getActiveCamera()
            if camera is None:
                return result
            picking_pass = PickingPass(camera.getViewportWidth(), camera.getViewportHeight())
            picking_pass.render()
            world = picking_pass.getPickedPosition(event.x, event.y)
            if world is None:
                return result
            matrix = numpy.asarray(node.getWorldTransformation().getData(), dtype=numpy.float64)
            inv = numpy.linalg.inv(matrix)
            local = inv @ numpy.array([world.x, world.y, world.z, 1.0])
            self._pick_point = local[:3] / local[3]
            self._has_pick = True
            self._stats_text = "placed - click Preview"
            self.propertyChanged.emit()
        return result

    def _captureDir(self) -> str:
        """Directory where emboss dumps failed-boolean inputs for diagnosis."""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

    def _shapeParams(self) -> dict:
        return {
            "diameter": self._diameter,
            "width": self._rect_width,
            "height": self._rect_height,
            "points": self._star_points,
            "inner_ratio": self._star_inner_ratio,
            "rotation": self._rotation,
        }

    def _computeForFeature(self, mesh):
        """Run the active feature; return (result_mesh, stats_text)."""
        if self._feature == "fillholes":
            filled, n = fill_holes(mesh)
            return filled, f"holes filled: {n}"
        if self._feature == "emboss":
            if not self._has_pick or self._pick_point is None:
                return mesh, "click the model to place"
            outline = shape_outline(self._shape, self._shapeParams())
            normal = nearest_face_normal(mesh, self._pick_point)
            res, ok, reason = emboss(mesh, self._pick_point, normal, outline,
                                     depth=self._depth, mode=self._emboss_mode,
                                     capture_dir=self._captureDir())
            if not ok:
                Logger.log("w", "ObjectTweaker emboss failed: %s", reason)
                return mesh, reason or "emboss failed"
            return res, "engraved" if self._emboss_mode == "engrave" else "embossed"
        result = run(mesh, self._currentOptions())
        extra = f", removed {result.parts_removed} part(s)" if result.parts_removed else ""
        return result.mesh, f"tris: {result.tris_before} -> {result.tris_after}{extra}"

    # ---- preview / apply / reset --------------------------------------
    def preview(self) -> None:
        node = self._selectedMeshNode()
        if node is None or self._busy:
            return
        self._revertPreview()
        self._target_node = node
        self._original_mesh = node.getMeshData()
        self._busy = True
        self._stats_text = "Working..."
        self.propertyChanged.emit()
        threading.Thread(target=self._previewWorker, args=(node,), daemon=True).start()

    def _previewWorker(self, node: CuraSceneNode) -> None:
        result_box = {}

        def _compute() -> None:
            mesh = self._extractLocal(node)
            result_box["result"] = self._computeForFeature(mesh)

        worker = threading.Thread(target=_compute, daemon=True)
        worker.start()
        worker.join(_COMPUTE_TIMEOUT_S)

        def _finish() -> None:
            self._busy = False
            if worker.is_alive() or "result" not in result_box:
                self._stats_text = "Failed (timed out or error)"
                self._has_preview = False
            else:
                result_mesh, stats_text = result_box["result"]
                self._preview_mesh = self._buildMeshData(result_mesh)
                node.setMeshData(self._preview_mesh)
                node.calculateBoundingBoxMesh()
                self._stats_text = stats_text
                self._has_preview = True
            self.propertyChanged.emit()

        CuraApplication.getInstance().callLater(_finish)

    def _revertPreview(self) -> None:
        if self._target_node is not None and self._original_mesh is not None and self._has_preview:
            self._target_node.setMeshData(self._original_mesh)
            self._target_node.calculateBoundingBoxMesh()
        self._preview_mesh = None
        self._has_preview = False

    def reset(self) -> None:
        self._revertPreview()
        self._target_node = None
        self._original_mesh = None
        self._stats_text = ""
        self.propertyChanged.emit()

    def apply(self) -> None:
        if not self._has_preview or self._target_node is None:
            return
        if self._original_mesh is None or self._preview_mesh is None:
            return
        op = _SetMeshDataOperation(self._target_node, self._original_mesh, self._preview_mesh)
        Application.getInstance().getOperationStack().push(op)
        Logger.log("d", "ObjectTweaker: applied %s", self._stats_text)
        # The committed mesh is now the baseline; clear preview state.
        self._target_node = None
        self._original_mesh = None
        self._preview_mesh = None
        self._has_preview = False
        self.propertyChanged.emit()
