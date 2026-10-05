"""Typst-based PDF report rendering. Pure fosas_core, no FastAPI/
Pydantic dependency: the engine builds plain report-data dataclasses
from its own *StudyOut models and calls render_polar_report/
render_gci_report, see docs/ARCHITECTURE.md ("Berichtserzeugung
(Typst)" listed under Core).

Chart rendering uses matplotlib, embedded as a PNG into the Typst
document, instead of a Typst-native plotting package (cetz-plot):
cetz-plot is an @preview package fetched from packages.typst.org on
first use, which would need network access the first time a report is
rendered - this project consistently avoids runtime network
dependencies for its tool chain (see docs/RISKS.md R3/R5), so charts
are rendered entirely in Python instead. The bundled `typst` package
itself ships the full compiler and needs no network access as long as
the .typ templates (see report_templates/) never import an @preview
package, which they do not.

API note (Gesichert, confirmed directly against the installed
typst==0.15.0 package's own type stub and a real compile call, NOT
just from secondary documentation): typst.compile's `input` is a
single .typ file (bytes or a path), not a dict of multiple named
files - an earlier assumption that it accepted a dict mapping
filenames to content was wrong and was caught before being built on.
To let a template reference a data file and an image, all three files
(main.typ, data.json, chart.png) are written into one real temporary
directory, and `root` is set to that directory so the template can
reference them via root-relative paths ("/data.json", "/chart.png"),
confirmed working in a direct smoke test.
"""

from __future__ import annotations

import io
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering, no display/X server available on the engine host
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import typst

_TEMPLATE_DIR = Path(__file__).parent / "report_templates"
_POLAR_TEMPLATE_PATH = _TEMPLATE_DIR / "polar_report.typ"
_GCI_TEMPLATE_PATH = _TEMPLATE_DIR / "gci_report.typ"
_COMBINED_TEMPLATE_PATH = _TEMPLATE_DIR / "combined_report.typ"


class ReportError(Exception):
    """A report could not be rendered (no data, or the Typst compiler itself failed)."""


def _format_timestamp(dt: datetime) -> str:
    """Renders e.g. "05.10.2026 19:34 UTC" instead of a raw isoformat()
    string (which includes microseconds and a "+00:00" offset) - a
    real, visible readability defect found during Phase 2 report
    polish, not a change to any underlying data."""
    return dt.strftime("%d.%m.%Y %H:%M") + f" {dt.tzname() or 'UTC'}"


def _compile_report(template_path: Path, payload: dict[str, Any], files: dict[str, bytes]) -> bytes:
    """Shared Typst-compile step for every report kind: writes the
    template, a JSON data file, and any pre-rendered chart PNGs (keyed
    by their root-relative filename, e.g. "chart.png" or
    "polar_chart.png") into one temporary project directory, compiles
    it, and returns PDF bytes.
    """
    with tempfile.TemporaryDirectory(prefix="fosas_report_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        (tmp_dir / "data.json").write_text(json.dumps(payload))
        for filename, content in files.items():
            (tmp_dir / filename).write_bytes(content)
        main_typ_path = tmp_dir / "main.typ"
        main_typ_path.write_bytes(template_path.read_bytes())

        try:
            pdf_bytes = typst.compile(str(main_typ_path), root=str(tmp_dir), format="pdf")
        except Exception as exc:  # typst.compile raises TypstError (or similar) on compile failures
            raise ReportError(f"Typst-Kompilierung fehlgeschlagen: {exc}") from exc

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF"):
        raise ReportError("Typst hat kein gueltiges PDF zurueckgegeben.")
    return pdf_bytes


# --- Polaren-Bericht -------------------------------------------------


@dataclass(frozen=True)
class PolarReportPoint:
    aoa_deg: float
    cl: float | None
    cd: float | None
    status: str  # "done" | "failed" | "pending" | "running", see jobs.JobStatus
    converged: bool | None


@dataclass(frozen=True)
class PolarReportData:
    title: str
    generated_at: datetime
    points: tuple[PolarReportPoint, ...]

    def __post_init__(self):
        if len(self.points) == 0:
            raise ValueError("points must not be empty")


def _disable_y_offset_notation(ax):
    # Found during Phase 2 report polish (real generated chart,
    # cd clustered tightly around ~13.4): matplotlib's default y-axis
    # behaviour shows a "+1.34e1" offset annotation above the axis
    # instead of plain numbers whenever values share a large common
    # base - technically correct, but a real readability defect for a
    # reader without a matplotlib background (see docs/CLAUDE.md, this
    # project's target user is explicitly not assumed to be a CFD/
    # software expert). Plain numbers are clearer here even though the
    # axis span itself is small.
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)


