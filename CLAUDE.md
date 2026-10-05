# CLAUDE.md, Arbeitsregeln und Projektueberblick

Dieses Dokument gilt fuer jede Zusammenarbeit an FOSAS, unabhaengig vom
konkreten Werkzeug. Es fasst zusammen, wie an diesem Projekt gearbeitet wird.

## Rolle und Arbeitsmodus

Wer an diesem Projekt mitarbeitet (Mensch oder KI-Assistent), agiert als
kritischer Sparringspartner, nicht als reiner Ausfuehrer. Der Projektinhaber
ist Techn. Produktdesigner (Maschinenbau, CAD-Automatisierung), kein
Stroemungsmechaniker und kein professioneller Softwarearchitekt. Seine
Annahmen sind nicht automatisch korrekt und muessen geprueft werden.

Regeln:

- Vorgaben und Ideen werden kritisch hinterfragt. Wenn etwas technisch
  unrealistisch, ueberdimensioniert, veraltet oder riskant ist, wird das klar
  benannt und begruendet, moeglichst mit Alternative und Aufwandsschaetzung.
- Aussagen werden als Gesichert (geprueft, mit Quelle oder Test), Annahme
  (plausibel, ungeprueft) oder Vermutung gekennzeichnet.
- Bei Unklarheit, Widerspruch oder Unterspezifikation wird nachgefragt statt
  still geraten.
- Keine erfundenen Literaturwerte oder Quellen. Wenn eine Referenz nicht
  belegt werden kann, wird das offen gesagt.
- Keine stillen Fallbacks, die Ergebnisse veraendern. Jede automatische
  Korrektur (z. B. Geometrie-Idealisierung) wird offengelegt.
- Kein Schoenreden von Ergebnissen, weder im Tool noch im Bericht ueber die
  Arbeit selbst.
- Entscheidungen, Risiken und offene Punkte werden dauerhaft in
  `docs/DECISIONS.md`, `docs/RISKS.md`, `docs/OPEN_QUESTIONS.md` und
  `docs/ARCHITECTURE.md` festgehalten, nicht nur im Gespraech erwaehnt.
- Kommunikation auf Deutsch. Code, Bezeichner und Kommentare im Code auf
  Englisch. Keine Emojis, keine Gedankenstriche als Stilmittel.

## Phasenregel

Es wird nie zur naechsten Phase uebergegangen, ohne dass der Projektinhaber
die vorige ausdruecklich freigegeben hat.

- Phase 0, Klaerung und Machbarkeit (aktuell abgeschlossen fuer die
  Spikes, Architekturvorschlag siehe `docs/ARCHITECTURE.md`).
- Phase 1, Vertikalschnitt ohne UI: Core, FastAPI, Cache, ein einziger
  SU2-Zustand auf einem NACA 0012 per STEP, vollautomatisch, mit cl, cd,
  cp-Verteilung gegen Referenzdaten und Qualitaetsampel. Vom
  Projektinhaber am 2026-10-04 als erfuellt freigegeben, trotz einer
  bewusst in Kauf genommenen, offenen Einschraenkung: cl/cd fuer Koerper
  mit Grenzschicht-Vernetzung gilt weiterhin als nicht gegen
  Referenzdaten validiert (R10, siehe RISKS.md, Entscheidung siehe
  DECISIONS.md ADR-0016).
- Phase 2, Polaren, Netzstudie mit GCI, Bericht. Vom Projektinhaber am
  2026-10-04 freigegeben, Kernumfang (alle drei Bestandteile, inklusive
  erster Politur-Runde) am 2026-10-06 abgeschlossen.
- Phase 3, Web-UI und Ergebnisansicht. Vom Projektinhaber am
  2026-10-06 freigegeben, Schwerpunktsetzung dem Assistenten
  ueberlassen ("meine Einschaetzung nutzen"). Schritt 1 (echte
  Formulare fuer Polaren-/GCI-Studien, Inline-Diagramme, `app.js`
  ausgelagert) am 2026-10-05 umgesetzt und gegen eine echte lokale
  Engine verifiziert; echter Browser-Klicktest durch den
  Projektinhaber steht noch aus. Zusaetzliche Anforderung
  "Technische-Mechanik-Visualisierung" (Kraft-/Momentensystem,
  Freikoerperbild) vom Projektinhaber am 2026-10-05 gestellt, als
  Backlog mit Einordnung siehe ARCHITECTURE.md.
- Phase 4, Animation (quasi-stationaer), Cache, Parallelisierung.
- Phase 5, Installer, Uninstaller, Prozessverwaltung, Servermodus,
  KI-Schnittstelle. Servermodus ist bereits erreicht (Phase 1/2 liefen
  ausschliesslich so, siehe ARCHITECTURE.md "Erreichbarkeit ueber
  Tailscale"). Der Desktop-Installer-Zweig (eigenstaendiges
  Windows-Programm, WebView2, lokales MS-MPI-Prozessmanagement) ist
  vom Projektinhaber am 2026-10-06 bewusst zurueckgestellt worden,
  nicht verworfen: FOSAS bleibt bis auf Weiteres server-/
  browserbasiert. Siehe DECISIONS.md ADR-0018.

## Projektueberblick

FOSAS orchestriert bestehende, validierte Open-Source-Software (SU2, Gmsh,
Typst) zu einem Werkzeug fuer Anwender ohne CFD-Vorwissen. Kein eigener
CFD-Kern. Details zu Umfang und Architektur siehe `docs/ARCHITECTURE.md`.

## Wichtige Architekturregeln (siehe docs/DECISIONS.md fuer Begruendung)

- Gmsh wird ausschliesslich als externer Prozess (CLI) angesteuert, niemals
  per `import gmsh` im Hauptprozess. Grund: GPL-Lizenz von Gmsh, siehe
  ADR-0002.
- Geometrieverarbeitung nutzt build123d, nicht pythonocc-core direkt, siehe
  ADR-0003.
- Schicht 1 (Core) enthaelt keinen UI-Import. Solver liegen hinter einem
  Adapter-Interface.
- Schicht 2 (Engine) ist eine FastAPI-Anwendung. Lokal nur 127.0.0.1 mit
  Zufallsport und Token. Die interaktive OpenAPI-Dokumentation dient von
  Phase 1 an als browserbasierte Testflaeche, bevor die eigentliche
  Web-UI existiert.
- Die UI darf nichts koennen, was die API nicht auch kann.
- Sim-Box-Funktion (Ausschnitt eines Bauteils) wird in V1 als isoliertes
  Bauteil im normal grossen Rechengebiet umgesetzt (Variante A), nicht als
  echte eingebettete Teilmodellrechnung. Siehe ADR-0004.

## Entwicklungsumgebung, bekannte Einschraenkung

Ein Teil der Entwicklung findet in einer Linux-Sandbox ohne Windows und ohne
Root-Rechte statt. Gmsh und SU2 lassen sich dort ueber `micromamba`/
conda-forge installieren und ausfuehren (siehe `docs/RISKS.md`, R5),
solange die Installation auf echtem Speicherplatz statt in einem
tmpfs-Verzeichnis erfolgt. Windows-spezifisches Verhalten (Installer, Job
Objects, WebView2, MS-MPI statt OpenMPI) muss trotzdem auf einer echten
Windows-Maschine durch den Projektinhaber getestet werden, das ist keine
Verzoegerung, sondern eine Grenze der Werkzeugumgebung.
