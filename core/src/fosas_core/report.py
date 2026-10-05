"""Typst-based PDF report rendering. Pure fosas_core, no FastAPI/
Pydantic dependency: the engine builds a plain PolarReportData from its
own PolarStudyOut/JobStore and calls render_polar_report, see
docs/ARCHITECTURE.md ("Berichtserzeugung (Typst)" listed under Core).

Chart rendering uses matplotlib, embedded as a PNG into the Typst
document, instead of a Typst-native plotting package (cetz-plot):
cetz-plot is an @preview package fetched from packages.typst.org on
first use, which would need network access the first time a report is
rendered - this project consistently avoids runtime network
dependencies for its tool chain (see docs/RISKS.md R3/R5), so the
chart is rendered entirely in Python instead. The bundled `typst`
package itself ships the full compiler and needs no network access as
long as the .typ template (see report_templates/polar_report.typ)
never imports an @preview package, which it does not.

API note (Gesichert, confirmed directly against the installed
typst==0.15.0 package's own type stub and a real compile call, NOT
just from secondary documentation): typst.compile's `input` is a
single .typ file (bytes or a path), not a dict of multiple named
files - an earlier assumption that it accepted a dict mapping
filenames to content was wrong and was caught before being built on.
To let the template reference a data file and an image, all three
files (main.typ, data.json, chart.png) are written into one real
temporary directory, and `root` is set to that directory so the
template can reference them via root-relative paths ("/data.json",
"/chart.png"), confirmed working in a direct smoke test.
"""

from __future__ import annotations

import io
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless rendering, no display/X server available on the engine host
import matplotlib.pyplot as plt
import typst

_TEMPLATE_PATH = Path(__file__).parent / "report_templates" / "polar_report.typ"


class ReportError(Exception):
    """A report could not be rendered (no data, or the Typst compiler itself failed)."""


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


def _render_chart_png(data: PolarReportData) -> bytes:
    plotted = [p for p in data.points if p.cl is not None and p.cd is not None]
    fig, (ax_cl, ax_cd) = plt.subplots(1, 2, figsize=(8, 3.2))
    if plotted:
        aoas = [p.aoa_deg for p in plotted]
        ax_cl.plot(aoas, [p.cl for p in plotted], marker="o")
        ax_cl.set_xlabel("Anstellwinkel (Grad)")
        ax_cl.set_ylabel("cl")
        ax_cl.grid(True, alpha=0.3)
        ax_cd.plot(aoas, [p.cd for p in plotted], marker="o", color="tab:orange")
        ax_cd.set_xlabel("Anstellwinkel (Grad)")
        ax_cd.set_ylabel("cd")
        ax_cd.grid(True, alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def render_polar_report(data: PolarReportData) -> bytes:
    """Renders a one-polar PDF report: a cl/cd-vs-AoA chart plus a data
    table, disclosing any non-converged/failed point rather than
    hiding it (see docs/DECISIONS.md ADR-0016/ADR-0017's disclosure
    principle: no sugar-coating a result). Raises ReportError if
    there is nothing to render or if the Typst compiler itself fails.
    """
    chart_png = _render_chart_png(data)
    any_not_converged = any(p.status != "done" or p.converged is False for p in data.points)
    payload = {
        "title": data.title,
        "generated_at": data.generated_at.isoformat(),
        "any_not_converged": any_not_converged,
        "points": [
            {"aoa_deg": p.aoa_deg, "cl": p.cl, "cd": p.cd, "status": p.status, "converged": p.converged}
            for p in data.points
        ],
    }

    with tempfile.TemporaryDirectory(prefix="fosas_report_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        (tmp_dir / "data.json").write_text(json.dumps(payload))
        (tmp_dir / "chart.png").write_bytes(chart_png)
        main_typ_path = tmp_dir / "main.typ"
        main_typ_path.write_bytes(_TEMPLATE_PATH.read_bytes())

        try:
            pdf_bytes = typst.compile(str(main_typ_path), root=str(tmp_dir), format="pdf")
        except Exception as exc:  # typst.compile raises TypstError (or similar) on compile failures
            raise ReportError(f"Typst-Kompilierung fehlgeschlagen: {exc}") from exc

    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF"):
        raise ReportError("Typst hat kein gueltiges PDF zurueckgegeben.")
    return pdf_bytes
