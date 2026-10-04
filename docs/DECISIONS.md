# Entscheidungen (ADR-Stil)

Jede Entscheidung nennt Kontext, Entscheidung, Alternativen und Konsequenzen.
Spaetere Revisionen werden als neuer ADR-Eintrag ergaenzt, bestehende
Eintraege werden nicht rueckwirkend veraendert.

## ADR-0001: Eigene Projektlizenz Apache-2.0

Kontext: Lizenzaudit aller geplanten Abhaengigkeiten (SU2 LGPL-2.1, Gmsh GPL,
Typst Apache-2.0, MS-MPI und WebView2 proprietaer/redistributable,
OpenCASCADE LGPL-2.1 mit Exception, CadQuery/build123d Apache-2.0,
pythonocc-core LGPL-3.0, PyVista MIT, VTK BSD-3-Clause, trame Apache-2.0).
Keine dieser Komponenten zwingt unseren eigenen Code zu Copyleft, sofern
Gmsh und SU2 als externe Prozesse angesprochen werden (siehe ADR-0002).

Entscheidung: Eigener Code unter Apache-2.0.

Alternativen: MIT (kuerzer, aber keine explizite Patentklausel, dadurch
etwas weniger Schutz bei so vielen kombinierten Fremdkomponenten).
GPL-3.0 (nicht technisch erzwungen, wuerde aber die Verbreitung und
Nachnutzung staerker einschraenken, ohne dass ein Zwang dazu besteht).

Konsequenzen: Passt zu den meisten Kernabhaengigkeiten (Typst, CadQuery,
build123d, trame). Vor dem ersten Release wird eine
`THIRD-PARTY-NOTICES.md` mit allen Fremdlizenzen und Versionsnummern noetig
(siehe RISKS.md, R4).

## ADR-0002: Gmsh ausschliesslich als externer Prozess

Kontext: Gmsh steht unter GPL, mit Ausnahmeklausel nur fuer die Kombination
mit Netgen, METIS, OpenCASCADE und ParaView, nicht fuer unseren eigenen
Code. Wird `import gmsh` im Hauptprozess der Engine verwendet, laedt das
GPL-lizenzierten Code in unseren Adressraum, was nach gaengiger
FSF-Auslegung (Kriterium: Kommunikationsmechanismus und Datensemantik)
unseren Code zu einem GPL-Verbund machen kann. Gmsh bietet ein vollwertiges
Kommandozeilenprogramm.

Entscheidung: Der Core-Adapter ruft Gmsh ausschliesslich als externes
Programm per Subprozess auf (Geometrie- und Skriptdatei rein, Netzdatei
raus), niemals per Python-Import im selben Prozess.

Alternativen: `import gmsh` direkt (Risiko GPL-Ansteckung, verworfen).
Eigener Mesher (deutlich zu aufwaendig fuer den Projektumfang, verworfen).

Konsequenzen: Etwas mehr Aufwand fuer Prozesssteuerung und
Dateiaustausch, aber lizenzsicher. Erleichtert zudem einen spaeteren
Wechsel oder eine Ergaenzung der Meshing-Engine, da die Schnittstelle
ohnehin auf Dateiebene beziehungsweise Prozessgrenze liegt.

## ADR-0003: Geometriebibliothek build123d statt pythonocc-core

Kontext: STEP-Import-Spike zeigt, dass build123d (mit cadquery-ocp als
OpenCASCADE-Bindung) per pip installierbar ist, Apache-2.0-lizenziert und
aktiv gepflegt ist (taeglicher Commit-Stand zum Testzeitpunkt). pythonocc-core
ist LGPL-3.0, aber schlechter fuer pip/venv geeignet und historisch primaer
ueber conda-forge vertrieben. CadQuery hat eine ungeklaerte Diskrepanz
zwischen PyPI-Lizenzangabe (Apache-2.0) und GitHub-API-Metadaten
(NOASSERTION).

Entscheidung: build123d als primaere Geometriebibliothek fuer STEP-Import,
Wasserdichtheitspruefung und Bounding-Box-Berechnung.

Alternativen: pythonocc-core (LGPL-3.0, unproblematisch lizenzrechtlich,
aber schlechter in unseren pip-basierten Windows-Packaging-Ansatz
integrierbar). CadQuery (Lizenzmetadaten-Widerspruch ungeklaert, waere vor
Nutzung zu klaeren).

Konsequenzen: Wasserdichtheitspruefung darf sich nicht auf
`BRepCheck_Analyzer` allein verlassen (dieser meldet auch offene Schalen als
gueltig), sondern muss zusaetzlich Solid-Typ und `is_manifold` pruefen
(eigener Test bestaetigt: offene Testgeometrie wurde von
BRepCheck_Analyzer faelschlich als gueltig bewertet).

## ADR-0004: Sim-Box in Version 1 als isoliertes Bauteil (Variante A)

Kontext: Die urspruengliche Nutzeridee, das Rechengebiet an den Waenden
einer frei waehlbaren Box wie an einer Windkanalwand enden zu lassen
(Variante B), erzeugt an der Schnittflaeche eine physikalisch unzutreffende
Randbedingung, vergleichbar mit einem FEM-Submodell ohne aus dem
Gesamtmodell uebertragene Schnittlasten. Eine fachlich korrekte eingebettete
Rechnung mit uebertragenen Randbedingungen (Variante C) ist deutlich
aufwaendiger.

Entscheidung: Fuer Version 1 wird nur Variante A umgesetzt: der gewaehlte
Ausschnitt wird als eigenstaendiger Koerper in einem normal grossen
Rechengebiet simuliert. Ergebnisse werden im Bericht ausdruecklich als
isolierte Bauteilrechnung ohne Einbauumgebung gekennzeichnet.

