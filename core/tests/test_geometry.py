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
def disconnected_box_faces_step(tmp_path):
    # All 6 faces of a box, exported as separate disconnected patches
    # (not sewn into a shell). This is the same shape as the real-world
    # test file (a car spoiler with 182 disconnected single-face shells,
    # see docs/RISKS.md), reproduced minimally: sewing should fully close
    # this one, since nothing is actually missing, only disconnected.
    box = Box(1, 1, 1)
    faces = box.faces()
    compound = Compound(children=list(faces))
    path = tmp_path / "disconnected_faces.step"
    export_step(compound, str(path))
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
    assert result.repair_report is None


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


def test_import_step_without_sewing_tolerance_rejects_disconnected_faces(disconnected_box_faces_step):
    # Default behaviour is unchanged: no repair unless explicitly asked for.
    with pytest.raises(GeometryError, match="no solid body"):
        import_step(disconnected_box_faces_step)


def test_import_step_with_sewing_tolerance_repairs_disconnected_faces(disconnected_box_faces_step):
    result = import_step(disconnected_box_faces_step, sewing_tolerance=1e-4)
    assert result.volume == pytest.approx(1.0, rel=1e-3)
    assert result.repair_report is not None
    assert result.repair_report.became_solid is True
    assert result.repair_report.free_edge_count == 0
    assert result.repair_report.input_face_count == 6


def test_import_step_with_sewing_tolerance_still_rejects_a_genuine_gap(open_shell_step):
    # Sewing can reconnect disconnected-but-matching patches, it cannot
    # invent a face that was never exported in the first place.
    with pytest.raises(GeometryError, match="open"):
        import_step(open_shell_step, sewing_tolerance=1e-3)
