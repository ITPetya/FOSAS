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

Massnahme: Vor einer erneuten Erfolgsmeldung zu diesem Risiko entweder (a)
den echten `extrudeBoundaryLayer`-Mechanismus per `.geo`-Skript
nachvollziehen (Syntax noch zu klaeren, moeglicherweise ueber die
`Extrude ... { Layers{...} }`-Konstruktion mit Grenzschicht-Modus, noch
nicht verifiziert), oder (b) eine funktionierende gmsh-Python-Umgebung auf
einer x86_64- oder Windows-Maschine nutzen, wo die offiziellen Python-Wheels
verfuegbar sind, und das offizielle Beispiel `naca_boundary_layer_3d.py`
direkt als Ausgangspunkt verwenden. Bis dahin gilt: jedes Meshing-Ergebnis
wird erst nach Pruefung der VOLLSTAENDIGEN Log-Ausgabe (nicht nur der
letzten Zeilen) auf das Wort "Error" hin als erfolgreich gewertet, das wird
als feste Vorgehensregel fuer alle weiteren Gmsh-Tests in diesem Projekt
uebernommen.

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
