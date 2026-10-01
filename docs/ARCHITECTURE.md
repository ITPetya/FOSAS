# Architektur

Stand: Phase 0, nach Abschluss der technischen Spikes. Dies ist ein
lebendes Dokument, Aenderungen werden zusammen mit einem ADR-Eintrag in
`DECISIONS.md` vorgenommen, sobald sie architekturrelevant sind.

## Grundprinzip

FOSAS orchestriert bestehende, validierte Open-Source-Software. Kein
eigener CFD-Kern, kein eigener Mesher. Der Mehrwert liegt in Automatisierung,
Qualitaetspruefung und ehrlicher Ausweisung von Unsicherheit.

## Drei Schichten

**Schicht 1, Core-Bibliothek.** Reine Python-Logik ohne UI-Import:
Geometrieaufbereitung (build123d, siehe ADR-0003), Rechengebiet- und
Referenzgroessen-Ableitung, Netzsteuerung, Loeseraufrufe, Cache, Auswertung,
Berichtserzeugung (Typst). Solver liegen hinter einem Adapter-Interface.
Zielsolver: SU2 (LGPL-2.1, offizielle Windows-Binaries verfuegbar, siehe
DECISIONS.md-Kontext), spaeter optional OpenFOAM unter Linux. Vernetzung
ueber Gmsh, ausschliesslich als externer Prozess (ADR-0002), nicht als
In-Process-Import.

**Schicht 2, Engine-Dienst.** FastAPI mit REST, WebSocket fuer Fortschritt,
Job-Warteschlange, OpenAPI-Schema. Standardmaessig nur 127.0.0.1 mit
Zufallsport und Token, im Servermodus echte Authentifizierung (Interface
wird von Anfang an so entworfen, dass Auth spaeter eingehaengt werden
kann, ohne die API-Form zu brechen). Die automatisch erzeugte interaktive
OpenAPI-Dokumentation dient von Phase 1 an als browserbasierte Testflaeche.

**Erreichbarkeit ueber Tailscale (seit Phase 1).** Der Server war anfangs
nur per SSH-Tunnel von einem einzelnen, vorher eingerichteten Geraet aus
erreichbar, das war fuer mehrere eigene Geraete zu umstaendlich. Loesung:
Tailscale (privates VPN) auf dem Server und auf jedem Geraet des
Projektinhabers, alle im selben, privaten Tailnet. Die Engine bindet
dafuer explizit an die eigene Tailscale-Interface-Adresse
(`fosas_engine.server --host <Tailscale-IP>`), nicht an `0.0.0.0`: Damit
ist sie beweisbar nur ueber das Tailnet erreichbar, unabhaengig davon, ob
eine separate Firewall/Security-Group-Konfiguration das ebenfalls korrekt
absichert. Zugriffsschutz bleibt weiterhin das Bearer-Token, jetzt aber
gegen ein privates statt ein oeffentliches Netz. `--host` ohne Angabe
bleibt beim sicheren Standard `127.0.0.1`, ein Aufruf ohne Tailscale
aendert also nichts am bisherigen Verhalten.

**Job-Persistenz und geteilte Sitzung (seit Phase 1, siehe RISKS.md R14).**
Es gibt bewusst kein Nutzerkonto und keine Browser-Sitzung im ueblichen
Sinn: Ein Auftrag gehoert nicht einem Tab oder Geraet, sondern ist ueber
seine Auftrags-ID identifizierbar, die die Weboberflaeche in die
Webadresse schreibt (`?job=<id>`). Wer den Link oeffnet, egal auf welchem
Geraet, sieht denselben Status, da der Zustand serverseitig in
`fosas_engine.jobs.JobStore` gehalten und zusaetzlich als `job_meta.json`
im jeweiligen Arbeitsverzeichnis des Auftrags auf die Festplatte
gespiegelt wird. Das ist fuer den vorgesehenen Einzelnutzer-Betrieb
(ein Server, eine Person, siehe CLAUDE.md Phasenregel) ausreichend, aber
kein Mehrnutzer-Modell: Es gibt keine Zugriffskontrolle pro Auftrag,
jeder mit dem Bearer-Token sieht alle Auftraege (`GET /jobs`). Ein
Engine-Neustart laedt beim Start alle Auftraege von der Festplatte
(`JobStore.load_from_disk`) und stoesst dabei automatisch jeden Auftrag,
der beim letzten Stopp noch "running" war, erneut an; `run_case` erkennt
selbst, ob Netz oder SU2-Zwischenspeicherung schon vorliegen, und setzt
dort fort statt neu zu beginnen (siehe RISKS.md R14 fuer die bekannte
Grenze dieses Mechanismus).

