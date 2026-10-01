# Offene Punkte

## Technisch, vor der jeweiligen Phase zu klaeren

- Echte Unterstuetzung fuer mehrteilige/verjuengte/lofted Geometrie
  (mehrere Querschnitte statt einem konstanten, siehe ADR-0007), zum
  Beispiel fuer einen Fluegel mit Endplatten (RISKS.md R18) oder eine
  Verjuengung (R12). Aktuell bewusst zurueckgestellt, kein konkretes
  Konzept. Groesserer, eigener Ausbauschritt, nicht nebenbei zu machen.
- Ein Auftrag, der am Timeout oder durch einen Absturz unterbrochen wird
  (siehe RISKS.md R14, R17), kann aktuell nur manuell (direkter
  `run_case`-Aufruf auf dem Server) fortgesetzt werden, nicht ueber die
  API oder die Weboberflaeche selbst. Eine "Fortsetzen"-Aktion pro
  Auftrag (z. B. `POST /jobs/{id}/resume`, das `run_case` erneut auf
  demselben Arbeitsverzeichnis mit hoeherem Timeout aufruft) waere ein
  naheliegender, aber eigener Ausbauschritt.
- trame wurde per Spike als grundsaetzlich geeignet bestaetigt (RISKS.md,
  R9), aber nur mit einem stark vereinfachten synthetischen Datensatz. Ein
  Lasttest mit echter Netzaufloesung inklusive Stromlinien/Schnittflaechen
  steht vor Phase 3 noch aus.
- Konkreter Schwellwert fuer den Ablösungsanteil in der erweiterten
  Qualitaetsampel (ADR-0005): noch nicht kalibriert, braucht
  Validierungsfaelle aus Phase 2.
- Genauer EULA-Wortlaut von MS-MPI und WebView2 (RISKS.md, R4): noch nicht
  aus den Installer-Paketen selbst gelesen.
- Gmsh-Grenzschichtvernetzung an einer duennen Hinterkante ist fuer den
  Fall eines Koerpers mit konstantem Querschnitt geloest (2D
  `CurvesList`-Feld plus translatorische Extrusion, siehe ADR-0007,
  RISKS.md R1), nachdem ein erster, faelschlich als erfolgreich gemeldeter
  Versuch korrigiert werden musste. Die Frage, ob das auch mit einer aus
  einer STEP-Datei importierten Kontur funktioniert (statt einer direkt in
  Gmsh aufgebauten), ist jetzt beantwortet: ja, per eigenem Test bestaetigt
  (`fosas_core.meshing.generate_constant_section_geo_from_step_profile`,
  `core/tests/test_meshing.py::test_step_imported_profile_produces_real_boundary_layer`),
  echte abgestufte Wandzellen auch bei importierter Kontur. Weiterhin
  offen: ob Koerper mit Verjuengung/Pfeilung/Fluegelspitzen (kein
  konstanter Querschnitt) einen anderen Ansatz brauchen. Konkret bestaetigt
  an einer zweiten realen Kundendatei (verjuengter Fluegel aus Autodesk
  Inventor, siehe RISKS.md R12): ein einzelner Naeherungs-Querschnitt laesst
  sich problemlos vernetzen, aber echte Loft-Vernetzung ueber mehrere
  Querschnitte mit durchgehender Grenzschicht ist nicht implementiert,
  das ist ein eigenes, noch nicht begonnenes Arbeitspaket.
- Ein erster SU2-Loeserlauf mit korrekter Koordinatenkonvention und echter
  Grenzschicht lief, aber nicht bis zur Konvergenz (siehe RISKS.md, R10).
  Implizites Zeitschema fuehrte in dieser Sandbox zu einem
  Speicherueberlauf, explizites Schema ist stabil aber sehr langsam. Ein
  konvergiertes cl/cd fuer den NACA-0012-Testfall steht noch aus.