Alternativen: Variante B (verworfen, methodisch irrefuehrend). Variante C
(zurueckgestellt auf eine spaetere Version, siehe OPEN_QUESTIONS.md).

Konsequenzen: Eingeschraenkter Nutzen fuer Fragestellungen, bei denen die
Wechselwirkung mit dem Rest der Geometrie entscheidend ist (z. B. Winglet im
induzierten Feld des Restfluegels). Muss im Bericht klar kommuniziert
werden.

## ADR-0005: Qualitaetsampel um Modelltauglichkeits-Kennzahl erweitert

Kontext: Stationaeres RANS kann bei massiver, instationaerer Ablösung
(stumpfe Koerper) nicht nur quantitativ ungenau sein, sondern eine
qualitativ falsche mittlere Stroemungstopologie liefern. Das ist kein
Konvergenz- oder Netzproblem und wird von den urspruenglich vorgesehenen
Ampel-Kriterien (Netzqualitaet, y+, Konvergenz, Netzunabhaengigkeit) nicht
erfasst. Der Projektinhaber hat klargestellt, dass fuer ihn 10 Prozent
numerische Abweichung akzeptabel ist, aber eine generische, nicht wirklich
berechnete Darstellung inakzeptabel ist.

Entscheidung: Die Ampel bekommt zusaetzlich eine Kennzahl fuer den Anteil
der Oberflaeche mit umgekehrter Wandschubspannung (Ablösungsanteil).
Ueberschreitet dieser einen noch festzulegenden Schwellwert, wird das
Ergebnis unabhaengig von Konvergenz und Netzqualitaet als "eingeschraenkt
aussagekraeftig ausserhalb des validierten Bereichs fuer stationaeres RANS"
gekennzeichnet.

Alternativen: Keine zusaetzliche Kennzahl, nur textliche Erwaehnung im
Bericht (verworfen, zu unauffaellig fuer den Anspruch "keine
Schoenfaerberei"). Instationaere Rechnung bei erkannter Ablösung (verworfen,
explizit Nicht-Ziel von Version 1).

Konsequenzen: Konkreter Schwellwert muss in Phase 2 anhand von
Validierungsfaellen kalibriert werden, aktuell offen (siehe
OPEN_QUESTIONS.md).

## ADR-0006: Projektname FOSAS, oeffentliches GitHub-Repository von Beginn an

Kontext: Projektinhaber wuenscht GitHub als einzigen kanonischen Ort fuer
den Projektstand, oeffentlich sichtbar von Anfang an, passend zum
Open-Source-Anspruch.

Entscheidung: Repository-Name FOSAS (Free Open-Source Aerodynamic Solver),
oeffentlich, unter dem GitHub-Account des Projektinhabers.

Alternativen: Privates Repository bis Phase 1 abgeschlossen ist (vom
Projektinhaber abgelehnt).

Konsequenzen: Auch der fruehe, unfertige Planungsstand ist von Anfang an
oeffentlich sichtbar. Das ist eine bewusste Entscheidung des
Projektinhabers, kein Versehen.

## ADR-0007: 3D-Grenzschichtvernetzung fuer Koerper mit konstantem Querschnitt

Kontext: Das Gmsh-Feld vom Typ `BoundaryLayer` unterstuetzt in der
aktuellen Version keine flaechenbasierte 3D-Ansteuerung (`FacesList` oder
`SurfacesList` existieren nicht, siehe RISKS.md R1), sondern nur
kantenbasierte 2D-Ansteuerung (`CurvesList`). Der von Gmsh offiziell
gezeigte generische 3D-Weg (`extrudeBoundaryLayer`) ist bisher nur per
Python-API demonstriert, die in unserer Entwicklungssandbox nicht verfuegbar
ist.

Entscheidung: Fuer Koerper mit konstantem oder stueckweise konstantem
Querschnitt entlang einer Achse (typisch fuer einen ungepfeilten,
ungetaperten Fluegelabschnitt) wird die Grenzschicht in 2D am
Querschnittsprofil erzeugt (`BoundaryLayer`-Feld mit `CurvesList`) und das
Ergebnis anschliessend klassisch translatorisch entlang der Achse extrudiert
(`Extrude {...} { Surface{s}; Layers{n}; }`). Die resultierende `.su2`-Datei
enthaelt allerdings, per eigener Pruefung der Rohdaten, durchgehend
Tetraeder (Elementtypcode 10), keine Prismen wie urspruenglich angenommen,
Gmsh zerlegt die Extrusionsschicht offenbar automatisch. Die Anisotropie
der Grenzschicht bleibt davon unberuehrt, da sie an den Knotenpositionen
haengt, nicht am Elementtyp. Erfolgreich getestet an einem
NACA-0012-Testfall, siehe RISKS.md R1.

Alternativen: `extrudeBoundaryLayer` per Python-API (verworfen fuer den
Moment, keine funktionierende Python-Umgebung verfuegbar). Isotropes Netz
ohne echte Grenzschicht (verworfen, macht y+ und wandnahe Werte unbrauchbar).

Update, in Code gegossen: Als `fosas_core.meshing.generate_constant_section_geo`
plus `run_gmsh` implementiert und mit einem echten Gmsh-Lauf getestet
(core/tests/test_meshing.py). Eine Erkenntnis aus der Implementierung: ein
einzelner, in sich geschlossener Spline (erster Punkt gleich letzter
Punkt) scheiterte mit "Could not create spline", zwei Splines die sich an
gemeinsamen Endpunkten treffen (wie im urspruenglichen Testfall) funktionieren
zuverlaessig. Die erste Zellhoehe kommt jetzt aus
`fosas_core.boundary_layer.first_cell_height` (y+-basiert) statt aus einem
geratenen Wert.