**Fortschrittsanzeige waehrend der Rechnung.** Kein WebSocket, kein
neuer Kanal: `GET /jobs/{id}` berechnet den Fortschritt bei jedem Aufruf
neu aus dem Dateisystem (`fosas_engine/progress.py`), abgeleitet aus
Zustand, den `fosas_core` ohnehin schreibt. Zwei Phasen, mehr nicht:
"meshing" (solange `mesh.su2` noch nicht existiert) und "solving"
(danach). Fuer "solving" liefert SU2s eigene, waehrend der Rechnung
laufend geschriebene `history.csv` die Zeilenzahl als Iterationsstand,
daraus Prozent und eine grobe ETA (Restzeit = bisherige Zeit pro
Iteration mal verbleibende Iterationen). Fuer "meshing" gibt es
bewusst keine Prozentanzeige: Gmsh gibt waehrend des Laufs keinen fuer
FOSAS auslesbaren Fortschrittswert aus, eine erfundene Prozentzahl waere
eine stille Falschangabe. Die Weboberflaeche zeigt in dem Fall nur die
verstrichene Zeit.

**Schicht 3, Clients.** Web-UI (trame mit VTK/vtk.js, Eignung fuer begehbare
Animation mit vielen Zustaenden noch nicht durch Spike bestaetigt, siehe
OPEN_QUESTIONS.md), CLI, KI-Zugriff (MCP-Server oder Tool-Schema aus
OpenAPI). Regel: Die UI darf nichts koennen, was die API nicht auch kann.
Lokal laeuft die Web-UI in einem eigenen Fenster (WebView2), auf einem
Server im Browser.

## Koordinatenkonvention (wichtig, empirisch bestaetigt)

SU2 erwartet fuer Kraft-/Momentenbeiwerte und die automatische Berechnung
von Anstellwinkel/Schiebewinkel aus dem Geschwindigkeitsvektor eine feste
Achsenkonvention: X in Anstroemrichtung (stromab), Y spannweitig, Z vertikal
(Auftriebsrichtung). Anstellwinkel ist die Drehung in der X-Z-Ebene,
Schiebewinkel die Drehung in der X-Y-Ebene. Das wurde in einem eigenen
Testlauf bestaetigt: Eine Geometrie mit vertauschten Achsen (Spannweite
entlang Z statt Y, Profildicke/Auftriebsrichtung entlang Y statt Z) fuehrte
dazu, dass SU2 den vorgegebenen Anstroemvektor als "Anstellwinkel 0 Grad,
Schiebewinkel 10 Grad" interpretierte, obwohl 10 Grad Anstellwinkel
beabsichtigt waren, und CL infolgedessen die ganze Rechnung ueber exakt bei
0,000000 blieb.

Konsequenz fuer die Core-Pipeline: Die vom Nutzer angegebene Ausrichtung
(Anstroemrichtung und "oben", siehe Abschnitt Eingaben) muss beim Export
von der Eingabegeometrie in das Rechennetz immer in dieses kanonische
Koordinatensystem transformiert werden (X = Anstroemrichtung, Z = "oben"),
unabhaengig davon, wie die STEP-Datei urspruenglich orientiert war. Das ist
kein Detail, sondern eine harte Voraussetzung fuer korrekte Kraftbeiwerte,
und erklaert, warum die vom Nutzer per 3D-Vorschau zu bestaetigende
Ausrichtung (Abschnitt 3 der urspruenglichen Anforderungen) architektonisch
notwendig ist, nicht nur eine Komfortfunktion.

