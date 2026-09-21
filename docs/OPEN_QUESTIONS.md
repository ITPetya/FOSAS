# Offene Punkte

## Technisch, vor der jeweiligen Phase zu klaeren

- trame versus Qt versus eigene vtk.js-Anwendung fuer die begehbare,
  zeitlich animierte Feldvisualisierung: Spike noch nicht durchgefuehrt
  (siehe RISKS.md, R9). Muss vor Phase 3 erledigt sein.
- Konkreter Schwellwert fuer den Ablösungsanteil in der erweiterten
  Qualitaetsampel (ADR-0005): noch nicht kalibriert, braucht
  Validierungsfaelle aus Phase 2.
- Genauer EULA-Wortlaut von MS-MPI und WebView2 (RISKS.md, R4): noch nicht
  aus den Installer-Paketen selbst gelesen.
- Reales Hands-on-Testergebnis fuer Gmsh-Grenzschichtvernetzung an einer
  duennen Hinterkante (RISKS.md, R1) und fuer SU2-Laufzeiten auf x86_64
  (RISKS.md, R5): beides nur aus Sekundaerquellen abgeleitet, noch nicht
  selbst gemessen.

## Fachlich/Nutzerseitig, noch nicht final entschieden

- Trennung von Qualitaetsstufen (Vorschau/Standard/fein) und der
  verpflichtenden Drei-Netz-GCI-Studie: Vorschlag, die GCI-Studie als
  separaten, einmaligen Validierungslauf pro Geometrie/Setup-Kombination
  zu behandeln statt bei jedem Einzellauf, wurde vom Projektinhaber noch
  nicht ausdruecklich bestaetigt.
- Variante C der Sim-Box-Funktion (eingebettete Rechnung mit uebertragenen
  Randbedingungen, siehe ADR-0004): als spaetere Ausbaustufe vorgemerkt,
  aber ohne konkreten Zeitpunkt.
- Welche Koerperklassen ausser dem NACA-0012-Validierungsfall zuerst mit
  konkreten Toleranzen hinterlegt werden (Zylinder als naechster Klassiker
  wurde vom Projektinhaber selbst genannt, aber nicht formal festgelegt).
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
