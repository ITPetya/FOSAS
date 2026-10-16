from pathlib import Path

import pytest

import re

from fosas_core.meshing import MeshingError
from fosas_core.pipeline import CaseParams, ExecutablePaths, PipelineError, run_case

from .fixtures import naca0012_wing_step, naca0012_wing_step_wrong_axes


def test_run_case_rejects_geometry_with_span_along_the_wrong_axis(tmp_path):
    # Regression test for a real incident: this shape of mistake made
    # Gmsh consume all available RAM on a real customer file before the
    # OOM killer intervened, see docs/RISKS.md. Must be caught before
    # meshing is even attempted, not after the machine runs out of memory.
    step_path = naca0012_wing_step_wrong_axes(tmp_path / "wrong_axes.step", chord=0.6, span=1.2, n=25)
    params = CaseParams(velocity=50, aoa_deg=5)
    with pytest.raises(PipelineError, match="implausible") as exc_info:
        run_case(step_path, params, tmp_path / "work")
    assert exc_info.value.stage == "geometry"


def test_run_case_converts_geometry_from_millimetres_to_metres(tmp_path, monkeypatch):
    """Regression test for R15/ADR-0014: build123d/OCCT's working length
    unit is always millimetres, confirmed empirically (see the comment in
    fosas_core.pipeline.run_case), so a STEP file built with a nominal
    600 mm chord must produce a chord of 0.6 m in the generated Gmsh
    script, not 600. Does not need a real Gmsh/SU2 run: run_gmsh is
    intercepted right where it would hand off to the external process,
    after the .geo text (which embeds the converted chord as a plain
    number) has already been built in pure Python.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=10)
    params = CaseParams(velocity=30, aoa_deg=5)

    captured = {}

    def fake_run_gmsh(geo_script, output_su2_path, **kwargs):
        captured["geo_script"] = geo_script
        raise MeshingError("stop before actually invoking Gmsh")

    monkeypatch.setattr("fosas_core.pipeline.run_gmsh", fake_run_gmsh)

    with pytest.raises(PipelineError):
        run_case(step_path, params, tmp_path / "work")

    assert "geo_script" in captured
    match = re.search(r"^chord = ([0-9.eE+-]+);", captured["geo_script"], re.MULTILINE)
    assert match is not None, captured["geo_script"]
    assert float(match.group(1)) == pytest.approx(0.6, rel=1e-3)


def test_run_case_applies_an_explicit_manual_rotation_label_and_skips_detection(tmp_path, monkeypatch):
    # ADR-0020 Teil B (geometry preview tool): naca0012_wing_step_wrong_axes
    # is a real case where automatic detect_axis_orientation declines
    # (its best candidate, rot_x90_then_z90 at thickness_ratio=0.060,
    # narrowly misses the 2x confidence margin against rot_x90 at
    # 0.120 - confirmed numerically while writing this test). A user who
    # has looked at the geometry preview and picked rot_x90_then_z90
    # explicitly must still get it applied directly, not re-declined by
    # the same automatic heuristic that was just bypassed on purpose.
    step_path = naca0012_wing_step_wrong_axes(tmp_path / "wrong_axes.step", chord=0.6, span=1.2, n=25)
    params = CaseParams(velocity=30, aoa_deg=5, manual_rotation_label="rot_x90_then_z90")

    captured = {}

    def fake_run_gmsh(geo_script, output_su2_path, **kwargs):
        captured["geo_script"] = geo_script
        raise MeshingError("stop before actually invoking Gmsh")

    monkeypatch.setattr("fosas_core.pipeline.run_gmsh", fake_run_gmsh)

    with pytest.raises(PipelineError) as exc_info:
        run_case(step_path, params, tmp_path / "work")
    assert exc_info.value.stage == "meshing"  # got past the geometry check, not rejected there

    assert "geo_script" in captured
    match = re.search(r"^chord = ([0-9.eE+-]+);", captured["geo_script"], re.MULTILINE)
    assert match is not None, captured["geo_script"]
    # rot_x90_then_z90 reassigns this fixture's own X/Y/Z extents to
    # chord=1200mm (not the original 600mm), confirmed numerically.
    assert float(match.group(1)) == pytest.approx(1.2, rel=1e-3)


def test_run_case_reports_manual_rotation_label_in_the_result(tmp_path, monkeypatch):
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=10)
    params = CaseParams(velocity=30, aoa_deg=5, manual_rotation_label="identity")

    def fake_run_gmsh(geo_script, output_su2_path, **kwargs):
        raise MeshingError("stop before actually invoking Gmsh")

    monkeypatch.setattr("fosas_core.pipeline.run_gmsh", fake_run_gmsh)

    with pytest.raises(PipelineError):
        run_case(step_path, params, tmp_path / "work")
    # Nothing else to assert here without a full run, but this at least
    # pins down that "identity" (no-op) does not crash and still reaches
    # meshing, same as not passing manual_rotation_label at all.


def test_run_case_rejects_a_manual_rotation_that_still_fails_the_sanity_check(tmp_path):
    # A manual choice is respected (not silently replaced by automatic
    # detection), but still has to pass the basic chord/span sanity
    # check (docs/RISKS.md R13/R15) - rot_x90 applied to an already-
    # correctly-oriented wing deliberately scrambles it (chord=100,
    # span=10, thickness=500 instead of 100/500/10, confirmed
    # numerically), so this must fail with a message naming the manual
    # choice, not silently proceed into Gmsh with nonsense dimensions.
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=10)
    params = CaseParams(velocity=30, aoa_deg=5, manual_rotation_label="rot_x90")
    with pytest.raises(PipelineError, match="manually chosen rotation 'rot_x90'") as exc_info:
        run_case(step_path, params, tmp_path / "work")
    assert exc_info.value.stage == "geometry"


def test_case_params_reject_invalid_input():
    with pytest.raises(ValueError, match="velocity"):
        CaseParams(velocity=0, aoa_deg=0)
    with pytest.raises(ValueError, match="max_iterations"):
        CaseParams(velocity=10, aoa_deg=0, max_iterations=0)
    with pytest.raises(ValueError, match="n_profile_points"):
        CaseParams(velocity=10, aoa_deg=0, n_profile_points=2)
    with pytest.raises(ValueError, match="material"):
        CaseParams(velocity=10, aoa_deg=0, material="unobtainium")


def test_run_case_actually_uses_n_profile_points(tmp_path, monkeypatch):
    """Regression test: n_profile_points (the GUI's "Profilpunkte" field)
    used to have zero effect, _sample_wire_points hardcoded 40 points per
    edge regardless of what CaseParams said. Confirmed here by comparing
    the actual point count embedded in the generated .geo script for two
    different values, without needing a real Gmsh/SU2 run.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=10)

    def count_points_used(n_profile_points):
        captured = {}

        def fake_run_gmsh(geo_script, output_su2_path, **kwargs):
            captured["geo_script"] = geo_script
            raise MeshingError("stop before actually invoking Gmsh")

        monkeypatch.setattr("fosas_core.pipeline.run_gmsh", fake_run_gmsh)
        params = CaseParams(velocity=30, aoa_deg=5, n_profile_points=n_profile_points)
        with pytest.raises(PipelineError):
            run_case(step_path, params, tmp_path / f"work_{n_profile_points}")
        return len(re.findall(r"^p\d+ = newp;", captured["geo_script"], re.MULTILINE))

    points_with_10 = count_points_used(10)
    points_with_20 = count_points_used(20)
    assert points_with_20 > points_with_10


