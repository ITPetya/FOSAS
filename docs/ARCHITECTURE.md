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

## Phase 3, Erweiterungsanforderung: Technische-Mechanik-Visualisierung

Vom Projektinhaber am 2026-10-05 als zusaetzliche Anforderung an die
Ergebnisansicht gestellt, waehrend an Phase-3-Schritt 1 (Formulare fuer
Polaren-/GCI-Studien, siehe unten) gearbeitet wurde: Zielgruppe sind
Maschinenbauer mit Kenntnissen in Technischer Mechanik (zentrales/
allgemeines Kraeftesystem, Freikoerperbild, Kraftzerlegung, Momente), die
Ergebnisse sollen mit genau diesem Wissen direkt verstaendlich sein, als
einzeln einblendbare Ebenen (wie Layer im CAD), alle Werte in SI. Bewusst
nicht in Schritt 1 umgesetzt (Projektinhaber-Vorgabe: laufenden Plan nicht
unterbrechen), hier als Backlog mit grober Einordnung festgehalten, wo
jeder Punkt spaeter andockt. Nummerierung wie in der Originalanforderung.

Wichtigster Befund vorab (direkt im Code gegengeprueft, nicht nur Annahme):
`fosas_core.pipeline.CaseResult` liefert aktuell nur `cl`, `cd`,
`mean_y_plus`/`max_y_plus`, `chord`, `span`, keine Momentenbeiwerte, keine
Schiebewinkel-Unterstuetzung, keine waehlbare Referenzflaeche/-laenge
(siehe `pipeline.py`-Docstring: "Reference length/area/moment origin are
derived from the geometry's bounding box, not user-overridable yet.").
SU2 bekommt zwar bereits `REF_LENGTH`/`REF_AREA` (siehe `solver.py`) und
berechnet darueber vermutlich schon Momentenbeiwerte in seiner eigenen
`AERO_COEFF`-Historiengruppe (Annahme, nicht geprueft), `fosas_core` liest
davon aber bisher nur die Kraftbeiwerte aus. Die meisten Punkte unten
haengen an dieser einen Luecke.

Wichtige Randbedingung, die beim Aufbau der Kraftpfeile (Punkt 4)
zusaetzlich gegengeprueft wurde: `solver.py`s SU2-Konfiguration setzt
nirgends einen expliziten `AOA`/`AOS`-Parameter, die gedrehte
Anstroemrichtung kommt ausschliesslich ueber `INC_VELOCITY_INIT= (vx,
vy, vz)` (siehe `aoa_to_velocity_components`). **Gesichert per echtem
Test (2026-10-05):** SU2 meldet CL/CD trotzdem korrekt in Windachsen,
nicht in festen globalen Achsen, bezogen auf diesen Geschwindigkeitsvektor
selbst, nicht auf einen separaten Winkel-Parameter. Am Zylinder-Testfall
bei AoA=0 und AoA=5 Grad bleibt cd praktisch gleich (5.559 vs. 5.565, wie
bei einem rotationssymmetrischen Querschnitt physikalisch zu erwarten)
und cl bleibt nahe null bei beiden Winkeln; waere CL/CD stattdessen ein
ungedrehter globaler Achsenwert, muesste bei 5 Grad ein deutlicher
Querkomponenten-Leck von CD nach CL auftreten (ueberschlagen rund 0.48,
beobachtet aber nur -0.009). Damit ist die Grundlage fuer Punkt 4
(L = CL*q*A, D = CD*q*A in echten Windachsen) bestaetigt, nicht nur
angenommen.

1. Koordinatensysteme (Windachsen/Koerperachsen, alpha/beta als
   Winkelbogen, Vorzeichenkonvention) -> 3D-Viewer (`index.html`/
   `viewer.html`), neue Layer-Ebene. Alpha existiert schon als Eingabe;
   Beta (Schiebewinkel) ist nicht modelliert, `aoa_to_velocity_components`
   dreht nur in der X-Z-Ebene. Braucht zuerst eine Core-Erweiterung
   (Drehung zusaetzlich in der X-Y-Ebene), bevor es visualisiert werden
   kann.
2. Anstroemung (Pfeil mit v, rho, Staudruck q, Reynolds-Zahl) ->
   Ergebnis-Metadaten (Ergebnis-Panel + Bericht). **Umgesetzt
   (2026-10-05):** q und Re werden in `fosas_core.boundary_layer`
   berechnet (`dynamic_pressure`, `reynolds_number`), in `CaseResult`
   gefuehrt und als zwei neue Kacheln im Ergebnis-Panel angezeigt, gegen
   eine echte Rechnung von Hand nachgerechnet. Der Windrichtungspfeil
   selbst (im 3D-Viewer) fehlt noch, reine Darstellung, kein
   Berechnungsaufwand mehr.
3. Bezugsflaeche (projizierte Stirnflaeche/Draufsicht, farbig,
   waehlbar) und Bezugslaenge fuer Momentenbeiwerte -> **Anzeige-Teil
   umgesetzt (2026-10-06):** Bezugsflaeche (Grundrissflaeche = Sehnenlaenge
   * Spannweite) als eigene Kachel im Ergebnis-Panel, mit explizitem
   Hinweis, dass das NICHT allgemein dieselbe Flaeche ist wie eine
   projizierte Stirnflaeche (nur beim Zylinder-Testfall zufaellig
   gleich, weil dort Sehnenlaenge = Durchmesser). Weiterhin offen: die
   Flaeche ist noch fest aus der Geometrie-Bounding-Box abgeleitet,
   waehlbar machen (eigene Stirnflaechen-Option) heisst ein neues
   `CaseParams`-Feld plus farbige Darstellung als Ebene im 3D-Viewer.
4. Kraftpfeile (R massstaeblich in N, Zerlegung in D/L/S oder
   Fx/Fy/Fz, Winkel der Resultierenden, Gleitzahl L/D, Beschriftung mit
   Kraft und Beiwert) -> **Zahlenteil umgesetzt (2026-10-05):**
   `fosas_core.forces.compute_force_system` berechnet L, D, R
   (atan2-basierter Winkel, robust auch bei D=0 oder negativem L),
   Gleitzahl L/D, alle vier als neue Kacheln im Ergebnis-Panel,
   End-to-End gegen Handrechnung bestaetigt (inkl. negativem L bei
   negativem AoA). Noch offen: die D/L/S- bzw. Fx/Fy/Fz-Zerlegung in
   Koerperachsen (braucht Beta/Schiebewinkel, siehe Punkt 1, das
   symmetrische Testprofil liefert dafuer bisher keinen sinnvollen
   Pruefwert) und die eigentliche 3D-Pfeil-Visualisierung im Viewer
   (reine Darstellung, keine neue Rechnung mehr noetig).
5. Momente (Druckpunkt markiert, Bezugspunkt waehlbar: Schwerpunkt/
   Ursprung/frei, Mx/My/Mz in Nm mit Momentenbeiwerten) ->
   **Rohmomente umgesetzt (2026-10-06), kleiner als urspruenglich
   eingeschaetzt:** direkt im Code gegengeprueft, SU2 schreibt CMx/CMy/CMz
   bereits in seine `AERO_COEFF`-Historiengruppe (die vermutete Luecke
   oben war also keine echte Luecke, nur ungenutzte, bereits vorhandene
   Daten). `fosas_core.forces.compute_moment_system` liest sie aus,
   skaliert mit q*A*Bezugslaenge zu Mx/My/Mz in Nm, drei neue Kacheln im
   Ergebnis-Panel inklusive Hinweistext zum aktuellen (festen)
   Bezugspunkt. Gegen Handrechnung bestaetigt (echter Lauf: CMx=0.938 ->
   Mx=4.60e-6 Nm, CMy=-0.00329 -> My=-1.61e-8 Nm, CMz=-10.92 ->
   Mz=-5.35e-5 Nm, alle exakt per q*A*L nachgerechnet). Am
   rotationssymmetrischen Zylinder-Testfall sind Mx/Mz erwartungsgemaess
   klein (vermutlich Netzaufloesungs-Rauschen, keine reale Asymmetrie),
   My (Nickmoment) ist die bei einem Fluegelprofil eigentlich
   interessante Komponente.
   Noch offen, nicht in diesem Schritt: Druckpunkt-Markierung,
   waehlbarer Bezugspunkt mit Momentensatz-Umrechnung (M_neu = M_alt +
   r x F) auf einen anderen Punkt (Schwerpunkt/Ursprung/frei) - das
   braucht die tatsaechliche Geometrieposition dieser Wahl, nicht nur
   die bereits vorliegenden Zahlen, und die 3D-Darstellung im Viewer.
6. Oberflaeche (cp-Farbkarte existiert bereits im 3D-Viewer; lokale
   Druckkraftpfeile, Wandschubspannung, Aufteilung Druck-/
   Reibungswiderstand) -> `fosas_core.solver.SurfaceData` ist laut
   eigenem Docstring bereits fuer "Cp, y+, skin friction" ausgelegt,
   aktuell wird aber nur cp bis zur API durchgereicht (zu pruefen, ob
   skin friction tatsaechlich schon aus SU2 extrahiert wird oder nur im
   Docstring vorgesehen ist).
7. Freikoerperbild-Modus (2D-Schnittansicht, optional Gewichtskraft und
   Befestigungspunkt mit Lagerreaktionen) -> eigene neue Ansicht, setzt
   Punkt 4/5 voraus, eigener spaeterer Schritt.
8. Rechenweg (F = c*q*A, M = cm*q*A*l mit eingesetzten Zahlen) ->
   Ergebnis-Panel und Bericht (`fosas_core.report` + Typst-Vorlagen),
   sobald 2-5 vorhanden sind, reine Darstellung bereits berechneter
   Werte.
9. Plausibilitaets-Referenzwerte (Kugel, Platte, Pkw, Profil) ->
   eigene kleine Konstantentabelle. Achtung: braucht belegbare Quellen,
   siehe CLAUDE.md-Regel "keine erfundenen Literaturwerte" -- vor
   Umsetzung muessen diese Werte entweder mit Quelle belegt oder explizit
   als Vermutung markiert werden, keine stillschweigenden Richtwerte.
10. Tooltips mit Technische-Mechanik-Analogie -> `INFO_TEXT`-Objekt in
    `app.js`, exakt das in Schritt 1 bereits verwendete Muster
    (Gesichert/Annahme-Kennzeichnung je Begriff); fuer neue Begriffe (R,
    D/L/S, cm, Freikoerperbild, ...) wird es ergaenzt, sobald die
    jeweilige Ebene entsteht.
11. Aktive Ansichten/Werte in den Bericht uebernehmen -> `fosas_core.report`
    + Typst-Vorlagen, letzter Schritt, erst wenn 1-9 existieren.

Harte Vorgabe fuer die Umsetzung, sobald sie beginnt: alle Werte werden in
der Logikschicht (`fosas_core`) berechnet, die UI zeigt nur an, keine
eigene Physik/Umrechnung im Client.

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
