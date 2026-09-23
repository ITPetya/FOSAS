# Core

Reine Python-Logik ohne UI-Import. Siehe `../docs/ARCHITECTURE.md`.

Bisher enthalten:

- `fosas_core.boundary_layer`: Reynolds-Zahl und y+-basierte
  Ersteinschaetzung der ersten Zellhoehe fuer die Grenzschichtvernetzung.
- `fosas_core.geometry`: STEP-Import und Wasserdichtheitspruefung ueber
  build123d, siehe ADR-0003 in `../docs/DECISIONS.md`.

Noch nicht enthalten: Netzerzeugung (Gmsh-Adapter), Loeseraufruf
(SU2-Adapter), Cache, Bericht.

## Einrichtung

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Fuer `fosas_core.geometry` (build123d/OpenCASCADE-Bindings) wird unter
Linux ohne grafische Oberflaeche zusaetzlich `libgl1`, `libglx0`,
`libglvnd0` (oder das Distributions-Aequivalent) benoetigt, siehe
`../docs/RISKS.md` R7. `fosas_core.boundary_layer` hat keine
Zusatzabhaengigkeiten.

## Tests

```
pytest tests/
```

