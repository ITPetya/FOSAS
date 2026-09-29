from pathlib import Path

import pytest

from fosas_core.cache import CacheStore, combined_hash, hash_file, hash_value
from fosas_core.meshing import BoundaryLayerMeshParams, ConstantSectionMeshParams, generate_constant_section_geo, run_gmsh

from .airfoils import naca4_points


def test_hash_file_changes_with_content(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("hello")
    b.write_text("hello")
    assert hash_file(a) == hash_file(b)
    b.write_text("hello!")
    assert hash_file(a) != hash_file(b)


def test_hash_value_is_order_independent_for_dicts():
    assert hash_value({"a": 1, "b": 2}) == hash_value({"b": 2, "a": 1})


def test_hash_value_differs_for_different_values():
    assert hash_value({"a": 1}) != hash_value({"a": 2})


def test_hash_value_supports_dataclasses_and_paths():
    params = BoundaryLayerMeshParams(first_cell_height=1e-5, growth_ratio=1.2, thickness=0.02)
    other = BoundaryLayerMeshParams(first_cell_height=2e-5, growth_ratio=1.2, thickness=0.02)
    assert hash_value(params) == hash_value(params)
    assert hash_value(params) != hash_value(other)
    assert hash_value(Path("/a/b")) == hash_value(Path("/a/b"))


def test_combined_hash_is_deterministic_and_order_sensitive():
    assert combined_hash("geometry-hash", {"iter": 1}) == combined_hash("geometry-hash", {"iter": 1})
    assert combined_hash("geometry-hash", {"iter": 1}) != combined_hash({"iter": 1}, "geometry-hash")


def test_cache_store_roundtrip(tmp_path):
    store = CacheStore(tmp_path / "cache")
    key = "abc123"
    assert not store.has(key)
    assert store.read_metadata(key) is None

    store.reserve(key)
    assert not store.has(key)  # reserving alone does not mark it complete

    store.write_metadata(key, inputs={"chord": 0.6, "path": Path("/tmp/x.step")})
    assert store.has(key)
    metadata = store.read_metadata(key)
    assert metadata["inputs"]["chord"] == 0.6
    assert metadata["inputs"]["path"] == "/tmp/x.step"


@pytest.mark.slow
def test_cache_avoids_recomputing_a_real_mesh(tmp_path, gmsh_executable):
    """Realistic use: the same geometry and mesh parameters must produce
    the same key, and a cache hit must skip the (slow) Gmsh call
    entirely, not just look identical by accident.
    """
    store = CacheStore(tmp_path / "cache")
    chord, span = 0.6, 1.2
    mesh_params = ConstantSectionMeshParams(
        profile_points_xz=naca4_points(chord=chord, n=25),
        span=span,
        chord=chord,
        boundary_layer=BoundaryLayerMeshParams(first_cell_height=2.7e-6, growth_ratio=1.25, thickness=0.02),
        span_layers=8,
    )
    key = combined_hash("no-source-geometry-file-in-this-test", mesh_params)

    def mesh_or_get_cached():
        if store.has(key):
            return store.entry_dir(key) / "mesh.su2", True
        entry = store.reserve(key)
        mesh_path = entry / "mesh.su2"
        geo = generate_constant_section_geo(mesh_params, mesh_path)
        run_gmsh(geo, mesh_path, gmsh_executable=gmsh_executable, timeout=180)
        store.write_metadata(key, inputs={"mesh_params": mesh_params})
        return mesh_path, False

    first_path, first_was_cached = mesh_or_get_cached()
    assert not first_was_cached
    assert first_path.exists()
    first_mtime = first_path.stat().st_mtime

    second_path, second_was_cached = mesh_or_get_cached()
    assert second_was_cached
    assert second_path == first_path
    assert second_path.stat().st_mtime == first_mtime  # never touched, proves Gmsh did not rerun
