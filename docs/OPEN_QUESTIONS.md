# Offene Punkte

## Technisch, vor der jeweiligen Phase zu klaeren

- trame wurde per Spike als grundsaetzlich geeignet bestaetigt (RISKS.md,
  R9), aber nur mit einem stark vereinfachten synthetischen Datensatz. Ein
  Lasttest mit echter Netzaufloesung inklusive Stromlinien/Schnittflaechen
  steht vor Phase 3 noch aus.
- Konkreter Schwellwert fuer den Ablösungsanteil in der erweiterten
  Qualitaetsampel (ADR-0005): noch nicht kalibriert, braucht
  Validierungsfaelle aus Phase 2.
- Genauer EULA-Wortlaut von MS-MPI und WebView2 (RISKS.md, R4): noch nicht
  aus den Installer-Paketen selbst gelesen.
- Gmsh-Grenzschichtvernetzung an einer duennen Hinterkante wurde an einem
  ersten realen NACA-0012-Testfall erfolgreich durchgefuehrt (RISKS.md,
  R1), aber noch nicht mit einem vollstaendigen SU2-Loeserlauf (y+-Kontrolle
  fehlt) und nicht mit anspruchsvolleren Geometrien (z. B. Fluegelspitze)
  wiederholt. SU2-Laufzeiten wurden noch nicht systematisch gemessen, nur
  ein einzelner Vernetzungslauf.

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
