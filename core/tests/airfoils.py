"""NACA 4-digit profile point generator, used only by tests as a known
geometry fixture. Not part of the shipped fosas_core package: FOSAS takes
arbitrary STEP geometry from users, it does not generate airfoils itself.
"""

import math


def naca4_points(chord: float, thickness: float = 0.12, n: int = 40) -> tuple[tuple[float, float], ...]:
    """Closed profile loop (x, z) for a symmetric NACA 4-digit section,
    cosine-spaced, starting and ending at the trailing edge.
    """

    def half_thickness(x: float) -> float:
        return 5 * thickness * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )

    xs = [0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]
    upper = [(x * chord, half_thickness(x) * chord) for x in xs]
    lower = [(x * chord, -half_thickness(x) * chord) for x in reversed(xs[1:-1])]
    return tuple(upper + lower)
