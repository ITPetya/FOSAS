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

**Zugriff ohne Tailscale, nur per Browser (seit 2026-10-16, siehe
RISKS.md R23).** Auf Wunsch des Projektinhabers: `tailscale funnel`
macht den lokalen Port unter einer echten, oeffentlichen HTTPS-Adresse
erreichbar (`--host` bleibt `127.0.0.1`, Funnel proxyt selbst dorthin),
aber dafuer muss zuerst `Settings.public_password` gesetzt werden
(`FOSAS_PUBLIC_PASSWORD`-Umgebungsvariable bevorzugt), sonst wuerde
Funnel den Bearer-Token jedem im Internet schenken, der die URL findet
(`/`, `/viewer`, `/app.js` liefern ihn sonst ungeprueft mit aus, siehe
R23). Mit gesetztem Passwort verlangen diese Routen zusaetzlich eine
`/login`-Sitzung, bevor sie den Token ausliefern; alle echten
API-Routen bleiben unveraendert beim Bearer-Token. Einmalige, ausserhalb
des Codes liegende Einrichtung: Funnel in der Tailscale-Admin-Konsole
fuer den Tailnet freigeben, danach `sudo tailscale set
--operator=<user>` auf dem Server (einmalig), danach
`tailscale funnel --bg <port>`.

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

**Web-UI-Rahmen, seit 2026-10-16 (siehe ADR-0019).** `clients/web/
index.html`/`app.js` sind EIN Fenster (CSS-Grid, kein Framework/Build-
Schritt), nicht mehr ein Stapel einzelner Panels: Menueband oben
(`#topbar`, Knoepfe "Neue Berechnung"/"Archiv"/"Bericht"), linkes
Panel (`#left-panel`, EIN Eingabeformular fuer alle drei Anfragearten),
zentraler Bereich (`#center-panel`, 3D-Ansicht/Freikoerperbild/cp-
Verteilung als Reiter), rechtes Panel (`#result-panel`, alle Ergebnis-
Kacheln, trotz des Namens inhaltlich unveraendert aus der fruehreren
"Ergebnis"-Panel-Logik), Konsole unten (`#console-wrap`, die
3-Phasen-Fortschrittsanzeige, eingeklappt per Standard). Das Archiv
(Topbar-Knopf, `#archive-overlay`) fasst die drei fruehreren getrennten
Listen (Auftraege/Polarstudien/GCI-Studien) zu einer einzigen,
Datums-sortierten Liste zusammen. Die drei Backend-Endpunkte (`/jobs`,
`/polar-studies`, `/gci-studies`) sind dabei unveraendert; welcher
angesprochen wird, entscheidet das Formular selbst (Anzahl
Anstellwinkel, GCI-Kontrollkaestchen), siehe ADR-0019 fuer die
Begruendung ("virtueller Windkanal, nicht drei Tools"). Spaetere
Backlog-Eintraege in diesem Dokument, die noch von einzelnen
getrennten Formular-/Listen-Panels sprechen (z. B. in der
"Technische-Mechanik-Visualisierung"-Historie unten), beschreiben den
damaligen Stand zum jeweiligen Zeitpunkt, nicht die heutige Struktur -
bewusst nicht rueckwirkend umgeschrieben, nur hier an einer Stelle
klargestellt. `viewer.html` ist von diesem Umbau unberuehrt.

**Mobile-Tauglichkeit und sofortige Geometrie-Vorschau, seit 2026-10-18
(siehe ADR-0021).** Das linke und das rechte Panel sind ueber zwei
Kopfzeilen-Knoepfe ein-/ausklappbar (Desktop: Grid-Spalte auf 0,
schmale Bildschirme <=860px: seitliche Schubladen-Overlays, dort auch
standardmaessig eingeklappt); drei Zieh-Griffe (links/Mitte,
Mitte/rechts, Mitte/Konsole) verstellen die jeweilige Groesse in einer
Achse ueber CSS-Variablen (`--left-w`/`--right-w`/`--console-h`). Der
"Vollbild"-Knopf ruft die echte Fullscreen-API auf `#center-panel` auf
statt (wie zuvor) `/viewer?job=...` in einem neuen Tab zu oeffnen. Eine
STEP-Datei wird sofort nach Auswahl automatisch zu `/geometry/preview`
hochgeladen (`autoPreviewUploadedGeometry`) und als Netz im 3D-Tab
angezeigt, noch vor jeder Berechnung - reine passive Bestaetigung
("richtige Datei, richtige Achsen"), nicht Teil des eigentlichen
Absendevorgangs.

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

