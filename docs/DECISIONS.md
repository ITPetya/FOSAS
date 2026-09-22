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
(`Extrude {...} { Surface{s}; Layers{n}; }`), was automatisch Prismen
erzeugt. Erfolgreich getestet an einem NACA-0012-Testfall, siehe RISKS.md
R1.

Alternativen: `extrudeBoundaryLayer` per Python-API (verworfen fuer den
Moment, keine funktionierende Python-Umgebung verfuegbar). Isotropes Netz
ohne echte Grenzschicht (verworfen, macht y+ und wandnahe Werte unbrauchbar).

Konsequenzen: Dieser Ansatz ist auf Koerper mit (stueckweise) konstantem
Querschnitt beschraenkt, keine allgemeine Loesung fuer beliebige
STEP-Geometrie mit Verjuengung, Pfeilung oder Fluegelspitzen. Ausserdem
wurde er bisher nur mit einer direkt in Gmsh aufgebauten Profilkurve
getestet, nicht mit einer aus einer STEP-Datei importierten Kontur (siehe
OPEN_QUESTIONS.md). Fuer allgemeinere Geometrie bleibt der
`extrudeBoundaryLayer`-Weg oder eine Windows/x86_64-Umgebung mit
Python-Bindings notwendig zu klaeren.
