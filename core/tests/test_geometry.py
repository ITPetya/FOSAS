import pytest

pytest.importorskip("build123d")

from build123d import Box, Compound, Locations, export_step

from fosas_core.geometry import GeometryError, ROTATION_LABELS, apply_named_rotation, detect_axis_orientation, import_step


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


# --- detect_axis_orientation (docs/RISKS.md R13): synthetic boxes with
# exactly the real-world dimension ratios two actual, previously-failing
# STEP files had (see docs/ARCHITECTURE.md/DECISIONS.md ADR-0020),
# captured once (2026-10-16) and kept here as regression fixtures - the
# real files themselves are the project owner's own CAD data, not
# committed to the repository.

def test_detect_axis_orientation_leaves_an_already_correct_shape_alone():
    # chord=100, span=500, thickness=10 - already plausible as given.
    box = Box(100, 500, 10)
    result = detect_axis_orientation(box)
    assert result.applied_label is None
    assert result.confident is True
    assert result.shape is box  # not even a same-dimensions rotated copy, the exact original


def test_detect_axis_orientation_confidently_fixes_the_real_wing_case():
    # Exact dimension ratios of a real STEP file that failed in
    # production (docs/RISKS.md R13): chord=100, but what FOSAS read as
    # "span" (Y) and "thickness" (Z) were swapped - the real span (500)
    # was along Z, the real thickness (10.23) was along Y.
    box = Box(100, 10.23, 500)
    result = detect_axis_orientation(box)
    assert result.confident is True
    assert result.applied_label == "rot_x90"
    bbox = result.shape.bounding_box()
    chord = bbox.max.X - bbox.min.X
    span = bbox.max.Y - bbox.min.Y
    thickness = bbox.max.Z - bbox.min.Z
    assert chord == pytest.approx(100, rel=1e-3)
    assert span == pytest.approx(500, rel=1e-3)
    assert thickness == pytest.approx(10.23, rel=1e-3)


def test_detect_axis_orientation_declines_an_ambiguous_real_case():
    # Exact dimension ratios of a second real STEP file (docs/RISKS.md
    # R13) that is NOT a simple single wing - even its best candidate
    # among all 6 possible axis assignments has an implausibly thick
    # (49%) thickness/chord ratio, so no automatic fix should be
    # confidently applied; this must stay a manual/preview case.
    box = Box(207.5, 150.2, 308)
    result = detect_axis_orientation(box)
    assert result.confident is False
    assert result.applied_label is None
    assert result.shape is box
    # All 6 candidates must still be reported, for the error message/
    # future preview tool to show real numbers instead of nothing.
    assert len(result.candidates) == 6
    assert any(c.plausible for c in result.candidates)  # some candidates do pass the loose bound
    assert min(c.thickness_ratio for c in result.candidates if c.plausible) > 0.3  # but none confidently


def test_detect_axis_orientation_picks_up_a_genuine_3_cycle_permutation():
    # A case only reachable via one of the two combined rotations, not
    # any single 90-degree rotation about one axis alone: real chord=50
    # should be read off the geometry's own Z-extent, real span=400 off
    # its own X-extent, real thickness=5 off its own Y-extent.
    box = Box(400, 5, 50)  # (X=400, Y=5, Z=50) in the box's own frame
    result = detect_axis_orientation(box)
    assert result.confident is True
    bbox = result.shape.bounding_box()
    chord = bbox.max.X - bbox.min.X
    span = bbox.max.Y - bbox.min.Y
    thickness = bbox.max.Z - bbox.min.Z
    assert chord == pytest.approx(50, rel=1e-3)
    assert span == pytest.approx(400, rel=1e-3)
    assert thickness == pytest.approx(5, rel=1e-3)


# --- apply_named_rotation (ADR-0020 Teil B, geometry preview tool):
# must use the exact same recipes as detect_axis_orientation above, so
# a label picked in the preview tool means the same physical rotation
# server-side as it did when detect_axis_orientation itself computed it.


def test_apply_named_rotation_matches_detect_axis_orientations_own_recipe():
    box = Box(100, 10.23, 500)
    detected = detect_axis_orientation(box)
    assert detected.applied_label == "rot_x90"

    manually_rotated = apply_named_rotation(box, "rot_x90")
    bbox = manually_rotated.bounding_box()
    detected_bbox = detected.shape.bounding_box()
    assert (bbox.max.X - bbox.min.X) == pytest.approx(detected_bbox.max.X - detected_bbox.min.X)
    assert (bbox.max.Y - bbox.min.Y) == pytest.approx(detected_bbox.max.Y - detected_bbox.min.Y)
    assert (bbox.max.Z - bbox.min.Z) == pytest.approx(detected_bbox.max.Z - detected_bbox.min.Z)


def test_apply_named_rotation_identity_returns_the_same_dimensions():
    box = Box(100, 500, 10)
    rotated = apply_named_rotation(box, "identity")
    bbox = rotated.bounding_box()
    assert (bbox.max.X - bbox.min.X) == pytest.approx(100)
    assert (bbox.max.Y - bbox.min.Y) == pytest.approx(500)
    assert (bbox.max.Z - bbox.min.Z) == pytest.approx(10)


def test_apply_named_rotation_rejects_an_unknown_label():
    box = Box(100, 500, 10)
    with pytest.raises(GeometryError, match="Unknown rotation label"):
        apply_named_rotation(box, "rot_sideways")


def test_rotation_labels_lists_exactly_the_six_candidates_detect_axis_orientation_uses():
    box = Box(207.5, 150.2, 308)
    candidates = detect_axis_orientation(box).candidates
    assert {c.label for c in candidates} == set(ROTATION_LABELS)
    assert len(ROTATION_LABELS) == 6