**Umgesetzt (2026-10-16, siehe ADR-0020, RISKS.md R13):**
`fosas_core.geometry.detect_axis_orientation` erkennt und korrigiert
jetzt automatisch den eindeutigen Fall (Achsen um ein Vielfaches von 90
Grad verwechselt, typisch bei unterschiedlichen CAD-Export-Konventionen),
direkt gegen zwei echte, zuvor gescheiterte STEP-Dateien bestaetigt.
Eine bereits plausible Geometrie wird nie angetastet. Eine mehrdeutige
Geometrie (die Heuristik findet keine eindeutig beste Zuordnung) scheitert
weiterhin, jetzt aber mit einer genauen Fehlermeldung (alle sechs
moeglichen Zuordnungen mit echten Zahlen).

Die urspruenglich vorgesehene manuelle "Ausrichtung per 3D-Vorschau
bestaetigt" fuer genau diesen mehrdeutigen Rest ist jetzt ebenfalls
umgesetzt: `POST /geometry/preview` (`fosas_engine/app.py`) nimmt eine
STEP-Datei entgegen, legt sie kurzlebig (max. 2 Stunden,
`fosas_engine.geometry_previews.GeometryPreviewStore`) unter einer
`preview_id` ab und liefert alle 6 moeglichen Achsenzuordnungen bereits
vorberechnet zurueck (Zahlen plus tesselliertes Dreiecksnetz je
Zuordnung, `Shape.tessellate`, kein Gmsh/SU2-Aufruf). Die Web-UI zeigt
diese 6 Varianten als anklickbare Kandidatenkarten in einer eigenen,
kleinen three.js-Szene (`clients/web/app.js`:
`renderRotationPreviewVariant`/`renderRotationCandidates`) - ein Klick
auf eine Karte tauscht nur die bereits geladene Geometrie aus (keine
weitere Serveranfrage, echte Live-Vorschau). `POST /jobs`/
`/polar-studies`/`/gci-studies` akzeptieren seitdem optional
`preview_id` (keine erneute Datei-Uebertragung) und
`manual_rotation_label` (eines von `geometry.ROTATION_LABELS`, direkt
angewendet, OHNE `detect_axis_orientation` erneut zu befragen - eine
vom Nutzer in der Vorschau getroffene Wahl wird nie von der Automatik
ueberschrieben). Siehe ADR-0020 fuer die bewusste Abweichung von der
urspruenglich geplanten Umsetzung (sechs benannte Labels statt drei
freier Drehwinkel, wegen der Nichtkommutativitaet von Rotationen).

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
   Winkelbogen, Vorzeichenkonvention) -> **Alpha-Teil umgesetzt
   (2026-10-06):** neue einblendbare Ebene "Koerper-/Windachsen, Winkel
   α" im 3D-Viewer der Hauptseite (`index.html`/`app.js`, nicht
   `viewer.html`, siehe unten): Koerperachsen-Dreibein (bestehender
   `AxesHelper`, jetzt als eigene Ebene), ein Pfeil in echter
   Windrichtung (aus `aoa_deg`, dafuer neu in `CaseResult`/API
   verfuegbar gemacht, vorher nur Eingabe, nirgends im Ergebnis
   echoed), ein Winkelbogen, der tatsaechlich um `aoa_deg` schwenkt
   (nicht nur dekorativ fest). Vorzeichenkonvention direkt im Tooltip
   dokumentiert (positives alpha dreht von X zu Z, siehe
   `aoa_to_velocity_components`). Rein geometrisch gegen die reale
   Orthogonalitaet/Vektorsumme der Windachsen-Basis nachgerechnet, kein
   Browser-Test (siehe eigene Einschraenkung weiter unten im
   Dokument).
   Beta (Schiebewinkel) bleibt wie beschrieben unmodelliert, dafuer
   also bewusst kein Winkelbogen. **Auch in `viewer.html` umgesetzt
   (2026-10-14):** dieselbe 3D-Ebene (Koerperachsen, Windrichtungspfeil,
   Winkelbogen) jetzt auch in der Vollbildansicht, als eigener
   Umschalt-Knopf "Achsen/Windrichtung" (ersetzt den vorherigen reinen
   `AxesHelper`-Knopf). `bodyDirToScene`/`bodyPointToScene`/
   `buildCoordLayer` 1:1 aus `app.js` uebernommen (dieselbe Datei-
   Duplizierung wie beim cp-/Freikoerperbild-Diagramm, siehe RISKS.md
   R21 fuer die Begruendung), gegen eine echte Rechnung per
   Node-Simulation mit einem minimalen three.js-Stub geprueft.
   **Beta-Teil nachtraeglich umgesetzt (2026-10-14), Entscheidung des
   Projektinhabers ("ja Seitenwinde oder schraeg angreifende Winde
   waeren schon gut"):** `aoa_to_velocity_components` um `sideslip_deg`
   erweitert, Standard-Windachsen-zu-Koerperachsen-Zerlegung (vx = V*
   cos(α)*cos(β), vy = V*sin(β), vz = V*sin(α)*cos(β), reduziert sich
   bei β=0 exakt auf die vorherige Formel), neue volle 3D-Windachsen-
   Basis (D/L/S-Richtungen) rein rechnerisch per Skalarprodukt auf
   Orthonormalitaet geprueft (D.L = D.S = L.S = 0, je Einheitslaenge).
   `buildCoordLayer` zeichnet jetzt zusaetzlich einen zweiten
   Winkelbogen fuer β (eigene Farbe, X-Y-Ebene, nur bei β != 0
   sichtbar), der α-Bogen bleibt wie bisher in der X-Z-Ebene (zwei
   getrennte Boegen fuer zwei getrennte Eingabewinkel, keine
   zusammengesetzte Drehung). SU2 liefert den Seitenkraftbeiwert "CSF"
   bereits in derselben `AERO_COEFF`-Historiengruppe wie CL/CD/CM*
   (keine Solver-Konfigurationsaenderung noetig). End-to-End gegen
   eine echte Rechnung verifiziert (Zylinder-Testfall, α=4°, β=6°,
   lokale Engine): `cs=-0.6293`, daraus per Hand nachgerechnet
   `side = cs*q*A = -0.03084 N`, `resultant = hypot(L,D,S) = 0.30565 N`,
   `resultant_angle_deg = atan2(hypot(L,S), D) = 5.79°`, alle drei exakt
   mit der API-Antwort uebereinstimmend. In `app.js` und `viewer.html`
   identisch umgesetzt (Datei-Duplizierung wie bei den anderen 3D-
   Ebenen). Das 2D-Freikoerperbild (reine X-Z-Ebene) kann eine
   Seitenkraft grundsaetzlich nicht zeichnen (Y-Komponente); dort
   zeigt der "R"-Pfeil deshalb jetzt explizit nur noch den
   X-Z-Ebenen-Anteil (`R(D,L) = hypot(L,D)`, nicht den vollen 3D-Wert),
   mit einem sichtbaren Hinweistext, sobald S != 0 ist (keine stille,
   irrefuehrende Darstellung, CLAUDE.md "keine stillen Fallbacks").
2. Anstroemung (Pfeil mit v, rho, Staudruck q, Reynolds-Zahl) ->
   Ergebnis-Metadaten (Ergebnis-Panel + Bericht). **Umgesetzt
   (2026-10-05):** q und Re werden in `fosas_core.boundary_layer`
   berechnet (`dynamic_pressure`, `reynolds_number`), in `CaseResult`
   gefuehrt und als zwei neue Kacheln im Ergebnis-Panel angezeigt, gegen
   eine echte Rechnung von Hand nachgerechnet. Der Windrichtungspfeil
   selbst (im 3D-Viewer) fehlt noch, reine Darstellung, kein
   Berechnungsaufwand mehr.
3. Bezugsflaeche (projizierte Stirnflaeche/Draufsicht, farbig,
   waehlbar) und Bezugslaenge fuer Momentenbeiwerte -> **Beide
   Flaechen jetzt verfuegbar (2026-10-06), ohne neuen Solver-Lauf:**
   Grundrissflaeche (Sehnenlaenge * Spannweite) UND eine Stirnflaechen-
   Naeherung (Spannweite * groesste Bauteildicke aus der Bounding-Box,
   `fosas_core.forces.rescale_coefficient_to_frontal_area`) jetzt beide
   als eigene Kacheln sichtbar, mit cl/cd zusaetzlich auf beide Flaechen
   umgerechnet (dieselbe Kraft, zwei Konventionen: F = c_a \* q \* A_a =
   c_b \* q \* A_b, reine Umrechnung, kein zweiter Solver-Lauf noetig).
   Explizit als Annahme/Naeherung gekennzeichnet (nicht Gesichert): die
   Stirnflaeche ist eine Bounding-Box-Naeherung, keine exakte
   projizierte Silhouette, und rotiert nicht mit dem Anstellwinkel.
   None statt eines Wertes bei nahezu null Dicke (echte duenne Platte),
   nicht eine stillschweigend riesige/unendliche Zahl.
   Noch offen: eine *eigene*, vom Nutzer frei gewaehlte/eingegebene
   Stirnflaeche (statt der automatischen Naeherung) und die farbige
   Darstellung als Ebene im 3D-Viewer.
4. Kraftpfeile (R massstaeblich in N, Zerlegung in D/L/S oder
   Fx/Fy/Fz, Winkel der Resultierenden, Gleitzahl L/D, Beschriftung mit
   Kraft und Beiwert) -> **Zahlenteil umgesetzt (2026-10-05):**
   `fosas_core.forces.compute_force_system` berechnet L, D, R
   (atan2-basierter Winkel, robust auch bei D=0 oder negativem L),
   Gleitzahl L/D, alle vier als neue Kacheln im Ergebnis-Panel,
   End-to-End gegen Handrechnung bestaetigt (inkl. negativem L bei
   negativem AoA). **3D-Pfeile ebenfalls umgesetzt (2026-10-06):** neue
   einblendbare Ebene "Kraftpfeile" zeigt D (orange, entlang der
   Windachse), L (blau, senkrecht dazu) und R (weiss, Vektorsumme) als
   `THREE.ArrowHelper`, Laenge zueinander massstabsgetreu (laengster
   der drei = feste visuelle Laenge, sonst waeren Kraefte im
   Mikronewton-Bereich unsichtbar), Beschriftung mit Kraft und Beiwert
   als Text-Legende unter der 3D-Ansicht (bewusst keine
   3D-Sprite-Beschriftung direkt am Pfeil, siehe Begruendung im
   zugehoerigen Tooltip: neue Rendering-Infrastruktur nur dafuer waere
   unverhaeltnismaessig). Die Richtungs-/Laengen-Mathematik direkt gegen
   echte Kraftwerte dieser Sitzung nachgerechnet (Orthogonalitaet von
   D-/L-Richtung, Resultierende per Vektorsumme exakt reproduziert).
   Pfeile setzen am Momenten-Bezugspunkt an, nicht am tatsaechlichen
   Druckpunkt (den gibt es noch nicht, siehe Punkt 5).
   **Auch in `viewer.html` umgesetzt (2026-10-14):** dieselben 3D-Pfeile
   (D/L/R) jetzt auch in der Vollbildansicht, als eigener Umschalt-Knopf
   "Kraftpfeile" (`buildForcesLayer`, 1:1 aus `app.js` uebernommen). Die
   Hauptseite und die Vollbildansicht zeigen die Kraft-/Momentenebenen
   damit jetzt beide vollstaendig, in 3D UND (nur `viewer.html`) auch
   als 2D-Freikoerperbild.
   **D/L/S-Zerlegung in Windachsen nachtraeglich umgesetzt (2026-10-14),
   siehe Punkt 1 fuer die Beta-Herleitung/Verifikation:**
   `buildForcesLayer` zeichnet jetzt einen vierten Pfeil S (eigene
   Farbe) entlang der Seitenkraft-Richtung der vollen Windachsen-Basis,
   die Resultierende R ist jetzt die Vektorsumme aller drei (D+L+S),
   nicht mehr nur D+L. Bei β=0 bleibt S exakt null (kein Pfeil
   gezeichnet), die bisherige reine D/L-Darstellung aendert sich dann
   nicht. Fx/Fy/Fz in reinen Koerperachsen (statt Windachsen) ist
   weiterhin nicht umgesetzt, war auch urspruenglich nur als
   Alternative ("D/L/S *oder* Fx/Fy/Fz") formuliert, Windachsen sind
   fuer die Zielgruppe (Technische Mechanik, Kraeftesystem aus der
   Anstroemung) die sinnvollere Wahl.
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
   Reibungswiderstand) -> **Wandschubspannung umgesetzt (2026-10-06):**
   die Vermutung hat sich bestaetigt, SU2 schreibt
   `Skin_Friction_Coefficient_x/y/z` bereits pro Oberflaechenpunkt in die
   Surface-CSV. `fosas_core.pipeline.run_case` berechnet daraus
   tau = cf * q (Betrag) je Punkt und gibt Mittelwert/Maximum in Pa als
   zwei neue Kacheln im Ergebnis-Panel aus, gegen die rohen
   Oberflaechenpunkte exakt zurueckgerechnet. Die einzelnen
   Skin-Friction-Komponenten je Punkt sind jetzt auch ueber die API
   verfuegbar (`SurfacePointOut`), fuer eine spaetere ortsaufgeloeste
   3D-Darstellung.
   Noch offen: lokale Druckkraftpfeile und eine ortsaufgeloeste
   Wandschubspannungs-Darstellung im 3D-Viewer (reine Visualisierung,
   Daten liegen vor).
   **Aufteilung Druck-/Reibungswiderstand nachtraeglich umgesetzt
   (2026-10-14):** Die urspruengliche Einschaetzung oben ("braucht eine
   echte Flaechenintegration") galt nur fuer die Herleitung aus der
   History-Ausgabe (`AERO_COEFF`, dort tatsaechlich weiterhin keine
   CD_P/CD_V-Spalten) - SU2 fuehrt diese Flaechenintegration aber
   bereits selbst durch und schreibt das Ergebnis in einen eigenen,
   bisher ungenutzten Bericht: Per echtem Test bestaetigt (Zylinder-
   Testfall), dass die SU2-Konfigurationsoption `WRT_FORCES_BREAKDOWN=
   YES` eine Text-Datei "forces_breakdown.dat" erzeugt, die Druck- und
   Reibungsanteil fuer CD (und CL/CSF/CM*, hier aber nur CD genutzt)
   explizit auftrennt ("Total CD: 6.263383 | Pressure (98%): 6.142443 |
   Friction (1%): 0.120940 | ..."), unabhaengig von der sonstigen
   `OUTPUT_FILES`-Konfiguration geschrieben, auch unter MPI
   (mpi_ranks=3 real getestet) fehlerfrei. `fosas_core.solver.
   _parse_forces_breakdown` liest die globale "Total CD:"-Zeile per
   Regex aus (nicht die spaeter im selben Bericht wiederholte
   Pro-Oberflaechen-Zeile), `pipeline.run_case` prueft das Ergebnis
   gegen die unabhaengig aus der History gelesene End-CD (Toleranz 1%
   oder 1e-6 absolut, da der Bericht nur 6 Nachkommastellen druckt) statt
   es ungeprueft zu uebernehmen, und wirft einen Fehler bei
   Abweichung statt die Werte stillschweigend zu benutzen. Neue Felder
   `cd_pressure`/`cd_friction` (Beiwerte) und `drag_pressure`/
   `drag_friction` (N, = Beiwert * q * A) auf `CaseResult`, durchgaengig
   bis in API, UI-Kacheln, Tooltip, Rechenweg und PDF-Bericht verfuegbar.
   End-to-End gegen eine echte Rechnung bestaetigt (Zylinder, α=4°):
   `cd_pressure=6.150884`, `cd_friction=0.121526`, daraus per Hand
   nachgerechnet `drag_pressure=0.301393 N`, `drag_friction=0.005955 N`,
   Summe exakt gleich `forces.drag=0.307348 N`.
   Als Risiko dokumentiert (siehe RISKS.md): Das ist ein unstrukturierter
   Text-Bericht, kein stabiles, versioniertes Dateiformat, das Parsen
   per Regex ist also an die aktuell installierte SU2-Version (8.5.0)
   gebunden, nicht an eine oeffentliche, stabile Schnittstelle.
7. Freikoerperbild-Modus (2D-Schnittansicht, optional Gewichtskraft und
   Befestigungspunkt mit Lagerreaktionen) -> **Pflichtteil umgesetzt
   (2026-10-06):** neue 2D-SVG-Ansicht (`drawFreeBodyDiagram`) direkt
   unter der 3D-Ansicht, zeigt den echten Koerper-Querschnitt
   (Oberflaechenpunkte auf die X-Z-Ebene projiziert, bei konstantem
   Querschnitt entlang der Spannweite faellt jeder Punkt auf dieselbe
   Kontur, siehe ADR-0007) mit denselben D/L/R-Kraftpfeilen wie in der
   3D-Ansicht, hier mit echter Beschriftung direkt am Pfeil (in 2D ohne
   Sprite-Text einfacher als in 3D). Einheitlicher Massstab auf beiden
   Achsen, damit der rechte Winkel zwischen D und L nicht optisch
   verzerrt wird. Rein geometrisch gegen echte Lauf-Daten nachgerechnet
   (keine nicht-endlichen projizierten Punkte, Pfeilenden endlich).
   **Bewusst nicht umgesetzt (die zwei "optionalen" Teile der
   Anforderung):** Gewichtskraft und Befestigungspunkt mit
   Lagerreaktionen. Dafuer fehlen FOSAS aktuell zwei echte neue Eingaben
   (Masse bzw. Schwerpunktlage, Lagerposition), die nicht einfach
   plausibel geraten werden sollten (CLAUDE.md: keine stillen Annahmen
   bei Unterspezifikation). Eigener, spaeterer Schritt, sobald eine
   Entscheidung zur Schwerpunktlage getroffen ist.
   **Teilentscheidung getroffen (2026-10-14):** Falls/wenn dieser Punkt
   umgesetzt wird, soll der Schwerpunkt automatisch aus der STEP-
   Geometrie berechnet werden, nicht manuell eingegeben ("der
   Schwerpunkt soll wenn dann berechnet werden aus der STEP"). Noch
   offen: Lagerposition (weiterhin keine Eingabe dafuer vorhanden) und
   die Massenquelle fuer eine Schwerpunktberechnung (Volumen * Dichte
   setzt eine homogene Dichteannahme voraus, die bei einem realen,
   nicht-homogenen Bauteil explizit als Annahme gekennzeichnet werden
   muesste, siehe CLAUDE.md).
   **Geometrischer Schwerpunkt umgesetzt (2026-10-14):**
   `fosas_core.pipeline.run_case` berechnet jetzt `center_of_mass` direkt
   aus der STEP-Geometrie (`build123d.Shape.combined_center(...,
   CenterOf.MASS)`, OCCTs Volumenschwerpunkt unter einer angenommenen
   homogenen Materialverteilung), neues Feld auf `CaseResult`/API, eigene
   Kachel/Tooltip im Ergebnis-Panel (mit explizitem
   Annahme-Hinweis) und ein neuer gruener Punkt-Marker in der 3D-Ansicht
   (beide Clients) sowie im PDF-Bericht. Gegen zwei echte Faelle
   bestaetigt: am symmetrischen Zylinder-Testfall trifft der Schwerpunkt
   exakt die Bounding-Box-Mitte (wie physikalisch erwartet), am
   asymmetrischen NACA0012-Fluegelprofil (realer SU2-Lauf) liegt er bei
   x=0.2526 m eines 0.6 m Chords (42%, deutlich VOR der Bounding-Box-
   Mitte bei 0.3 m/50%, wie fuer ein vorne dickeres Profil zu erwarten),
   y auf halber Spannweite, z praktisch null (Ober-/Unterseiten-
   Symmetrie). Ausdruecklich NICHT derselbe Punkt wie der (weiterhin
   festen, Bounding-Box-basierten) Momenten-Bezugspunkt.
   **Entscheidungen getroffen (2026-10-14):** Massequelle = Material-
   Dropdown + Dichte-Tabelle (nicht direkte Masseeingabe); Lagerposition
   = Anklicken im 3D-Viewer (nicht Koordinaten-Eingabe).
   **Material/Masse/Gewichtskraft umgesetzt (2026-10-14):** neues Modul
   `fosas_core.materials` (`MATERIAL_DENSITIES_KG_M3`, acht Materialien:
   Aluminium/Stahl/Titan/CFK/GFK/ABS/PLA/Balsaholz, Dichtewerte per
   Websuche gegen oeffentliche Quellen geprueft, siehe Modul-Docstring
   fuer die einzelnen Quellen, alle als Annahme/Richtwert gekennzeichnet,
   keine exakte Legierung/Charge). Neues optionales `CaseParams.material`
   (None = kein Material, keine Masse/Gewichtskraft, keine stille Null).
   `fosas_core.pipeline.run_case` berechnet `volume` immer (reine
   Geometrie, `build123d.Shape.compute_volume()`, Gesichert), bei
   gesetztem Material zusaetzlich `material_density`/`mass`/`weight`
   (G = Masse \* g, g = 9.80665 m/s² Gesichert). Material-Dropdown in
   allen drei Formularen (Einzelauftrag, Polaren-/GCI-Studie), neue
   Kachelgruppe "Masse / Gewichtskraft" im Ergebnis-Panel, neue
   Gewichtskraft-Pfeile (eigene Farbe, am geometrischen Schwerpunkt
   statt am Momenten-Bezugspunkt, da Gewichtskraft dort wirkt) sowohl im
   2D-Freikoerperbild (dort tatsaechlich darstellbar, anders als die
   Seitenkraft) als auch in der 3D-Ansicht (beide Clients), sowie im
   PDF-Bericht. Bewusst in dieselbe Laengenskala wie D/L/S/R gefaltet,
   nicht eine eigene zweite Skala: ein echtes Bauteilgewicht und seine
   Luftkraft bei einer bescheidenen Testgeschwindigkeit koennen sich um
   Groessenordnungen unterscheiden, das ehrlich zu zeigen ist besser als
   es durch eine zweite, nicht vergleichbare Skala zu verstecken.
   End-to-End gegen eine echte Rechnung bestaetigt (Zylinder, Material
   Stahl): `volume=1.5708e-6 m^3`, `material_density=7850`,
   `mass=0.012331 kg`, `weight=0.1209 N`, alle per Hand nachgerechnet
   (volume\*density=mass, mass\*g=weight) und im echten PDF-Bericht
   wiedergefunden.
   **Lagerreaktionsberechnung umgesetzt (2026-10-19, siehe ADR-0022):**
   Die urspruengliche Notiz unten (siehe naechster Absatz, historisch
   belassen) ging von einer neuen Zweiphasen-Abgabe aus. Tatsaechlich
   gebaut wurde stattdessen eine reine Nachrechnung auf dem bereits
   fertigen Ergebnis: neues, schmales Modul
   `fosas_core.reactions.compute_bearing_reaction` (Starrkoerper-
   Statik, Kraefte-/Momentengleichgewicht, Annahme einer einzigen,
   vollstaendig starren Einspannung, explizit als solche ausgewiesen),
   neuer Endpunkt `POST /jobs/{job_id}/bearing-reaction` (keine
   Persistenz, jede Anfrage rechnet neu), neue Pick-Interaktion in der
   Web-UI (`clients/web/app.js`: Raycaster gegen die bereits gerenderte
   Oberflaechen-Punktwolke, Einrasten auf einen echten Oberflaechen-
   knoten, Drag-vs-Klick-Unterscheidung ueber die Zeigerbewegung
   zwischen Pointerdown/-up). Keine Erweiterung des 2D-Freikoerperbilds
   in dieser Runde (siehe ADR-0022 fuer die vollstaendige Abgrenzung).

   **Urspruengliche Notiz, historisch belassen (nicht mehr aktuell):**
   die eigentliche Lagerreaktionsberechnung braucht einen Lagerpunkt, und der
   entschiedene Mechanismus dafuer (Anklicken im 3D-Viewer) setzt eine
   neue, bisher nicht existierende Zweiphasen-Abgabe voraus (STEP
   hochladen -> Geometrie-Vorschau in 3D ohne Loeserlauf -> Punkt
   anklicken -> erst dann den eigentlichen Auftrag mit dem gewaehlten
   Punkt abschicken), da FOSAS aktuell STEP-Datei und Parameter immer
   gemeinsam in einem Schritt abschickt und vor dem Loeserlauf keine
   3D-Vorschau zeigt. Das ist eine echte Erweiterung der
   Upload-/Abgabe-Architektur, kein reines Implementierungsdetail des
   bereits gefassten Beschlusses - bewusst zurueckgestellt, bis das mit
   dem Projektinhaber abgestimmt ist, statt eine neue
   Interaktionsarchitektur ungefragt zu bauen.
8. Rechenweg (F = c*q*A, M = cm*q*A*l mit eingesetzten Zahlen) ->
   **Ergebnis-Panel-Teil umgesetzt (2026-10-06):** aufklappbarer
   "Rechenweg"-Block zeigt L, D, Mx, My, Mz jeweils als Formel mit den
   tatsaechlichen Zahlen dieser Rechnung (Startpunkt bewusst bei q/A/l,
   nicht bei rho/v, da letztere aktuell nicht separat ueber die API
   verfuegbar sind). Dafuer musste `fosas_core.forces.MomentSystem`
   die rohen cmx/cmy/cmz-Beiwerte zusaetzlich zu den skalierten Nm-
   Werten mitfuehren (sonst haette die UI den Beiwert durch Ruecktteilen
   rekonstruieren muessen, ein Physik-Schritt im Client, was die eigene
   Vorgabe "alle Werte in der Logikschicht" verletzt haette).
   Noch offen: Uebernahme in den PDF-Bericht (`fosas_core.report` +
   Typst-Vorlagen), das ist Punkt 11.
9. Plausibilitaets-Referenzwerte (Kugel, Platte, Pkw, Profil) ->
   **Quellen recherchiert (2026-10-06), Umsetzung bewusst zurueckgestellt
   auf Wunsch des Projektinhabers.** Gefundene, zitierfaehige Werte
   (alle bezogen auf die projizierte Stirnflaeche):
   - Platte quer zur Stroemung: cd = 1,28; Keilprofil: cd = 1,14;
     Stromlinienkoerper/Geschoss: cd = 0,295; "Fluegelprofil"
     (NASA-Pauschalwert): cd = 0,045. Quelle: NASA Glenn Research
     Center, "Shape Effects on Drag"
     (https://www.grc.nasa.gov/www/k-12/VirtualAero/BottleRocket/airplane/shaped.html),
     Unterschall-Windkanal, vergleichbare Reynolds-Zahl.
   - Kugel: stark Re-abhaengig ("Drag Crisis"), ein einzelner Wert ohne
     Re-Angabe waere irrefuehrend: unterkritisch (Re < ca. 2-3e5)
     cd ≈ 0,47-0,5; ueberkritisch (Re > ca. 3e5) cd ≈ 0,1-0,2. Quelle:
     Wikipedia "Drag crisis" (https://en.wikipedia.org/wiki/Drag_crisis),
     durch mehrere wissenschaftliche Quellen gestuetzt.
   - Pkw (moderner Durchschnitt): cd ≈ 0,25-0,35. Quelle: Wikipedia
     "Automobile drag coefficient"
     (https://en.wikipedia.org/wiki/Automobile_drag_coefficient).

   **Grund fuer die Zurueckstellung, nicht nur Quellenmangel:** Alle
   diese Werte beziehen sich auf die projizierte Stirnflaeche, FOSAS
   rechnet cd aber aktuell immer gegen die Grundrissflaeche (Sehnenlaenge
   * Spannweite, siehe Punkt 3). Beim Zylinder-Testfall stimmt das
   zahlenmaessig zufaellig ueberein, bei einem echten Fluegelprofil oder
   Fahrzeug waere ein direkter Vergleich mit den obigen Werten
   irrefuehrend, nicht nur ungenau.

   **Umgesetzt (2026-10-06), nachdem Punkt 3 die Stirnflaechen-
   Naeherung lieferte:** neue Tabelle im Ergebnis-Panel, vergleicht
   cd_Stirnflaeche dieses Laufs direkt gegen die obigen Werte (gleiche
   Flaechenkonvention jetzt auf beiden Seiten). Explizit als grobe
   Einordnungshilfe gekennzeichnet, nicht als exakter Vergleich: weder
   Geometrie noch Testbedingungen sind identisch mit der jeweiligen
   Quelle, und die eigene Stirnflaeche ist selbst nur eine Bounding-Box-
   Naeherung (siehe Punkt 3).
10. Tooltips mit Technische-Mechanik-Analogie -> `INFO_TEXT`-Objekt in
    `app.js`, exakt das in Schritt 1 bereits verwendete Muster
    (Gesichert/Annahme-Kennzeichnung je Begriff); fuer neue Begriffe (R,
    D/L/S, cm, Freikoerperbild, ...) wird es ergaenzt, sobald die
    jeweilige Ebene entsteht.
11. Aktive Ansichten/Werte in den Bericht uebernehmen -> **Umgesetzt
    (2026-10-06):** neuer Einzelauftrags-Bericht (`render_job_report`,
    `job_report.typ`, Route `GET /jobs/{id}/report`, neuer "Bericht
    (PDF)"-Knopf im Ergebnis-Panel) spiegelt das Ergebnis-Panel
    vollstaendig auf Papier: Kraftbeiwerte, Anstroemung, Kraeftesystem,
    Momente (inkl. Bezugspunkt), Rechenweg, Freikoerperbild-Diagramm
    (als vorgerendertes matplotlib-Bild, dieselbe Geometrie-/
    Pfeil-Logik wie `drawFreeBodyDiagram` im Browser) und
    Wandschubspannung/cp-Diagramm. Gegen eine echte Rechnung erzeugt
    und per Textextraktion inhaltlich geprueft (nicht nur "ist ein
    PDF"), ein Tippfehler (nicht escapetes `*` in reinem Markup-Text,
    "unclosed delimiter") dabei gefunden und behoben. Wartet nicht auf
    Punkt 9 (Referenzwerte), die haben keine eigene Darstellung, die
    uebernommen werden muesste.
    Nicht umgesetzt: Polaren-/GCI-Berichte zeigen weiterhin nur cl/cd,
    nicht die neuen Kraft-/Momentenwerte pro Zustand - waere eine
    eigene, separate Erweiterung derselben Berichte, kein Teil dieses
    Einzelauftrags-Berichts.
    **Um Schiebewinkel/Seitenkraft ergaenzt (2026-10-14):** Bericht
    zeigt jetzt zusaetzlich Schiebewinkel, cs und Seitenkraft S, mit
    demselben Hinweistext wie das Ergebnis-Panel, sobald β != 0 ist
    (Winkel-R-Mehrdeutigkeit, Freikoerperbild zeigt keine Seitenkraft).
    Per echtem Lauf erzeugt und per Textextraktion (`pypdf`) inhaltlich
    geprueft, nicht nur "ist ein PDF".

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
