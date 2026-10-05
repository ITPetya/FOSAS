# Offene Punkte

## Technisch, vor der jeweiligen Phase zu klaeren

- Echte Unterstuetzung fuer mehrteilige/verjuengte/lofted Geometrie
  (mehrere Querschnitte statt einem konstanten, siehe ADR-0007), zum
  Beispiel fuer einen Fluegel mit Endplatten (RISKS.md R18) oder eine
  Verjuengung (R12). Aktuell bewusst zurueckgestellt, kein konkretes
  Konzept. Groesserer, eigener Ausbauschritt, nicht nebenbei zu machen.
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

## Phase 2, Vorbereitung (noch keine Umsetzung, nur Recherche)

- Typst-Anbindung recherchiert (Gesichert, direkt bei den Projekten
  nachgeprueft, Stand 2026-10-01): Das Python-Paket `typst` auf PyPI
  (`pip install typst`, aktuelle Version 0.15.0) ist eine inoffizielle,
  aber aktiv gepflegte Python-Anbindung (`messense/typst-py`) an den
  eigentlichen Typst-Compiler (`typst/typst`). Beide Projekte stehen
  unter Apache License 2.0 (LICENSE-Datei direkt aus beiden
  GitHub-Repos gelesen), keine GPL-Problematik wie bei Gmsh (ADR-0002),
  kein externer Systemdienst/Binary-Download durch den Nutzer noetig,
  einfache `typst.compile(...)`-API. Das waere der naheliegende Weg fuer
  die PDF-Berichtserzeugung in Phase 2. Nicht geprueft: ob die
  Python-Anbindung auf der Zielhardware (Windows, siehe R3/CLAUDE.md)
  ueberhaupt ein vorgefertigtes Wheel hat oder dort selbst kompiliert
  werden muesste.
- Phase 2 ist laut CLAUDE.md mehr als nur ein PDF-Bericht fuer einen
  Einzelfall: "Polaren, Netzstudie mit GCI, Bericht". Polaren bedeuten
  mehrere Zustaende (z. B. eine Anstellwinkel-Sweep-Reihe), nicht nur
  einen. Die GCI-Netzstudie ist bereits als eigener, noch nicht final
  entschiedener Punkt weiter unten vermerkt. Der Bericht selbst haengt
  also von beiden anderen Teilen ab (ein Bericht ueber eine Polare
  braucht mehrere Einzelrechnungen, keine neue Einzelrechnung).

Status (2026-10-05): Milestone 0 (Low-Re-Zylinder konvergiert, siehe
ADR-0017), Milestone 1 (Polaren-Sweep, `POST /polar-studies` und
zugehoerige Routen) und Milestone 2 (GCI-Netzstudie, `POST /gci-studies`,
`fosas_core.gci`) sind umgesetzt, automatisiert getestet (57 core- und
59 engine-Tests, alle gruen) und je einmal echt end-to-end gegen die
laufende Produktions-Engine auf dem AWS-Server verifiziert:
- Polaren-Sweep (AoA 0/15/30 Grad am Zylinder): cl blieb bei allen drei
  Winkeln nahe null (0,0110 bis 0,0112), cd praktisch konstant (13,399
  bis 13,403), exakt die erwartete Rotationssymmetrie eines Kreises.
- GCI-Studie (Verfeinerungsverhaeltnis 1,2, drei echte SU2-Laeufe mit
  1,36/1,77/2,42 Mio. Elementen): lief fehlerfrei durch, lieferte fuer
  cd eine plausible GCI-Kennzahl (p=1,51, 29,8 Prozent), fuer cl eine
  formal korrekte, aber wegen eines nahe-Null-Nenners nicht
  interpretierbare Kennzahl, siehe RISKS.md R20.
- Ein erster GCI-Versuch mit Verfeinerungsverhaeltnis 1,5 und implizitem
  Zeitschema fuehrte beim feinsten Netz (4,9 Mio. Elemente) zu einem
  Speicherueberlauf auf der kleinen AWS-Testmaschine (7,6 GB RAM), siehe
  R10 zum generellen Speicherbedarf des impliziten Schemas bei grossen
  Netzen. Kein Fehler in der neuen GCI-Logik selbst (das Scheitern eines
  einzelnen Jobs wird korrekt als "failed" aggregiert, ohne die
  GCI-Berechnung fehlerhaft auf unvollstaendige Daten anzuwenden), aber
  eine reale Ressourcengrenze: ein Nutzer mit wenig verfuegbarem
  Speicher sollte ein moderates Verfeinerungsverhaeltnis und/oder das
  explizite Zeitschema waehlen, bevor eine GCI-Studie an einem bereits
  grossen Netz nochmals verfeinert wird. Noch nicht umgesetzt: eine
  automatische Warnung oder Speicherabschaetzung vor dem Start einer
  GCI-Studie.
  Update (2026-10-05): Ein erster Typst-Bericht ist jetzt umgesetzt und
  echt verifiziert (`fosas_core.report`, `GET /polar-studies/{id}/
  report`): ein Diagramm (cl/cd ueber Anstellwinkel, per matplotlib als
  PNG vorgerendert, nicht ueber ein Typst-eigenes Plot-Paket, siehe
  Begruendung im Modul-Docstring), eine Tabelle mit Status/Konvergenz
  pro Punkt, sichtbarer Warnhinweis bei mindestens einem nicht
  konvergierten/fehlgeschlagenen Punkt. Bewusst klein gehalten: nur
  eine einzelne Polare, keine GCI-Daten (ARCHITECTURE.md nennt
  "Typst-Bericht mit GCI-Netzstudie" als bestaetigten V1-Gesamtumfang,
  das ist also eine spaetere Erweiterung dieses Berichts, keine
  abweichende Entscheidung). Mit der echten, heute abgeschlossenen
  3-Punkte-Zylinder-Polare erzeugt und visuell begutachtet (reales PDF,
  67 KB, alle drei Punkte konvergiert, keine Falschdarstellung). Dabei
  ein eigener Planungsfehler noch vor der Umsetzung gefunden und
  korrigiert: die per Websuche angenommene `typst.compile`-API (ein
  Dict mit mehreren benannten Dateien als Eingabe) existiert in der
  tatsaechlich installierten Version 0.15.0 nicht, direkt am
  Paket-eigenen Type-Stub und mit einem echten Testlauf auf dem
  AWS-Server nachgewiesen, bevor Code darauf aufgebaut wurde.
  Weiterhin offen: GCI-Abschnitt im Bericht, mehrere Studien/Faelle,
  Vorlagenlayout-Feinschliff, Pruefung der Windows-Wheel-Verfuegbarkeit
  fuer `typst` (R3, in dieser Linux-Sandbox nicht pruefbar), jegliche
  Visualisierung der Polaren-/GCI-Ergebnisse in der GUI ueber eine
  minimale Listenansicht plus PDF-Download-Knopf hinaus.

## Fachlich/Nutzerseitig, noch nicht final entschieden

- Variante C der Sim-Box-Funktion (eingebettete Rechnung mit uebertragenen
  Randbedingungen, siehe ADR-0004): als spaetere Ausbaustufe vorgemerkt,
  aber ohne konkreten Zeitpunkt.

Entschieden (2026-10-04, siehe DECISIONS.md ADR-0017, damit aus dieser
Liste entfernt): GCI-Studie als separater, bewusst ausgeloester Lauf
statt automatisch bei jedem Einzellauf; Zylinder als primaerer
Nachweisfall fuer Phase 2 (Polaren/GCI/Bericht), NACA0012 bleibt
parallel als bekannt eingeschraenkter Fall (R10) bestehen.
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