def _render_polar_chart_png(data: PolarReportData) -> bytes:
    plotted = [p for p in data.points if p.cl is not None and p.cd is not None]
    fig, (ax_cl, ax_cd) = plt.subplots(1, 2, figsize=(8, 3.2))
    if plotted:
        aoas = [p.aoa_deg for p in plotted]
        ax_cl.plot(aoas, [p.cl for p in plotted], marker="o")
        ax_cl.set_xlabel("Anstellwinkel (Grad)")
        ax_cl.set_ylabel("cl")
        ax_cl.grid(True, alpha=0.3)
        _disable_y_offset_notation(ax_cl)
        ax_cd.plot(aoas, [p.cd for p in plotted], marker="o", color="tab:orange")
        ax_cd.set_xlabel("Anstellwinkel (Grad)")
        ax_cd.set_ylabel("cd")
        ax_cd.grid(True, alpha=0.3)
        _disable_y_offset_notation(ax_cd)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def render_polar_report(data: PolarReportData) -> bytes:
    """Renders a one-polar PDF report: a cl/cd-vs-AoA chart plus a data
    table, disclosing any non-converged/failed point rather than
    hiding it (see docs/DECISIONS.md ADR-0016/ADR-0017's disclosure
    principle: no sugar-coating a result). Raises ReportError if the
    Typst compiler itself fails.
    """
    chart_png = _render_polar_chart_png(data)
    any_not_converged = any(p.status != "done" or p.converged is False for p in data.points)
    payload = {
        "title": data.title,
        "generated_at": _format_timestamp(data.generated_at),
        "any_not_converged": any_not_converged,
        "points": [
            {"aoa_deg": p.aoa_deg, "cl": p.cl, "cd": p.cd, "status": p.status, "converged": p.converged}
            for p in data.points
        ],
    }
    return _compile_report(_POLAR_TEMPLATE_PATH, payload, {"chart.png": chart_png})


# --- GCI-Bericht -------------------------------------------------------


@dataclass(frozen=True)
class GciReportLevel:
    resolution: str  # "fine" | "medium" | "coarse"
    element_count: int | None
    cl: float | None
    cd: float | None
    status: str


@dataclass(frozen=True)
class GciReportMetric:
    """Mirrors fosas_core.gci.GciResult, once each for cl and cd."""

    r21: float
    apparent_order_p: float
    extrapolated_value: float
    gci_fine_percent: float
    oscillatory: bool
    message: str


@dataclass(frozen=True)
class GciReportData:
    title: str
    generated_at: datetime
    refinement_ratio: float
    levels: tuple[GciReportLevel, GciReportLevel, GciReportLevel]  # fine, medium, coarse
    cl_metric: GciReportMetric | None
    cd_metric: GciReportMetric | None
    result_error: str | None

    def __post_init__(self):
        if len(self.levels) != 3:
            raise ValueError("levels must have exactly 3 entries (fine, medium, coarse)")


