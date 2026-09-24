# Core

Reine Python-Logik ohne UI-Import. Siehe `../docs/ARCHITECTURE.md`.

Bisher enthalten:

- `fosas_core.boundary_layer`: Reynolds-Zahl und y+-basierte
  Ersteinschaetzung der ersten Zellhoehe fuer die Grenzschichtvernetzung.
- `fosas_core.geometry`: STEP-Import und Wasserdichtheitspruefung ueber
  build123d, siehe ADR-0003 in `../docs/DECISIONS.md`.
- `fosas_core.meshing`: Gmsh-Adapter (ausschliesslich externer Prozess,
  siehe ADR-0002) fuer Koerper mit konstantem Querschnitt, mit echter
  Grenzschicht (2D-Kurve plus Extrusion, siehe ADR-0007). Nutzt
  `boundary_layer` fuer die erste Zellhoehe statt eines geratenen Werts.

- `fosas_core.solver`: SU2-Adapter (ausschliesslich externer Prozess) fuer
  inkompressibles RANS. Anders als bei Gmsh ist der Exit-Code bei SU2
  ein verlaesslicher Fehlerindikator (eigener Test bestaetigt), deshalb
  kein Scan des vollstaendigen Logs noetig, nur Auswertung von Exit-Code
  und History-Datei.

`meshing` funktioniert nachweislich sowohl mit direkt uebergebenen
Profilpunkten als auch mit einer aus einer STEP-Datei importierten
Kontur, aber nur fuer Koerper mit konstantem Querschnitt (siehe
`../docs/ARCHITECTURE.md`, `../docs/OPEN_QUESTIONS.md`).

Noch nicht enthalten: Cache, Bericht, automatische
Konvergenzbeurteilung/Qualitaetsampel (siehe RISKS.md R10, ein Testlauf
mit dieser Werkzeugkette konvergiert auf dem aktuellen Testnetz nicht
zuverlaessig, das ist eine offene fachliche Frage, keine Einschraenkung
des Solver-Adapters selbst).

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
export FOSAS_GMSH_EXECUTABLE=/pfad/zu/gmsh   # falls gmsh nicht im PATH liegt
pytest tests/                # alle Tests, inklusive langsamer Gmsh-Laeufe
pytest tests/ -m "not slow"  # nur die schnellen, ohne externe Prozesse
```

