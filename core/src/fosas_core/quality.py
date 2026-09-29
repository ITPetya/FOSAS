"""Convergence assessment.

This is deliberately narrow: it only judges whether a residual history
has actually converged, not the full quality ampel described in the
project scope (y+ distribution, mesh independence/GCI, balances). Those
need a mesh study (multiple meshes) and are Phase 2 work. Judging
convergence from a single run's history is something we can and should
do now, and the Phase 1 spike (see docs/RISKS.md R10) showed exactly why
it matters: a residual can plateau far from any reasonable target while
looking superficially stable, and reporting that as "converged" would be
the kind of dishonest result this project explicitly rejects (see
CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConvergenceAssessment:
    converged: bool
    final_residual: float
    residual_threshold: float
    is_plateaued: bool
    message: str


def assess_convergence(
    residual_history: tuple[float, ...],
    residual_threshold: float = -8.0,
    plateau_window: int = 100,
    plateau_slope_threshold: float = 1e-4,
) -> ConvergenceAssessment:
    """Judge whether a residual history (e.g. log10 RMS of a flow
    variable, more negative is better) indicates real convergence.

    "Converged" requires the final value to be at or below
    residual_threshold. Additionally, the trend over the last
    plateau_window iterations is checked: if the average per-iteration
    change is smaller than plateau_slope_threshold while the threshold
    has not been reached, that is flagged as a plateau, not slow but
    ongoing convergence, since more iterations would not help.
    """
    if len(residual_history) == 0:
        raise ValueError("residual_history must not be empty")

    final_residual = residual_history[-1]
    window = residual_history[-plateau_window:] if len(residual_history) >= 2 else residual_history
    if len(window) >= 2:
        slope = (window[-1] - window[0]) / (len(window) - 1)
    else:
        slope = float("inf")  # a single point says nothing about trend
    is_plateaued = abs(slope) < plateau_slope_threshold

    converged = final_residual <= residual_threshold

    if converged:
        message = (
            f"Restfehler {final_residual:.3g} erreicht das Ziel {residual_threshold:.3g}, "
            "als konvergiert bewertet."
        )
    elif is_plateaued:
        message = (
            f"Restfehler {final_residual:.3g} liegt ueber dem Ziel {residual_threshold:.3g} "
            f"und aendert sich ueber die letzten {len(window)} Iterationen kaum noch "
            "(Plateau). Weitere Iterationen werden das voraussichtlich nicht loesen, "
            "siehe docs/RISKS.md R10 fuer bekannte Ursachenkandidaten."
        )
    else:
        message = (
            f"Restfehler {final_residual:.3g} liegt ueber dem Ziel {residual_threshold:.3g}, "
            "faellt aber noch. Mehr Iterationen koennten helfen."
        )

    return ConvergenceAssessment(
        converged=converged,
        final_residual=final_residual,
        residual_threshold=residual_threshold,
        is_plateaued=is_plateaued,
        message=message,
    )
