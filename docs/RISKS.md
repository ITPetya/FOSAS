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

## R15: Manuell nachgedrehte reale Fluegeldatei fuehrt zu einem eigenen, reproduzierbaren Gmsh-Speicherueberlauf (offen, Ursache ungeklaert)

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

Status: Nicht behoben, Ursache nicht im Detail untersucht (Vermutung
oben, nicht verifiziert). Naechste sinnvolle Schritte waeren, den
tatsaechlich aus `geometry.py`/`pipeline.py` extrahierten Querschnitt
(die `profile_points_xz`-Liste) direkt zu inspizieren, bevor er an Gmsh
geht, und/oder eine Obergrenze fuer Gmsh-Speicherverbrauch beziehungsweise
einen Prozess-Timeout mit klarer Fehlermeldung einzuziehen, statt den
Server erneut ungebremst in den OOM-Killer laufen zu lassen (aktuell
gibt es zwar `mesh_timeout`, der greift aber nur bei Zeitueberschreitung,
nicht bei Speicherueberschreitung). Noch nicht umgesetzt, da noch nicht
vom Projektinhaber beauftragt.
