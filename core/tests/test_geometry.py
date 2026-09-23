import pytest

pytest.importorskip("build123d")

from build123d import Box, Compound, Locations, export_step

from fosas_core.geometry import GeometryError, import_step


@pytest.fixture
def closed_box_step(tmp_path):
    box = Box(1, 1, 1)
    path = tmp_path / "box.step"
    export_step(box, str(path))
    return path


@pytest.fixture
def open_shell_step(tmp_path):
    # A box with one face removed: topologically consistent per-face, but
    # not a closed solid. This is the exact case that a naive
    # BRepCheck_Analyzer-only check misses, see geometry.py docstring.
    box = Box(1, 1, 1)
    faces = box.faces()
    shell = Compound.make_composite(faces[:-1])
    path = tmp_path / "open_shell.step"
    export_step(shell, str(path))
    return path


@pytest.fixture
def two_solids_step(tmp_path):
    with Locations((0, 0, 0), (5, 0, 0)):
        boxes = Box(1, 1, 1)
    path = tmp_path / "two_boxes.step"
    export_step(boxes, str(path))
    return path


def test_import_step_accepts_closed_box(closed_box_step):
    result = import_step(closed_box_step)
    assert result.volume == pytest.approx(1.0, rel=1e-6)
    assert result.source_path == closed_box_step


def test_import_step_rejects_missing_file(tmp_path):
    with pytest.raises(GeometryError, match="not found"):
        import_step(tmp_path / "does_not_exist.step")


def test_import_step_rejects_open_shell(open_shell_step):
    # A box missing one face round-trips through STEP as bare surfaces,
    # not a Solid at all (verified empirically), so it is rejected by the
    # "no solid body" check rather than the is_manifold check. Both checks
    # stay in geometry.py as defense in depth; this test documents which
    # one actually fires for this case instead of assuming.
    with pytest.raises(GeometryError, match="no solid body"):
        import_step(open_shell_step)


def test_import_step_rejects_multiple_solids(two_solids_step):
    with pytest.raises(GeometryError, match="separate solid bodies"):
        import_step(two_solids_step)