Update, offene Frage geklaert: Die Technik funktioniert nachweislich auch
mit einer aus einer STEP-Datei importierten Kontur (Gmsh `Merge`, nicht
nur mit direkt in Gmsh aufgebauten Kurven), per End-zu-Ende-Test mit
echtem Nachweis abgestufter Wandzellen bestaetigt
(`generate_constant_section_geo_from_step_profile`,
core/tests/test_meshing.py). Damit ist ADR-0007 fuer den Fall
"konstanter Querschnitt" vollstaendig validiert, unabhaengig davon, ob
die Kontur aus Python-Code oder aus einer STEP-Datei stammt.

Konsequenzen: Dieser Ansatz ist auf Koerper mit (stueckweise) konstantem
Querschnitt beschraenkt, keine allgemeine Loesung fuer beliebige
STEP-Geometrie mit Verjuengung, Pfeilung oder Fluegelspitzen. Ausserdem
wurde er bisher nur mit einer direkt in Gmsh aufgebauten Profilkurve
getestet, nicht mit einer aus einer STEP-Datei importierten Kontur (siehe
OPEN_QUESTIONS.md). Fuer allgemeinere Geometrie bleibt der
`extrudeBoundaryLayer`-Weg oder eine Windows/x86_64-Umgebung mit
Python-Bindings notwendig zu klaeren.

## ADR-0008: Optionale, offengelegte Sewing-Reparatur beim STEP-Import

Kontext: Ein vom Projektinhaber bereitgestelltes reales STEP-Modell (ein
Auto-Heckspoiler, `Test_Spoiler.step`) enthaelt 182 einzelne, nicht
verbundene Flaechen-Patches und null Solids, ein sehr realistischer Fall
fuer echte CAD-Exporte, der von der bisherigen strikten Ablehnung
("kein Solid, keine Reparatur") korrekt, aber wenig hilfreich behandelt
wurde. Ein Test mit `BRepBuilderAPI_Sewing` (verschiedene Toleranzen von
0,05 bis 0,7 mm) zeigt: Vernetzung nur unverbundener, aber eigentlich
passender Kanten ist damit grundsaetzlich moeglich und in unserem Testfall
teilweise erfolgreich (182 Flaechen zu einer einzigen zusammenhaengenden
Schale verbunden), aber bei diesem konkreten Modell bleiben bei jeder
getesteten Toleranz 6 bis 8 Kanten offen, das ist eine echte Luecke im
Quellmodell, kein reines Verbindungsproblem.

Entscheidung: `fosas_core.geometry.import_step` bekommt einen optionalen
Parameter `sewing_tolerance`. Ohne ihn bleibt das Verhalten unveraendert
strikt (keine Reparatur). Wird er gesetzt, wird bei nicht-solidem Import
automatisch genaeht, aber nur akzeptiert, wenn das Ergebnis danach
tatsaechlich ein einzelnes, geschlossenes, mannigfaltiges Solid mit
positivem Volumen ist. Der Reparaturversuch wird immer im Rueckgabewert
offengelegt (`ImportedGeometry.repair_report`, mit Toleranz,
Eingangsflaechenzahl und ob es geklappt hat). Schlaegt die Reparatur fehl,
enthaelt die Fehlermeldung die Anzahl und ungefaehre Position der noch
offenen Kanten, damit im Quell-CAD-System gezielt nachgebessert werden
kann, statt nur "nicht wasserdicht" zu melden.

Alternativen: Automatische Reparatur immer versuchen, ohne expliziten
Parameter (verworfen, das waere ein stiller Fallback, der Ergebnisse
veraendert, siehe Projektregel in CLAUDE.md). Gar keine Reparaturoption
anbieten (verworfen, unnoetig unfreundlich fuer den haeufigen Fall
einer nur unverbundenen, aber sonst passenden Flaechensammlung).

Konsequenzen: Die konkrete Testdatei `Test_Spoiler.step` bleibt weiterhin
abgelehnt (siehe RISKS.md), das ist korrekt so, keine Fehlfunktion. Die
Fehlermeldung nennt jetzt aber, wo im Modell nachgebessert werden muesste.

## ADR-0009: SU2-Fehlererkennung ueber Exit-Code, nicht per Log-Scan

Kontext: Bei Gmsh reicht der Exit-Code nicht aus, um Fehler zu erkennen
(siehe RISKS.md R1, ein ungueltiges Feld-Argument fuehrte zu einer
Fehlermeldung mitten im Log, aber Exit-Code 0). Das legt nahe, dieselbe
Vorsicht bei SU2 zu uebernehmen. Ein eigener Test mit absichtlich
ungueltiger Konfiguration (`NONSENSE_OPTION_THAT_DOES_NOT_EXIST`) zeigt
aber: SU2 bricht in diesem Fall zuverlaessig mit Exit-Code 1 ab (sowohl
einzeln als auch unter `mpirun`), mit einer klar erkennbaren
"Error in ...End Error Exit"-Bloc-Meldung. Ausserdem enthaelt harmlose
MPI-Startup-Ausgabe (`osc_ucx_component.c ... Error: ...`) das Wort
"Error", was einen reinen Text-Scan bei SU2 anfaelliger fuer
Falsch-Positive machen wuerde als bei Gmsh.

