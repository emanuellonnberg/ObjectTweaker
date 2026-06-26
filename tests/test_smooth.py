# Copyright (c) 2026 Emanuel Lönnberg.
# This tool is released under the terms of the LGPLv3 or higher.
import numpy
import trimesh

from core.smooth import smooth


def _noisy_sphere(seed: int = 0):
    sphere = trimesh.creation.icosphere(subdivisions=3)
    rng = numpy.random.default_rng(seed)
    sphere.vertices += rng.normal(scale=0.03, size=sphere.vertices.shape)
    return sphere


def _radius_std(mesh):
    radii = numpy.linalg.norm(mesh.vertices - mesh.centroid, axis=1)
    return float(numpy.std(radii))


def test_smoothing_reduces_surface_noise():
    noisy = _noisy_sphere()
    before = _radius_std(noisy)
    out = smooth(noisy, iterations=15)
    assert _radius_std(out) < before


def test_smoothing_preserves_topology_and_does_not_mutate_input():
    noisy = _noisy_sphere()
    original = noisy.vertices.copy()
    out = smooth(noisy, iterations=5)
    assert out.faces.shape == noisy.faces.shape
    assert out.vertices.shape == noisy.vertices.shape
    assert numpy.allclose(noisy.vertices, original)  # input untouched
