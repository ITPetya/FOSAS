# FOSAS, Free Open-Source Aerodynamic Solver

FOSAS ist ein Open-Source-Programm, das aus einer STEP-Datei und wenigen
bauteilunabhaengigen Parametern automatisiert Aussenaerodynamik-Simulationen
orchestriert, auswertet und als wissenschaftlichen Bericht aufbereitet.

FOSAS ist kein eigener CFD-Loeser. Der Mehrwert liegt in der Automatisierung
(Geometrieaufbereitung, Vernetzung, Loeseraufruf, Auswertung), in ehrlicher
Ausweisung von Unsicherheit, und in einem reproduzierbaren, exportierbaren
Bericht statt einer huebschen, aber unbelegten Animation.

## Status

Projekt befindet sich in Phase 0 (Klaerung und Machbarkeit). Es existiert noch
keine Fachlogik. Siehe `docs/ARCHITECTURE.md` fuer den aktuellen Planungsstand,
`docs/DECISIONS.md` fuer bereits getroffene Entscheidungen, `docs/RISKS.md` fuer
bekannte Risiken, und `docs/OPEN_QUESTIONS.md` fuer offene Punkte.

Der Phasenplan (siehe `CLAUDE.md`) sieht vor, dass keine Phase begonnen wird,
bevor die vorige durch den Projektverantwortlichen freigegeben wurde.

## Umfang Version 1 (Kurzfassung)

Nur starre Koerper, reine Aussenumstroemung, stationaeres RANS (k-omega SST,
optional Transitionsmodell fuer niedrige Reynolds-Zahlen). Kraft- und
Momentenbeiwerte, Polaren, Oberflaechen-cp, Stromlinien, Q-Kriterium,
Ablösegebiete. Automatische Qualitaetspruefung mit Ampel (Netzqualitaet, y+,
Konvergenz, Netzunabhaengigkeit, Modelltauglichkeit). Wissenschaftlicher
PDF-Bericht mit Netzstudie und GCI. Quasi-stationaere, frei begehbare
Animation ueber vorab berechnete Einzelzustaende. Details siehe
`docs/ARCHITECTURE.md`.

Kein eigener Solver, keine Materialien/Statik/Thermik, keine Innenstroemung,
keine rotierenden Teile, keine transsonische/supersonische Stroemung.

## Architektur (Kurzfassung)

Drei Schichten: eine UI-freie Core-Bibliothek (Python) mit Solver-Adapter
(SU2, Gmsh), eine FastAPI-Engine mit REST/WebSocket, und mehrere Clients
(Web-UI, CLI, KI-Zugriff via MCP/OpenAPI). Die UI darf nichts koennen, was
die API nicht auch kann. Details siehe `docs/ARCHITECTURE.md`.

## Lizenz

Apache License 2.0, siehe `LICENSE`. Eine Liste der Lizenzen aller
eingebundenen Fremdkomponenten folgt vor dem ersten Release in
`THIRD-PARTY-NOTICES.md` (noch nicht angelegt, siehe `docs/RISKS.md`).

## Mitwirken

Aktuell ein Ein-Personen-Projekt in frueher Planungsphase. Issues und
Diskussion sind willkommen, ein Beitragsleitfaden folgt, sobald Phase 1
abgeschlossen ist.