## Geometrie- und Vernetzungspipeline

1. STEP-Import per build123d. Wasserdichtheitspruefung nicht allein ueber
   `BRepCheck_Analyzer` (prueft nur topologische Konsistenz vorhandener
   Elemente, keine geschlossene Huelle), sondern zusaetzlich ueber
   Solid-Typ und `is_manifold` (siehe ADR-0003).
2. Bei nicht wasserdichter Geometrie: harter, verstaendlicher Fehler mit
   Handlungsoption, kein stiller Fallback. Automatische Reparatur
   (`BRepBuilderAPI_Sewing`) kann nur unverbundene, aber vorhandene
   Kanten/Flaechen verbinden, keine fehlenden Flaechen ergaenzen.
3. Vernetzung per Gmsh (externer Prozess). Bekanntes Risiko an duennen
   Hinterkanten (siehe RISKS.md, R1), Gegenmassnahme automatische
   Mindestradius-Anwendung, mit Offenlegung im Bericht.
4. Solverlauf per SU2 (externer Prozess, MPI-parallelisiert).

## Sim-Box (Bauteilausschnitt)

Version 1 unterstuetzt ausschliesslich Variante A: der gewaehlte Ausschnitt
wird als eigenstaendiger Koerper in einem normal dimensionierten
Rechengebiet simuliert, ohne Wechselwirkung mit dem Rest der urspruenglichen
Geometrie. Ergebnisse werden im Bericht klar als isolierte Bauteilrechnung
gekennzeichnet. Eine eingebettete Rechnung mit aus einer Gesamtrechnung
uebertragenen Randbedingungen (Variante C) ist eine moegliche spaetere
Ausbaustufe, siehe ADR-0004 und OPEN_QUESTIONS.md.

## Qualitaetsampel

Kriterien: Netzqualitaet, y+, Konvergenz, Bilanzen, Netzunabhaengigkeit
(GCI), und zusaetzlich eine Modelltauglichkeits-Kennzahl auf Basis des
Anteils der Oberflaeche mit umgekehrter Wandschubspannung (ADR-0005).
Bereich nach dem Stall wird automatisch als unsicher gekennzeichnet.
Ergebnis: "vertrauenswuerdig" oder "eingeschraenkt aussagekraeftig", mit
Begruendung, nie eine unbegruendete Einzelzahl.

## Referenzdaten fuer den NACA-0012-Validierungsfall

Gesichert (NASA Turbulence Modeling Resource, umgezogen von
turbmodels.larc.nasa.gov nach https://tmbwg.github.io/turbmodels/,
Unterseite naca0012numerics_val_sa_withoutpv.html, Stand Abruf 2026-09-23):
Fuer den Testfall Mach 0,15, Reynolds 6 Millionen, Anstellwinkel 10 Grad,
Spalart-Allmaras, ohne Point-Vortex-Korrektur, liefern netzunabhaengig
extrapolierte Werte aus drei unabhaengigen, etablierten CFD-Codes:

| Code | CL | CD |
|------|----|----|
| FUN3D | 1,09102722 | 0,0122724643 |
| TAU | 1,09104043 | 0,0122725244 |
| CFL3D (2. Ordnung) | 1,09090004 | 0,0122702792 |

Quellen mit Rohdaten (nicht selbst heruntergeladen, nur Seiteninhalt
geprueft): fun3d_results_sa_nopv_withN.dat, cfl3d_results_sa_nopv_withN.dat,
tau_results_sa_nopv_withN.dat unter demselben Verzeichnis, sowie gepackte
Archive unter nasa.gov/wp-content/uploads. Bezug zu Experimentaldaten
(Gregory) wird auf der Seite erwaehnt, aber in dieser Sitzung nicht mit
Zahlenwert abgerufen.