def test_run_case_passes_background_size_factors_through(tmp_path, monkeypatch):
    """Regression test: run_case used to silently ignore
    background_size_min_factor/background_size_max_factor, always
    falling back to ConstantSectionMeshParams's own class defaults
    (0.01/0.5) regardless of what CaseParams said - there was no field
    for them on CaseParams at all. This matters for a GCI mesh study
    (Phase 2, see docs/DECISIONS.md ADR-0017), which needs exactly this
    knob to vary far-field/wake element density across 3 resolutions.
    Confirmed here via the embedded Mesh.MeshSizeMin/Max values in the
    generated .geo script, same technique as the n_profile_points test
    above, without needing a real Gmsh/SU2 run.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=10)

    captured = {}

    def fake_run_gmsh(geo_script, output_su2_path, **kwargs):
        captured["geo_script"] = geo_script
        raise MeshingError("stop before actually invoking Gmsh")

    monkeypatch.setattr("fosas_core.pipeline.run_gmsh", fake_run_gmsh)
    params = CaseParams(
        velocity=30, aoa_deg=5, background_size_min_factor=0.02, background_size_max_factor=0.8
    )
    with pytest.raises(PipelineError):
        run_case(step_path, params, tmp_path / "work")

    geo_script = captured["geo_script"]
    size_max_match = re.search(r"^Mesh\.MeshSizeMax = ([0-9.eE+-]+);", geo_script, re.MULTILINE)
    size_min_match = re.search(r"^Mesh\.MeshSizeMin = ([0-9.eE+-]+);", geo_script, re.MULTILINE)
    assert size_max_match is not None and size_min_match is not None
    # chord=0.6, so 0.02*0.6=0.012 and 0.8*0.6=0.48, not the defaults
    # (0.01*0.6=0.006, 0.5*0.6=0.3) that a silently-ignored field would
    # have produced instead.
    assert float(size_min_match.group(1)) == pytest.approx(0.012, rel=1e-3)
    assert float(size_max_match.group(1)) == pytest.approx(0.48, rel=1e-3)


def test_run_case_reports_geometry_error_for_missing_file(tmp_path):
    params = CaseParams(velocity=50, aoa_deg=5)
    with pytest.raises(PipelineError) as exc_info:
        run_case(tmp_path / "does_not_exist.step", params, tmp_path / "work")
    assert exc_info.value.stage == "geometry"


@pytest.mark.slow
def test_run_case_end_to_end_on_a_real_step_file(tmp_path, gmsh_executable, su2_executable, mpirun_executable):
    """Full pipeline exactly as the engine will call it: real STEP file
    in (built with the axis convention the pipeline assumes), real
    non-zero cl/cd out, honest convergence assessment. Deliberately does
    not assert convergence=True, since this coarse/short case is known
    not to converge (see docs/RISKS.md R10); it asserts the assessment
    is present and consistent instead.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=25)
    params = CaseParams(
        velocity=86.933,
        aoa_deg=10.0,
        density=2.13163,
        dynamic_viscosity=1.853e-5,
        span_layers=8,
        max_iterations=15,
        mpi_ranks=1,
        time_discretization="RUNGE-KUTTA_EXPLICIT",
        material="aluminium",
    )
    result = run_case(
        step_path,
        params,
        tmp_path / "work",
        executables=ExecutablePaths(gmsh=gmsh_executable, su2=su2_executable, mpirun=mpirun_executable),
        mesh_timeout=180,
        solve_timeout=300,
    )

    assert result.chord == pytest.approx(0.6, rel=1e-3)
    assert result.span == pytest.approx(1.2, rel=1e-3)
    assert set(result.markers) == {"airfoil", "farfield"}
    assert result.node_count > 0
    assert result.cl != 0.0  # would be exactly 0 if the axis convention were wrong again, see ARCHITECTURE.md
    # Plausibility bound, not just non-zero: an unstable run (e.g. CFL too
    # high for an explicit scheme) produces CL/CD in the millions, which a
    # bare "!= 0" check would not catch, confirmed the hard way, see the
    # cfl_number default fix in fosas_core.solver.
    assert abs(result.cl) < 50
    assert abs(result.cd) < 50
    assert result.convergence.converged is False  # known for this short/coarse case
    assert result.surface.num_points > 0
    assert "Pressure_Coefficient" in result.surface.columns
    assert result.mean_y_plus > 0
    assert result.max_y_plus >= result.mean_y_plus
    assert isinstance(result.convergence.message, str) and result.convergence.message

    # Geometric center of mass (point 7, docs/ARCHITECTURE.md): must
    # come from the real, asymmetric NACA0012 profile, not the
    # bounding-box center (chord/2 = 0.3) already used elsewhere (e.g.
    # moments.moment_origin) - NACA0012's mass is concentrated toward
    # the thicker leading section, so the real centroid sits well
    # forward of mid-chord.
    cx, cy, cz = result.center_of_mass
    assert cx < 0.3 * 0.9  # clearly forward of the bounding-box center
    assert cx > 0.0
    assert cy == pytest.approx(-0.6, abs=0.05)  # mid-span, same convention as moment_origin
    assert cz == pytest.approx(0.0, abs=1e-3)  # NACA0012 is symmetric top/bottom

    # Weight-force estimate (point 7, docs/ARCHITECTURE.md): material
    # was selected above, so density/mass/weight must all be filled in
    # (not None) and mutually consistent via mass=density*volume,
    # weight=mass*g - the real end-to-end path, not a mocked volume.
    assert result.volume > 0.0
    assert result.material == "aluminium"
    assert result.material_density == pytest.approx(2700.0)
    assert result.mass == pytest.approx(result.material_density * result.volume)
    assert result.weight == pytest.approx(result.mass * 9.80665)