Entscheidung: `fosas_core.solver.run_su2` behandelt den Exit-Code als
primaeres, verlaessliches Fehlersignal. Bei Exit-Code ungleich 0 wird
zusaetzlich versucht, den spezifischen "Error in ..." Block aus der
Ausgabe zu extrahieren, um eine praezise Fehlermeldung zu liefern, aber
die Erkennung selbst haengt nicht davon ab, ob dieser Block gefunden
wird.

Alternativen: Denselben Volltext-Scan wie bei Gmsh uebernehmen (verworfen,
haette wegen der harmlosen "Error:"-Zeile aus dem MPI-Startup zu
Fehlalarmen fuehren koennen, durch eigenen Test widerlegt als noetig).

Konsequenzen: Sollte sich in einer spaeteren SU2-Version herausstellen,
dass der Exit-Code doch nicht immer verlaesslich ist, muss dieser ADR
revidiert werden. Bis dahin gilt: fuer Gmsh gilt Log-Scan, fuer SU2 gilt
Exit-Code, jeweils empirisch begruendet, nicht symmetrisch aus Vorsicht
uebernommen.

## ADR-0010: cp/y+-Oberflaechendaten ueber SURFACE_CSV mit WRT_RESTART_COMPACT=NO

Kontext: Fuer die in Abschnitt 3 der urspruenglichen Anforderungen
verlangte cp-Verteilung fehlte bisher jeder Zugriff auf
Oberflaechen-Einzelwerte, nur integrierte cl/cd aus der History waren
verfuegbar. Ein erster Versuch mit `OUTPUT_FILES= (SURFACE_CSV)` lieferte
nur eine sehr schmale Spaltenauswahl (PointID, x, y, z, Pressure,
Velocity, Nu_Tilde), ohne `Pressure_Coefficient` oder `Y_Plus`, obwohl
diese Felder laut SU2-Quellcode (`CFlowIncOutput.cpp`,
`AddVolumeOutput("PRESSURE_COEFF", ...)` und `AddVolumeOutput("Y_PLUS",
...)`) zur Gruppe `PRIMITIVE` gehoeren, die im Standard-`VOLUME_OUTPUT`
bereits enthalten ist. Ursache gefunden im SU2-Quellcode
(`SU2_CFD/src/output/COutput.cpp`, `WriteToFile`, Fall
`OUTPUT_TYPE::SURFACE_CSV`): Ist `WRT_RESTART_COMPACT` aktiv (das ist
der Fall, sobald irgendein kompaktes Restart-Verhalten greift), wird die
Oberflaechen-CSV auf `requiredVolumeFieldNames` beschraenkt, also nur die
fuer einen Neustart noetigen Felder, nicht die vollen `PRIMITIVE`-Felder.

Entscheidung: `fosas_core.solver.generate_config` setzt immer
`OUTPUT_FILES= (SURFACE_CSV)`, `VOLUME_OUTPUT= (COORDINATES, SOLUTION,
PRIMITIVE)` und `WRT_RESTART_COMPACT= NO`. Die Oberflaechendatei wird
danach zuverlaessig mit `Pressure_Coefficient`, `Y_Plus`,
`Skin_Friction_Coefficient_x/y/z` und weiteren Feldern geschrieben, per
eigenem Test bestaetigt, nicht nur aus dem Quellcode abgeleitet.
`fosas_core.pipeline.CaseResult` gibt diese Daten jetzt als `surface`
(vollstaendige Punktliste) sowie `mean_y_plus`/`max_y_plus` weiter, auch
ueber die FastAPI-Engine.

