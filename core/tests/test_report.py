from datetime import datetime, timezone

import pytest

from fosas_core.report import PolarReportData, PolarReportPoint, ReportError, render_polar_report


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
