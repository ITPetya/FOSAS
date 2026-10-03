# Risiken

Jeder Eintrag nennt Risiko, Quelle/Beleg, Status und geplante Massnahme.
Nichts hier ist schoengeredet, ein Risiko bleibt offen bis es durch einen
echten Test oder eine belastbare Quelle geschlossen wird.

## R1: Gmsh, kollabierende Grenzschichtzellen an scharfen Hinterkanten

Beleg (urspruenglich): Mehrere unabhaengige Sekundaerquellen (Gmsh-
Mailingliste 2016, GitLab-Issue-Titel, ResearchGate-Diskussion) beschreiben
uebereinstimmend, dass das `BoundaryLayer`-Feld an scharfen Hinterkanten
sich ueberschneidende oder kollabierende Prismenschichten erzeugt.
Verbreiteter Workaround: kleiner Radius/Halbkreis an der Hinterkante statt
idealer Schaerfe.

Korrektur eines eigenen Fehlers (wichtig): In einem ersten Testlauf wurde
faelschlich behauptet, dieses Risiko sei durch einen erfolgreichen
3D-Grenzschichtnetz-Test an einer scharfen NACA-0012-Hinterkante teilweise
entkraeftet worden. Das war falsch und wurde nur durch eine zweite,
sorgfaeltigere Pruefung entdeckt. Tatsaechlich hatte das verwendete
`.geo`-Skript beim Setzen des Feldes `Field[3].FacesList = {...}` einen
Fehler produziert ("Unknown option 'FacesList' in field 3 of type
'BoundaryLayer'"), der aber nicht das gesamte Skript abgebrochen hat,
sondern nur als Fehlermeldung protokolliert wurde, waehrend die restliche
Vernetzung ganz normal weiterlief. Diese Fehlermeldung stand mitten in
mehreren hunderttausend Zeilen Fortschrittsausgabe des Delaunay-Verfeinerers
und wurde beim ersten Mal uebersehen, weil nur die letzten Zeilen der
Ausgabe (`tail`) gepruef wurden. Der tatsaechlich erzeugte, als Erfolg
gemeldete Mesh mit 2,14 Mio. Elementen war also kein anisotropes
Grenzschichtnetz, sondern ein gewoehnliches isotropes Tetraedernetz mit
lokal feinerer Aufloesung nahe der Fluegeloberflaeche (ueber ein separates,
gueltiges Distance/Threshold-Feld). Die eigentliche Frage (kollabieren
Prismenschichten an der scharfen Hinterkante) wurde damit gar nicht
getestet.

Ursache geklaert (Gesichert, Gmsh-Quellcode auf GitHub, Datei
`src/mesh/Field.cpp`, Klasse BoundaryLayerField): Der Feldtyp
`BoundaryLayer` registriert aktuell die Optionen `CurvesList`, `Size`,
`SizesList`, `Ratio`, `SizeFar`, `Thickness`, `Quads`, `IntersectMetrics`,
`AnisoMax`, `BetaLaw`, `Beta`, `NbLayers`, `ExcludedSurfacesList`, sowie als
veraltete Aliase `EdgesList`, `FanNodesList`, `NodesList`, `hwall_n`,
`hwall_n_nodes`, `ratio`, `hfar`, `thickness`, `ExcludedFaceList`. Weder
`FacesList` noch `SurfacesList` sind darunter, auch nicht als veralteter
Alias. Das Feld ist also curve-getrieben (2D-Kanten), nicht
flaechen-getrieben. Der offizielle, im Gmsh-Beispielverzeichnis mitgelieferte
Referenzfall fuer echte 3D-Grenzschichten an einem NACA-0012-Fluegel
(`examples/api/naca_boundary_layer_3d.py`) nutzt konsequent einen anderen
Mechanismus, `gmsh.model.geo.extrudeBoundaryLayer(...)`, eine geometrische
CAD-Kernel-Extrusion, kein Feld. Dieser Mechanismus ist bisher nur ueber die
Python-API demonstriert, eine funktionierende reine `.geo`-Skript-Fassung
davon wurde in dieser Sitzung noch nicht erfolgreich nachgebaut, und die
Python-Bindings von Gmsh sind in unserer aarch64-Sandbox nicht installierbar
(siehe R5).

Status: Weiterhin offen, unveraendert gegenueber dem urspruenglichen,
sekundaerquellenbasierten Stand. Es gibt keinen eigenen erfolgreichen Test
einer echten 3D-Grenzschichtvernetzung an dieser Geometrie, weder
bestaetigend noch widerlegend. Neu und fuer sich genommen bereits relevant:
das Setzen einer 3D-Grenzschicht ueber die Gmsh-Kommandozeile/`.geo`-Skripte
ist nicht trivial und die naheliegende, in mehreren aelteren Foreneintraegen
und Tutorials beschriebene Syntax (`FacesList` am `BoundaryLayer`-Feld) ist
in der aktuellen Version schlicht falsch/veraltet, ohne dass Gmsh dabei hart
abbricht. Das ist selbst ein kleines Robustheits- und
Fehlerbarkeit-Risiko der Werkzeugkette, unabhaengig von der
Hinterkanten-Frage.

Massnahme: Erledigt fuer den einfachen (ungepfeilten, ungetaperten)
Fluegelfall, siehe Update unten. Fuer komplexere 3D-Formen (Fluegelspitzen,
Verjuengung, echte freie STEP-Geometrie ohne konstanten Querschnitt) bleibt
offen, ob derselbe Ansatz uebertragbar ist oder der generische
`extrudeBoundaryLayer`-Mechanismus (bisher nur per Python-API demonstriert)
noetig wird. Feste Vorgehensregel bleibt: jedes Meshing-Ergebnis wird erst
nach Pruefung der VOLLSTAENDIGEN Log-Ausgabe (nicht nur der letzten Zeilen)
auf das Wort "Error" hin als erfolgreich gewertet.

Update, funktionierender Ansatz gefunden und verifiziert (Gesichert, eigener
Test): Fuer einen Fluegel mit konstantem Profilquerschnitt (unser
Testfall) funktioniert ein zweistufiges Vorgehen zuverlaessig. Erstens wird
das 2D-Profil direkt in Gmsh (nicht aus STEP) mit zwei Splines aufgebaut,
und das `BoundaryLayer`-Feld mit der tatsaechlich existierenden Option
`CurvesList` (statt des nicht existierenden `FacesList`) auf diese Splines
angewandt, wobei jede Kante an genau eine Flaeche angrenzen darf (die reine
Profilflaeche ohne Fluidbereich musste dafuer entfernt werden, sonst Fehler
"Only 2D Boundary Layers are supported, curve is adjacent to 2 surfaces").
Das ergab ein sauberes 2D-Netz mit 8447 Knoten, 16782 Elementen, ohne
Fehler im vollstaendigen Log. Zweitens wird dieses 2D-Netz klassisch
translatorisch entlang der Spannweite extrudiert (`Extrude {0,span,0}
{ Surface{s}; Layers{n}; }`), was aus den 2D-Dreieckselementen automatisch
3D-Elemente macht (per eigener Nachpruefung ueber die Rohdaten der
`.su2`-Datei tatsaechlich Tetraeder, Elementtypcode 10, nicht Prismen wie
zunaechst angenommen, vermutlich zerlegt Gmsh die Extrusions-Prismen
automatisch; die Knotenpositionen und damit die Anisotropie der Schichten
bleiben davon unberuehrt) und die Grenzschichtstruktur mitnimmt. Ergebnis:
208343 Knoten, 1225358 Elemente, Vernetzungszeit nur rund 27 s (deutlich
schneller als der fruehere, fehlerhafte isotrope Tetraeder-Ansatz). Die
Randflaechen wurden erneut per Bounding-Box-Heuristik klassifiziert (2
Fluegel-, 6 Farfield-Flaechen), nicht per angenommener Extrude-Reihenfolge,
um keine ungeprueften Annahmen zu wiederholen.

Wichtige Einschraenkung des Testfalls: Der erfolgreiche Test hat die
Profilgeometrie direkt in Gmsh mit zwei Splines aus der NACA-0012-Formel
neu aufgebaut, nicht die zuvor per build123d erzeugte und als STEP
exportierte Geometrie wiederverwendet. Ob sich derselbe curve-basierte
2D-BoundaryLayer-Ansatz auf eine aus einer echten STEP-Datei importierte
Kontur uebertragen laesst (z. B. bei einer Kontur mit vielen kleinen
Segmenten wie in R1 urspruenglich beobachtet, 200 Teilflaechen aus einer
Polyline), ist NICHT getestet und bleibt offen fuer Phase 1.

Verifikation der echten Anisotropie (Gesichert, eigene Nachrechnung): Die
Knotenkoordinaten der exportierten `.su2`-Datei wurden bei 50 Prozent
Sehnenlaenge nahe der Oberseite ausgewertet. Gefundene Abstaende von der
analytisch berechneten Profiloberflaeche: 0,00011 m, 0,000199 m,
0,000498 m (aufsteigend), ein klar erkennbares, wachsendes Schichtmuster,
kein isotropes Netz. Damit ist die urspruengliche Frage aus R1 (kollabieren
Grenzschichtzellen an der scharfen Hinterkante) fuer diesen Testfall jetzt
tatsaechlich mit einer echten Grenzschicht beantwortet: die Vernetzung ist
gelungen, keine Fehlermeldung im vollstaendigen Log, keine entarteten
Elemente erkennbar. Ein erster SU2-Loeserlauf mit diesem Netz und korrekter
Koordinatenkonvention (siehe ARCHITECTURE.md) lieferte nach rund 200
expliziten Iterationen (in 8 Minuten auf dieser Sandbox erreicht, noch
nicht konvergiert, RMS_DENSITY erst bei -0,73 von angestrebt -8) einen
plausiblen, von Null verschiedenen Auftriebsbeiwert (CL um 1,25, fallende
Tendenz) und Widerstandsbeiwert (CD um 0,29, fallende Tendenz). Das ist
ausdruecklich kein konvergiertes, belastbares Ergebnis, nur ein Beleg, dass
die gesamte Kette Geometrie-Netz-Loeser-Kraftbeiwerte grundsaetzlich
funktioniert.

## R2: MS-MPI-Prozessbeendigung unter Windows Job Object nicht spezifisch belegt

Beleg: Microsoft-Dokumentation zu Job Objects und JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
sowie zu Nested Jobs (seit Windows 8 unterstuetzt) ist eindeutig. Eine
MS-MPI-spezifische Bestaetigung, dass die komplette mpiexec/smpd/Worker-
Hierarchie zuverlaessig mitgerissen wird, wurde nicht gefunden. Ein
Community-Bericht zu Intel MPI (nicht MS-MPI) beschreibt verwaiste
Worker-Prozesse nach taskkill auf den Hauptprozess, das ist nur ein
Risikoindikator, keine Aussage ueber MS-MPI.

Status: Offen, ungeprueft auf echtem Windows.

Massnahme: Job Object mit KILL_ON_JOB_CLOSE als Sicherheitsnetz einplanen,
zusaetzlich beim geordneten Abbruch aktiv den MPI-eigenen Abbruchmechanismus
ansprechen statt sich allein auf TerminateProcess zu verlassen. Expliziter
Testfall mit echtem SU2-Lauf unter Windows ist Pflichtbestandteil von
Phase 5.

## R3: Zielhardware reicht nicht fuer "fein" oder grosse Animationen

Beleg: Literaturbasierte Abschaetzung (Autodesk RAM-Faustregel, SU2-
Tutorialfaelle, SU2-Skalierungspaper). Fuer "fein" (Schaetzung 10 bis 20
Mio. Zellen) waeren 20 bis 40 GB RAM noetig, auf dem genannten 16-GB-Laptop
also grundsaetzlich ausgeschlossen. Fuer "Standard" (Schaetzung 2 bis 5 Mio.
Zellen) ist eine ganze Animation mit 30 bis 60 Zustaenden auf dem Laptop
eher eine Sache von Tagen als einer Nacht. Diese Zahlen sind eigene
Einordnung auf Basis der Quellen, nicht selbst gemessen (kein
Skalierungstest auf Zielhardware moeglich).

Status: Offen, Annahme, kein Test auf echter Zielhardware.

Massnahme: Engine so bauen, dass sie von Anfang an auf einer separaten
Maschine laufen kann (ergibt sich ohnehin aus der Client-Server-Trennung).
Erwartungsmanagement: "Fein" und groessere Animationen sind auf dem lokalen
Laptop nicht das vorgesehene Einsatzszenario, sondern fuer einen gemieteten
Server gedacht.

## R4: MS-MPI- und WebView2-Lizenztext nicht im Volltext geprueft

Beleg: Beide Redistributables sind offiziell zur Weitergabe vorgesehen
(Microsoft-Downloadseiten, WebView2-Distributions-Dokumentation), der genaue
EULA-Wortlaut wurde aber nur ueber Sekundaerquellen und Zusammenfassungen
eingeschaetzt, nicht direkt aus den Installer-Paketen gelesen.

Status: Offen.

Massnahme: Vor dem ersten Installer-Release beide EULA-Texte aus den
tatsaechlichen Installer-Paketen extrahieren, archivieren und in
`THIRD-PARTY-NOTICES.md` aufnehmen.

## R5: Eigene Testumgebung ist ARM64-Linux ohne Root (teilweise geloest)

Beleg (urspruenglich): `pip install gmsh` bietet kein Linux-aarch64-Wheel.
Der offizielle Gmsh-Bereich stellt nur Linux32/Linux64 (x86) bereit.
`apt-get install gmsh` scheitert ohne Root. Ein erster SU2-Installations-
versuch per conda-forge scheiterte, allerdings nur weil er versehentlich in
ein 2-GB-tmpfs-Verzeichnis (`/tmp`) statt auf die eigentliche Festplatte
(209 GB frei unter `/home`) zielte.

Beleg (Nachtest, erfolgreich): Mit `micromamba` (aarch64-Binary von
micro.mamba.pm) und Installationsverzeichnis auf der echten Festplatte
liessen sich sowohl Gmsh 4.15.2 als auch SU2 8.5.0 (mit Python 3.11 und
OpenMPI, conda-forge-Kanal) erfolgreich installieren und ausfuehren. Beide
Kommandozeilenprogramme (`gmsh`, `SU2_CFD`, `mpirun`) laufen. Einschraenkung:
Das conda-forge-Gmsh-Paket fuer diese Plattform/Python-Kombination liefert
keine Python-Bindings (kein `import gmsh` moeglich), nur die CLI und die
C/C++/Fortran-SDK-Header. Das ist fuer unsere Architektur unproblematisch,
da Gmsh ohnehin nur als externer Prozess angesprochen wird (ADR-0002).
Fuer OpenCASCADE-Bindings (build123d) war zusaetzlich das manuelle
Extrahieren von `libgl1`/`libglx0`/`libglvnd0` per `apt-get download` +
`dpkg -x` noetig (siehe R7).

Status: Fuer Gmsh- und SU2-Kommandozeilenwerkzeuge geloest, hands-on-Tests
sind in dieser Sandbox jetzt tatsaechlich moeglich (siehe R1-Update). Fuer
Windows-spezifisches Verhalten (Installer, Job Objects, WebView2, MS-MPI
statt OpenMPI) bleibt die Einschraenkung bestehen, das ist weiterhin nur auf
echtem Windows pruefbar.

Massnahme: Diese conda-forge-basierte Werkzeugkette (`micromamba`-Umgebungen
unter `/home/development/mamba_root`, nicht Teil des Repos) fuer weitere
Phase-1-Tests in dieser Sandbox weiterverwenden. Windows-spezifische Tests
bleiben Aufgabe des Projektinhabers auf echter Windows-Hardware, siehe R2.

## R6: Lizenzmetadaten-Widersprueche bei zwei Komponenten

Beleg: conda-forge klassifiziert SU2 8.5.0 als "GPL-2.0-or-later", waehrend
das GitHub-Repository (LICENSE.md, COPYING) LGPL-2.1 zeigt. CadQuery zeigt
auf PyPI "Apache Public License 2.0", die GitHub-API meldet aber
"NOASSERTION" (kein erkanntes SPDX-Tag).

Status: Offen, nicht sicher aufloesbar aus den bisher geprueften Quellen.

Massnahme: Fuer SU2 gilt die GitHub-Quelle (COPYING/LICENSE.md) als
massgeblich, vor einem produktiven Release aber nochmals gegenpruefen. Da
wir ohnehin build123d statt CadQuery bevorzugen (ADR-0003), ist die
CadQuery-Frage fuer uns nachrangig, sollte aber nicht unbeachtet bleiben,
falls sich das aendert.

## R7: Headless Linux braucht libGL/libGLX fuer OpenCASCADE-Bindings

Beleg: Eigener Test. Import von `build123d`/`cadquery-ocp` scheitert auf
einem System ohne Grafikausgabe zunaechst mit `ImportError: libGL.so.1`,
danach `libGLdispatch.so.0`. Die OCCT-Bindings sind fest gegen
OpenGL/GLX/GLdispatch gelinkt, auch wenn keine Grafikausgabe benoetigt wird.

Status: Bestaetigt.

Massnahme: `libgl1`, `libglx0`, `libglvnd0` (oder Distributions-Aequivalent)
als Systemabhaengigkeit fuer jeden Linux-Server-Betrieb und jedes CI/Docker-
Image dokumentieren und in Setup-Skripten/Dockerfiles vorsehen.

## R8: Stationaeres RANS bei starker Ablösung kann qualitativ falsch liegen

Beleg: Allgemein anerkannte Grenze von stationaerem RANS bei bluff bodies
und massiver instationaerer Ablösung (Fachwissen, keine einzelne Quelle
zitierfaehig geprueft in diesem Spike-Zyklus). Das ist keine
10-Prozent-Abweichung, sondern potenziell eine falsche mittlere
Stroemungsform.

Status: Anerkannt, adressiert durch ADR-0005, konkreter Schwellwert fuer
den Ablösungsanteil noch nicht kalibriert.

Massnahme: Schwellwert in Phase 2 anhand von Validierungsfaellen festlegen.

## R9: trame-Performance fuer begehbare Animation mit vielen Zustaenden

Beleg: Spike durchgefuehrt. trame, trame-vtk, trame-vuetify und VTK 9.7.0
liessen sich per pip vollstaendig installieren (inklusive fertigem
aarch64-Wheel fuer VTK selbst ueber piwheels), deutlich unproblematischer
als der Gmsh-Fall. Ein synthetischer Test mit 40 Zeitschritten (1682 Punkte,
3360 Zellen je Zustand mit Skalarfeld) liess sich in 0,11 s aufbauen, Peak-
Speicher rund 189 MB fuer alle 40 Zustaende im Prozess. `VtkLocalView`
(Geometrie einmalig an den Client uebertragen, danach rein clientseitige
Kamera/Interaktion) ist der fuer unseren Anwendungsfall passende Baustein,
per Codeinspektion bestaetigt vorhanden. Ein Forumsbericht (VTK Discourse)
und ein aktuelles Paper zu petaskaligem zeitabhaengigem Rendering weisen
darauf hin, dass vtk.js/Three.js bei sehr vielen Actors beziehungsweise bei
Datensaetzen mit hunderten Zeitschritten an Grenzen stossen, das betraf aber
deutlich groessere Volumendaten als unsere geplanten 30 bis 60 Zustaende mit
Oberflaechendaten.

Status: Ueberwiegend entkraeftet fuer den geplanten Umfang, aber nicht
abschliessend. Der Test lief mit einer stark vereinfachten synthetischen
Kugel, nicht mit realer CFD-Netzaufloesung inklusive Stromlinien und
Schnittflaechen, die die Punktzahl pro Zustand deutlich erhoehen koennen.

Massnahme: Vor Phase 3 einen Lasttest mit echter Netzaufloesung (z. B. dem
Netz aus R1) inklusive Stromlinien und Schnittflaechen wiederholen, um die
Hochrechnung zu bestaetigen.

## R10: SU2-Konvergenz in dieser Sandbox sehr langsam, implizites Schema geht in OOM

Beleg (eigener Test): Ein erster Loeserlauf mit dem impliziten Zeitschema
(`EULER_IMPLICIT`) fuer die Stroemungsgleichungen auf dem isotropen
1,92-Mio.-Elemente-Netz wurde vom Betriebssystem mit SIGKILL beendet
(Exit-Code 137), waehrend der Arbeitsspeicher (4 GB total in dieser
Sandbox) beim Aufbau der Jacobi-Matrix nahezu vollstaendig belegt war. Mit
explizitem Zeitschema (`RUNGE-KUTTA_EXPLICIT`) blieb der Speicherverbrauch
stabil bei rund 3,1 bis 3,3 GB, lief also durch, aber die Konvergenz ist
dadurch sehr langsam: nach 8 Minuten (rund 200 Iterationen) auf dem
Grenzschichtnetz war der RMS_DENSITY-Reststand erst bei -0,73 von
angestrebt -8, Auftriebs- und Widerstandsbeiwert waren noch klar in
Bewegung (CL fallend von 1,35 auf 1,25, CD fallend von 0,33 auf 0,29
innerhalb der letzten rund 40 beobachteten Iterationen).

Status: Bestaetigt fuer diese Sandbox (4 GB RAM, ARM64, 1 Kern effektiv
genutzt in den bisherigen Tests). Nicht direkt uebertragbar auf die
eigentliche Zielhardware (siehe R3), aber ein konkreter Hinweis, dass
implizite RANS-Loesung nennenswerten Arbeitsspeicher braucht und explizite
Verfahren als Rueckfalloption deutlich mehr Iterationen bis zur Konvergenz
brauchen als in einer kurzen Testsitzung praktikabel sind.

Update, mit MPI (3 Prozesse) und implizitem Verfahren fortgesetzt (Gesichert,
eigener Test): Mit 3 statt 1 MPI-Rang blieb der Speicherverbrauch bei
implizitem Verfahren stabil (rund 3 GB), kein OOM mehr. Ueber insgesamt
rund 3200 Iterationen (Neustart aus dem expliziten Lauf, dann zwei weitere
Fortsetzungen) zeigte sich folgendes Muster: Nach dem Umschalten auf
implizit mit hoeherer CFL-Zahl zunaechst eine stark gedaempfte Schwingung
von CL und CD um Werte nahe der Referenz (CL-Ausschlaege 0,5 bis 1,03 in
den ersten rund 600 Iterationen), die sich bis etwa Iteration 800 auf ein
recheinerisch ruhiges Niveau (CL um 0,88, CD um 0,11) einzupendeln schien.
Ab dort jedoch, ueber die naechsten rund 2400 Iterationen, eine langsame,
gleichmaessige Drift weiter WEG von der Referenz statt einer weiteren
Annaeherung (CL sinkt von 0,88 auf 0,65, CD steigt leicht von 0,11 auf
0,13), waehrend der Restfehler (rms[P]) durchgehend flach bei etwa -4,3
bis -4,5 verharrt, also weder weiter faellt noch der Vollkonvergenz (-8)
naeherkommt.

Status: Weiterhin offen, jetzt praeziser eingegrenzt. Das ist kein Fall
von "braucht nur mehr Zeit", da der Restfehler nicht mehr sinkt, waehrend
sich die Loesung selbst weiter aendert, das ist untypisch fuer eine
schlicht langsame Konvergenz. Plausible Erklaerungen (nicht geprueft,
Vermutung): (a) das Netz ist fuer eine belastbare Loesung bei diesem
Anstellwinkel schlicht ungeeignet (kein kontrolliertes y+, willkuerlich
gewaehlte erste Zellhoehe von 0,3 mm ohne Bezug zur tatsaechlichen
Reynolds-Zahl), (b) die Fernfeldgrenze oder Aufloesung ausserhalb der
Grenzschicht ist zu grob und beeinflusst die Loesung schleichend, (c) bei
10 Grad Anstellwinkel liegt fuer dieses Netz eine schwache, echte
Instationaritaet vor (z. B. eine langsam wandernde Ablöseblase), die ein
stationaerer Loeser nicht sauber abbilden kann. Keine dieser Erklaerungen
ist durch einen eigenen Test bestaetigt.

Massnahme: Nicht weiter blind Iterationen anhaengen, das hat sich als
wenig zielfuehrend erwiesen. Fuer Phase 1/2 stattdessen: (1) y+ aus der
tatsaechlichen Reynolds-Zahl berechnen und die erste Zellhoehe entsprechend
setzen statt eines geratenen Werts, (2) denselben Fall bei 0 Grad
Anstellwinkel (einfacherer, symmetrischer Fall) zuerst zum Laufen bringen,
bevor 10 Grad versucht wird, (3) pruefen, ob eine kurze instationaere
(URANS) Rechnung eine echte, physikalisch reale Instationaritaet aufdeckt,
(4) erst mit ausreichend Rechenleistung (siehe R3) eine echte Netzstudie
mit kontrolliertem y+ durchfuehren. Jedes cl/cd aus den bisherigen Laeufen
dieser Sandbox bleibt ausdruecklich unbrauchbar als Ergebnis, nur als Beleg
dass die Werkzeugkette technisch funktioniert.

Update: Der SU2-Adapter (`fosas_core.solver`) ist jetzt als getesteter,
wiederverwendbarer Code vorhanden (siehe ADR-0009) und funktioniert
mechanisch zuverlaessig (echter End-zu-Ende-Test Geometrie zu Netz zu
Loeser zu auslesbarer History, core/tests/test_solver.py). Das hier
beschriebene Konvergenzproblem ist also kein Fehler im Adapter, sondern
weiterhin eine offene fachliche Frage zu Netzaufloesung/Domaingroesse
bei diesem Testfall, siehe Massnahmen (1) bis (4) oben.

Update (Gesichert, per neu geschriebenem und getestetem
`fosas_core.boundary_layer`, siehe core/tests/test_boundary_layer.py):
Hypothese (a) ist bestaetigt. Die flache-Platte-Abschaetzung fuer y+=1 bei
unseren Testbedingungen (Re=6e6, Sehnenlaenge 0,6 m) ergibt eine noetige
erste Zellhoehe von rund 2,67 Mikrometern (0,00000267 m). Im Spike-Testfall
wurde eine erste Zellhoehe von 0,3 mm verwendet, also mehr als das
50-fache des noetigen Werts, das entspricht schaetzungsweise einem
tatsaechlichen y+ von grob 50 bis 100 statt der fuer Spalart-Allmaras ohne
Wandfunktion vorausgesetzten Groessenordnung von 1. Das ist eine sehr
plausible Erklaerung fuer das beobachtete Nicht-Konvergieren: die
Turbulenzmodellierung nahe der Wand war mit dieser Netzaufloesung schlicht
nicht zulaessig eingesetzt. Naechster konkreter Schritt fuer Phase 1: die
Gmsh-Grenzschichtparameter (`Size` am BoundaryLayer-Feld) aus
`fosas_core.boundary_layer.first_cell_height` ableiten statt aus einem
geratenen Wert, und den Testfall damit wiederholen.

Update, Hypothese (a) widerlegt (Gesichert, eigener Test mit korrigierter
Zellhoehe): Mit dem tatsaechlich berechneten y+=1-Wert (2,674 Mikrometer,
Netz mit 323500 Knoten statt vorher 208343, mehr Grenzschichtlagen wegen
der kleineren ersten Zelle) tritt bei Iteration 1532 (implizit, 3
MPI-Raenge) weiterhin ein Restfehler-Plateau auf, diesmal bei rund -3,4
statt -8, sogar etwas schlechter als das fruehere Plateau bei -4,4 mit
dem falschen y+-Wert. CL und CD sind bei diesem Zwischenstand 0,87 bzw.
0,156, die Referenzwerte (1,091 bzw. 0,0123) werden also weiterhin klar
verfehlt, CD um mehr als das Zehnfache. Fazit: Die falsche Zellhoehe war
ein echter, es lohnt sich behobener Fehler, aber sie war nicht die
(alleinige) Ursache des Konvergenzproblems. Das spricht jetzt fuer
Hypothese (b) grobes Fernfeld oder (c) echte schwache Instationaritaet
bei diesem Anstellwinkel, nicht mehr fuer (a).

Nebenbefund zur Prozessverwaltung (relevant fuer R2): Ein zu knapp
bemessener `timeout` in `subprocess.run` (2 Stunden fuer einen dann zu
lange laufenden Fall) fuehrte zu einer `TimeoutExpired`-Ausnahme im
Python-Code. Nach dieser Ausnahme lief zunaechst kein SU2-Prozess mehr
(ueberprueft mit `pgrep`), die Prozessgruppe wurde also auch bei einem
mit `mpirun` gestarteten Mehrprozess-Lauf sauber beendet, kein
Prozessleichnam blieb zurueck. Das ist ein positiver Datenpunkt fuer
Linux, aber keine Aussage ueber Windows/MS-MPI (R2 bleibt dort offen),
und der genaue Zeitpunkt der Beendigung wurde nicht lueckenlos
protokolliert (Annahme: Python/subprocess hat beim Timeout sauber
durchgegriffen, nicht sicher von einer anderen Ursache unterschieden).

Update, Test bei 0 Grad Anstellwinkel abgeschlossen (Gesichert, eigener
Test, gleiches Netz wie oben, 1200 Iterationen, implizit, 3 MPI-Raenge):
Der Restfehler pendelt sich erneut bei fast demselben Niveau ein (rms[P]
rund -3,53, gegenueber -3,4 bei 10 Grad), also praktisch unveraendert
trotz voelig anderem Anstellwinkel. CL ergibt sich zu rund -0,002, also
korrekt nahe null, wie es die Symmetrie eines NACA-0012-Profils bei 0
Grad physikalisch verlangt, das ist ein gutes Zeichen fuer die generelle
Kraftauswertung. CD liegt bei rund 0,030, damit naeher an plausiblen
Werten fuer den Nullauftriebsfall als der 10-Grad-Fall an seiner
Referenz war, aber immer noch deutlich erhoeht gegenueber literatur-
ueblichen Cd-Werten fuer NACA0012 bei Re=6e6 und 0 Grad (Groessenordnung
0,006 bis 0,008 fuer einen sauber konvergierten Fall, hier nicht mit
Primaerquelle belegt, als Einordnung/Vermutung markiert).

Einordnung: Da das Restfehler-Plateau bei einem symmetrischen,
physikalisch unauffaelligen Nullauftriebsfall genauso auftritt wie bei
10 Grad, ist Hypothese (c) (auftriebsbedingte Instationaritaet) als
alleinige oder Haupt-Ursache unwahrscheinlicher geworden. Das Plateau
haengt offenbar nicht am Anstellwinkel, sondern ist wahrscheinlich in der
Netz- oder Domainkonfiguration selbst begruendet (Hypothese b), zum
Beispiel im Uebergangsbereich zwischen Grenzschichtnetz und dem groeberen
isotropen Aussenfeld, oder in der Fernfeldaufloesung/-distanz. Das ist
der naechste sinnvolle Untersuchungspunkt (Netzqualitaetskennzahlen im
Uebergangsbereich pruefen, Fernfeld verfeinern oder vergroessern), aber
noch nicht durchgefuehrt.

Update, zwei neue Verdachtspunkte, beide unbestaetigt (Gesichert nur als
Beobachtung, Interpretation ist Vermutung): Beim Vernetzen mit
`generate_constant_section_geo` erscheinen durchgehend 12 Warnungen
"Skipping curve with no begin or end point" fuer eine interne
Platzhalterkurve (Tag 444444, "Discrete curve"), vermutlich Teil der
Eck-/Fan-Behandlung des `BoundaryLayer`-Felds an Vorder- und Hinterkante.
Nicht bekannt, ob das ein bekanntes, harmloses Gmsh-Verhalten ist oder auf
tatsaechlich fehlerhafte Zellen an genau der aerodynamisch wichtigsten
Stelle hindeutet, dazu wurde keine Quelle gefunden. Zusaetzlich faellt
auf: Der "Optimizing mesh"-Schritt nach der Extrusion braucht nur rund
27 Millisekunden bei ueber 100000 Knoten, das ist zu schnell fuer eine
echte Qualitaetsoptimierung und deutet darauf hin, dass der
Extrusionsvernetzungsweg (anders als der urspruengliche isotrope
Tetraeder-Ansatz aus R1, der eine sichtbare, mehrere Sekunden dauernde
Optimierung mit Qualitaetshistogramm durchlief) keine echte
Nachbearbeitung der Zellqualitaet bekommt. Kein Werkzeug in dieser
Sandbox (keine Gmsh-Python-Bindings, kein ParaView) erlaubt aktuell eine
direkte Pruefung der Zellqualitaet im Uebergangsbereich, das bleibt eine
Werkzeuglücke.

Update, Test mit dreifach vergroessertem Fernfeld abgeschlossen (Gesichert,
eigener Test): Erster Versuch (gleiche Zellgroesse wie vorher, nur
groesseres Gebiet) fuehrte zu 3,66 Mio. Elementen statt 1,84 Mio. und ging
in einen Speicherueberlauf (Signal 9), bevor ueberhaupt eine Iteration
lief, kein verwertbares Ergebnis. Nach Korrektur (Fernfeld 15/25/15
Sehnenlaengen statt 5/10/6, aber Hintergrundnetz dort auch entsprechend
groeber, background_size_max_factor 1,25 statt 0,5) ergab sich mit 313075
Knoten eine zum bisherigen Testfall vergleichbare Netzgroesse. 1500
Iterationen, gleiches Restfehler-Plateau wie zuvor (rms[P] pendelt sich
bei rund -3,37 bis -3,40 ein, praktisch identisch zu den Faellen mit dem
kleineren Fernfeld), CL=0,826, CD=0,150, beide weiterhin klar entfernt von
der Referenz (1,091 bzw. 0,0123).

Einordnung: Damit sind jetzt alle drei urspruenglichen Hypothesen aus
diesem Risikoeintrag durch eigene Tests ueberprueft und keine einzelne
konnte das Plateau erklaeren oder auch nur spuerbar veraendern: (a)
falsches y+ widerlegt, (c) auftriebsbedingte Instationaritaet
unwahrscheinlich (Plateau auch bei 0 Grad), (b) Fernfelddistanz widerlegt
(dreifache Distanz aendert nichts). Der wahrscheinlichste verbleibende
Verdaechtige ist eine tatsaechliche Netzqualitaetsschwaeche, am ehesten im
Uebergangsbereich zwischen Grenzschicht und Aussenfeld oder an den
Vorder-/Hinterkanten-Ecken (siehe die "curve 444444"-Beobachtung oben),
aber das ist in dieser Sandbox mangels Werkzeug (keine
Gmsh-Python-Bindings fuer Zellqualitaetsabfragen, kein ParaView fuer
visuelle Kontrolle) nicht direkt nachweisbar.

Status: Drei von drei getesteten Hypothesen widerlegt oder stark
entkraeftet, die verbleibende, wahrscheinlichste Erklaerung (Netzqualitaet)
ist mit der aktuellen Werkzeugausstattung nicht weiter pruefbar. Weiteres
blindes Ausprobieren an dieser Stelle ist nicht mehr zielfuehrend.

Massnahme, fuer eine spaetere Fortsetzung: Entweder (1) eine x86_64-Umgebung
mit echten Gmsh-Python-Bindings und/oder ParaView beschaffen, um die
Zellqualitaet im Uebergangsbereich direkt zu messen und sichtbar zu
machen, oder (2) den alternativen `extrudeBoundaryLayer`-Vernetzungsweg
ausprobieren (bisher nur per Python-API demonstriert, siehe ADR-0007),
der die Eckbehandlung eventuell anders und robuster loest, oder (3) den
Vergleichsfall exakt wie im SU2-Tutorial nachbauen (strukturiertes
C-Netz statt unseres unstrukturierten Ansatzes), um auszuschliessen,
dass die Unstrukturiertheit selbst die Ursache ist. Alle drei sind
groessere, eigene Arbeitspakete, keine schnelle naechste Aktion.

Update, Fortsetzung mit echten Gmsh-Python-Bindings auf x86_64 (Massnahme
1 jetzt verfuegbar, siehe AWS-Server aus der aktuellen Sitzung): Direkte
Zellqualitaetsmessung durchgefuehrt (`gmsh.model.mesh.getElementQualities`,
Mass "minSICN") und vier weitere, bisher nie getestete Numerik-Varianten
durchgerechnet. Keine davon hat das Konvergenzproblem behoben, aber alle
liefern neue, Gesicherte Befunde, die R10 praeziser eingrenzen.

(1) Zellqualitaet direkt gemessen: Mit dem bisherigen Vernetzungsweg
(`generate_constant_section_geo`, Extrude mit `Layers{n}`) sind 72,7 %
aller 3D-Elemente (620208 Tetraeder) mit minSICN < 0,1, Median 0,0123, bei
0 invertierten Elementen. Aufgeschluesselt nach Wandabstand (Vielfaches
der Grenzschichtdicke): innerhalb der Grenzschicht (0-100 % Dicke) Median
0,001-0,0014, direkt ausserhalb (1x-2x Dicke, "Uebergangszone") immer noch
Median 0,0061 mit 96,9 % unter 0,1, erst bei 2x-10x Dicke deutliche
Besserung (Median 0,175), im reinen Fernfeld gut (Median 0,90). Wichtige
Einordnung, bevor daraus voreilig eine Fehlerursache gemacht wird: minSICN
ist ein isotropes Formmass, das jede absichtlich anisotrope
Grenzschichtzelle (duenn in Wandnormalenrichtung, lang tangential) prinzip-
bedingt als "schlecht" bewertet, auch wenn die Zelle fuer ihren Zweck genau
richtig geformt ist. Diese Zahlen allein sind also kein Beweis fuer einen
echten Vernetzungsfehler.

(2) Tetraeder- vs. Prismen-Vernetzung: Mit `Recombine;` am Extrude-Befehl
erzeugt Gmsh direkt Prismen (Elementtyp 6) statt die Extrusionsschicht in
Tetraeder zu zerlegen (261758 statt 620208 3D-Elemente, "Subdividing
extruded mesh"-Schritt im Log verschwindet). Die minSICN-Verteilung bleibt
aber praktisch identisch (69,9 % unter 0,1, Median 0,0151), und ein echter
SU2-Lauf (implizit, CFL=5, 500 Iterationen, Re/Mach/AoA wie Referenzfall)
zeigt dasselbe qualitative Restfehler-Plateau wie mit Tetraedern zuvor
(rms[P] um -2,6, CL endet bei 0,95 nach sichtbarem Schwanken). Schluss:
Die Tetraeder-Zerlegung der Extrusionsschicht ist nicht die Ursache des
Plateaus, trotz der auffaelligen minSICN-Zahlen.

(3) Die Platzhalterkurve "444444" direkt untersucht (per
`gmsh.model.getType`/`getBoundingBox`/`getNodes`): Typ "Discrete curve",
0 Knoten, leere Bounding Box. Das ist ein echtes, aber vollstaendig leeres
Gmsh-internes Artefakt (vermutlich aus der Eck-/Fan-Behandlung des
`BoundaryLayer`-Felds), das Gmsh selbst erkennt und beim Vernetzen
uebergeht (passend zur Warnung "Skipping curve with no begin or end
point"). Die tatsaechlich schlechtesten Elemente im Netz liegen zudem
raeumlich NICHT konzentriert an Vorder-/Hinterkante (Stichprobe von 2000
schlechtesten Tetraedern: 0 davon innerhalb 1 cm von LE oder TE). Die
"curve 444444"-Spur aus einem fruehen Update dieses Risikoeintrags ist
damit ausdruecklich als Fehlspur geklaert, nicht als Ursache.

(4) CFL-Schema variiert (bisher nie getestet): Adaptive CFL
(`CFL_ADAPT=YES`, Start-CFL 1,0 statt fest 5,0) auf demselben Prismennetz
fuehrt zu einem ANDEREN Plateau als die feste CFL-Zahl auf demselben Netz
(CL steigt ueber 450 Iterationen kontinuierlich von 0,26 auf 0,69, beim
Abbruch immer noch steigend, waehrend der Restfehler bei rund -2,7 bis
-2,9 verharrt). Zwei numerische Pfade auf identischer Geometrie und
identischem Netz landen also in unterschiedlichen Quasi-Plateaus, keiner
in der Naehe der Referenz.

(5) Innerer linearer Loeser verstaerkt (bisher nie getestet, naheliegende
Erklaerung fuer "Restfehler faellt nicht mehr, Loesung aendert sich
trotzdem" aus einem fruehen Update dieses Eintrags): `LINEAR_SOLVER_ITER`
von 10 auf 50 und `LINEAR_SOLVER_ERROR` von 1E-6 auf 1E-8 erhoeht. Bei 10
Grad Anstellwinkel zunaechst sehr vielversprechend (CL=1,30 bei Iteration
12, nahe an der Referenz 1,091), aber bereits bis Iteration 131
abgedriftet auf CL=0,08-0,22, Restfehler weiterhin bei rund -2,9 bis -3,0
pendelnd. Bei 0 Grad (der eigentlich einfachste, symmetrische Fall)
dasselbe Muster: CD zunaechst bei 0,0135 (deutlich naeher an
literaturueblichen 0,006-0,008 als jeder bisherige Lauf), aber innerhalb
von nur 3 weiteren Iterationen auf 0,033 abgedriftet, CL bleibt immerhin
nahe am physikalisch korrekten Wert 0 (-0,006 bis -0,013). Wichtige
methodische Lektion daraus: Ein frueher, gut aussehender Zwischenwert ist
bei diesem Testfall kein verlaessliches Zeichen fuer tatsaechliche
Konvergenz, in beiden Faellen dieses Updates hat sich ein vielversprechend
wirkender frueher Stand als Durchgangsstadium erwiesen, nicht als
Ankunft.

Einordnung (Gesichert als Beobachtung, Interpretation Vermutung): Fuenf
voneinander unabhaengige numerische Konfigurationen (Tetraeder/Prismen,
feste/adaptive CFL, schwacher/starker innerer Loeser, 0/10 Grad
Anstellwinkel) zeigen alle dasselbe qualitative Muster: Der aeussere
Restfehler pendelt sich auf einem Plateau weit ueber dem Ziel ein (-2,6
bis -2,9 statt -8), waehrend die daraus abgeleiteten Kraftbeiwerte auch
NACH diesem scheinbaren Plateau noch deutlich weiterwandern, in
unterschiedliche Richtungen je nach Numerik. Das spricht gegen "braucht
nur mehr Zeit" und auch gegen die in diesem Update einzeln getesteten
Erklaerungen (Tetraeder-Zerlegung, Eckkurven-Artefakt, CFL-Schema,
Loeser-Staerke). Es stuetzt erneut Hypothese (c) aus der urspruenglichen
Fassung dieses Eintrags (eine fuer einen stationaeren Loeser nicht
cleanly abbildbare, schwache Instationaritaet), jetzt aber mit einem
wichtigen neuen Datenpunkt: Sogar der 0-Grad-Fall, der im fruehen Verlauf
dieses Eintrags als vermeintlicher Gegenbeweis fuer Hypothese (c) galt
(1200 Iterationen stabil bei rms[P] rund -3,53), zeigt mit der staerkeren
Loeser-Einstellung aus diesem Update erneut spuerbares Abdriften statt
Stabilitaet, die fruehere "0 Grad ist stabil"-Schlussfolgerung muss also
mit Vorsicht behandelt werden, sie koennte selbst nur ein breiteres oder
laenger anhaltendes Plateau gewesen sein, keine echte Konvergenz.

Status: Weiterhin offen. Phase 1 (cl/cd/cp-Verteilung gegen
Referenzdaten) ist mit diesem Befund NICHT erreicht, ausdruecklich kein
Erfolg zu vermelden. Fuenf zusaetzliche Erklaerungen sind jetzt mit
echten Daten geprueft und verworfen (Tetraeder-Zerlegung, Eckkurven-
Artefakt, CFL-Schema, Loeser-Staerke, und implizit die vorherige
"0 Grad ist stabil"-Annahme), zusaetzlich zu den drei bereits vorher
widerlegten (falsches y+, zu kleines Fernfeld, reine AoA-Abhaengigkeit).

Massnahme, fuer eine weitere Fortsetzung, nach Dringlichkeit geordnet:

1. `gmsh.model.geo.extrudeBoundaryLayer` ist auf dem jetzt verfuegbaren
   x86_64-Server bestaetigt vorhanden (Gmsh 4.15.2,
   Signatur `extrudeBoundaryLayer(dimTags, numElements=[1], heights=[],
   recombine=False, second=False, viewIndex=-1)`), bisher aber nicht
   ausprobiert: Das ist ein geometrisch anderer Vernetzungsweg (echte
   Extrusion entlang der Flaechennormalen statt 2D-Feld plus
   translatorischem Extrude) und braucht den nativen "geo"-Kernel statt
   OpenCASCADE, also einen eigenen, nicht trivialen Nachbau der
   Geometrieerzeugung. Noch nicht begonnen, geschaetzt ein eigenes,
   mehrstuendiges Arbeitspaket fuer sich.
2. Eine aussagekraeftigere Qualitaetskennzahl fuer die Uebergangszone
   waere eine, die nicht wie minSICN von Anisotropie allein schon
   bestraft wird, zum Beispiel eine direkte Messung der
   Flaechenorthogonalitaet/Skewness an den Zellgrenzen (relevant fuer
   SU2s Finite-Volumen-Diskretisierung), nicht ausprobiert in dieser
   Runde.
3. Strukturiertes C-Netz exakt wie im SU2-Tutorial nachbauen bleibt die
   aufwaendigste, aber eindeutigste Methode, um "liegt es an unserem
   unstrukturierten Vernetzungsweg ueberhaupt" zu klaeren.

Alle drei weiterhin groessere, eigene Arbeitspakete. Produktionscode
(`fosas_core`) wurde in dieser Untersuchungsrunde nicht veraendert, da
keiner der getesteten Ansaetze das Problem behoben hat; alle Tests liefen
ausserhalb der Produktionspipeline auf eigens dafuer erzeugten
Testnetzen/-configs, um die laufende Engine nicht zu beeinflussen.

Update, Durchbruch mit Massnahme 3 (Gesichert, eigener Test, direkt an
den Rohdaten auf dem Server nachgeprueft): Das SU2-Projekt stellt den
tatsaechlichen Tutorial-Fall oeffentlich bereit
(`github.com/su2code/Tutorials`, `incompressible_flow/
Inc_Turbulent_NACA0012/`, LGPL-2.1 wie SU2 selbst), inklusive des
echten strukturierten Netzes (`n0012_897-257.su2`, 229376 Elemente,
strukturierte Quads) und der Original-Config (`turb_naca0012.cfg`,
Autoren Economon & Palacios, 2018, mit Verweis auf dieselbe NASA-TMR-
Validierungsseite, aus der unsere Referenzwerte stammen). Kein eigener
Netzbau noetig.

Unveraendert mit unserem installierten SU2 8.5.0 auf 2000 Iterationen
gedeckelt (Original-Config: 99999) gelaufen. Ergebnis, direkt aus
`su2_run.log`/`history.csv` gelesen: Restfehler (rms[P]) faellt
durchgehend und OHNE Plateau von -4,3 (Iteration 0) auf -7,24
(Iteration 1999), bei Abbruch immer noch fallend, Zielwert der
Original-Config war -14. CL erreicht bereits bei Iteration 1606 den
Wert 1,0913, praktisch exakt die Referenz (1,091), und liegt am Ende
bei 1,098 (0,6 % Abweichung). CD faellt stetig von anfangs ueber 0,1
auf 0,0172 am Ende, immer noch klar in Richtung der Referenz (0,0123)
fallend, nicht geplatzt. Das ist ein grundlegend anderes Verhalten als
jeder eigene Lauf bisher: keine grossamplitudige Oszillation, kein
hartnaeckiges Restfehler-Plateau, sondern eine erkennbar echte,
fortschreitende Konvergenz.

Einordnung: Das widerlegt die bisherige Haupthypothese (c) aus diesem
Eintrag (der Fall habe moeglicherweise gar keinen fuer einen
stationaeren Loeser erreichbaren Zustand). Er hat einen, SU2 selbst
findet ihn auf einem geeigneten Netz mit geeigneter Numerik zuverlaessig.
Das Problem liegt also bei unserer eigenen Vernetzung und/oder unserer
eigenen Loeser-Konfiguration (`fosas_core.solver`), nicht am Testfall
oder an SU2 selbst.

Direkter Konfigurationsvergleich (Gesichert, aus beiden Config-Dateien
gelesen), vier Abweichungen zwischen Original und unserer generierten
Config:

| Einstellung | Original (Tutorial) | Unsere Config |
|---|---|---|
| `SLOPE_LIMITER_FLOW` | `NONE` | `VENKATAKRISHNAN` |
| `CFL_NUMBER` | 25,0 (fest) | 1,0 (Standard, R10/ADR-0012) |
| `LINEAR_SOLVER_PREC` | `ILU` | `JACOBI` |
| `LINEAR_SOLVER_ERROR` | 1E-10 | 1E-6 |

Update, erster Eingrenzungsversuch (Vermutung, nicht abschliessend
getestet wegen Zeitbudget dieser Runde): Ein frueheres Update dieses
Eintrags hatte bereits einen staerkeren inneren Loeser (10->50
Iterationen, 1E-6->1E-8 Fehler) auf dem EIGENEN unstrukturierten Netz
getestet, mit JACOBI-Vorkonditionierer und VENKATAKRISHNAN-Limiter
unveraendert: Kein Erfolg, weiterhin Plateau/Abdriften. Das spricht
dagegen, dass die lineare Loeser-Toleranz allein (ohne die anderen drei
Aenderungen) ausreicht.

Update, Isolations-Experimente auf dem EIGENEN Netz durchgefuehrt
(Gesichert, eigener Test, dasselbe unstrukturierte Netz wie in den
fruehen Teilen dieses Eintrags: 118341 Knoten, 623544 Tetraeder, Re=6e6,
chord=0,6 m, 10 Grad, span_layers=8). Drei Varianten, jeweils nur ein
oder zwei der vier oben gefundenen Abweichungen uebernommen, Rest wie
unsere eigene Standard-Config:

- **Nur CFL=25 (sonst unveraendert):** SU2 divergiert explosiv, Restfehler
  ueberschreitet 10^20 bereits bei Iteration 4 (CL/CD laufen auf
  astronomische Werte). CFL=25 ist also keine universell uebertragbare
  "bessere" Einstellung, sondern vermutlich auf die Zellqualitaet des
  strukturierten Tutorial-Netzes abgestimmt und auf unserem Netz schlicht
  zu aggressiv.
- **Nur Limiter aus (CFL weiterhin bei unserem sicheren Wert 1,0):**
  Divergiert genauso explosiv und genauso schnell (Iteration 4, gleiches
  Fehlerbild). Der VENKATAKRISHNAN-Limiter ist auf unserem Netz also kein
  Stilunterschied, sondern fuer die numerische Stabilitaet notwendig,
  vermutlich wegen der in einem fruehen Update dieses Eintrags gemessenen
  schlechten Zellqualitaet (72,7 % minSICN < 0,1) im Grenzschicht-
  Uebergangsbereich.
- **Nur ILU-Vorkonditionierer + 1E-10-Toleranz (CFL=1,0, Limiter an):**
  Divergiert NICHT, laeuft stabil, zeigt aber dasselbe bekannte Muster:
  Restfehler faellt schnell auf rund -2,8 und bleibt dort (bei Iteration
  69 sogar leicht auf -2,83 zurueckgefallen statt weiter zu fallen),
  waehrend CL weiter von 1,04 auf 1,34 wandert, CD von 0,54 auf 0,64.
  Praktisch identisch zum bereits bekannten Plateau-Muster mit dem
  schwaecheren JACOBI/1E-6-Loeser. ILU und die straffere Toleranz allein
  bringen also keinen Durchbruch.

Einordnung (Gesichert als Beobachtung): Von den vier urspruenglich
gefundenen Abweichungen sind zwei (CFL=25, Limiter aus) auf unserem Netz
destabilisierend statt hilfreich, eine (ILU+Toleranz) macht praktisch
keinen Unterschied zum bisherigen Plateau. Keine Einzelmassnahme oder
Zweier-Kombination aus den vier Abweichungen reproduziert auf unserem
eigenen Netz das Konvergenzverhalten des Tutorial-Laufs. Das spricht
jetzt dafuer (Vermutung, naechster logischer, aber noch nicht bewiesener
Schritt waere Massnahme 1 oder 3 von oben), dass primaer die
Netzstruktur selbst (strukturiert, mit gleichmaessiger, fuer CFL=25
geeigneter Zellqualitaet) der entscheidende Faktor ist, nicht eine
einzelne uebertragbare Solver-Einstellung. CFL=25 und Limiter-aus sind
vermutlich nur deshalb im Tutorial sicher, WEIL dessen Netz dafuer
gebaut ist, nicht weil sie universell bessere Werte waeren.

Kein Code in `fosas_core` in dieser Runde geaendert: Keine der drei
isolierten Varianten liefert einen klaren, sicheren Verbesserungsvorschlag
fuer unseren eigenen Vernetzungsweg, zwei davon waeren als neuer
Standardwert sogar gefaehrlich (sofortige Divergenz). Naechster
sinnvoller Schritt bleibt, die Netzstruktur selbst anzugehen (Massnahme 1
`extrudeBoundaryLayer` oder Massnahme 2, Flaechenorthogonalitaet/Skewness
statt minSICN messen), nicht weitere Solver-Parameter-Kombinationen.

Status: R10 bleibt im Kern offen (Phase-1-Referenzvergleich mit der
EIGENEN Vernetzungstechnik weiterhin nicht erreicht), aber die Frage hat
sich grundlegend verschoben: von "hat dieser Testfall ueberhaupt einen
erreichbaren stationaeren Zustand" (jetzt widerlegt) zu "welche konkrete
Kombination aus Netzstruktur und/oder Loeser-Numerik verhindert, dass
unser eigener Weg ihn findet" (noch offen, aber jetzt mit einer
nachgewiesenen, erreichbaren Zielmarke und vier konkreten, bekannten
Kandidatenursachen statt einer offenen Vermutung).

Update, y+-Ist-Wert gegen y+-Ziel geprueft (Gesichert, eigene Auswertung
der `surface_flow.csv` aus dem ILU+enge-Toleranz-Lauf oben, 1845
Oberflaechenpunkte): Der tatsaechlich erreichte y+ liegt im Mittel bei
3,03 (Minimum 0,27, Maximum 3,94, Median 3,10) gegenueber dem
Zielwert 1,0. Das ist eine Abweichung um den Faktor rund 3, deutlich
weniger dramatisch als die urspruengliche 50-bis-100-fache Abweichung
aus der widerlegten Hypothese (a) weiter oben. Als alleinige Erklaerung
fuer ein hartes Konvergenz-Plateau ist ein Faktor 3 bei y+ eher
unwahrscheinlich (Vermutung), auch wenn es nicht ideal ist.

Update, direkter Vergleich BoundaryLayer-Feld gegen isotropes Netz, erste
echte Netzqualitaetsmessung ueberhaupt (Gesichert, eigener Test mit den
jetzt auf dem x86_64-Server verfuegbaren echten Gmsh-Python-Bindings,
siehe `/tmp/r10_quality_compare` auf dem AWS-Server): Zwei Netze fuer
dieselbe NACA-0012-Geometrie wurden erzeugt, identisch bis auf ein Detail:
Variante A exakt wie `fosas_core.meshing` sie heute baut (mit
BoundaryLayer-Feld), Variante B dieselbe Geometrie/Felder, aber ohne das
BoundaryLayer-Feld (nur isotropes Hintergrundfeld). minSICN-Qualitaet im
selben raeumlichen Band um das Profil (innerhalb der zweifachen
Grenzschichtdicke): Variante A 69,5 Prozent der Elemente unter 0,1
(nahezu identisch zur fruehen 72,7-Prozent-Messung oben, guter
Konsistenzcheck), Variante B 0,0 Prozent unter 0,1 (Minimum 0,35,
Mittelwert 0,62). Der Unterschied ist real und reproduzierbar.

Aber (Gesichert, direkt nachgeprueft, und das relativiert die bisherige
Einordnung dieser Messung erheblich): minSICN misst Form-Regelmaessigkeit
(wie nah an gleichseitig), nicht geometrische Gueltigkeit. Eine
vorsaetzlich extrem gestreckte, aber korrekt orientierte
Grenzschichtzelle hat praktisch immer eine sehr niedrige minSICN, ganz
unabhaengig davon, ob sie fuer die Loesung brauchbar ist, weil genau das
der Zweck einer Grenzschichtzelle ist (erste Zellhoehe hier 2,674
Mikrometer gegen Hintergrundzellen im Millimeter- bis Zentimeterbereich,
ein Seitenverhaeltnis von mehreren Tausend zu eins). Entscheidend ist
stattdessen, ob Elemente invertiert (negative minSICN) sind, das waere
ein echter, harter Defekt. Direkte Pruefung auf Variante A (309000
Elemente): kein einziges Element mit negativer minSICN, das absolute
Minimum liegt bei +0,000032 (positiv, nur extrem klein). Es handelt sich
also, soweit mit diesem Mass pruefbar, nicht um invalide/umgeklappte
Zellen, sondern um erwartbar stark anisotrope, aber gueltige
Grenzschichtzellen. Die fruehere Einordnung "72,7 Prozent niedrige
minSICN deutet auf eine Netzqualitaetsschwaeche hin" war selbst nur eine
Vermutung, keine Pruefung auf echte Invaliditaet, und haelt dieser
Pruefung so nicht stand.

Update, Fan-Behandlung an der scharfen Hinterkante direkt getestet und
die "curve 444444"-Vermutung dabei mitgeklaert (Gesichert, eigener Test):
Gmsh liefert zwei eigene Beispielskripte exakt fuer diesen Fall
(`naca_boundary_layer_2d.py`/`_3d.py`, im eigenen Gmsh-Paket enthalten).
Deren Kommentar zur scharfen (nicht abgerundeten) Hinterkante: ohne
expliziten `FanPointsList`-Eintrag am Eckpunkt kennt das BoundaryLayer-
Feld die Sonderbehandlung der Ecke nicht. Das passt auffaellig gut zur
seit Wochen offenen "Skipping curve with no begin or end point"/"No
elements in curve 444444"-Beobachtung (vermutlich genau diese fehlende
Fan-Zuweisung). Direkter Test mit `Field[3].FanPointsList` am
Hinterkanten-Eckpunkt: Die Warnung bleibt unveraendert bestehen (curve
444444 wird weiterhin als leer gemeldet), und die Qualitaetsverteilung
aendert sich nur marginal (2D-Isolationstest: 49,0 auf 47,7 Prozent unter
0,1). Eine raeumliche Auswertung der schlechtesten Elemente zeigt ausserdem:
Sie liegen nicht konzentriert an den beiden Profil-Ecken, sondern nahezu
gleich verteilt ueber die GESAMTE Sehnenlaenge (rund 920 von 9413
"schlechten" Elementen pro Zehntel-Sehnenlaenge, von x/chord=0,1 bis 0,9).
Das widerlegt die Ecken/Fan-Hypothese als Hauptursache: Es ist kein
lokaler Eckendefekt, sondern ein durchgehendes Merkmal des gesamten
Uebergangsrings zwischen Grenzschicht- und Hintergrundfeld, siehe
Vermutung oben: wahrscheinlich einfach die erwartete Form von
Grenzschichtzellen, kein Fehler.

Einordnung nach diesen drei neuen Tests: Die im vorherigen Durchlauf als
"wahrscheinlichste verbleibende Ursache" eingestufte Netzqualitaet
(gemessen per minSICN) ist nach genauerer Pruefung keine belastbare
Erklaerung mehr, weil das verwendete Mass (minSICN) genau das straft, was
eine Grenzschichtzelle per Definition tun soll, und weil keine
tatsaechlich invaliden (invertierten) Elemente gefunden wurden. Die
Fan/Ecken-Idee aus Gmshs eigenen Beispielen ist ebenfalls direkt getestet
und verworfen. Damit ist R10 wieder offener als im vorherigen
Zwischenstand suggeriert: Von den inzwischen fuenf geprueften Hypothesen
((a) y+, (b) Fernfeld, (c) Instationaritaet bei AoA, (d) einzelne
Solver-Parameter, (e) minSICN-Netzqualitaet/Eckenbehandlung) ist keine
einzige als Hauptursache bestaetigt, vier sind mit eigenen Tests
widerlegt oder stark entkraeftet, eine (y+, Faktor 3 statt 50-100) bleibt
ein kleiner, aber wahrscheinlich nicht alleine ausreichender Faktor.

Massnahme, fuer eine spaetere Fortsetzung: Noch nicht getestet und am
ehesten vielversprechend (Vermutung): eine CFD-uebliche
Netzqualitaetskennzahl, die tatsaechlich fuer anisotrope Grenzschicht-
netze gedacht ist (z. B. Flaechen-Orthogonalitaet am Uebergang
Grenzschicht/Hintergrundfeld, oder die lokale Zellgroessen-Sprungrate
zwischen benachbarten Zellen, statt einer generischen Form-Kennzahl wie
minSICN), oder der komplett andere `extrudeBoundaryLayer`-Vernetzungsweg
(geo-Kernel statt Feld-basiert, siehe Gmshs eigene 3D-Beispieldatei), der
mangels Zeit in dieser Runde nicht mehr getestet wurde.

Korrektur und Schliessung einer Luecke in der obigen Isolationsmatrix
(Gesichert, eigener Test): Beim genauen Nachlesen der eigenen
Experimentskripte (`gen_configs.py` vs. `gen_configs_v2.py` auf dem
AWS-Server) zeigt sich, dass "CFL=25 alone" oben tatsaechlich der
vollen Vier-Parameter-Kombination (`tutorial_numerics`: CFL=25 UND
Limiter aus UND ILU UND 1E-10) entsprach, nicht einer echten Isolation
von CFL=25 fuer sich allein. Eine echte Einzelisolation (nur CFL=25,
Praekonditionierer/Toleranz/Limiter unveraendert bei JACOBI/1E-6/
VENKATAKRISHNAN) wurde deshalb nachtraeglich eigens durchgefuehrt.
Ergebnis: CFL=25 allein divergiert ebenfalls, aber deutlich langsamer
als die volle Kombination. rms[P] startet stabil fallend (-2.8 bei
Iteration 7), kippt aber bei Iteration 85 ins Positive und waechst von
dort monoton (rms[P]=+2,33 bei Iteration 99, CL/CD bereits im
zweistelligen Millionenbereich), Lauf nach Iteration 99 manuell
abgebrochen, da die Richtung eindeutig war. Damit ist jetzt tatsaechlich
jede der vier einzelnen Tutorial-Abweichungen fuer sich allein auf dem
eigenen Netz getestet (CFL=25 allein: divergiert, langsamer; Limiter
aus allein: divergiert, Iteration 4; ILU+enge Toleranz zusammen: stabil,
aber reproduziert nur das alte Plateau; alle vier zusammen: divergiert,
Iteration 4), und keine davon, einzeln oder kombiniert, bringt das
eigene Netz zur Konvergenz. Das staerkt die Einordnung von oben (die
Tutorial-Werte sind vermutlich nur sicher, WEIL das Tutorial-Netz dafuer
gebaut ist), jetzt ohne die Luecke einer nie wirklich isoliert
getesteten Einzelmassnahme.

Update, `extrudeBoundaryLayer` als Alternative zum Feld-Ansatz prototypisch
getestet (Gesichert, eigener Test, siehe `/tmp/r10_extrudebl_proto.py` auf
dem AWS-Server): Dieser von Gmsh selbst fuer genau diesen Anwendungsfall
empfohlene Weg (geo-Kernel-Extrusion entlang der Wandnormalen statt
Feld-basierter anisotroper Vernetzung, Massnahme 1 oben) wurde fuer das
echte NACA-0012-Profil (zwei Splines, scharfe Hinterkante) nachgebaut.
Ergebnis, mehrfach gegengeprueft: Die erzeugten Netze haben eine klar
bessere mittlere Elementqualitaet als der Feld-Ansatz (minSICN-Mittel
rund 0,66 bis 0,79 statt 0,12 im Wandnahbereich), ABER enthalten jetzt
tatsaechlich eine kleine Zahl ECHT invertierter Elemente (negative
minSICN, zwischen 3 und 11 Prozent je nach Parametrisierung), waehrend
der bisherige Feld-Ansatz bei derselben Pruefung null invertierte
Elemente hatte. Das ist nach dem einzigen eindeutigen Kriterium (invalide
Elemente: ja oder nein) also ein Rueckschritt, nicht ein Fortschritt.

Die invertierten Elemente treten immer in exakt einer radialen Spalte
auf (ihre Anzahl ist bei jedem Testlauf exakt gleich der Anzahl
Grenzschichtlagen, sie liegen also alle an derselben Stelle entlang des
Profils, ueber alle Lagen hinweg). Zwei Erklaerungen wurden ueberprueft
und beide verworfen: (1) zu grosse Gesamtdicke im Verhaeltnis zum
lokalen Kruemmungsradius, widerlegt, weil der Defekt auch bei einer
Dicke von nur 0,33 Prozent der Sehnenlaenge weiterhin auftritt, das ist
fuer dieses Profil weit innerhalb jedes plausiblen Kruemmungsradius; (2)
zu grobe Diskretisierung des Profils, widerlegt, weil der Defekt bei 40,
60, 120 und 240 Stuetzpunkten gleich stark bleibt. Auffaellig und noch
nicht erklaert (Vermutung): Die genaue x-Position des Defekts
verschiebt sich zwischen Testlaeufen unvorhersehbar (0,162 oder 0,831
Sehnenanteil je nach Punktanzahl), was eher auf eine Kante/Numerik-
Eigenart von Gmshs eigener Normalenberechnung fuer `extrudeBoundaryLayer`
auf gesplineten Kurven hindeutet als auf eine echte geometrische
Unmoeglichkeit.

Einordnung: `extrudeBoundaryLayer` ist damit kein einfacher Ersatz "schnell
eingebaut, sofort besser". Es loest das eine Problem (niedrige minSICN im
wandnahen Bereich, siehe oben ohnehin schon als vermutlich unproblematisch
eingeordnet), erzeugt aber ein neues, echtes Problem (tatsaechlich
invalide Elemente), das beim Feld-Ansatz nicht vorkommt. Um das nutzbar
zu machen, waere eine eigene, noch nicht begonnene Fehlersuche in Gmshs
Normalenberechnung oder ein anderer Kurvenaufbau (z. B. eine einzelne
glatte Spline statt zwei, oder eine analytische statt interpolierte
Kurve) noetig, kein kurzer Test mehr.

Status nach dieser Runde: Beide bisher verfuegbaren Gmsh-Vernetzungswege
fuer dieses Profil (Feld-basiert und Extrusions-basiert) haben je einen
eigenen, unterschiedlichen Mangel, keiner ist eindeutig besser, und
keiner wurde bisher mit einem tatsaechlich konvergierenden SU2-Lauf
verknuepft (der extrudeBoundaryLayer-Pfad wurde mangels eines validen
Netzes noch nicht einmal bis zum SU2-Lauf gebracht). R10 bleibt offen.

## R11: Reales Kundenmodell (Auto-Heckspoiler) ist kein Solid, echte Luecke

Beleg (eigener Test mit vom Projektinhaber bereitgestellter Datei
`Test_Spoiler.step`, STEP-Datei von Open CASCADE 7.7 erzeugt, automotive
design schema): Der Import ergibt 182 einzelne, nicht verbundene
Flaechen-Patches (182 Shells mit je 1 Face), null Solids, nicht
mannigfaltig. Groessenordnung passt zu einem realen Heckspoiler
(Bounding Box ca. 1521 x 331 x 217 mm, vermutlich mm als Einheit).
Sewing-Reparatur (siehe ADR-0008) verbindet bei Toleranzen zwischen 0,05
und 0,7 mm alle 182 Flaechen zu einer einzigen zusammenhaengenden Schale,
aber es bleiben durchgehend 6 bis 8 offene Kanten uebrig, unabhaengig von
der genauen Toleranz. Vier der offenen Kanten sind auffaellig lang (rund
1490 bis 1516 mm, nahe der vollen Spannweite) und liegen alle nahe x=0,
bei unterschiedlichen z-Hoehen (rund 15,5 mm, 24,3 mm doppelt, 45,5 mm),
zwei davon fast deckungsgleich (Abstand unter 0,01 mm). Das deutet auf
eine unvollstaendig vernaehte Vorder- oder Hinterkante ueber die gesamte
Spannweite hin, plus moeglicherweise eine doppelt vorhandene, leicht
versetzte Flaeche an einer Stelle. Die uebrigen 2 bis 4 offenen Kanten
liegen nahe den beiden Enden (x nahe -750 bzw. +750), passend zu den
Endplatten/Randbereichen eines Fluegelprofils.

Status: Bestaetigt. Kein Fehler in FOSAS, sondern eine echte Luecke im
Quellmodell, die automatische Reparatur nicht schliessen kann und auch
nicht schliessen sollte (Projektregel: keine erfundene Geometrie).

Massnahme: Keine, dies ist der erwartete, korrekte Ablehnungsfall.
Wichtig als Validierung: Der Geometrie-Import-Code (`fosas_core.geometry`)
verhaelt sich bei einer echten, "unordentlichen" Kundendatei genau wie
vorgesehen, mit einer nuetzlichen, lokalisierten Fehlermeldung statt eines
Absturzes oder einer stillen Fehlinterpretation.

## R12: Zweite reale Kundendatei (Fluegel, Autodesk Inventor), verjuengt

Beleg (eigener Test mit vom Projektinhaber bereitgestellter Datei
`Tragflaeche_Halbsymmetrisches_Profil.stp`, Autodesk Inventor 2024,
Einheit Millimeter): Anders als der Spoiler ist diese Datei ein gueltiger,
wasserdichter Solid-Koerper (nur 5 Flaechen, sauberes Modell), also ein
erfolgreicher Durchlauf durch `fosas_core.geometry.import_step` ohne
jede Reparatur. Querschnittsvergleich an drei Spannweitenpositionen zeigt
aber: Der Fluegel ist verjuengt (Sehnenlaenge sinkt von rund 100 mm an der
Wurzel auf rund 75 mm an der Spitze, Flaeche von 689 auf 466 mm²), also
kein Koerper mit konstantem Querschnitt im Sinne von ADR-0007.

Als Naeherung wurde ein einzelner Querschnitt (Mittelspann, Sehnenlaenge
87,5 mm) mit `fosas_core.geometry` extrahiert (`Shape.intersect(Plane)`)
und mit der bestehenden Technik (`generate_constant_section_geo`)
vernetzt, mit aus der echten Reynolds-Zahl berechneter Zellhoehe (Re=1,48e5
bei angenommenen 25 m/s, y+=1 entspricht 1,21e-5 m). Ergebnis: 99583
Knoten, 533640 Elemente, echte abgestufte Wandzellen mit Abstaenden von
rund 1,2e-5 bis 1,5e-5 m nahe der Oberflaeche, passend zum berechneten
Zielwert. Bestaetigt zusaetzlich zu R1/ADR-0007, dass die Technik auch
mit einer aus einem echten Autodesk-Inventor-Export stammenden Kontur
funktioniert, nicht nur mit selbst erzeugter Geometrie.

Status: Der Mittelspann-Querschnitt ist ausdruecklich eine Naeherung, die
Verjuengung wird dabei nicht abgebildet, das Ergebnis eines Loeserlaufs
auf diesem Netz waere kein Ergebnis fuer den echten, verjuengten Fluegel.
Echte Vernetzung eines verjuengten Koerpers (Loft zwischen mehreren
Querschnitten mit Grenzschicht) ist nicht implementiert, siehe
OPEN_QUESTIONS.md.

Massnahme: Keine akute, dieser Fall ist als Naeherung klar gekennzeichnet
und nicht fuer einen Loeserlauf verwendet worden. Echte Loft-Vernetzung
fuer verjuengte Koerper bleibt ein groesseres, eigenes Arbeitspaket fuer
eine spaetere Phase.

## R13: Falsch orientierte Geometrie fuehrte zu echtem Speicherueberlauf (behoben)

Beleg (echter Vorfall, eigene Webflaeche, dieselbe Datei wie R12): Der
Projektinhaber hat die reale Fluegel-Datei ueber die neue Weboberflaeche
hochgeladen, mit Standardeinstellungen (Geschwindigkeit 30 m/s,
Anstellwinkel 5 Grad). Die Datei hat die Spannweite tatsaechlich entlang
Z (rund 500 mm), nicht entlang Y wie von `fosas_core.pipeline.run_case`
angenommen (Y ist bei dieser Datei die Dickenrichtung, nur rund 10 mm).
Die bisherige Pruefung (`chord <= 0 or span <= 0`) hat das nicht erkannt,
da beide Werte positiv waren, nur die falsche physikalische Groesse
gemessen wurde. Die Pipeline hat daraufhin einen Querschnitt quer durch
die Dickenrichtung ueber die volle Laenge geschnitten, eine unsinnige,
sehr komplexe Kontur. Gmsh hat beim Versuch, das zu vernetzen, fast den
gesamten verfuegbaren Arbeitsspeicher (8 GB auf dem AWS-Server)
aufgebraucht, bis der Linux-OOM-Killer den Gmsh-Prozess beendet hat
(bestaetigt per `dmesg`, "Out of memory: Killed process ... (python)
... anon-rss:6651276kB").

Status: Behoben. `run_case` prueft jetzt zusaetzlich, ob die berechnete
Spannweite plausibel im Verhaeltnis zur Sehnenlaenge und Dicke steht
(Spannweite muss mindestens die halbe Sehnenlaenge betragen, Dicke darf
nicht mehr als doppelt so gross wie die Spannweite sein), und bricht bei
Verdacht auf falsche Achsenzuordnung sofort mit einer klaren Fehlermeldung
ab, bevor ueberhaupt vernetzt wird. Mit einem eigenen Regressionstest
abgesichert (`test_run_case_rejects_geometry_with_span_along_the_wrong_axis`,
absichtlich falsch orientierte Testgeometrie, reproduziert dieselbe
Verwechslung wie im echten Vorfall).

Wichtig zur Einordnung: Der Webserver selbst (FastAPI/Uvicorn) blieb
beim OOM-Vorfall unberuehrt und lief weiter, nur der einzelne
Gmsh-Kindprozess wurde beendet. Das Zugriffsproblem, das der
Projektinhaber danach hatte, war ein separates, unabhaengiges Problem
(abgebrochener SSH-Tunnel auf dem iPad), keine Folge des OOM-Vorfalls.

Massnahme: Die eigentliche Ursache (kein automatischer
Ausrichtungsschritt fuer beliebig orientierte STEP-Dateien) bleibt
bestehen, das ist ADR-mässig weiterhin genau die vom Projektinhaber in
der urspruenglichen Anforderung vorgesehene, aber noch nicht gebaute
"Ausrichtung per 3D-Vorschau bestaetigt" (Abschnitt 3 der
urspruenglichen Anforderungen). Bis dahin schuetzt die neue Pruefung nur
vor Ressourcenverschwendung und gibt eine verstaendliche Fehlermeldung,
loest das eigentliche UX-Problem aber nicht automatisch.

## R14: Kein Absturzschutz, Auftragsstatus an einen einzelnen Browser-Tab gebunden (in Arbeit)

Anlass: Der Projektinhaber hat nach dem Server-Neustart (siehe R13,
notwendig zur Fehlerbehebung) direkt zwei reale Probleme erlebt. Erstens
einen abgelaufenen Token nach dem Neustart (401 "Missing or invalid
bearer token"), weil die Engine bei jedem Start ein neues Zufallstoken
erzeugt (siehe ARCHITECTURE.md) und die offene Webseite noch das alte
Token im Speicher hatte. Zweitens die grundsaetzliche Frage, ob ein
Absturz waehrend der Rechnung den gesamten Fortschritt vernichtet, und ob
der Auftragsstatus von einem anderen Geraet aus einsehbar ist, ohne den
urspruenglichen Tab offen zu halten.

Status: In Arbeit, drei Teile vom Projektinhaber ausdruecklich alle drei
gleichzeitig beauftragt ("Alle drei jetzt umsetzen"):

1. Auftrags-ID landet in der Webadresse (`?job=<id>`), damit ein Link auch
   von einem anderen Geraet aus denselben Auftrag anzeigt.
2. Auftragsdaten werden auf die Festplatte geschrieben, nicht nur im
   Arbeitsspeicher der Engine gehalten, damit sie einen Engine-Neustart
   ueberleben.
3. Nach einem Absturz waehrend der Rechnung wird beim naechsten Versuch
   automatisch an SU2s eigener Zwischenspeicherung fortgesetzt, statt bei
   Iteration 0 neu zu beginnen.

Teil 3 ist in `fosas_core.pipeline.run_case` umgesetzt und durch
`test_run_case_resumes_instead_of_restarting_from_scratch` bestaetigt.
Dabei wurden zwei eigene, unabhaengige Fehler gefunden und behoben:

- ADR-0013: OUTPUT_FILES hat RESTART seit ADR-0010 stillschweigend
  deaktiviert, es gab bis dahin ueberhaupt keine Zwischenspeicherung.
- Der Test selbst war flakig: Der erste Testentwurf hat geprueft, ob
  sich der erste Restfehler (rms[P]) von Lauf 2 vom ersten Restfehler
  von Lauf 1 unterscheidet, in der Annahme, ein Kaltstart und ein
  fortgesetzter Lauf muessten sich sichtbar unterscheiden. Bei einer
  echten Testausfuehrung ist dieser Vergleich unerwartet fehlgeschlagen
  (2.1544 gegen 2.1581, unter der 1-Prozent-Toleranz). Ursache: Genau
  dieser Fall zeigt das aus R10 bekannte Restfehler-Plateau, das
  Restfehlerniveau liegt unabhaengig von Kalt- oder Warmstart in einem
  aehnlichen erhoehten Bereich (durch manuellen SU2-Nachlauf auf
  demselben Config bestaetigt: 2.4528 bei einem dritten, garantiert
  warmgestarteten Lauf, ebenfalls im selben Bereich). Der Restfehler ist
  fuer diesen Testfall also kein verlaessliches Kriterium fuer
  Kalt-/Warmstart. Ersetzt durch eine direkte Pruefung von SU2s eigener
  Log-Ausgabe ("Read flow solution from: <Pfad>."), die zweifelsfrei
  zeigt, ob die Restart-Datei tatsaechlich gelesen wurde, statt es aus
  Restfehlerwerten zu erschliessen. Dazu schreibt `run_su2` jetzt immer
  eine `su2.log`-Datei ins Ausgabeverzeichnis (Rohausgabe von SU2,
  bisher verworfen).

Teile 1 und 2 (Engine-Persistenz in `fosas_engine.jobs`, Wiederanmeldung
laufender Auftraege beim Engine-Start in `fosas_engine.app`, URL-Handling
in `clients/web/index.html`) sind zum Zeitpunkt dieses Eintrags noch nicht
umgesetzt.

Bekannte Grenze, bereits jetzt absehbar: Die Wiederaufnahme in
`run_case` prueft nur, ob `mesh.su2` beziehungsweise `restart_flow.dat`
bereits existieren, es gibt keine Pruefung, ob sie zu denselben Parametern
gehoeren wie der aktuelle Aufruf. Wird ein Auftrag mit demselben
Arbeitsverzeichnis, aber geaenderten Parametern (z. B. anderer
Anstellwinkel) erneut gestartet, wuerde faelschlich das alte Netz und der
alte Restart-Stand weiterverwendet. Fuer V1 unkritisch, da jeder Auftrag
ein eigenes, per Auftrags-ID benanntes Arbeitsverzeichnis bekommt und
Parameter pro Auftrag nicht nachtraeglich geaendert werden koennen, aber
in ARCHITECTURE.md/OPEN_QUESTIONS.md festzuhalten, falls das V1-Modell
(ein Auftrag, ein Arbeitsverzeichnis, unveraenderliche Parameter) je
aufgeweicht wird.

## R15: Manuell nachgedrehte reale Fluegeldatei fuehrt zu einem eigenen, reproduzierbaren Gmsh-Speicherueberlauf (behoben)

Beleg (echter Vorfall, eigene Webflaeche, Server-Log und `dmesg`
bestaetigt): Nach der R13-Behebung wurde dieselbe reale Fluegeldatei,
manuell um 90 Grad um die X-Achse gedreht (`wing_reoriented.step`, siehe
R12/R13), erneut ueber die Weboberflaeche hochgeladen, mit
Standardeinstellungen (30 m/s, 5 Grad, `span_layers=24`,
`n_profile_points=60`, `EULER_IMPLICIT`, 500 Iterationen). Die
Achsen-Pruefung aus R13 greift diesmal korrekt nicht (Geometrie besteht
die Plausibilitaetspruefung), die Pipeline geht in die Vernetzung.

Zwei unabhaengige Versuche sind dort jeweils mit Gmsh-Exitcode -9
abgestuerzt, beide Male mit denselben Warnungen ("Skipping curve with no
begin or end point", "No elements in curve 444444") kurz vor dem Absturz.
Per `dmesg` (mit `sudo`, da `dmesg` ohne Rechte auf diesem Server leer
blieb) fuer beide Versuche eindeutig als OOM-Kill bestaetigt (Prozesse
8876 und 10406, jeweils rund 6,5 GB RSS beim Kill, Server hat 7,6 GB
insgesamt, kein Swap). Der zweite Versuch wurde live beobachtet: Der
Speicherverbrauch von Gmsh wuchs ueber gut sieben Minuten kontinuierlich
und zuletzt schnell (von rund 2,2 GB auf ueber 6,5 GB in den letzten
anderthalb Minuten vor dem Kill), keine sofortige Explosion, aber klar
unbegrenztes Wachstum ohne Konvergenz zu einer fertigen Vernetzung.

Wichtig zur Einordnung: Das ist ein anderer Fehler als R13. R13 betraf
die Achsenzuordnung (falscher, viel zu grosser Querschnitt). Hier ist
die Achsenzuordnung korrekt, aber die aus dem gedrehten STEP-Modell
extrahierte Querschnittskontur enthaelt offenbar degenerierte oder
unzusammenhaengende Kurven (die "Skipping curve"-Warnungen deuten
darauf hin), was Gmsh vermutlich in eine pathologische, nicht
konvergierende Verfeinerung treibt statt sauber abzubrechen.

Status: Behoben, siehe ADR-0014. Die vermutete Ursache oben ("degenerierte
Kurven") war eine Fehlspur: Die tatsaechliche Ursache lag nicht in der
Kontur, sondern darin, dass `run_case` die aus der Geometrie gelesene
Sehnenlaenge (100, in Wirklichkeit Millimeter, siehe R12) ungeprueft als
100 Meter in alle physikalischen Formeln eingesetzt hat. Die dadurch um
Faktor 1000 ueberhoehte Reynolds-Zahl fuehrte zu einer relativ zur
(ebenfalls falsch skalierten) Rechengebietsgroesse extrem duennen
Grenzschicht-Zellhoehe, was Gmsh in eine explodierende Verfeinerung
getrieben hat. `run_case` rechnet jetzt alle aus der Geometrie gelesenen
Laengen konsequent von Millimeter auf Meter um. Mit der echten Datei
verifiziert: Sehnenlaenge kommt jetzt korrekt als 0,1 m zurueck (passt zu
R12), das Mesh braucht nur noch rund 230 MB (vorher unbegrenzt wachsend
bis zum OOM-Kill) und ist nach unter einer Minute fertig.

Die "Skipping curve"-Warnungen traten weiterhin nicht mehr auf, sobald
die Groessenverhaeltnisse realistisch waren, was die urspruengliche
"degenerierte Kontur"-Vermutung zusaetzlich entkraeftet: Sie war
vermutlich ein Symptom des extremen Groessenverhaeltnisses (numerische
Rundungsprobleme bei der Kurvendiskretisierung ueber viele
Groessenordnungen hinweg), nicht eine eigene, unabhaengige Ursache.

## R16: GUI-Feld "Profilpunkte" hatte keinerlei Wirkung (behoben)

Beleg: `fosas_core.pipeline._sample_wire_points` hatte die Anzahl
Stuetzpunkte pro Kante fest auf 40 verdrahtet, unabhaengig davon, was
`CaseParams.n_profile_points` sagte, das die Weboberflaeche als
"Profilpunkte" anzeigt und dem Nutzer zur Aenderung anbietet. Wer diesen
Wert in der Weboberflaeche geaendert hat, bekam also stillschweigend
immer dieselbe Aufloesung, unabhaengig vom eingegebenen Wert, das war
kein sichtbarer Fehler, sondern ein wirkungsloses Eingabefeld.

Status: Behoben, `n_profile_points` wird jetzt tatsaechlich durchgereicht.
Zusaetzlich eine Untergrenze (mindestens 3) in `CaseParams.__post_init__`
ergaenzt, damit ein zu kleiner Wert eine klare Fehlermeldung statt einen
kryptischen Fehler tiefer in der Vernetzung ausloest. Abgesichert durch
einen neuen, schnellen Regressionstest, der die Punktanzahl im erzeugten
Gmsh-Skript fuer zwei verschiedene Werte direkt vergleicht (ohne echten
Gmsh/SU2-Lauf), sowie durch die volle langsame Testsuite, um zu
bestaetigen, dass der neue Standardwert (60 statt der bisher faktisch
immer verwendeten 40 pro Kante) keine echten Laeufe destabilisiert.

## R17: Engine-Standard-Timeout (7200 s) ignoriert die angeforderte Iterationszahl, echter Abbruch bei 5000 Iterationen (behoben)

Beleg (echter Vorfall, eigene Webflaeche, AWS-Server): Der Projektinhaber
hat "just for fun" denselben realen Fluegel mit `max_iterations=5000`
gestartet. Nach genau 7200 Sekunden (2 Stunden) ist der Auftrag mit
`[solving] SU2 did not finish within 7200.0 seconds` fehlgeschlagen,
nach 2961 von 5000 Iterationen (Restfehler zu dem Zeitpunkt: -5,84,
weiter fallend, kein haengender Lauf).

Ursache: `fosas_engine.app._execute_job` hat `fosas_core.pipeline.run_case`
ohne `solve_timeout` aufgerufen, also immer dessen festen Vorgabewert
(7200 s) verwendet, unabhaengig von `params.max_iterations`. Bei der
beobachteten Rechengeschwindigkeit (rund 2 bis 3 s pro Iteration auf dem
AWS-Referenzserver) reicht das fuer gut 2500-3500 Iterationen, aber nicht
fuer 5000. Kein Datenverlust, da SU2 sein eigenes Zwischenergebnis
(`restart_flow.dat`, `history.csv`) bereits regelmaessig (`OUTPUT_WRT_FREQ`)
geschrieben hatte: Manuell mit hoeherem Timeout ueber `run_case` direkt
fortgesetzt (auf demselben Arbeitsverzeichnis, siehe R14-Mechanismus),
kein Neustart von vorne noetig.

Entscheidung: `_execute_job` berechnet den Timeout jetzt aus
`params.max_iterations` (10 Sekunden pro Iteration als bewusst
grosszuegige Obergrenze, deutlich ueber der beobachteten echten Rate,
mit 7200 s als Mindestwert fuer kleine Faelle). Das ist eine
Betriebsgrenze (wie lange gewartet wird, bevor ehrlich aufgegeben wird),
keine Annahme, die ein Rechenergebnis veraendert. Abgesichert durch
einen Test, der `run_case` abfaengt und prueft, dass der uebergebene
Timeout mit `max_iterations` skaliert statt am festen Standardwert zu
kleben.

Nachtrag: `POST /jobs/{id}/resume` (siehe ADR-0015-Fortsetzung weiter
unten) deckt das inzwischen auch ueber die API ab, nicht mehr nur
manuell wie in diesem Vorfall.

## R18: Realer F1-Heckfluegel hat keinen konstanten Querschnitt, Endplatten nicht abbildbar (offen, bewusst zurueckgestellt)

Beleg (echte, vom Projektinhaber hochgeladene Datei
`Heckfluegel.stp`): Geometrie liest sauber ein (wasserdicht, 1 Koerper,
36 Flaechen), besteht aber die Querschnitts-Plausibilitaetspruefung aus
R13 nicht (Dicke 308 mm > 2x Spannweite 150 mm). Direkte Untersuchung
mit mehreren Schnitten entlang der vermuteten Spannweitenachse zeigt:
An den Enden (±150 mm) ist der Querschnitt gross (~207x150 mm, sieht
nach Endplatte aus), in der Mitte klein (~40x35 bis 40x75 mm) und
wechselt dabei auch noch seine Position. Kein konstanter Querschnitt,
wie von ADR-0007 vorausgesetzt: Ein typischer F1-Heckfluegel-Aufbau aus
Hauptprofil, Flap und zwei grossen, aerodynamisch wichtigen Endplatten
(fuer die Kontrolle des Randwirbels), nicht ein einzelnes, extrudiertes
Profil.

Status: Bewusst nicht weiterverfolgt (Projektinhaber-Entscheidung): Eine
erzwungene Naeherung (Achsen passend drehen, einen beliebigen
Mittelschnitt nehmen) wuerde die Endplatten komplett ignorieren, also
ein im Kern anderes Bauteil berechnen, kein eingeschraenktes Ergebnis
fuer den echten Heckfluegel. Reiht sich ein in R11 (Spoiler, kein
Solid) und R12 (verjuengter Fluegel): Echte, mehrteilige oder verjuengte
Bauteile sprengen regelmaessig den V1-Rahmen (ein Koerper, ein
konstanter Querschnitt). Echte Unterstuetzung fuer mehrteilige/lofted
Geometrie bleibt ein eigener, grosser Ausbauschritt, siehe
OPEN_QUESTIONS.md.

## R19: Fortsetzen eines Auftrags kann ein Netz aus der Zeit vor einem Pipeline-Fix unveraendert weiterverwenden (bekannte Grenze, nicht behoben)

Beleg (bei der Selbstueberpruefung des R14/R17-Codes gefunden, nicht an
einem echten Vorfall): `fosas_core.pipeline.run_case` prueft nur, ob
`mesh.su2` im Arbeitsverzeichnis existiert, um zu entscheiden, ob neu
vernetzt werden muss (siehe R14). Wenn sich zwischen dem urspruenglichen,
gescheiterten Lauf und einem spaeteren `POST /jobs/{id}/resume` die
Berechnung von Sehnenlaenge/Spannweite/Profilpunkten selbst aendert (wie
es die R15-Korrektur, Millimeter-auf-Meter-Umrechnung, getan hat), wird
das alte, nach altem Massstab gebaute Netz unveraendert weiterverwendet,
waehrend `chord`/`span`/`mid_y` fuer die Referenzwerte und das
Stroemungsfeld mit der neuen, korrigierten Rechnung bestimmt werden. Die
Rechnung liefe durch, aber mit einem Einheiten-Missverhaeltnis zwischen
Netzgeometrie und Physik, also einem stillen, falschen Ergebnis statt
eines Fehlers.

Einordnung: Kein allgemeines Problem der Resume-Funktion selbst, sondern
ein grundsaetzliches Risiko jeder Aenderung an der Vernetzungs-/
Geometrielogik: Ein bereits vorhandenes `mesh.su2` kann nach einem
solchen Fix nicht mehr vertrauenswuerdig sein. Fuer den konkreten R15-Fix
nicht akut, da der einzige damals betroffene reale Auftrag
(`bb8db25c...`, R17) erst NACH dem R15-Fix erzeugt wurde, also keinen
Alt-Mesh-Fall hat.

Status: Nicht behoben, nur dokumentiert. Eine vollstaendige Loesung
(z. B. eine Versions- oder Pruefsumme der mesh-relevanten Pipeline-Logik
im `job_meta.json`, die bei Abweichung ein Neuvernetzen erzwingt) ist im
Verhaeltnis zur seltenen, schmalen Zeitfenster-Natur des Problems noch
nicht umgesetzt worden.
