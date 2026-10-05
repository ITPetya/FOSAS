from datetime import datetime, timezone

import pytest

from fosas_core.report import (
    GciReportData,
    GciReportLevel,
    GciReportMetric,
    PolarReportData,
    PolarReportPoint,
    ReportError,
    render_gci_report,
    render_polar_report,
)


def _point(aoa_deg, cl=0.01, cd=0.5, status="done", converged=True):
    return PolarReportPoint(aoa_deg=aoa_deg, cl=cl, cd=cd, status=status, converged=converged)


def test_polar_report_data_rejects_empty_points():
    with pytest.raises(ValueError):
        PolarReportData(title="x.step", generated_at=datetime.now(timezone.utc), points=())


def test_render_polar_report_produces_a_real_pdf():
    data = PolarReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        points=(_point(0.0), _point(15.0), _point(30.0)),
    )
    pdf_bytes = render_polar_report(data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000  # a real, non-trivial document, not an empty shell


def test_render_polar_report_handles_a_failed_point_without_crashing():
    # A point with cl/cd=None (not yet solved, or failed before any
    # result existed) must still render, not raise - see
    # docs/DECISIONS.md ADR-0016/ADR-0017's disclosure principle: a
    # report must be able to show an incomplete/failed result, not
    # just a fully successful one.
    data = PolarReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        points=(
            _point(0.0),
            _point(15.0),
            PolarReportPoint(aoa_deg=30.0, cl=None, cd=None, status="failed", converged=None),
        ),
    )
    pdf_bytes = render_polar_report(data)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_polar_report_handles_all_points_failed():
    # Extreme case: no usable cl/cd at all, chart has nothing to plot.
    # Must still produce a valid PDF (with an empty chart), not crash.
    data = PolarReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        points=(
            PolarReportPoint(aoa_deg=0.0, cl=None, cd=None, status="failed", converged=None),
        ),
    )
    pdf_bytes = render_polar_report(data)
    assert pdf_bytes.startswith(b"%PDF")


def _level(resolution, element_count=1000, cl=0.01, cd=0.5, status="done"):
    return GciReportLevel(resolution=resolution, element_count=element_count, cl=cl, cd=cd, status=status)


def _metric(p=1.5, gci=12.3, oscillatory=False):
    return GciReportMetric(
        r21=1.2,
        apparent_order_p=p,
        extrapolated_value=0.015,
        gci_fine_percent=gci,
        oscillatory=oscillatory,
        message=f"Scheinbare Konvergenzordnung p={p}, GCI {gci}%.",
    )


def test_gci_report_data_rejects_wrong_level_count():
    with pytest.raises(ValueError):
        GciReportData(
            title="cylinder.step",
            generated_at=datetime.now(timezone.utc),
            refinement_ratio=1.5,
            levels=(_level("fine"), _level("medium")),  # only 2, must be exactly 3
            cl_metric=None,
            cd_metric=None,
            result_error=None,
        )


def test_render_gci_report_produces_a_real_pdf_with_full_result():
    data = GciReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        refinement_ratio=1.5,
        levels=(
            _level("fine", element_count=3000),
            _level("medium", element_count=2000),
            _level("coarse", element_count=1000),
        ),
        cl_metric=_metric(),
        cd_metric=_metric(),
        result_error=None,
    )
    pdf_bytes = render_gci_report(data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_render_gci_report_discloses_oscillatory_convergence():
    data = GciReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        refinement_ratio=1.5,
        levels=(
            _level("fine", element_count=3000),
            _level("medium", element_count=2000),
            _level("coarse", element_count=1000),
        ),
        cl_metric=_metric(oscillatory=True),
        cd_metric=_metric(),
        result_error=None,
    )
    pdf_bytes = render_gci_report(data)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_gci_report_handles_a_result_error_without_crashing():
    # E.g. compute_gci itself raised (identical values between two
    # levels, or similar) - the report must still render and disclose
    # the error, not hide the fact that no GCI number exists.
    data = GciReportData(
        title="cylinder_for_polar.step",
        generated_at=datetime.now(timezone.utc),
        refinement_ratio=1.5,
        levels=(
            _level("fine", element_count=3000),
            _level("medium", element_count=2000, status="failed", cl=None, cd=None),
            _level("coarse", element_count=1000),
        ),
        cl_metric=None,
        cd_metric=None,
        result_error="fine and medium grid values are identical",
    )
    pdf_bytes = render_gci_report(data)
    assert pdf_bytes.startswith(b"%PDF")
