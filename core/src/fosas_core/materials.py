"""Reference material densities for an optional weight-force estimate
(point 7 of the Technische-Mechanik-Visualisierung backlog, see
docs/ARCHITECTURE.md). Explicitly Annahme/Richtwert, not Gesichert: real
alloys/batches vary, and FOSAS has no way to verify which exact grade a
user's part is actually made of, nor whether the part is even made of a
single homogeneous material throughout. Values are representative
reference points from public engineering sources, not measured for any
specific part.

Sources (checked 2026-10-14 via web search):
- Aluminium (6061): ~2700 kg/m^3. Wikipedia "6061 aluminium alloy" and
  multiple engineering material datasheets agree on this value.
- Stahl (Baustahl, generic carbon steel): ~7850 kg/m^3, a standard
  engineering reference value (e.g. EngineeringToolbox-style density
  tables).
- Titan (Ti-6Al-4V, the common aerospace titanium alloy): ~4430 kg/m^3,
  standard reference value for this specific alloy.
- CFK (Kohlefaser-Verbund/CFRP, thermoset): ~1570 kg/m^3; carbon-fiber
  composites in general cluster around 1500-1600 kg/m^3 depending on
  fiber/resin ratio, so this is explicitly a representative midpoint,
  not a specific layup's measured value.
- GFK (Glasfaser-Verbund/GFRP): ~2000 kg/m^3, a standard reference
  value for glass-fiber composites.
- ABS (Kunststoff, Spritzguss/3D-Druck): ~1050 kg/m^3.
- PLA (Kunststoff, 3D-Druck): ~1240 kg/m^3.
- Balsaholz: ~160 kg/m^3; real balsa varies widely (roughly
  100-200 kg/m^3 depending on the individual piece of wood), 160 is a
  commonly cited typical value, not a guarantee for any specific piece.
"""

from __future__ import annotations

MATERIAL_DENSITIES_KG_M3: dict[str, float] = {
    "aluminium": 2700.0,
    "stahl": 7850.0,
    "titan": 4430.0,
    "cfk": 1570.0,
    "gfk": 2000.0,
    "abs": 1050.0,
    "pla": 1240.0,
    "balsaholz": 160.0,
}

# Standard gravity, SI-defined exact constant (CODATA/ISO 80000-3), not
# a location-dependent measured value.
STANDARD_GRAVITY = 9.80665
