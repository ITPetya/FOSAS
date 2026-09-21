# Risiken

Jeder Eintrag nennt Risiko, Quelle/Beleg, Status und geplante Massnahme.
Nichts hier ist schoengeredet, ein Risiko bleibt offen bis es durch einen
echten Test oder eine belastbare Quelle geschlossen wird.

## R1: Gmsh, kollabierende Grenzschichtzellen an scharfen Hinterkanten

Beleg: Mehrere unabhaengige Sekundaerquellen (Gmsh-Mailingliste 2016,
GitLab-Issue-Titel, ResearchGate-Diskussion) beschreiben uebereinstimmend,
dass das `BoundaryLayer`-Feld an scharfen Hinterkanten sich ueberschneidende
oder kollabierende Prismenschichten erzeugt. Verbreiteter Workaround: kleiner
Radius/Halbkreis an der Hinterkante statt idealer Schaerfe. Kein eigener Test
moeglich (siehe R5).

Status: Offen, ungeprueft mit eigenem Testfall.

Massnahme: In Phase 1 automatische Mindestradius-Anwendung an duennen
Kanten vorsehen, falls noetig. Jede solche automatische Korrektur wird im
Bericht offengelegt (Projektregel, keine stillen Fallbacks). Realer Test mit
NACA-0012-Geometrie ist Teil der Phase-1-Abnahme.

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

## R5: Eigene Testumgebung ist ARM64-Linux ohne Root

Beleg: Eigener Installationsversuch. `pip install gmsh` bietet kein
Linux-aarch64-Wheel. Der offizielle Gmsh-Bereich stellt nur Linux32/Linux64
(x86) bereit. `apt-get install gmsh` scheitert ohne Root. SU2-Installation
per conda-forge scheiterte am begrenzten Speicherplatz der Sandbox
(2 GB tmpfs).

Status: Bestaetigt, strukturelle Einschraenkung der aktuellen
Entwicklungsumgebung, kein Bug im Projekt selbst.

Massnahme: Hands-on-Tests von Gmsh-Vernetzung und SU2-Laeufen brauchen
entweder eine x86_64-Linux-Umgebung mit Root-Rechten und ausreichend
Speicherplatz, oder muessen auf einer Windows-Maschine erfolgen. Das ist
Voraussetzung fuer die Abnahme von Phase 1, nicht optional.

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

## R9: trame-Performance fuer begehbare Animation mit vielen Zustaenden ungeprueft

Beleg: Noch kein eigener Spike zu trame vs. Qt vs. eigener vtk.js-Anwendung
durchgefuehrt.

Status: Offen, siehe OPEN_QUESTIONS.md.

Massnahme: Spike vor Phase 3 nachholen.