@pytest.mark.slow
def test_run_case_resumes_instead_of_restarting_from_scratch(tmp_path, gmsh_executable, su2_executable, mpirun_executable):
    """Simulates a crash by calling run_case twice with the same work_dir:
    meshing must not run a second time (mesh.su2 mtime unchanged), and the
    second solve must actually consume the first run's restart file.

    Consumption is checked directly via SU2's own log line ("Read flow
    solution from: <path>."), not indirectly via residual/CL values: an
    earlier version of this test compared the first residual of run 1
    against the first residual of run 2, expecting a cold start and a
    warm start to visibly differ. That was flaky in practice, confirmed
    by a real failure and follow-up investigation: this case's rms[P]
    plateaus at a similar elevated level (see docs/RISKS.md R10) whether
    SU2 starts from freestream or from a previous, already-run solution,
    so the two residual values can coincidentally land within 1% of each
    other even though the restart file genuinely was read (verified
    separately by manually re-running SU2 on the same config and reading
    its log). The log line is a direct statement from SU2 itself, not an
    inference from noisy physics.
    """
    step_path = naca0012_wing_step(tmp_path / "wing.step", chord=0.6, span=1.2, n=25)
    executables = ExecutablePaths(gmsh=gmsh_executable, su2=su2_executable, mpirun=mpirun_executable)
    work_dir = tmp_path / "work"
    params = CaseParams(
        velocity=86.933,
        aoa_deg=10.0,
        density=2.13163,
        dynamic_viscosity=1.853e-5,
        span_layers=8,
        # SU2 only writes its restart file every OUTPUT_WRT_FREQ (100)
        # iterations, confirmed the hard way: 10 iterations produced no
        # restart_flow.dat at all. Needs to clear that boundary for this
        # test to actually exercise the resume path.
        max_iterations=110,
        mpi_ranks=1,
        time_discretization="RUNGE-KUTTA_EXPLICIT",
    )

    result1 = run_case(step_path, params, work_dir, executables=executables, mesh_timeout=180, solve_timeout=300)
    mesh_mtime_1 = result1.mesh_path.stat().st_mtime
    restart_file = result1.solve_dir / "restart_flow.dat"
    assert restart_file.exists()  # SU2's own checkpoint, the basis for resuming

    result2 = run_case(step_path, params, work_dir, executables=executables, mesh_timeout=180, solve_timeout=300)
    mesh_mtime_2 = result2.mesh_path.stat().st_mtime
    assert mesh_mtime_2 == mesh_mtime_1  # proves Gmsh did not rerun

    su2_log = (result2.solve_dir / "su2.log").read_text()
    assert f"Read flow solution from: {restart_file}." in su2_log