Alternativen: Cp selbst aus der rohen `Pressure`-Spalte berechnen
(verworfen, haette die genaue interne Referenzdruck-Konvention des
inkompressiblen SU2-Loesers erfordert, die nicht mit ausreichender
Sicherheit verifiziert werden konnte, siehe Projektregel "keine
Schoenrederei"). Die von SU2 selbst mitgelieferte, bereits korrekt
definierte `Pressure_Coefficient`-Spalte zu nutzen ist robuster und
version-unabhaengiger.

Konsequenzen: Ein echter Vergleich der cp-Verteilung gegen
Referenzdaten (wie im urspruenglichen Scope gefordert) ist damit
technisch moeglich, aber noch nicht umgesetzt, es fehlt weiterhin eine
konkrete, belastbare Referenz-cp-Kurve fuer unseren Testfall (siehe
docs/OPEN_QUESTIONS.md). Ausserdem laesst sich jetzt zum ersten Mal das
tatsaechlich erreichte y+ direkt nachpruefen statt nur die Zielgroesse
aus der Netzgenerierung zu kennen, das ist ein bisher fehlender
Ruecklkopplungsschritt fuer die R10-Untersuchung.

## ADR-0011: mpirun immer mit --oversubscribe aufrufen

Kontext: Auf einer neu eingerichteten x86_64-Cloud-Instanz (AWS,
`m7i-flex.large`, 2 vCPU) schlug selbst ein trivialer Aufruf `mpirun -np 2
hostname` fehl, mit der Fehlermeldung "prte-rmaps-base:alloc-error". Das
betraf nicht nur unseren Code, sondern OpenMPI/PRRTE selbst: die
moderne PRRTE-Laufzeitumgebung (OpenMPI 5.x) erkennt auf manchen
virtualisierten/Cloud-Hosts die tatsaechlich verfuegbaren Kerne
("Slots") nicht korrekt, auch wenn die angeforderte Prozesszahl genau
der echten Kernzahl entspricht. Mit `--oversubscribe` laeuft derselbe
Aufruf sofort fehlerfrei.

Entscheidung: `fosas_core.solver.run_su2` haengt bei `mpi_ranks > 1`
immer `--oversubscribe` an den `mpirun`-Aufruf an. Das ist bei korrekt
erkannten Slots wirkungslos (kein echtes Oversubscribing, solange
`mpi_ranks` die echte Kernzahl nicht uebersteigt), macht das Verhalten
aber robust gegenueber dieser Klasse von Umgebungsfehlern.

Alternativen: Nutzer selbst dazu anhalten, die Umgebung zu reparieren
(z. B. Hostfile oder Slot-Hinweise per Umgebungsvariable, verworfen, zu
fehleranfaellig und nicht ohne Weiteres automatisierbar). Nur bei
Bedarf/Fehlerfall nachtraeglich mit `--oversubscribe` erneut versuchen
(verworfen, unnoetig kompliziert fuer einen Flag ohne Nachteil im
Normalfall).

Konsequenzen: Falls in einer Umgebung tatsaechliches Oversubscribing
(mehr Prozesse als Kerne) fachlich unerwuenscht waere, faellt diese
Sicherheitsbremse jetzt weg. Das ist fuer unseren Anwendungsfall
akzeptabel, da `mpi_ranks` ohnehin vom Aufrufer bewusst gesetzt wird.

## ADR-0012: Standard-CFL-Zahl auf 1,0 gesenkt, echter Divergenz-Fehler gefunden

Kontext: Beim Bau der ersten Weboberfläche (`clients/web`) wurde ein
End-zu-Ende-Testlauf ueber die echte HTTP-Schnittstelle gemacht, mit
denselben Parametern wie in unseren bestehenden Tests. Ergebnis: CL rund
-2,9 Millionen, CD rund -524000, offensichtlich unsinnig. Ursache
gefunden und durch Gegentest bestaetigt: `SolverParams.cfl_number` hatte
den Standardwert 5,0, unabhaengig vom gewaehlten Zeitintegrationsverfahren.
Bei `RUNGE-KUTTA_EXPLICIT` (unser Rueckfall-Schema fuer Faelle ohne
genug Arbeitsspeicher fuer implizit, siehe R10) ist CFL 5,0 weit ueber
der Stabilitaetsgrenze, die Rechnung divergiert sichtbar (Restfehler
waechst statt zu fallen, positiv statt negativ). Mit CFL 1,0 auf
demselben Netz sofort ein plausibles Ergebnis (CL rund 1,29 statt -2,9
Millionen).

Besonders unangenehmer Nebenbefund: Unsere bestehenden End-zu-Ende-Tests
(`test_solver.py`, `test_pipeline.py`, `test_app.py`) liefen mit genau
dieser Kombination (explizit, Standard-CFL) bereits vorher erfolgreich
durch, weil sie nur `cl != 0` statt eines Plausibilitaetsbereichs
gepglueft haben. Ein Ergebnis in Millionenhoehe waere also unbemerkt als
"Test bestanden" durchgerutscht.

Entscheidung: Standardwert von `cfl_number` auf 1,0 gesenkt (sicher fuer
explizit und implizit, implizit kann bei Bedarf weiterhin explizit
hoeher gesetzt werden). Alle betroffenen Tests bekommen zusaetzlich eine
Plausibilitaetsgrenze (`abs(cl) < 50`, `abs(cd) < 50`), nicht nur eine
Ungleich-Null-Pruefung.

Alternativen: CFL abhaengig vom gewaehlten Zeitintegrationsverfahren
automatisch waehlen (verworfen fuer den Moment, mehr Komplexitaet als
ein einzelner, fuer beide Faelle sicherer Standardwert braucht).

Konsequenzen: Alle bisherigen End-zu-Ende-Testlaeufe mit explizitem
Verfahren und Standardeinstellungen (siehe RISKS.md R10) muessen als
womoeglich durch diesen Fehler beeinflusst neu bewertet werden, auch
wenn die Kernaussage von R10 (Restfehler-Plateau weit ueber dem
Konvergenzziel) davon nicht beruehrt sein sollte, da die grossen
Validierungslaeufe in R10 mit explizit gesetzter CFL-Zahl liefen, nicht
mit dem betroffenen Standardwert.

## ADR-0013: OUTPUT_FILES ueberschreibt SU2-Standardliste statt sie zu erweitern, RESTART war seit ADR-0010 stillschweigend aus

Kontext: Beim Bau der Absturzsicherheit (Wiederaufnahme nach Abbruch,
siehe RISKS.md R14) wurde ein Test geschrieben, der `run_case` zweimal
mit demselben Arbeitsverzeichnis aufruft und erwartet, dass der zweite
Lauf an SU2s eigener Zwischenspeicherung (`restart_flow.dat`) fortsetzt.
Auch nach 110 Iterationen (ueber `OUTPUT_WRT_FREQ`, Standard 100, hinaus)
wurde nie eine `restart_flow.dat` geschrieben.

Ursache gefunden: In `fosas_core/solver.py` steht seit ADR-0010 (Cp- und
y+-Ausgabe fuer die Weboberflaeche) `OUTPUT_FILES= (SURFACE_CSV)` in der
generierten SU2-Konfiguration. Der SU2-Schluessel `OUTPUT_FILES` ERSETZT
die eingebaute Standardliste `(RESTART, PARAVIEW, SURFACE_PARAVIEW)`,
er erweitert sie nicht. Das bedeutet: seit ADR-0010 hat kein einziger
SU2-Lauf in FOSAS jemals eine Restart-Datei geschrieben, unabhaengig von
Iterationszahl. Das war bisher unbemerkt, weil vorher niemand versucht
hat, eine Wiederaufnahme zu testen.

Entscheidung: `OUTPUT_FILES= (RESTART, SURFACE_CSV)` gesetzt, mit
erklaerendem Kommentar direkt im generierten Konfigurationstext, damit
dieselbe stille Falle nicht bei der naechsten Erweiterung der Ausgabe
(z. B. weitere Feldgroessen) wieder zuschlaegt. Durch
`test_run_case_resumes_instead_of_restarting_from_scratch` abgesichert
(bestaetigt: Netz wird wiederverwendet, zweiter Lauf startet nachweislich
nicht beim Anfangsrestfehler neu, sondern dort, wo der erste aufgehoert
hat).

Konsequenzen: PARAVIEW/SURFACE_PARAVIEW-Ausgabedateien werden weiterhin
nicht geschrieben (waren schon seit ADR-0010 weg, das war so beabsichtigt
und aendert sich hier nicht). Keine sonstigen Verhaltensaenderungen fuer
bestehende, nicht wiederaufgenommene Faelle, da RESTART lediglich eine
zusaetzliche Ausgabedatei ist und den eigentlichen Loesungsverlauf nicht
beeinflusst.

## ADR-0014: Laengen aus STEP-Geometrie werden von Millimeter auf Meter umgerechnet (behebt R15)

Kontext: R15 beschreibt einen reproduzierbaren Gmsh-Speicherueberlauf bei
der manuell nachgedrehten realen Fluegeldatei. Direkte Untersuchung des
tatsaechlich generierten `.geo`-Skripts zeigte: Sehnenlaenge (chord) kam
als 100 an (die Datei ist laut eigenem STEP-Header tatsaechlich in
Millimetern, Sehnenlaenge real 100 mm, siehe R12), wurde aber in
`fosas_core.pipeline.run_case` ungeprueft als 100 Meter in alle
physikalischen Formeln (Reynolds-Zahl, y+-Zellhoehe ueber
`first_cell_height`, Referenzwerte fuer CL/CD) eingesetzt.

Ursache mit einem gezielten, kontrollierten Experiment zweifelsfrei
bestaetigt (Gesichert, nicht Vermutung): Ein mit build123d exportierter
Wuerfel `Box(1,1,1)` kommt beim erneuten Einlesen als Bounding Box 1.0
zurueck, unabhaengig davon, welche Laengeneinheit im STEP-Header steht.
Eine Kopie derselben Datei, deren Header von Hand auf `SI_UNIT($,.METRE.)`
geaendert wurde, kommt beim Einlesen als Bounding Box 1000.0 zurueck.
Das beweist: build123d/OCCT arbeitet intern immer in Millimetern und
rechnet beim Import konsequent in diese interne Einheit um, unabhaengig
vom deklarierten Einheitentyp der Quelldatei. `fosas_core.geometry`
gibt also immer Millimeterwerte zurueck, ganz gleich, was die
Ursprungsdatei deklariert.

Fuer die inflationierte Reynolds-Zahl (chord faelschlich 100 statt 0,1)
folgt daraus eine um den Faktor 1000 zu grosse Reynolds-Zahl und dadurch
eine unrealistisch duenne, y+-basierte erste Wandzellenhoehe relativ zur
(ebenfalls faelschlich 1000-fach zu grossen) Rechengebietsgroesse. Das
Verhaeltnis von groesster zu kleinster noetiger Netzzellengroesse steigt
dadurch von einem beherrschbaren Bereich (~5000, mit korrekter Skalierung
nachgerechnet) auf einen unrealistischen Bereich (~3 Millionen), was
Gmsh vermutlich in eine explodierende, nicht konvergierende Verfeinerung
treibt und den Arbeitsspeicher erschoepft.

Wichtig: Die eigenen synthetischen Testgeometrien (`core/tests/fixtures.py`)
haben diesen Fehler nie aufgedeckt, weil sie ebenfalls ueber build123d
gebaut UND wieder eingelesen werden: Eine Sehnenlaenge, die als "0,6"
gemeint war (0,6 Meter, so haben die Testautoren die Zahl gewaehlt), kam
nach Export/Reimport wieder als "0,6" zurueck (build123d/OCCT rechnet
nicht neu um, wenn Quell- und Zieleinheit beide Millimeter sind), und
der anschliessende Fehler ("behandle das als Meter") hat dieselbe Zahl
zufaellig unveraendert gelassen, zwei sich gegenseitig aufhebende
Fehlannahmen statt eines einzigen korrekten Schritts.

Entscheidung: `run_case` rechnet Sehnenlaenge, Spannweite, Dicke,
Mittelspannposition und alle Querschnittspunkte direkt nach der
Extraktion aus der Bounding Box beziehungsweise dem geschnittenen
Querschnitt von Millimeter auf Meter um (Faktor 0,001), bevor
irgendeine physikalische Formel oder die Netzerzeugung diese Werte
verwendet. Die Testgeometrien in `core/tests/fixtures.py` wurden
angepasst: `naca0012_wing_step` und `naca0012_wing_step_wrong_axes`
bauen die Geometrie jetzt beim 1000-fachen des als Meter gemeinten
`chord`/`span`-Arguments (also tatsaechlich in Millimetern), sodass alle
bestehenden Testaufrufe und Erwartungswerte (in Metern) unveraendert
gueltig bleiben. `naca0012_profile_step` bleibt bewusst unskaliert, da
ihr einziger Verwender (`generate_constant_section_geo_from_step_profile`,
ein separater, nicht produktiv genutzter Technikversuch aus ADR-0007)
Chord/Span-Argument und importierte STEP-Geometrie auf derselben
Zahlenskala erwartet, nicht ueber `run_case` laeuft und daher von diesem
Fehler nie betroffen war.

Verifikation: Ein neuer schneller Test
(`test_run_case_converts_geometry_from_millimetres_to_metres`) prueft
direkt im generierten `.geo`-Text, dass eine mit 0,6 m gemeinte
Sehnenlaenge dort als `chord = 0.6` erscheint, nicht als `chord = 600`,
ohne einen echten Gmsh-Lauf zu brauchen. Zusaetzlich wurde die reale,
zuvor abstuerzende Datei (`wing_reoriented.step`, siehe R15) direkt durch
den reparierten `run_case` geschickt: Sehnenlaenge kommt jetzt korrekt
als 0,1 m zurueck (passt zu R12s unabhaengiger Messung: real 100 mm),
das Mesh braucht nur noch rund 230 MB Speicher (vorher unbegrenzt
wachsend bis zum OOM-Kill) und ist nach unter einer Minute fertig, mit
211850 Knoten und 1199232 Elementen. Alle bestehenden Tests (schnell und
langsam) bleiben gruen.

Konsequenzen: Jede reale, in Millimetern authorierte STEP-Datei (der
CAD-Normalfall, siehe R11/R12) wird ab jetzt korrekt skaliert. Es gibt
weiterhin keine UI-Anzeige, welche Laengeneinheit erkannt beziehungsweise
angenommen wurde; da build123d/OCCT jede STEP-Datei unabhaengig von ihrer
deklarierten Einheit auf dieselbe interne Millimeter-Konvention normiert,
ist die Millimeter-Annahme kein Rateschritt, sondern eine feste,
bibliotheksweite Tatsache, die fuer jede STEP-Datei gleichermassen gilt.

## ADR-0015: Aufbewahrungsregeln fuer Auftraege (Archiv, automatisches Loeschen)

Kontext: Mit mehreren Nutzern/Geraeten auf derselben geteilten
Auftragsliste (siehe ARCHITECTURE.md, Job-Persistenz) wuerde die Liste
sonst unbegrenzt mit alten Auftraegen vollaufen. Vom Projektinhaber
explizit beauftragt: erfolgreiche Auftraege nach 5 Stunden automatisch
archivieren, fehlgeschlagene schon nach 1,5 Stunden, fehlgeschlagene
zusaetzlich nach 24 Stunden endgueltig loeschen, erfolgreiche nie
automatisch loeschen (nur archivieren oder von Hand loeschen). Manuelles
Archivieren/Loeschen soll jederzeit frueher moeglich sein.

Entscheidung, mit Begruendung fuer jede nicht ganz triviale Wahl:

- Die Frist wird ab `finished_at` gemessen (Zeitpunkt, an dem ein Auftrag
  "running" verlassen hat), nicht ab `created_at`. Sonst wuerde ein
  legitim mehrstuendiger Lauf mitten in der Rechnung archiviert werden,
  nur weil er vor langer Zeit gestartet wurde, siehe R17 fuer ein
  Beispiel, wie lange ein einzelner Lauf real dauern kann.
- Archivieren aendert nur Sichtbarkeit (faellt aus der Standardliste,
  taucht im Archiv auf), nicht die Datei- oder Datensatzexistenz.
  Loeschen entfernt das Arbeitsverzeichnis wirklich von der Platte
  (`shutil.rmtree`) und ist nicht rueckgaengig zu machen, deshalb in der
  Weboberflaeche mit einer Bestaetigungsabfrage abgesichert.
- Kein Hintergrund-Scheduler/Cron: Die Regeln werden bei jedem Lesezugriff
  auf den `JobStore` frisch angewendet (`_sweep`, aufgerufen von `list`
  und `get`). Bei der erwarteten Anzahl Auftraege fuer dieses Werkzeug ist
  das guenstig genug, und es gibt keinen zusaetzlichen Prozess/Thread zu
  verwalten oder der beim Absturz haengen bleiben koennte.
- Reihenfolge beim Loeschen bewusst: erst Dateisystem, dann
  Speicherstruktur. Schlaegt `shutil.rmtree` fehl, bleibt der Auftrag im
  Speicher bestehen (Fehler wird weitergereicht, kein stilles Schlucken):
  Waere die Reihenfolge umgekehrt und die Dateientfernung schluege fehl,
  bliebe ein Verzeichnis mit `job_meta.json` zurueck, das
  `JobStore.load_from_disk` beim naechsten Engine-Neustart faelschlich
  wieder als aktiven Auftrag einlesen wuerde, ein "geloeschter" Auftrag
  waere also wiederauferstanden.
- Loeschen (und auch Archivieren) ist fuer `pending`/`running` Auftraege
  gesperrt (`JobNotDeletableError`): Ihr Arbeitsverzeichnis kann noch von
  einem laufenden Gmsh/SU2-Subprozess beschrieben werden, siehe R14 zur
  Rolle des Arbeitsverzeichnisses als Zustandsquelle.

Konsequenzen: `GET /jobs` liefert standardmaessig nur nicht archivierte
Auftraege, `GET /jobs?archived=true` nur archivierte. Neue Endpunkte
`POST /jobs/{id}/archive`, `POST /jobs/{id}/unarchive`,
`DELETE /jobs/{id}`. Kein Weg, einen laufenden Auftrag ueber die API
abzubrechen, das war schon vorher nicht moeglich und bleibt ein anderes,
eigenes Thema.

Nachtrag (direkt im Anschluss an R17): `POST /jobs/{id}/resume` ergaenzt,
nachdem genau dieser Vorfall (5000-Iterationen-Lauf am Timeout
gescheitert) nur manuell per direktem `run_case`-Aufruf auf dem Server
behoben werden konnte. Nur fuer Auftraege mit Status "failed" erlaubt
(`JobNotResumableError` sonst), setzt Status auf "pending", loescht
Fehlermeldung/Stage/Archiviert-Flag und reicht Datei/Parameter/
Arbeitsverzeichnis unveraendert an den Executor weiter.
`fosas_core.pipeline.run_case` erkennt selbst, ob Netz oder
SU2-Zwischenspeicherung im Arbeitsverzeichnis schon vorliegen (R14), ein
Fortsetzen ueber die API ist also kein Neustart von vorne. Absichtlich
nicht auf bestimmte Fehlerursachen beschraenkt (z. B. nur Timeout): Ein
erneuter Versuch bei einem unbehebbaren Fehler (z. B. Geometrieproblem)
schlaegt einfach sofort wieder fehl, das ist kein gefaehrliches
Verhalten, nur verschwendete Zeit.

## ADR-0016: Phase 1 wird trotz ungeloestem R10 als erfuellt behandelt, cl/cd fuer Grenzschicht-Koerper bleibt explizit unvalidiert

Kontext: R10 (siehe RISKS.md) ist nach einer sehr ausgedehnten
Untersuchung (zwei unabhaengige Gmsh-Vernetzungstechniken, vollstaendige
Isolationsmatrix der SU2-Loeserparameter, direkter Netzvergleich,
Community-Recherche inklusive eines seit 2017 offenen, ungeloesten
SU2-GitHub-Issues mit vergleichbarem Symptom) weiterhin offen: Die
eigene automatische Vernetzung eines Grenzschicht-Koerpers (NACA0012)
erreicht beim RANS-Loeser kein stationaeres cl/cd nahe der Referenz,
obwohl nachgewiesen wurde, dass der Testfall selbst (ueber ein
strukturiertes Vergleichsnetz) grundsaetzlich loesbar ist. Keine der
geprueften Einzelursachen (y+, Netzqualitaet/minSICN, Zellgroessen-
Sprung, Eckenbehandlung, jede einzelne und jede kombinierte
Loeserparameter-Abweichung) erklaert das beobachtete Plateau. Die
Aehnlichkeit zum ungeloesten SU2-Issue spricht dafuer, dass es sich um
ein echtes, auch von der SU2-Community nicht trivial geloestes
Robustheitsproblem handeln kann, nicht nur um einen eigenen Fehler.

Entscheidung (Projektinhaber, nach Abwaegung dreier Optionen: A,
trotzdem abschliessen; B, offen lassen bis geloest; C, Testfall
wechseln): Phase 1 wird als technisch/mechanisch erfuellt behandelt und
das Projekt geht zu Phase 2 weiter, OBWOHL R10 nicht gelost ist. cl/cd
fuer Koerper mit Grenzschicht-Vernetzung (also praktisch jeder reale
Fall) bleibt dabei explizit als nicht gegen Referenzdaten validiert
gekennzeichnet, nicht als Annahme-Richtwert schoengefaerbt. Die dafuer
noetige Offenlegung existiert technisch bereits
(`fosas_core.quality.assess_convergence`, die Konvergenz-Ampel in der
GUI zeigt ein erkanntes Plateau klar als Warnung statt als
"konvergiert").

Alternativen:
- B (Phase 1 offen lassen, bis R10 geloest ist): abgelehnt. Das seit
  2017 ungeloeste, vergleichbare SU2-Issue zeigt, dass der Zeithorizont
  dafuer unbekannt und moeglicherweise sehr lang oder unendlich ist,
  das Projekt soll davon nicht blockiert bleiben.
- C (anderer Testfall, z. B. Zylinder ohne scharfe Hinterkante, als
  Phase-1-Nachweis): nicht gewaehlt, aber bewusst nicht verworfen,
  siehe Konsequenzen. Grund fuer das Zurueckstellen: eigene Messung
  zeigt, dass die schwache Netzqualitaet gleichmaessig ueber das ganze
  Profil verteilt ist, nicht an der scharfen Kante konzentriert, ein
  Zylinder haette also vermutlich dasselbe Grundproblem, waere also
  keine verlaessliche Abkuerzung, nur ein weiterer ungetesteter
  Versuch.

Konsequenzen:
- R10 bleibt in RISKS.md als offenes Risiko stehen, nicht als geloest
  oder stillschweigend uebergangen.
- Phase 2 (Polaren, GCI-Netzstudie, Bericht) wird auf dieser Grundlage
  aufgebaut. Die GCI-Netzstudie koennte das Problem zufaellig mit
  aufdecken oder eingrenzen, das ist kein Plan, nur eine moegliche
  Nebenwirkung.
- Option C (anderer Testfall, insbesondere ein Zylinder) bleibt als
  spaeter nachholbarer, eigener Validierungsfall vorgemerkt, siehe
  OPEN_QUESTIONS.md, nicht verworfen.
- Sollte R10 zu einem spaeteren Zeitpunkt doch noch geloest werden
  (eigener Fortschritt, SU2-Update, oder eine Antwort/ein Fix aus der
  Community zum verwandten Issue #533), wird das rueckwirkend in
  RISKS.md vermerkt und die Validierungs-Markierung in der Qualitaets-
  ampel entsprechend wieder auf "validiert" angehoben. Dieser Fall ist
  erwuenscht, kein Rueckschritt.