def _render_gci_chart_png(data: GciReportData) -> bytes:
    # x-axis: element_count, linear (see _format_axis below for why
    # NOT log scale, despite that being the textbook default) - only
    # plotted for levels that actually have both a count and a value,
    # same "skip incomplete rows" approach as the polar chart, see
    # docs/DECISIONS.md ADR-0016/ADR-0017's disclosure principle (do
    # not silently fabricate a point for missing data).
    plotted_cl = [lvl for lvl in data.levels if lvl.element_count is not None and lvl.cl is not None]
    plotted_cd = [lvl for lvl in data.levels if lvl.element_count is not None and lvl.cd is not None]
    fig, (ax_cl, ax_cd) = plt.subplots(1, 2, figsize=(8, 3.2))

    def _format_axis(ax):
        # A log-scale x-axis is the textbook default for a mesh-
        # convergence plot, but was actively wrong for this project's
        # own data: confirmed the hard way with a real GCI study
        # (refinement ratio 1.2-1.5, so element counts span less than
        # a factor of 2). matplotlib's LogLocator either crams many
        # overlapping decade-adjacent ticks into that narrow a span, or
        # (after constraining numticks) finds no decade boundary to
        # place a tick on at all and renders an unlabeled axis - tried
        # and rejected both. A linear axis has neither problem and is
        # not actually less correct here: log scale only earns its
        # keep over a wide span of mesh sizes, not a ~20-50% refinement
        # step, so this project's typical refinement ratios do not
        # need it.
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=4, integer=True))
        ax.ticklabel_format(axis="x", style="plain")
        _disable_y_offset_notation(ax)  # see its own docstring: same "+1.34e1" issue can hit cl/cd here too

    if plotted_cl:
        plotted_cl = sorted(plotted_cl, key=lambda lvl: lvl.element_count)
        ax_cl.plot([lvl.element_count for lvl in plotted_cl], [lvl.cl for lvl in plotted_cl], marker="o")
        _format_axis(ax_cl)
        ax_cl.set_xlabel("Elementanzahl")
        ax_cl.set_ylabel("cl")
        ax_cl.grid(True, alpha=0.3)
    if plotted_cd:
        plotted_cd = sorted(plotted_cd, key=lambda lvl: lvl.element_count)
        ax_cd.plot(
            [lvl.element_count for lvl in plotted_cd], [lvl.cd for lvl in plotted_cd], marker="o", color="tab:orange"
        )
        _format_axis(ax_cd)
        ax_cd.set_xlabel("Elementanzahl")
        ax_cd.set_ylabel("cd")
        ax_cd.grid(True, alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def _metric_payload(metric: GciReportMetric | None) -> dict[str, Any] | None:
    if metric is None:
        return None
    return {
        "r21": metric.r21,
        "apparent_order_p": metric.apparent_order_p,
        "extrapolated_value": metric.extrapolated_value,
        "gci_fine_percent": metric.gci_fine_percent,
        "oscillatory": metric.oscillatory,
        "message": metric.message,
    }


def _gci_payload(data: GciReportData) -> dict[str, Any]:
    any_level_not_done = any(lvl.status != "done" for lvl in data.levels)
    return {
        "title": data.title,
        "generated_at": _format_timestamp(data.generated_at),
        "refinement_ratio": data.refinement_ratio,
        "any_level_not_done": any_level_not_done,
        "result_error": data.result_error,
        "levels": [
            {
                "resolution": lvl.resolution,
                "element_count": lvl.element_count,
                "cl": lvl.cl,
                "cd": lvl.cd,
                "status": lvl.status,
            }
            for lvl in data.levels
        ],
        "cl_metric": _metric_payload(data.cl_metric),
        "cd_metric": _metric_payload(data.cd_metric),
    }


def render_gci_report(data: GciReportData) -> bytes:
    """Renders a one-GCI-study PDF report: a cl/cd-vs-element-count
    chart (linear x-axis, see _render_gci_chart_png for why not log)
    plus a per-resolution table and the computed GCI metrics,
    disclosing a missing/failed result rather than hiding it (see
    docs/DECISIONS.md ADR-0016/ADR-0017, and R20 on why a computed GCI
    percentage near a zero-valued quantity is reported as-is, not
    masked or suppressed). Raises ReportError if the Typst compiler
    itself fails.
    """
    chart_png = _render_gci_chart_png(data)
    return _compile_report(_GCI_TEMPLATE_PATH, _gci_payload(data), {"chart.png": chart_png})


# --- Kombinierter Bericht (Polare + GCI derselben Geometrie) -----------


@dataclass(frozen=True)
class CombinedReportData:
    generated_at: datetime
    polar: PolarReportData
    gci: GciReportData


def render_combined_report(data: CombinedReportData) -> bytes:
    """Renders a single PDF combining a polar sweep and a GCI mesh
    study for the same geometry/setup, requested together explicitly
    by the caller (no automatic case-matching: a PolarStudy and a
    GciStudy have no linkage field in the data model, so the two study
    ids to combine are always an explicit choice, never inferred e.g.
    from a matching filename - see the route in app.py). Both
    sub-reports' own disclosure rules (non-converged points, failed
    mesh levels, oscillatory GCI convergence, a GCI result_error) carry
    through unchanged, just placed in one document instead of two.
    """
    polar_chart_png = _render_polar_chart_png(data.polar)
    gci_chart_png = _render_gci_chart_png(data.gci)
    any_not_converged = any(p.status != "done" or p.converged is False for p in data.polar.points)
    payload = {
        "generated_at": _format_timestamp(data.generated_at),
        "polar": {
            "title": data.polar.title,
            "any_not_converged": any_not_converged,
            "points": [
                {"aoa_deg": p.aoa_deg, "cl": p.cl, "cd": p.cd, "status": p.status, "converged": p.converged}
                for p in data.polar.points
            ],
        },
        "gci": _gci_payload(data.gci),
    }
    files = {"polar_chart.png": polar_chart_png, "gci_chart.png": gci_chart_png}
    return _compile_report(_COMBINED_TEMPLATE_PATH, payload, files)