- Referenzwerte fuer cl/cd bei Re=6 Mio., Mach 0,15, 10 Grad Anstellwinkel
  wurden gefunden (die NASA-TMR-Seite ist umgezogen nach
  tmbwg.github.io/turbmodels, siehe ARCHITECTURE.md fuer die Zahlen aus
  FUN3D/TAU/CFL3D). Offen bleibt: ein eigener, konvergierter Lauf mit
  vergleichbarer Netzqualitaet (y+ < 1, Feingitter), um den Vergleich
  tatsaechlich durchzufuehren, sowie der Abruf der experimentellen
  Gregory-Daten als zusaetzlicher, unabhaengiger Referenzpunkt.
- cp-Verteilung ist jetzt technisch verfuegbar (ADR-0010,
  `fosas_core.solver.SurfaceData`, `CaseResult.surface`, auch ueber die
  Engine-API), inklusive tatsaechlich erreichtem y+ pro Punkt. Was noch
  fehlt: eine konkrete, belastbare Referenz-cp-Kurve fuer den
  NACA-0012-Testfall, um den in Abschnitt 3 geforderten Vergleich "cp
  gegen Referenzdaten" tatsaechlich durchzufuehren, nicht nur die Rohdaten
  bereitzustellen. Ausserdem noch nicht genutzt: der jetzt verfuegbare
  tatsaechliche y+ pro Punkt wurde noch nicht mit dem y+=1-Ziel aus
  `fosas_core.boundary_layer` verglichen, das koennte die R10-Untersuchung
  weiterbringen (z. B. falls das tatsaechliche y+ stark vom Ziel abweicht,
  waere das ein weiterer Hinweis auf ein Netzproblem statt nur eine
  Vermutung).

## Fachlich/Nutzerseitig, noch nicht final entschieden

- Trennung von Qualitaetsstufen (Vorschau/Standard/fein) und der
  verpflichtenden Drei-Netz-GCI-Studie: Vorschlag, die GCI-Studie als
  separaten, einmaligen Validierungslauf pro Geometrie/Setup-Kombination
  zu behandeln statt bei jedem Einzellauf, wurde vom Projektinhaber noch
  nicht ausdruecklich bestaetigt.
- Variante C der Sim-Box-Funktion (eingebettete Rechnung mit uebertragenen
  Randbedingungen, siehe ADR-0004): als spaetere Ausbaustufe vorgemerkt,
  aber ohne konkreten Zeitpunkt.
- Welche Koerperklassen ausser dem NACA-0012-Validierungsfall zuerst mit
  konkreten Toleranzen hinterlegt werden (Zylinder als naechster Klassiker
  wurde vom Projektinhaber selbst genannt, aber nicht formal festgelegt).
- Genaues UI-Konzept fuer die vom Projektinhaber gewuenschte feingranulare
  Detailgrad-Einstellung der Animation (Partikel, Stromlinien, allgemeiner
  Detailbereich): noch nicht entworfen, gehoert in Phase 3/4.
- Berichtssprache, Zitierstil und Vorlagenlayout fuer den Typst-Bericht:
  noch nicht festgelegt (urspruenglich als Teil von Fragerunde 2
  vorgesehen).
- Konkreter Schwellwert fuer die reduzierte Frequenz k, ab der die
  quasi-stationaere Animation als ungueltig markiert wird: in der
  urspruenglichen Vorgabe mit "etwa 0,05" benannt, noch nicht anhand eines
  Testfalls bestaetigt.

## Rollen und Zustaendigkeit

- Windows-spezifische Tests (Installer, Job Object/MPI-Zusammenspiel,
  WebView2) koennen in der aktuellen Linux-Entwicklungsumgebung nicht
  durchgefuehrt werden und muessen vom Projektinhaber auf einer echten
  Windows-Maschine uebernommen werden, sobald Phase 5 ansteht. Eine
  Pruefliste dafuer wird zu gegebener Zeit erstellt.