Wichtig fuer die Einordnung eigener Ergebnisse: Diese Werte stammen aus
extrapolierten Feingitter-Rechnungen mit strukturierten C-Netzen (897x257
Knoten laut fruehrerem Spike-Fund) und y+ deutlich unter 1. Unser
aktueller Testfall nutzt inzwischen ein y+-kontrolliertes Netz (erste
Zellhoehe aus `fosas_core.boundary_layer.first_cell_height`, siehe
RISKS.md R10), ist aber trotzdem noch nicht konvergiert: Der Restfehler
pendelt sich auf einem Plateau weit ueber dem Ziel ein, unabhaengig von
Netz-Elementtyp, CFL-Schema oder Loeser-Einstellungen (RISKS.md R10,
Stand der Untersuchung mit echten Gmsh-Python-Bindings auf x86_64). Ein
direkter Zahlenvergleich mit dem aktuellen Testlauf ist daher weiterhin
nicht aussagekraeftig. Phase 1 ("cl, cd, cp-Verteilung gegen
Referenzdaten", siehe CLAUDE.md) ist aus diesem Grund noch nicht
abgeschlossen; ein konvergierter, mit diesen Werten vergleichbarer Lauf
steht weiterhin aus.

## Version 1, Kernumfang nach Spike-Auswertung

Bestaetigt fuer V1: Einzelzustand- und Polarenrechnung fuer beliebige
STEP-Geometrie (Fluegel, Fahrzeuge, Einzelbauteile), automatische
Ableitung von Rechengebiet und Referenzgroessen, Qualitaetsampel wie oben,
Typst-Bericht mit GCI-Netzstudie, quasi-stationaere begehbare Animation.

Explizit mit reduzierter Erwartung versehen, nicht aus V1 gestrichen: Ergebnisse
fuer Koerper mit massiver Ablösung (Fahrzeuge, stumpfe Formen) werden
berechnet, aber standardmaessig als eingeschraenkt aussagekraeftig markiert
(ADR-0005), nicht gleichwertig zu anliegender Stroemung an einem Fluegel bei
moderatem Anstellwinkel.

Aus V1 herausgenommen beziehungsweise auf spaeter verschoben:
Sim-Box-Variante C (echtes Teilmodell mit uebertragenen Randbedingungen),
jede Form automatischer Geometrievereinfachung ueber reines Naht-Sewing
hinaus (z. B. Hinterkante verdicken als generelle Strategie, nur die
gezielte Mindestradius-Massnahme fuer Grenzschichtvernetzung ist vorgesehen
und wird offengelegt), instationaere Animation, eigener Solver, Innenstroemung,
rotierende Teile, transsonische/supersonische Stroemung.

## Entwicklungsumgebung

Ein Teil der Entwicklung findet aktuell in einer Linux-Sandbox (ARM64, ohne
Root) statt. Entgegen der ersten Einschaetzung sind Gmsh und SU2 dort ueber
`micromamba`/conda-forge tatsaechlich installierbar und lauffaehig (siehe
RISKS.md, R5), solange die Installation auf echtem Speicherplatz statt in
einem tmpfs-`/tmp` erfolgt. Damit sind Hands-on-Tests der Vernetzungs- und
Loeserpipeline in dieser Sandbox grundsaetzlich moeglich, ein erster
erfolgreicher 3D-Grenzschichtnetzlauf an einer scharfen NACA-0012-
Hinterkante wurde bereits durchgefuehrt (RISKS.md, R1). Fuer
Linux-Server-Betrieb und CI muessen `libgl1`, `libglx0`, `libglvnd0` (oder
Distributions-Aequivalent) als Systemabhaengigkeit bereitgestellt werden
(RISKS.md, R7), da die OpenCASCADE-Bindings fest dagegen gelinkt sind, auch
ohne Grafikausgabe. Windows-spezifisches Verhalten (Installer, Job
Objects, WebView2, MS-MPI-Prozessbeendigung) kann in dieser Umgebung nach
wie vor nicht getestet werden und bleibt bis Phase 5 offen (RISKS.md, R2).
