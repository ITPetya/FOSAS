const TOKEN = "__FOSAS_TOKEN__";

// Must match fosas_core.materials.MATERIAL_DENSITIES_KG_M3's keys and
// the <option> labels in index.html's material dropdowns.
const MATERIAL_LABELS = {
  aluminium: "Aluminium",
  stahl: "Stahl",
  titan: "Titan",
  cfk: "CFK (Kohlefaser-Verbund)",
  gfk: "GFK (Glasfaser-Verbund)",
  abs: "ABS (Kunststoff)",
  pla: "PLA (Kunststoff, 3D-Druck)",
  balsaholz: "Balsaholz",
};

// Explanatory text for the (i) info buttons. Written for someone with
// no aerodynamics/CFD background, per the user's explicit request to
// learn while using the tool. Each entry is tagged Gesichert (settled
// physics/definition) or Annahme (a typical range or rule of thumb, not
// a universal law) per the project's own labeling convention, see
// CLAUDE.md. No invented numbers: every figure here is a standard
// textbook value or an explicit rule of thumb already used elsewhere in
// this codebase (e.g. the default growth_ratio/target_y_plus values).
const INFO_TEXT = {
  step_file: `
    <span class="tag gesichert">Gesichert</span>
    <h4>STEP-Datei</h4>
    <p>Das 3D-Modell deines Bauteils im STEP-Format (Standardaustauschformat
    fuer CAD-Geometrie, von praktisch jeder CAD-Software exportierbar).</p>
    <p>FOSAS geht aktuell davon aus, dass X in Stroemungsrichtung zeigt,
    Y entlang der Spannweite und Z nach oben, und dass der Querschnitt
    ueber die Spannweite konstant bleibt (keine Verjuengung wird
    abgebildet, nur die Mitte des Bauteils zaehlt).</p>
  `,
  velocity: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Anstroemgeschwindigkeit</h4>
    <p>Wie schnell die Luft auf dein Bauteil trifft (relativ dazu, nicht
    die Geschwindigkeit ueber Grund). Bestimmt zusammen mit der Groesse
    des Bauteils und der Luftviskositaet, ob die Stroemung eher glatt
    (laminar) oder verwirbelt (turbulent) ist.</p>
    <p class="example">Beispiel: 30 m/s = 108 km/h, ungefaehr
    Autobahntempo. 86,9 m/s = 313 km/h, typische kleine Flugzeug-
    Reisegeschwindigkeit.</p>
  `,
  aoa_input: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Anstellwinkel (Angle of Attack)</h4>
    <p>Der Winkel zwischen der Sehnenlinie des Profils (gerade Linie von
    Vorder- zu Hinterkante) und der ankommenden Luftstroemung.</p>
    <p>Groesserer Anstellwinkel erzeugt normalerweise mehr Auftrieb, aber
    auch mehr Widerstand, bis zu einem Punkt (Stroemungsabriss/Stall),
    ab dem der Auftrieb einbricht. FOSAS erkennt einen Stall nicht
    automatisch, ein stationaerer Loeser wie dieser kann in der Naehe
    eines Stalls zusaetzlich schlechter konvergieren.</p>
    <p>Ein einzelner Wert ("5") startet eine einzelne Berechnung; mehrere
    kommagetrennte Werte ("0, 5, 10, 15") starten eine Polare - fuer
    jeden Wert einen eigenstaendigen, unabhaengigen Auftrag (siehe
    docs/DECISIONS.md ADR-0017), danach gemeinsam als cl/cd-ueber-
    Anstellwinkel-Kurve im Archiv dargestellt.</p>
  `,
  gci_check: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Netzqualitaet pruefen (GCI)</h4>
    <p>Rechnet zusaetzlich auf zwei groeberen Netzaufloesungen, um zu
    pruefen, ob die eigentliche (feine) Aufloesung tatsaechlich fein
    genug ist (Grid Convergence Index, GCI) - eine Verifikation des
    Werkzeugs selbst, keine zusaetzliche aerodynamische Information.
    Ohne diese Pruefung bleibt unklar, ob ein Ergebnis am Netz haengt
    oder an der Physik liegt.</p>
    <p>Dauert dafuer etwa dreimal so lange wie eine einzelne Berechnung.
    Nur fuer einen einzelnen Anstellwinkel verfuegbar (nicht kombinierbar
    mit einer Winkel-Liste). Ergebnis und Diagramm erscheinen im Archiv.</p>
  `,
  sideslip_deg: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Schiebewinkel (Sideslip Angle)</h4>
    <p>Der Winkel zwischen der Sehnenrichtung und der Anstroemung,
    diesmal nicht wie der Anstellwinkel in der Hoehen-Richtung (X-Z-Ebene)
    gemessen, sondern seitlich (X-Y-Ebene, Spannweitenrichtung) - die
    uebliche Situation bei Seitenwind oder schraeg anliegendem Wind.
    0 Grad heisst: Wind kommt genau von vorne (bzw. nur mit dem
    Anstellwinkel geneigt), kein Seitenanteil.</p>
    <p>Erzeugt eine Seitenkraft S (siehe Kraeftesystem unten), die bei
    0 Grad Schiebewinkel immer null ist.</p>
  `,
  refinement_ratio: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>Verfeinerungsverhaeltnis</h4>
    <p>Um welchen Faktor sich die Netzaufloesung zwischen den drei
    Stufen (fein/mittel/grob) unterscheidet. Hoehere Werte ergeben eine
    aussagekraeftigere GCI-Kennzahl, aber ein deutlich groesseres
    feinstes Netz.</p>
    <p>Ein zu hoher Wert kann bei wenig verfuegbarem Arbeitsspeicher zu
    einem Speicherueberlauf beim feinsten Netz fuehren (eigener Vorfall,
    siehe docs/OPEN_QUESTIONS.md): moderat bleiben (z. B. 1,2 bis 1,5),
    besonders bei grossen Ausgangsnetzen oder implizitem Zeitschema.</p>
  `,
  density: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Luftdichte</h4>
    <p>Masse der Luft pro Volumen. Mehr Dichte bedeutet mehr Kraft bei
    gleicher Geschwindigkeit (Auftrieb und Widerstand skalieren beide
    direkt mit der Dichte).</p>
    <p class="example">1,225 kg/m^3 ist der Standardwert auf Meereshoehe
    bei 15 Grad Celsius (Normatmosphaere ISA). Auf einem Berg oder bei
    hoher Temperatur ist die Luft duenner, der Wert also kleiner.</p>
  `,
  dynamic_viscosity: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Dynamische Viskositaet</h4>
    <p>Ein Mass fuer die innere Reibung der Luft, wie "zaeh" sie ist.
    Zusammen mit Geschwindigkeit, Dichte und der Baugroesse ergibt sich
    daraus die Reynolds-Zahl, die bestimmt, wie duenn die
    Grenzschicht (die duenne, abgebremste Luftschicht direkt an der
    Oberflaeche) ausfaellt.</p>
    <p class="example">1,81e-5 Pa*s ist der Standardwert fuer Luft bei
    15 Grad Celsius, aendert sich kaum mit normalen Wetterbedingungen.</p>
  `,
  temperature: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Temperatur</h4>
    <p>Wird fuer die Berechnung der Stroemung selbst gebraucht (Luft ist
    hier als leicht kompressibel modelliert). 288,15 K = 15 Grad Celsius,
    der Normwert der internationalen Standardatmosphaere auf Meereshoehe.</p>
  `,
  target_y_plus: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Ziel y+</h4>
    <p>Eine dimensionslose Kennzahl, wie weit der erste Netzpunkt von der
    Oberflaeche entfernt liegt, in "Wandeinheiten" statt in Metern
    gemessen. Das Turbulenzmodell, das FOSAS verwendet, braucht y+ nahe
    1, um die duenne Grenzschicht direkt an der Wand richtig aufzuloesen.</p>
    <p>FOSAS berechnet daraus automatisch, wie duenn die erste Netzzelle
    an der Oberflaeche sein muss (haeufig im Bereich weniger
    hundertstel Millimeter). Ein zu grosser Wert (grobe erste Zelle)
    macht die Reibungs-/Widerstandsberechnung ungenauer.</p>
  `,
  growth_ratio: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>Wachstumsrate Grenzschicht</h4>
    <p>Um wie viel jede weitere Netzschicht in der Grenzschicht dicker
    wird als die vorherige, ausgehend von der sehr duennen ersten Zelle
    (siehe Ziel y+). 1,2 bedeutet: jede Schicht ist 20% dicker als die
    davor.</p>
    <p>Ueblicher Bereich in der Praxis ist etwa 1,1 bis 1,3. Kleinere
    Werte ergeben ein feineres, aber groesseres (langsamer zu
    rechnendes) Netz.</p>
  `,
  bl_thickness_factor: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>Grenzschichtdicke</h4>
    <p>Wie dick der Bereich mit den fein abgestuften Grenzschicht-Zellen
    insgesamt ist, als Anteil der Sehnenlaenge (0,05 = 5% der
    Sehnenlaenge). Muss die reale, physikalische Grenzschichtdicke
    grosszuegig einschliessen, sonst fehlt aufgeloeste Netzaufloesung
    genau dort, wo die Reibung am staerksten wirkt.</p>
  `,
  span_layers: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Spannweiten-Schichten</h4>
    <p>In wie viele Abschnitte das Netz entlang der Spannweite (Y-Achse)
    unterteilt wird. Reine Netzaufloesung in diese eine Richtung, mehr
    Schichten aendern nicht die Form der Geometrie, nur wie fein sie in
    dieser Richtung vernetzt ist.</p>
  `,
  n_profile_points: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Profilpunkte</h4>
    <p>Wie viele Stuetzpunkte verwendet werden, um die gekruemmte
    Profilkontur (Ober- und Unterseite) im Netz nachzubilden. Mehr
    Punkte folgen einer stark gekruemmten Kontur (z. B. an einer
    runden Vorderkante) genauer, kosten aber mehr Rechenzeit beim
    Vernetzen.</p>
  `,
  max_iterations: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Maximale Iterationen</h4>
    <p>Wie viele Rechenschritte der Loeser maximal durchfuehrt. Die
    Loesung startet bei Iteration 0 weit von der Realitaet entfernt und
    naehert sich schrittweise an, jede Iteration bringt (im guten Fall)
    einen kleineren Restfehler, siehe Konvergenzziel. Mehr Iterationen
    bedeuten laengere Rechenzeit, aber nicht automatisch ein besseres
    Ergebnis, wenn die Rechnung bereits ein Plateau erreicht hat.</p>
  `,
  mpi_ranks: `
    <span class="tag gesichert">Gesichert</span>
    <h4>MPI-Prozesse</h4>
    <p>Wie viele Rechenprozesse parallel arbeiten (Parallelrechnen ueber
    MPI, einen Standard fuer verteiltes Rechnen). Mehr Prozesse koennen
    die Rechnung auf einer Maschine mit mehreren Kernen beschleunigen,
    mehr als die Anzahl der verfuegbaren Kerne bringt aber nichts.</p>
  `,
  time_discretization: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Zeitintegration</h4>
    <p><b>Implizit</b> ist normalerweise robuster und braucht weniger
    Iterationen bis zur Konvergenz, verbraucht dafuer mehr Arbeitsspeicher
    pro Iteration.</p>
    <p><b>Explizit</b> braucht weniger Speicher pro Iteration, dafuer
    typischerweise deutlich mehr Iterationen und kleinere, stabilitaets-
    begrenzte Schritte, um nicht numerisch zu divergieren.</p>
  `,
  residual_threshold: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Konvergenzziel (Restfehler)</h4>
    <p>Der Restfehler misst, wie sehr sich die Loesung von einer
    Iteration zur naechsten noch aendert (auf einer logarithmischen
    Skala, negativer heisst kleiner/besser). -8 bedeutet: die Aenderung
    ist auf ein Zehnmillionstel des Anfangswerts gefallen, ein ueblicher,
    aber strenger Zielwert.</p>
    <p>Faellt der Restfehler bis zum Ende der Iterationen nicht unter
    dieses Ziel, gilt der Lauf als nicht konvergiert, das Ergebnis kann
    dann noch ungenau oder falsch sein.</p>
  `,
  convergence: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Konvergenz</h4>
    <p>Zeigt an, ob der Restfehler das Konvergenzziel erreicht hat.
    "Nicht konvergiert" ist eine ehrliche Aussage ueber den
    tatsaechlichen Rechenzustand, kein Fehler der Software: Es bedeutet,
    die Zahlen unten (CL, CD, ...) sind eine Zwischenauswertung, kein
    belastbares Endergebnis.</p>
    <p>"Plateau" bedeutet: Der Restfehler faellt praktisch nicht mehr
    weiter, mehr Iterationen wuerden vermutlich nicht mehr viel aendern
    (siehe docs/RISKS.md R10 fuer einen bekannten, realen Fall davon).</p>
  `,
  cl: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>CL, Auftriebsbeiwert</h4>
    <p>Eine dimensionslose Zahl fuer den erzeugten Auftrieb, unabhaengig
    von der absoluten Groesse des Bauteils (Auftriebskraft geteilt durch
    Staudruck mal Bezugsflaeche). Diese Definition/Formel ist Gesichert,
    die folgenden Beispielwerte sind nur grobe, ungepruefte Richtwerte.</p>
    <p class="example">Richtwerte fuer einfache Fluegelprofile: um 0 bei
    0 Grad Anstellwinkel (symmetrisches Profil), oft 0,3 bis 0,6 im
    Reiseflug, bis etwa 1,5-2 kurz vor dem Stroemungsabriss.</p>
  `,
  cd: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>CD, Widerstandsbeiwert</h4>
    <p>Dimensionslose Zahl fuer den Luftwiderstand, analog zu CL
    (Widerstandskraft geteilt durch Staudruck mal Bezugsflaeche). Diese
    Definition/Formel ist Gesichert, die folgenden Beispielwerte sind
    nur grobe, ungepruefte Richtwerte.</p>
    <p class="example">Richtwerte: ein schlankes Fluegelprofil bei
    kleinem Anstellwinkel liegt oft bei 0,01 bis 0,05, ein stumpfer
    Koerper (z. B. eine Platte quer zur Stroemung) kann leicht ueber 1
    liegen.</p>
  `,
  reference_area: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Bezugsflaeche A</h4>
    <p>A = Sehnenlaenge * Spannweite (Grundrissflaeche), die bei
    Fluegelprofilen uebliche Bezugsgroesse fuer CL/CD. Jede Kraftformel
    F = c * q * A bezieht sich auf genau diese Flaeche.</p>
    <p>Fuer einen Koerper, bei dem eher die Stirnflaeche quer zur
    Stroemung die erwartete Bezugsgroesse waere (z. B. ein Fahrzeug oder
    ein quer angestroemter Zylinder), kann das von der Grundrissflaeche
    abweichen. Beim Zylinder-Testfall dieses Projekts stimmen beide
    Flaechen nur deshalb zahlenmaessig ueberein, weil dort Sehnenlaenge
    gleich Durchmesser ist, nicht allgemein. Aktuell automatisch aus der
    Bounding-Box der Geometrie abgeleitet, noch nicht frei waehlbar.</p>
  `,
  frontal_area: `
    <span class="tag annahme">Annahme/Naeherung</span>
    <h4>Stirnflaeche (Naeherung)</h4>
    <p>Projizierte Flaeche quer zur Stroemung, so wie klassische
    Widerstandsbeiwert-Literatur (Kugel, Platte, Pkw, ...) sie
    normalerweise verwendet - anders als die Bezugsflaeche oben
    (Grundrissflaeche), siehe deren Tooltip.</p>
    <p>Hier bewusst einfach genaehert als Spannweite * groesste
    Bauteildicke (aus der Bounding-Box), NICHT die exakte projizierte
    Silhouette der echten 3D-Form. Rotiert auch nicht mit dem
    Anstellwinkel (immer die Naeherung bei AoA=0). Fuer einen Zylinder
    ist das exakt, fuer ein gewoelbtes Profil oder ein Fahrzeug nur eine
    grobe Naeherung.</p>
  `,
  cl_frontal: `
    <span class="tag annahme">Annahme/Naeherung</span>
    <h4>cl, bezogen auf Stirnflaeche</h4>
    <p>Derselbe Auftrieb wie beim oben gezeigten cl, nur durch die
    Stirnflaeche (statt der Grundrissflaeche) geteilt: cl_Stirn = cl *
    Grundrissflaeche / Stirnflaeche. Die physikalische Kraft aendert
    sich dadurch nicht, nur die Kennzahl. Fehlt ("-"), wenn die
    Stirnflaeche nicht sinnvoll bestimmbar ist (z. B. bei einer extrem
    duennen Platte).</p>
  `,
  cd_frontal: `
    <span class="tag annahme">Annahme/Naeherung</span>
    <h4>cd, bezogen auf Stirnflaeche</h4>
    <p>Wie cl (Stirnflaeche), nur fuer den Widerstand: cd_Stirn = cd *
    Grundrissflaeche / Stirnflaeche. Das ist der Wert, der mit den
    klassischen Literaturwerten unten vergleichbar ist (die beziehen
    sich fast immer auf die Stirnflaeche), nicht das cd oben.</p>
  `,
  plausibility_reference: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Plausibilitaets-Referenzwerte</h4>
    <p>Bekannte cd-Werte fuer einfache Formen, bezogen auf die
    Stirnflaeche (siehe cd-Stirnflaeche oben, nicht das cd-Kachel ganz
    oben). Dient nur der groben Einordnung ("liegt mein Ergebnis in
    einer plausiblen Groessenordnung"), nicht dem exakten Vergleich:
    weder dieses Bauteil noch die Referenzformen sind identisch mit den
    Testbedingungen der jeweiligen Quelle.</p>
    <p>Die Kugel-Werte haengen stark von der Reynolds-Zahl ab ("Drag
    Crisis"), siehe die Reynolds-Zahl-Kachel oben fuer den Wert dieses
    Laufs.</p>
  `,
  dynamic_pressure: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Staudruck q</h4>
    <p>q = 0,5 * rho * v^2. Der Druck, der entsteht, wenn die
    Anstroemgeschwindigkeit vollstaendig in Druck umgesetzt wird (wie am
    Staupunkt, siehe cp-Verteilung). Alle Kraftbeiwerte (CL, CD, ...)
    sind eine Kraft geteilt durch q mal Bezugsflaeche, q ist also der
    gemeinsame Massstab, der die Kraft in eine dimensionslose Zahl
    umrechnet.</p>
  `,
  reynolds_number: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Reynolds-Zahl Re</h4>
    <p>Re = rho * v * Sehnenlaenge / Viskositaet. Dimensionslose Zahl, die
    das Verhaeltnis von Traegheitskraeften zu Reibungskraeften in der
    Stroemung beschreibt. Kleine Re (laminar, Reibung dominiert) ergeben
    ein anderes Stroemungsbild als grosse Re (turbulent, Traegheit
    dominiert), siehe docs/RISKS.md R10 zur Bedeutung fuer die
    Konvergenz dieses Loesers.</p>
    <p class="example">Richtwert: der Umschlag laminar/turbulent liegt
    bei einer glatten Platte grob im Bereich Re = 10^5 bis 10^6, je nach
    Stoerungsgrad der Anstroemung.</p>
  `,
  lift_force: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Auftrieb L</h4>
    <p>L = CL * q * A (Bezugsflaeche A = Sehnenlaenge * Spannweite, bei
    diesem konstanten Profil). Die tatsaechliche Kraft senkrecht zur
    Anstroemrichtung in Newton, nicht nur die dimensionslose Kennzahl
    CL. Rechnet man wie im zentralen Kraeftesystem der Technischen
    Mechanik gewohnt: Kraft = Beiwert mal Druck mal Flaeche.</p>
  `,
  drag_force: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Widerstand D</h4>
    <p>D = CD * q * A, analog zu Auftrieb L, aber parallel zur
    Anstroemrichtung (in deren Richtung wirkend, daher immer positiv fuer
    einen realen, nicht antreibenden Koerper).</p>
  `,
  side_force: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Seitenkraft S</h4>
    <p>S = CS * q * A, senkrecht zu Auftrieb UND Widerstand (die dritte
    Richtung im raeumlichen Kraeftesystem). Nur bei einem Schiebewinkel
    ungleich 0 Grad (Seitenwind) ungleich null; bei reiner Frontal-
    anstroemung ist S immer 0.</p>
  `,
  resultant_force: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Resultierende R</h4>
    <p>R = Wurzel(L^2 + D^2 + S^2), die geometrische Summe aus Auftrieb,
    Widerstand und Seitenkraft, dieselbe Vektoraddition wie bei jedem
    zentralen Kraeftesystem in der Technischen Mechanik (bei S=0 reduziert
    sich das auf die bekannte 2D-Form Wurzel(L^2+D^2)).</p>
  `,
  resultant_angle: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Winkel der Resultierenden</h4>
    <p>Winkel zwischen der Resultierenden R und der Anstroemrichtung
    (= Widerstandsrichtung), berechnet per atan2(Wurzel(L^2+S^2), D). 0
    Grad hiesse: die gesamte Kraft zeigt genau in Widerstandsrichtung,
    weder Auftrieb noch Seitenkraft. 90 Grad hiesse: kein Widerstandsanteil.
    Dieser Winkel allein sagt nicht, in welche Richtung (Auftrieb oder
    Seite oder eine Mischung) die Kraft neben dem Widerstand zeigt, nur
    wie weit sie insgesamt von der reinen Widerstandsrichtung abweicht -
    dafuer L und S selbst ansehen, die ihr Vorzeichen jeweils einzeln
    behalten.</p>
  `,
  glide_ratio: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Gleitzahl L/D</h4>
    <p>Verhaeltnis von Auftrieb zu Widerstand, identisch zum Verhaeltnis
    CL/CD (die Bezugsgroessen q und A kuerzen sich heraus). Ohne
    Einheit; "-" wird angezeigt, wenn der Widerstand exakt null ist
    (Gleitzahl dann nicht definiert, kommt bei einer echten Rechnung
    praktisch nie vor).</p>
    <p class="example">Richtwert: ein gutes Segelflugzeugprofil erreicht
    Gleitzahlen über 30, ein stumpfer Koerper liegt oft deutlich unter
    5.</p>
  `,
  moment_mx: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Moment Mx</h4>
    <p>Mx = cmx * q * A * Bezugslaenge. Moment um die X-Achse (Stroemungsrichtung).
    Fuer einen Koerper mit konstantem Querschnitt entlang der Spannweite
    (Y-Achse, siehe Koordinatenkonvention) ist dieses Moment physikalisch
    meist klein bis vernachlässigbar; ein von null abweichender Wert kommt
    bei diesem Geometrietyp haeufig vor allem aus der Netzaufloesung, nicht
    aus einer realen Kraftwirkung.</p>
  `,
  moment_my: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Moment My (Nickmoment)</h4>
    <p>My = cmy * q * A * Bezugslaenge. Moment um die Y-Achse
    (Spannweitenrichtung). Fuer ein Fluegelprofil ist das das klassische
    Nickmoment (dreht die Nase rauf/runter), die aussagekraeftigste der
    drei Momentenkomponenten bei diesem Geometrietyp.</p>
  `,
  moment_mz: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Moment Mz</h4>
    <p>Mz = cmz * q * A * Bezugslaenge. Moment um die Z-Achse (vertikal).
    Wie Mx: bei einem Koerper mit konstantem Querschnitt entlang der
    Spannweite physikalisch meist klein, ein von null abweichender Wert
    ist hier oft Netzaufloesungs-Rauschen, keine reale Kraftwirkung.</p>
  `,
  center_of_mass: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Geometrischer Schwerpunkt</h4>
    <p>Der Volumenschwerpunkt der STEP-Geometrie, direkt aus der
    Geometrie berechnet (nicht manuell eingegeben) - so vom
    Projektinhaber entschieden, falls/wenn eine Schwerpunktanzeige
    kommt.</p>
    <p><span class="tag annahme">Annahme</span> Nimmt ueberall gleiche
    (homogene) Dichte an - eine gleichmaessige Dichte kuerzt sich aus
    der Schwerpunktformel heraus, aendert sich also NICHT durch die
    Material-Auswahl unten. Bei einem Bauteil mit ungleichmaessiger
    Materialverteilung (z. B. eingebauten Komponenten aus anderem
    Material) ist das NICHT der tatsaechliche Massenschwerpunkt. Dieser
    Punkt ist nicht dasselbe wie der Momenten-Bezugspunkt oben (der
    bleibt die feste Sehnen-/Spannweitenmitte, unabhaengig von der
    Massenverteilung).</p>
    <p>Fuer Lagerreaktionen fehlt FOSAS weiterhin ein Lager-/
    Befestigungspunkt (geplant: Anklicken im 3D-Viewer, noch nicht
    umgesetzt) - nicht Teil dieser Anzeige.</p>
  `,
  material: `
    <span class="tag annahme">Annahme (Richtwert)</span>
    <h4>Material</h4>
    <p>Optionale Auswahl fuer eine Gewichtskraftabschaetzung: FOSAS
    multipliziert das Bauteilvolumen (aus der STEP-Geometrie) mit einer
    typischen Dichte fuer das gewaehlte Material (siehe
    fosas_core.materials fuer die Werte und Quellen). Keine Auswahl
    (Standard) heisst: kein Material, keine Masse/Gewichtskraft
    berechnet.</p>
    <p>Die Dichtewerte sind Richtwerte fuer eine typische Legierung/
    Zusammensetzung, nicht fuer die exakte Materialcharge des eigenen
    Bauteils (z. B. "Aluminium" deckt viele verschiedene Legierungen
    mit leicht unterschiedlicher Dichte ab). FOSAS geht ausserdem von
    einem durchgehend homogenen Material aus (kein Hohlraum, keine
    eingebauten Teile aus anderem Material).</p>
  `,
  volume: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Volumen</h4>
    <p>Das Volumen der STEP-Geometrie, direkt aus der Geometrie berechnet
    (keine Annahme, reine Geometrie). Grundlage fuer die
    Massenabschaetzung unten, wird aber immer angezeigt, auch ohne
    Material-Auswahl.</p>
  `,
  mass: `
    <span class="tag annahme">Annahme (aus Materialauswahl)</span>
    <h4>Masse</h4>
    <p>Masse = Volumen * Dichte des gewaehlten Materials. Nur berechnet,
    wenn oben ein Material ausgewaehlt ist, sonst "-" (keine stille
    Null). Erbt die Annahmen von Volumen (reine Geometrie, Gesichert)
    und Material (Dichte-Richtwert, Annahme).</p>
  `,
  weight: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Gewichtskraft G</h4>
    <p>G = Masse * g (Standardschwerebeschleunigung g = 9,80665 m/s^2,
    SI-Definition). Wirkt senkrecht nach unten (-Z) am geometrischen
    Schwerpunkt oben, unabhaengig vom Anstell-/Schiebewinkel (anders als
    die aerodynamischen Kraefte L/D/S, die sich mit der Anstroemung
    mitdrehen). Nur berechnet, wenn ein Material ausgewaehlt ist (die
    Formel selbst ist Gesichert, die zugrunde liegende Masse erbt aber
    die Annahme aus der Materialauswahl).</p>
  `,
  calculation_steps: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Rechenweg</h4>
    <p>Dieselben Formeln, die die Kacheln oben bereits anwenden, hier
    noch einmal einzeln mit den tatsaechlichen Zahlen dieser Rechnung
    aufgeschrieben: Kraft = Beiwert * Staudruck * Flaeche, Moment =
    Momentenbeiwert * Staudruck * Flaeche * Bezugslaenge. Staudruck q,
    Bezugsflaeche A und Bezugslaenge l sind dieselben Werte wie in den
    Kacheln oben, hier nur wiederverwendet statt neu berechnet.</p>
  `,
  wall_shear_stress: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Wandschubspannung tau</h4>
    <p>Die Reibkraft pro Flaeche, die die Stroemung direkt an der
    Oberflaeche ausuebt (tau = cf * q, cf ist der von SU2 berechnete
    Reibungsbeiwert pro Oberflaechenpunkt). Das ist die Groesse, aus der
    sich letztlich der Reibungsanteil des Widerstands ergibt.</p>
    <p>Mittelwert und Maximum ueber alle Oberflaechenpunkte dieses
    Laufs; eine ortsaufgeloeste Darstellung auf der 3D-Oberflaeche
    selbst gibt es noch nicht, nur diese zusammenfassenden Werte. Die
    Aufteilung des Gesamtwiderstands in einen Druck- und einen
    Reibungsanteil (siehe Druckwiderstand D_p / Reibungswiderstand D_f
    weiter unten) kommt dagegen nicht aus dieser punktweisen
    Wandschubspannung, sondern direkt aus SU2s eigenem
    "forces_breakdown.dat"-Bericht.</p>
  `,
  drag_pressure: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Druckwiderstand D_p</h4>
    <p>Der Anteil des Widerstands D, der aus dem Druckunterschied
    zwischen Vorder- und Rueckseite des Koerpers entsteht (bei einem
    stumpfen Koerper meist der groessere Anteil). D_p = cd_Druck * q * A,
    aus SU2s eigenem "forces_breakdown.dat"-Bericht (nicht aus der
    Iterationshistorie ableitbar, die hat keine getrennten
    Druck-/Reibungs-Spalten). D_p + D_f = D (Pruefung gegen den
    unabhaengig gelesenen Gesamtwiderstand, nicht blind uebernommen).</p>
  `,
  drag_friction: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Reibungswiderstand D_f</h4>
    <p>Der Anteil des Widerstands D, der aus der Wandschubspannung
    (Reibung der Stroemung an der Oberflaeche) entsteht, dieselbe
    Groesse wie die Wandschubspannung oben, hier aber ueber die ganze
    Oberflaeche zu einer einzigen Kraft aufintegriert. D_f = cd_Reibung
    * q * A, Quelle wie bei Druckwiderstand D_p.</p>
  `,
  mean_y_plus: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Mittleres y+</h4>
    <p>Der tatsaechlich in der fertigen Rechnung erreichte y+-Wert
    (siehe Ziel y+ bei der Eingabe), gemittelt ueber die ganze
    Oberflaeche. Liegt er deutlich ueber dem Zielwert, war die erste
    Netzzelle an manchen Stellen groeber als beabsichtigt.</p>
  `,
  viewer_layer_coord: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Koerper- und Windachsen</h4>
    <p>Koerperachsen (X rot = stromab, Y gruen = Spannweite, Z blau =
    vertikal, siehe docs/ARCHITECTURE.md) sind fest mit dem Bauteil
    verbunden. Die weisse Windachse zeigt die tatsaechliche
    Anstroemrichtung; der Bogen dazwischen ist der Anstellwinkel alpha.
    Positives alpha dreht die Anstroemrichtung von der X-Achse zur
    Z-Achse (siehe aoa_to_velocity_components in fosas_core.pipeline).</p>
    <p><span class="tag annahme">Annahme</span> Ein Schiebewinkel beta
    (seitliche Anstroemung) wird von FOSAS aktuell nicht modelliert
    (nur Drehung in der X-Z-Ebene), daher gibt es dafuer noch keinen
    Winkelbogen.</p>
  `,
  viewer_layer_forces: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Kraftpfeile</h4>
    <p>D (orange) entlang der Windachse, L (blau) senkrecht dazu, R
    (weiss) als deren Vektorsumme. Richtung und Laenge sind
    massstabsgetreu zueinander (laengster Pfeil = der jeweils groesste
    der drei Werte), aber NICHT massstabsgetreu zur Bauteilgroesse
    selbst, sonst waeren die Pfeile bei kleinen Kraeften unsichtbar.</p>
    <p><span class="tag annahme">Annahme/Vereinfachung</span> Die Pfeile
    setzen am Momenten-Bezugspunkt an (siehe Momente oben), nicht am
    tatsaechlichen Druckpunkt; eine eigene Druckpunkt-Markierung gibt es
    noch nicht. Die Zahlenwerte stehen in der Legende unter der
    3D-Ansicht, nicht direkt am Pfeil.</p>
  `,
  free_body_diagram: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Freikoerperbild</h4>
    <p>Dieselbe Darstellung wie im Freikoerperbild der Technischen
    Mechanik: der Koerper-Querschnitt (Sehnenschnitt, X nach rechts, Z
    nach oben) mit den eingezeichneten Luftkraeften D, L und R. Die
    Pfeile setzen am Momenten-Bezugspunkt an und sind zueinander
    massstabsgetreu (nicht zum Koerper), genau wie die entsprechende
    Ebene in der 3D-Ansicht oben, hier nur als reine 2D-Seitenansicht
    ohne Drehen/Zoomen.</p>
    <p><span class="tag annahme">Noch nicht umgesetzt</span> Gewichtskraft
    und ein Befestigungspunkt mit berechneten Lagerreaktionen (die
    "optionalen" Teile dieser Anforderung) fehlen noch: dafuer wird eine
    Masse/Schwerpunktlage und eine Lagerposition benoetigt, die FOSAS
    aktuell nicht erfasst. Dieses Bild zeigt bisher ausschliesslich die
    Luftkraefte.</p>
  `,
  viewer3d: `
    <span class="tag gesichert">Gesichert</span>
    <h4>3D-Ansicht</h4>
    <p>Zeigt jeden berechneten Punkt auf der Bauteiloberflaeche an seiner
    echten 3D-Position, eingefaerbt nach seinem cp-Wert (siehe
    cp-Verteilung). Es ist eine Punktwolke aus echten Netzknoten, keine
    geglaettete, gerenderte Flaeche, und zeigt nur die Oberflaeche, keine
    Stroemung in der umgebenden Luft (Stromlinien o. ae. werden aktuell
    nicht berechnet/angezeigt).</p>
  `,
  cp_chart: `
    <span class="tag gesichert">Gesichert</span>
    <h4>cp, Druckbeiwert</h4>
    <p>Eine dimensionslose Kennzahl fuer den lokalen Druckunterschied
    zur ungestoerten Anstroemung. cp = 1 an einem Staupunkt (Luft kommt
    dort vollstaendig zum Stillstand, meist an der Vorderkante),
    negatives cp bedeutet Unterdruck (Sog), typisch auf der Oberseite
    eines auftriebserzeugenden Profils.</p>
    <p>Die cp-Achse im Diagramm ist bewusst umgedreht (Sog zeigt nach
    oben), das ist Konvention in der Aerodynamik, nicht Zufall.</p>
  `,
};

function setupInfoButtons() {
  document.querySelectorAll("[data-info]").forEach((el) => {
    const key = el.getAttribute("data-info");
    if (!INFO_TEXT[key] || el.querySelector(".info-btn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "info-btn";
    btn.textContent = "i";
    btn.setAttribute("aria-label", "Erklaerung anzeigen");
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleInfoPopover(btn, key);
    });
    el.appendChild(btn);
  });
}

let currentInfoPopover = null;
let currentInfoAnchor = null;

function closeInfoPopover() {
  if (currentInfoPopover) currentInfoPopover.remove();
  currentInfoPopover = null;
  currentInfoAnchor = null;
}

function toggleInfoPopover(anchorEl, key) {
  if (currentInfoAnchor === anchorEl) { closeInfoPopover(); return; }
  closeInfoPopover();
  const pop = document.createElement("div");
  pop.className = "info-popover";
  pop.innerHTML = INFO_TEXT[key]; // authored content, not user input
  document.body.appendChild(pop);
  const rect = anchorEl.getBoundingClientRect();
  const top = window.scrollY + rect.bottom + 6;
  let left = window.scrollX + rect.left;
  const maxLeft = window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 12;
  left = Math.max(8, Math.min(left, maxLeft));
  pop.style.top = top + "px";
  pop.style.left = left + "px";
  currentInfoPopover = pop;
  currentInfoAnchor = anchorEl;
  setTimeout(() => document.addEventListener("click", onOutsideInfoClick), 0);
}

function onOutsideInfoClick(e) {
  if (currentInfoPopover && !currentInfoPopover.contains(e.target) && e.target !== currentInfoAnchor) {
    closeInfoPopover();
    document.removeEventListener("click", onOutsideInfoClick);
  }
}

setupInfoButtons();

function authHeaders() {
  return { "Authorization": "Bearer " + TOKEN };
}

// The "Erweiterte Einstellungen" field set, shared by all three request
// kinds (single job, polar study, GCI study) FOSAS can send - one
// unified form now covers all three (see docs/ARCHITECTURE.md
// "virtueller Windkanal, nicht drei Tools"), so there is only ever one
// copy of these fields, no id-prefix juggling needed any more.
function advancedParamFieldNames() {
  return [
    "density", "dynamic_viscosity", "temperature", "target_y_plus",
    "growth_ratio", "bl_thickness_factor", "span_layers", "n_profile_points",
    "max_iterations", "mpi_ranks", "time_discretization", "residual_threshold",
    "material",
  ];
}

function appendAdvancedParams(form) {
  for (const name of advancedParamFieldNames()) {
    form.append(name, document.getElementById(name).value);
  }
}

function setFormError(elId, msg) {
  const el = document.getElementById(elId);
  if (msg) { el.textContent = msg; el.hidden = false; } else { el.hidden = true; el.textContent = ""; }
}

function setError(msg) {
  setFormError("error", msg);
}

function drawCpChart(surface) {
  const svg = document.getElementById("cp-chart");
  svg.innerHTML = "";
  if (!surface || surface.length === 0) return;

  const xs = surface.map(p => p.x);
  const cps = surface.map(p => p.cp);
  const xMin = arrayMin(xs), xMax = arrayMax(xs);
  const cpMin = arrayMin(cps), cpMax = arrayMax(cps);
  const padX = 40, padY = 20, W = 600, H = 320;

  function sx(x) { return padX + (x - xMin) / (xMax - xMin || 1) * (W - 2 * padX); }
  // cp axis inverted (more negative cp plotted upward), standard airfoil convention
  function sy(cp) { return padY + (cp - cpMax) / (cpMin - cpMax || 1) * (H - 2 * padY); }

  const ns = "http://www.w3.org/2000/svg";
  const zeroLine = document.createElementNS(ns, "line");
  const y0 = sy(0);
  zeroLine.setAttribute("x1", padX); zeroLine.setAttribute("x2", W - padX);
  zeroLine.setAttribute("y1", y0); zeroLine.setAttribute("y2", y0);
  zeroLine.setAttribute("stroke", "#2a2f3a");
  svg.appendChild(zeroLine);

  for (const p of surface) {
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("cx", sx(p.x));
    c.setAttribute("cy", sy(p.cp));
    c.setAttribute("r", 2.2);
    c.setAttribute("fill", p.z >= 0 ? "#4f8cff" : "#e0a72f");
    c.setAttribute("opacity", "0.85");
    svg.appendChild(c);
  }

  const label = document.createElementNS(ns, "text");
  label.setAttribute("x", padX);
  label.setAttribute("y", H - 4);
  label.setAttribute("fill", "#9aa3af");
  label.setAttribute("font-size", "11");
  label.textContent = "x (Sehnenrichtung)  |  cp-Achse invertiert (Sog nach oben)";
  svg.appendChild(label);
}

// Classic 2D free-body diagram (technical-mechanics "Freikoerperbild"):
// the body's own cross-section (every surface point projected onto the
// X-Z plane; since the body has a constant cross-section along the
// span, see ADR-0007, every point collapses onto the same outline, no
// need to filter by y first) plus the D/L/R force arrows, same
// direction/scaling logic as the 3D "Kraftpfeile" layer but drawn with
// a single uniform scale on both axes so the (physically perpendicular)
// angle between D and L is not visually distorted.
function drawFreeBodyDiagram(result) {
  const svg = document.getElementById("fbd-chart");
  svg.innerHTML = "";
  const surface = result.surface;
  if (!surface || surface.length === 0) return;

  const xs = surface.map((p) => p.x);
  const zs = surface.map((p) => p.z);
  const xMin = arrayMin(xs), xMax = arrayMax(xs);
  const zMin = arrayMin(zs), zMax = arrayMax(zs);
  const padX = 50, padY = 30, W = 600, H = 320;
  const spanX = (xMax - xMin) || 1, spanZ = (zMax - zMin) || 1;
  const scale = Math.min((W - 2 * padX) / spanX, (H - 2 * padY) / spanZ);
  const centerX = (xMin + xMax) / 2, centerZ = (zMin + zMax) / 2;

  function sx(x) { return W / 2 + (x - centerX) * scale; }
  function sy(z) { return H / 2 - (z - centerZ) * scale; } // SVG y grows downward, flip

  const ns = "http://www.w3.org/2000/svg";
  for (const p of surface) {
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("cx", sx(p.x));
    c.setAttribute("cy", sy(p.z));
    c.setAttribute("r", 1.6);
    c.setAttribute("fill", "#9aa3af");
    c.setAttribute("opacity", "0.6");
    svg.appendChild(c);
  }

  const originX = result.moments.moment_origin[0], originZ = result.moments.moment_origin[2];
  const originPx = { x: sx(originX), y: sy(originZ) };

  const originDot = document.createElementNS(ns, "circle");
  originDot.setAttribute("cx", originPx.x);
  originDot.setAttribute("cy", originPx.y);
  originDot.setAttribute("r", 3.5);
  originDot.setAttribute("fill", "#eeeeee");
  svg.appendChild(originDot);

  const aoaRad = (result.aoa_deg * Math.PI) / 180;
  const dragDir = { x: Math.cos(aoaRad), z: Math.sin(aoaRad) };
  const liftDir = { x: -Math.sin(aoaRad), z: Math.cos(aoaRad) };
  const lift = result.forces.lift, drag = result.forces.drag, resultant = result.forces.resultant;
  const weight = result.weight; // null when no material was selected
  // Weight is folded into the same scale as D/L/R (see buildForcesLayer
  // for the same reasoning in 3D): a real part's weight and its
  // aerodynamic forces at a modest test velocity can differ by orders
  // of magnitude, and showing that honestly beats a second, silently
  // incomparable scale.
  const maxMag = Math.max(Math.abs(lift), Math.abs(drag), resultant, Math.abs(weight || 0), 1e-12);
  // Fixed pixel length for the largest force arrow, independent of the
  // drawing's own px-per-metre scale: a force arrow is a separate,
  // schematic quantity, not something drawn to the same physical scale
  // as the body outline (see INFO_TEXT.free_body_diagram).
  const maxArrowPx = Math.min(W, H) * 0.3;

  function drawArrow(dirBody, signedMag, color, label, origin) {
    origin = origin || originPx;
    const mag = Math.abs(signedMag);
    if (mag < 1e-12) return;
    const sign = signedMag < 0 ? -1 : 1;
    const lengthPx = (mag / maxMag) * maxArrowPx;
    const dx = dirBody.x * sign, dz = dirBody.z * sign;
    const normLen = Math.hypot(dx, dz) || 1;
    // Flip z for pixels (same sy() convention: +z body is "up", up is
    // smaller SVG y).
    const endX = origin.x + (dx / normLen) * lengthPx;
    const endY = origin.y - (dz / normLen) * lengthPx;

    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", origin.x); line.setAttribute("y1", origin.y);
    line.setAttribute("x2", endX); line.setAttribute("y2", endY);
    line.setAttribute("stroke", color);
    line.setAttribute("stroke-width", "2.2");
    svg.appendChild(line);

    // Simple arrowhead: two short lines back from the tip.
    const angle = Math.atan2(endY - originPx.y, endX - originPx.x);
    const headLen = 9;
    for (const headAngleOffset of [2.5, -2.5]) {
      const ha = angle + headAngleOffset;
      const headLine = document.createElementNS(ns, "line");
      headLine.setAttribute("x1", endX); headLine.setAttribute("y1", endY);
      headLine.setAttribute("x2", endX - headLen * Math.cos(ha));
      headLine.setAttribute("y2", endY - headLen * Math.sin(ha));
      headLine.setAttribute("stroke", color);
      headLine.setAttribute("stroke-width", "2.2");
      svg.appendChild(headLine);
    }

    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", endX + 4);
    text.setAttribute("y", endY);
    text.setAttribute("fill", color);
    text.setAttribute("font-size", "11");
    text.textContent = label;
    svg.appendChild(text);
  }

  const side = result.forces.side;
  // This diagram is a pure X-Z-plane (body-axis chord/vertical) view: a
  // side force (Y-axis, perpendicular to this plane) cannot be drawn
  // here at all. Per CLAUDE.md's "no silent fallbacks" rule, do not draw
  // the full 3D resultant's magnitude in a 2D arrow that physically only
  // spans D and L - use the in-plane resultant for the arrow itself and
  // say so explicitly in the legend whenever a side force is present.
  const resultantInPlane = Math.hypot(lift, drag);
  drawArrow(dragDir, drag, "#e0a72f", "D = " + drag.toPrecision(3) + " N");
  drawArrow(liftDir, lift, "#4f8cff", "L = " + lift.toPrecision(3) + " N");
  const resVec = { x: dragDir.x * drag + liftDir.x * lift, z: dragDir.z * drag + liftDir.z * lift };
  drawArrow(resVec, resultantInPlane, "#eeeeee", "R(D,L) = " + resultantInPlane.toPrecision(3) + " N");

  if (weight != null) {
    // Gravity IS representable in this X-Z-plane view (unlike the side
    // force below), it acts straight down at the center of mass, not
    // at the moment reference point.
    const comX = result.center_of_mass[0], comZ = result.center_of_mass[2];
    const comPx = { x: sx(comX), y: sy(comZ) };
    const comDot = document.createElementNS(ns, "circle");
    comDot.setAttribute("cx", comPx.x);
    comDot.setAttribute("cy", comPx.y);
    comDot.setAttribute("r", 3.5);
    comDot.setAttribute("fill", "#33cc33");
    svg.appendChild(comDot);
    drawArrow({ x: 0, z: -1 }, weight, "#996633", "G = " + weight.toPrecision(3) + " N", comPx);
  }

  let legend =
    "Grauer Punkt: Momenten-Bezugspunkt (Pfeile setzen dort an, nicht am tatsaechlichen Druckpunkt). " +
    "Pfeillaenge nur relativ zueinander massstabsgetreu, nicht zur Koerpergroesse." +
    (weight == null ? "" : " Gruener Punkt: geometrischer Schwerpunkt (Gewichtskraft G setzt dort an).");
  if (Math.abs(side) > 1e-9) {
    legend +=
      " Achtung: Dieses Bild zeigt nur die X-Z-Ebene (Sehne/Hochachse). Die Seitenkraft S = " +
      side.toPrecision(3) + " N (Querrichtung, aus dem Schiebewinkel) liegt senkrecht zu dieser " +
      "Ebene und ist hier nicht darstellbar - der gezeichnete Pfeil 'R(D,L)' ist deshalb NICHT " +
      "der volle 3D-Resultierende (das ist die Kachel 'Resultierende R' oben, " +
      result.forces.resultant.toPrecision(3) + " N).";
  }
  document.getElementById("fbd-legend").textContent = legend;
}

// Generic small line-chart-in-SVG helper, used for the Polaren-/GCI-
// Studien result charts (cl/cd vs AoA, cl/cd vs Elementanzahl). Deliberately
// not merged with drawCpChart above (different axis conventions, a
// combination would need more parameters than it would save lines) -
// three similar-but-distinct chart functions is fine, see CLAUDE.md's
// "no premature abstractions" guidance.
function drawXYChart(svg, points, xKey, yKey, xLabel, yLabel, color) {
  svg.innerHTML = "";
  const usable = points.filter((p) => p[xKey] != null && p[yKey] != null);
  if (usable.length === 0) return;

  const sorted = [...usable].sort((a, b) => a[xKey] - b[xKey]);
  const xs = sorted.map((p) => p[xKey]);
  const ys = sorted.map((p) => p[yKey]);
  const xMin = arrayMin(xs), xMax = arrayMax(xs);
  const yMin = arrayMin(ys), yMax = arrayMax(ys);
  const padX = 8, padY = 18, W = 280, H = 180;

  function sx(x) { return padX + (x - xMin) / (xMax - xMin || 1) * (W - 2 * padX); }
  function sy(y) { return H - padY - (y - yMin) / (yMax - yMin || 1) * (H - 2 * padY); }

  const ns = "http://www.w3.org/2000/svg";
  const pathD = sorted.map((p, i) => (i === 0 ? "M" : "L") + sx(p[xKey]) + " " + sy(p[yKey])).join(" ");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", pathD);
  path.setAttribute("stroke", color);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke-width", "1.6");
  svg.appendChild(path);

  for (const p of sorted) {
    const c = document.createElementNS(ns, "circle");
    c.setAttribute("cx", sx(p[xKey]));
    c.setAttribute("cy", sy(p[yKey]));
    c.setAttribute("r", 2.6);
    c.setAttribute("fill", color);
    svg.appendChild(c);
  }

  const yMinLabel = document.createElementNS(ns, "text");
  yMinLabel.setAttribute("x", 4); yMinLabel.setAttribute("y", H - padY - 2);
  yMinLabel.setAttribute("fill", "#9aa3af"); yMinLabel.setAttribute("font-size", "9");
  yMinLabel.textContent = yLabel + " " + yMin.toFixed(4);
  svg.appendChild(yMinLabel);

  const yMaxLabel = document.createElementNS(ns, "text");
  yMaxLabel.setAttribute("x", 4); yMaxLabel.setAttribute("y", padY + 8);
  yMaxLabel.setAttribute("fill", "#9aa3af"); yMaxLabel.setAttribute("font-size", "9");
  yMaxLabel.textContent = yLabel + " " + yMax.toFixed(4);
  svg.appendChild(yMaxLabel);

  const xLabelEl = document.createElementNS(ns, "text");
  xLabelEl.setAttribute("x", padX); xLabelEl.setAttribute("y", H - 4);
  xLabelEl.setAttribute("fill", "#9aa3af"); xLabelEl.setAttribute("font-size", "9");
  xLabelEl.textContent = xLabel;
  svg.appendChild(xLabelEl);
}

// Builds two side-by-side <svg> elements (inherit background/border/
// sizing from the existing global "svg { ... }" rule, see index.html's
// <style>, same as #cp-chart) for a cl/cd dual-chart pair.
function buildDualChartPair() {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.gap = "10px";
  wrap.style.marginBottom = "10px";
  const ns = "http://www.w3.org/2000/svg";
  const svgCl = document.createElementNS(ns, "svg");
  svgCl.setAttribute("viewBox", "0 0 280 180");
  svgCl.style.flex = "1";
  svgCl.style.width = "50%";
  const svgCd = document.createElementNS(ns, "svg");
  svgCd.setAttribute("viewBox", "0 0 280 180");
  svgCd.style.flex = "1";
  svgCd.style.width = "50%";
  wrap.appendChild(svgCl);
  wrap.appendChild(svgCd);
  return { wrap, svgCl, svgCd };
}

let viewer3dState = null;

function arrayMin(arr) { return arr.reduce((m, v) => (v < m ? v : m), arr[0]); }
function arrayMax(arr) { return arr.reduce((m, v) => (v > m ? v : m), arr[0]); }
// arrayMin/arrayMax instead of Math.min(...arr): spreading a large array
// as call arguments can throw "Maximum call stack size exceeded" (engine
// dependent, but well within reach once span_layers/n_profile_points are
// pushed up), crashing the 3D view instead of just taking longer.

function cpToColor(cp, cpMin, cpMax) {
  // Diverging colormap, low cp (suction) to high cp: blue -> near-white -> red,
  // matching common CFD post-processor convention (e.g. ParaView "coolwarm").
  const t = cpMax > cpMin ? (cp - cpMin) / (cpMax - cpMin) : 0.5;
  const stops = [
    [0.0, [47, 111, 237]],
    [0.5, [230, 232, 235]],
    [1.0, [224, 82, 63]],
  ];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) { a = stops[i]; b = stops[i + 1]; break; }
  }
  const span = b[0] - a[0];
  const localT = span > 0 ? (t - a[0]) / span : 0;
  const lerp = (i) => (a[1][i] + (b[1][i] - a[1][i]) * localT) / 255;
  return [lerp(0), lerp(1), lerp(2)];
}

function disposeViewer3D() {
  if (!viewer3dState) return;
  viewer3dState.controls.dispose();
  viewer3dState.renderer.dispose();
  viewer3dState.container.innerHTML = "";
  cancelAnimationFrame(viewer3dState.frameHandle);
  window.removeEventListener("resize", viewer3dState.onResize);
  viewer3dState = null;
}

// Body-axes vector (x, y, z) -> three.js scene-space direction: three.js
// treats Y as "up", this project's own convention is Z vertical, so swap
// Y/Z. Directions only (no translation/scaling), see bodyPointToScene for
// positions.
function bodyDirToScene(x, y, z) {
  return new THREE.Vector3(x, z, y);
}

function bodyPointToScene(x, y, z, cx, cy, cz, extent) {
  return new THREE.Vector3((x - cx) / extent, (z - cz) / extent, (y - cy) / extent);
}

function renderSurface3D(result) {
  const surface = result.surface;
  const container = document.getElementById("viewer3d");
  const note = document.getElementById("viewer3d-note");
  const colorbarRow = document.getElementById("colorbar-row");
  disposeViewer3D();

  if (typeof THREE === "undefined") {
    // External CDN (jsdelivr) unreachable or blocked: degrade honestly
    // instead of leaving a blank box or throwing, the 2D chart below
    // still shows the same cp data.
    note.hidden = false;
    note.textContent = "3D-Bibliothek (three.js) konnte nicht geladen werden, siehe cp-Diagramm unten.";
    colorbarRow.hidden = true;
    return;
  }
  note.hidden = true;
  if (!surface || surface.length === 0) return;

  const cps = surface.map(p => p.cp);
  const cpMin = arrayMin(cps), cpMax = arrayMax(cps);
  document.getElementById("cp-min-label").textContent = "cp " + cpMin.toFixed(2);
  document.getElementById("cp-max-label").textContent = "cp " + cpMax.toFixed(2);
  colorbarRow.hidden = false;

  const xs = surface.map(p => p.x), ys = surface.map(p => p.y), zs = surface.map(p => p.z);
  const cx = (arrayMin(xs) + arrayMax(xs)) / 2;
  const cy = (arrayMin(ys) + arrayMax(ys)) / 2;
  const cz = (arrayMin(zs) + arrayMax(zs)) / 2;
  const extent = Math.max(arrayMax(xs) - arrayMin(xs), arrayMax(ys) - arrayMin(ys), arrayMax(zs) - arrayMin(zs), 1e-6);

  const positions = new Float32Array(surface.length * 3);
  const colors = new Float32Array(surface.length * 3);
  surface.forEach((p, i) => {
    // FOSAS axis convention is X chordwise, Y spanwise, Z vertical (see
    // docs/ARCHITECTURE.md); three.js treats Y as "up" by convention,
    // so swap Y/Z here purely for a sensible default camera orientation,
    // this does not change any underlying data.
    const scenePos = bodyPointToScene(p.x, p.y, p.z, cx, cy, cz, extent);
    positions[i * 3 + 0] = scenePos.x;
    positions[i * 3 + 1] = scenePos.y;
    positions[i * 3 + 2] = scenePos.z;
    const [r, g, b] = cpToColor(p.cp, cpMin, cpMax);
    colors[i * 3 + 0] = r; colors[i * 3 + 1] = g; colors[i * 3 + 2] = b;
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({ size: 0.02, vertexColors: true, sizeAttenuation: true });
  const points = new THREE.Points(geometry, material);

  const scene = new THREE.Scene();
  scene.add(points);

  const coordLayer = buildCoordLayer(result.aoa_deg, result.sideslip_deg);
  scene.add(coordLayer);

  const momentOriginScene = bodyPointToScene(
    result.moments.moment_origin[0], result.moments.moment_origin[1], result.moments.moment_origin[2],
    cx, cy, cz, extent,
  );
  // Small sphere marker for the geometric center of mass (point 7,
  // docs/ARCHITECTURE.md): part of the coordinate/reference layer, not
  // the forces layer, since it is itself a geometry-derived reference
  // point, not a force (the weight-force arrow anchored here, built
  // below, lives in the forces layer same as the aerodynamic arrows).
  // Deliberately not its own toggle layer: a single static point marker
  // does not add the visual clutter a dedicated on/off switch would be
  // worth, unlike the arrow/arc-heavy coord and forces layers.
  const comScene = bodyPointToScene(
    result.center_of_mass[0], result.center_of_mass[1], result.center_of_mass[2],
    cx, cy, cz, extent,
  );
  const comMarker = new THREE.Mesh(
    new THREE.SphereGeometry(0.025, 12, 12),
    new THREE.MeshBasicMaterial({ color: 0x33cc33 }),
  );
  comMarker.position.copy(comScene);
  coordLayer.add(comMarker);

  const forcesLayer = buildForcesLayer(result, momentOriginScene, comScene);
  scene.add(forcesLayer);

  // Exact colors THREE.AxesHelper itself renders (pure red/green/blue
  // vertex colors), not just a similar-looking tone, so the legend text
  // and the 3D lines are unambiguously the same color to the eye.
  document.getElementById("viewer3d-overlay-legend").innerHTML =
    "Achsen: <span style=\"color:#ff3333\">X</span> stromab, " +
    "<span style=\"color:#33ff33\">Y</span> Spannweite, " +
    "<span style=\"color:#3366ff\">Z</span> vertikal, " +
    "<span style=\"color:#eeeeee\">weiss</span> Windachse (α=" + result.aoa_deg.toFixed(1) +
    "°, β=" + result.sideslip_deg.toFixed(1) + "°) &middot; " +
    "Kraftpfeile: <span style=\"color:#e0a72f\">D</span>=" + result.forces.drag.toPrecision(3) + " N, " +
    "<span style=\"color:#4f8cff\">L</span>=" + result.forces.lift.toPrecision(3) + " N, " +
    "<span style=\"color:#cc66ff\">S</span>=" + result.forces.side.toPrecision(3) + " N, " +
    "<span style=\"color:#eeeeee\">R</span>=" + result.forces.resultant.toPrecision(3) + " N" +
    (result.weight == null ? "" :
      ", <span style=\"color:#996633\">G</span>=" + result.weight.toPrecision(3) + " N") +
    " &middot; <span style=\"color:#33cc33\">●</span> Geometrischer Schwerpunkt (Annahme: homogenes Material)";

  const width = container.clientWidth, height = container.clientHeight;
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 100);
  camera.position.set(1.6, 1.2, 1.6);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.update();

  function onResize() {
    const w = container.clientWidth, h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);
  // Defensive: a size read taken in the same tick as unhiding the
  // parent panel can be wrong in some browsers before layout has fully
  // settled (confirmed the hard way: the canvas ended up much shorter
  // than its container, leaving a "dead" area below it that looked like
  // part of the 3D view but silently passed drags through to the page
  // instead of to OrbitControls). Re-measuring a frame later corrects it.
  requestAnimationFrame(onResize);

  let frameHandle;
  function animate() {
    frameHandle = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  coordLayer.visible = document.getElementById("layer-toggle-coord").checked;
  forcesLayer.visible = document.getElementById("layer-toggle-forces").checked;

  viewer3dState = {
    renderer, controls, container, onResize, coordLayer, forcesLayer,
    get frameHandle() { return frameHandle; },
  };
}

// Geometry preview/rotate tool (docs/ARCHITECTURE.md
// "Koordinatenkonvention", ADR-0020 Teil B): a separate, self-contained
// three.js scene from the result viewer above - a plain tessellated
// mesh, not a cp-colored surface point cloud, and swappable between the
// 6 precomputed candidate orientations the server already sent, so
// switching candidates is instant (no server round-trip per click).
let rotationPreviewState = null;

function disposeRotationPreview3D() {
  if (!rotationPreviewState) return;
  rotationPreviewState.controls.dispose();
  rotationPreviewState.renderer.dispose();
  rotationPreviewState.mesh.geometry.dispose();
  rotationPreviewState.wireframe.geometry.dispose();
  rotationPreviewState.container.innerHTML = "";
  cancelAnimationFrame(rotationPreviewState.frameHandle);
  window.removeEventListener("resize", rotationPreviewState.onResize);
  rotationPreviewState = null;
}

// Flat [x,y,z]/[i,j,k] arrays from one /geometry/preview variant ->
// a centered, unit-scaled BufferGeometry. Same Z(FOSAS vertical)->Y
// (three.js up) swap as bodyPointToScene above, for the same reason.
// Centering/scaling is purely visual (this is an orientation check, not
// a to-scale model), so it is independent of the geometry's own size.
function buildRotationVariantGeometry(variant) {
  const verts = variant.vertices;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const [x, y, z] of verts) {
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
    if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
  }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2;
  const extent = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 1e-6);

  const positions = new Float32Array(verts.length * 3);
  verts.forEach(([x, y, z], i) => {
    positions[i * 3 + 0] = (x - cx) / extent;
    positions[i * 3 + 1] = (z - cz) / extent;
    positions[i * 3 + 2] = (y - cy) / extent;
  });
  const indices = new Uint32Array(variant.triangles.length * 3);
  variant.triangles.forEach(([a, b, c], i) => {
    indices[i * 3 + 0] = a; indices[i * 3 + 1] = b; indices[i * 3 + 2] = c;
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeVertexNormals();
  return geometry;
}

// Shared by renderRotationPreviewVariant (the dedicated rotate/preview
// overlay) and renderGeometryPreviewInMainViewer (the automatic, no-
// click-needed preview in the main 3D-Ansicht tab after choosing a
// file) - both show the exact same kind of thing (a tessellated STEP
// mesh, no cp data), just in different containers/state variables.
function buildTessellatedMeshScene(container, geometry) {
  const scene = new THREE.Scene();
  const material = new THREE.MeshStandardMaterial({ color: 0x4f8cff, side: THREE.DoubleSide, flatShading: true });
  const mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);
  const wireframe = new THREE.LineSegments(
    new THREE.WireframeGeometry(geometry),
    new THREE.LineBasicMaterial({ color: 0x0d0f13, transparent: true, opacity: 0.25 }),
  );
  scene.add(wireframe);
  scene.add(new THREE.AxesHelper(0.7));
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(1.5, 2, 1.5);
  scene.add(dirLight);

  const width = container.clientWidth, height = container.clientHeight;
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 100);
  camera.position.set(1.6, 1.2, 1.6);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.update();

  function onResize() {
    const w = container.clientWidth, h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);
  requestAnimationFrame(onResize);

  let frameHandle;
  function animate() {
    frameHandle = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  return {
    renderer, controls, container, onResize, mesh, wireframe,
    get frameHandle() { return frameHandle; },
  };
}

function renderRotationPreviewVariant(variant) {
  const container = document.getElementById("rotation-preview-viewer");
  if (typeof THREE === "undefined") {
    container.textContent = "3D-Bibliothek (three.js) konnte nicht geladen werden.";
    return;
  }

  const geometry = buildRotationVariantGeometry(variant);

  if (rotationPreviewState) {
    // Swap geometry only, keep camera/controls so the user's own view
    // angle survives switching between candidates (comparing
    // orientations is the whole point of this tool).
    rotationPreviewState.mesh.geometry.dispose();
    rotationPreviewState.mesh.geometry = geometry;
    rotationPreviewState.wireframe.geometry.dispose();
    rotationPreviewState.wireframe.geometry = new THREE.WireframeGeometry(geometry);
    return;
  }

  rotationPreviewState = buildTessellatedMeshScene(container, geometry);
}

// Automatic preview in the main 3D-Ansicht tab, right after choosing a
// STEP file - before any job is submitted, so the user can confirm the
// right file loaded and in the right orientation without having to
// open the separate rotate/preview overlay first (that overlay stays
// for the "something looks wrong, let me fix it" case; this is just a
// passive confirmation). Reuses the exact same viewer3dState/
// disposeViewer3D pair renderSurface3D uses for the real result, since
// the two are mutually exclusive in time (this one is replaced by the
// real result once a job finishes).
function renderGeometryPreviewInMainViewer(variant, confident) {
  const container = document.getElementById("viewer3d");
  const note = document.getElementById("viewer3d-note");
  const colorbarRow = document.getElementById("colorbar-row");
  disposeViewer3D();

  if (typeof THREE === "undefined") {
    note.hidden = false;
    note.textContent = "3D-Bibliothek (three.js) konnte nicht geladen werden.";
    colorbarRow.hidden = true;
    return;
  }
  note.hidden = true;
  colorbarRow.hidden = true; // no cp-Werte vorhanden, das ist nur die rohe Geometrie

  const geometry = buildRotationVariantGeometry(variant);
  viewer3dState = buildTessellatedMeshScene(container, geometry);

  document.getElementById("viewer3d-overlay-legend").innerHTML =
    "Vorschau der hochgeladenen Geometrie (noch keine Berechnung" +
    (confident ? ", Achsen automatisch erkannt" : ", Achsen ungeprueft") + ") &middot; " +
    "Achsen: <span style=\"color:#ff3333\">X</span> Sehne, " +
    "<span style=\"color:#33ff33\">Y</span> Spannweite, " +
    "<span style=\"color:#3366ff\">Z</span> vertikal";
}

// Simple colored-line coordinate triad (body axes) plus the wind-axis
// direction arrow and angle arcs for alpha (X-Z plane) and beta (X-Y
// plane, sideslip/crosswind), all anchored at the scene origin (the
// body's own bounding-box center, same point the old AxesHelper used).
// Wind direction uses the full wind-axes-to-body-axes basis (same
// formula as fosas_core.pipeline.aoa_to_velocity_components, see
// buildForcesLayer below for the matching lift/side directions and an
// orthonormality note); at beta=0 this reduces exactly to the previous
// alpha-only arrow.
function buildCoordLayer(aoaDeg, sideslipDeg) {
  const group = new THREE.Group();
  group.add(new THREE.AxesHelper(0.7));

  const aoaRad = (aoaDeg * Math.PI) / 180;
  const betaRad = (sideslipDeg * Math.PI) / 180;
  const windDirBody = {
    x: Math.cos(aoaRad) * Math.cos(betaRad),
    y: Math.sin(betaRad),
    z: Math.sin(aoaRad) * Math.cos(betaRad),
  };
  const windDirScene = bodyDirToScene(windDirBody.x, windDirBody.y, windDirBody.z).normalize();
  const windArrow = new THREE.ArrowHelper(windDirScene, new THREE.Vector3(0, 0, 0), 0.9, 0xeeeeee, 0.12, 0.06);
  group.add(windArrow);

  // Alpha arc: body +X axis to the wind direction's X-Z-plane component,
  // swept through the actual aoa_deg, drawn independent of beta (alpha
  // and beta are the two separate input angles, shown as two separate
  // arcs rather than one compound rotation arc).
  const arcRadius = 0.35;
  const arcSteps = 24;
  const alphaArcPoints = [];
  for (let i = 0; i <= arcSteps; i++) {
    const t = (aoaRad * i) / arcSteps;
    alphaArcPoints.push(bodyDirToScene(Math.cos(t) * arcRadius, 0, Math.sin(t) * arcRadius));
  }
  const alphaArcGeometry = new THREE.BufferGeometry().setFromPoints(alphaArcPoints);
  const alphaArcLine = new THREE.Line(alphaArcGeometry, new THREE.LineBasicMaterial({ color: 0xeeeeee }));
  group.add(alphaArcLine);

  // Beta arc: body +X axis to the wind direction's X-Y-plane component,
  // only drawn for an actually nonzero sideslip (otherwise a zero-length
  // arc would just clutter the default, still most common beta=0 view).
  if (Math.abs(betaRad) > 1e-9) {
    const betaArcPoints = [];
    for (let i = 0; i <= arcSteps; i++) {
      const t = (betaRad * i) / arcSteps;
      betaArcPoints.push(bodyDirToScene(Math.cos(t) * arcRadius, Math.sin(t) * arcRadius, 0));
    }
    const betaArcGeometry = new THREE.BufferGeometry().setFromPoints(betaArcPoints);
    const betaArcLine = new THREE.Line(betaArcGeometry, new THREE.LineBasicMaterial({ color: 0xcc66ff }));
    group.add(betaArcLine);
  }

  return group;
}

// Force arrows (D along the wind direction, L perpendicular to it in the
// X-Z plane, S perpendicular to both/the side-force direction, R as
// their vector sum), anchored at the moment reference point (not the
// true center of pressure, see INFO_TEXT.viewer_layer_forces). Plus,
// only when a material was selected (result.weight != null), a weight
// arrow G anchored at the geometric center of mass instead (gravity
// acts there, not at the aerodynamic moment reference point) - folded
// into the SAME visual scale as D/L/S/R rather than its own, since a
// real part's weight and its aerodynamic forces at a modest test
// velocity can differ by orders of magnitude; showing that real
// disparity (one arrow much longer than the others) is more honest
// than silently normalizing it away with a second, incomparable scale.
// All arrows scaled so the largest has a fixed visual length regardless
// of actual physical magnitude (otherwise a small validation case's
// micro-Newton forces would render as invisible, zero-length arrows).
// D/L/S directions are the same orthonormal wind-axes basis as
// buildCoordLayer's wind arrow (verified via dot products: D.L = D.S =
// L.S = 0, each unit length); at sideslip_deg=0 this reduces exactly to
// the previous drag/lift-only basis (S direction becomes body +Y, but S
// itself is then always 0 so no arrow is drawn).
function buildForcesLayer(result, originScene, comScene) {
  const group = new THREE.Group();
  const aoaRad = (result.aoa_deg * Math.PI) / 180;
  const betaRad = (result.sideslip_deg * Math.PI) / 180;
  const cosA = Math.cos(aoaRad), sinA = Math.sin(aoaRad);
  const cosB = Math.cos(betaRad), sinB = Math.sin(betaRad);
  const dragDirBody = { x: cosA * cosB, y: sinB, z: sinA * cosB };
  const liftDirBody = { x: -sinA, y: 0, z: cosA };
  const sideDirBody = { x: -cosA * sinB, y: cosB, z: -sinA * sinB };

  const lift = result.forces.lift, drag = result.forces.drag, side = result.forces.side;
  const resultant = result.forces.resultant;
  const weight = result.weight; // null when no material was selected
  const maxMag = Math.max(
    Math.abs(lift), Math.abs(drag), Math.abs(side), resultant, Math.abs(weight || 0), 1e-12
  );
  const visualScale = 0.9 / maxMag;

  function addArrow(dirBody, signedMagnitude, color, origin) {
    const mag = Math.abs(signedMagnitude);
    if (mag < 1e-12) return; // zero-length ArrowHelper direction is undefined, skip instead
    const sign = signedMagnitude < 0 ? -1 : 1;
    const dirScene = bodyDirToScene(dirBody.x * sign, dirBody.y * sign, dirBody.z * sign).normalize();
    group.add(new THREE.ArrowHelper(dirScene, origin, mag * visualScale, color, 0.1, 0.05));
  }

  addArrow(dragDirBody, drag, 0xe0a72f, originScene);
  addArrow(liftDirBody, lift, 0x4f8cff, originScene);
  addArrow(sideDirBody, side, 0xcc66ff, originScene);

  const resultantVecBody = {
    x: dragDirBody.x * drag + liftDirBody.x * lift + sideDirBody.x * side,
    y: dragDirBody.y * drag + liftDirBody.y * lift + sideDirBody.y * side,
    z: dragDirBody.z * drag + liftDirBody.z * lift + sideDirBody.z * side,
  };
  addArrow(resultantVecBody, resultant, 0xeeeeee, originScene);

  if (weight != null) {
    // Gravity acts in body -Z regardless of AoA/sideslip (unlike the
    // aerodynamic forces above, it does not rotate with the freestream).
    addArrow({ x: 0, y: 0, z: -1 }, weight, 0x996633, comScene);
  }

  return group;
}

document.getElementById("layer-toggle-coord").addEventListener("change", (e) => {
  if (viewer3dState && viewer3dState.coordLayer) viewer3dState.coordLayer.visible = e.target.checked;
});
document.getElementById("layer-toggle-forces").addEventListener("change", (e) => {
  if (viewer3dState && viewer3dState.forcesLayer) viewer3dState.forcesLayer.visible = e.target.checked;
});

let currentResultJobId = null;

document.getElementById("job-report-btn").addEventListener("click", async () => {
  if (!currentResultJobId) return;
  try {
    const res = await fetch("/jobs/" + currentResultJobId + "/report", { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) { alert("Bericht konnte nicht erzeugt werden (" + res.status + ")."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "job_report_" + currentResultJobId + ".pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Bericht konnte nicht geladen werden.");
  }
});

function renderCalculationSteps(result) {
  const q = result.dynamic_pressure;
  const A = result.forces.reference_area;
  const l = result.moments.reference_length;
  const fmt = (x) => x.toPrecision(3);
  const lines = [
    "Staudruck q = " + fmt(q) + " Pa, Bezugsflaeche A = " + fmt(A) +
      " m^2, Bezugslaenge l = " + fmt(l) + " m (siehe Kacheln oben).",
    "",
    "L = CL * q * A = " + fmt(result.cl) + " * " + fmt(q) + " * " + fmt(A) +
      " = " + fmt(result.forces.lift) + " N",
    "D = CD * q * A = " + fmt(result.cd) + " * " + fmt(q) + " * " + fmt(A) +
      " = " + fmt(result.forces.drag) + " N",
    "S = CS * q * A = " + fmt(result.cs) + " * " + fmt(q) + " * " + fmt(A) +
      " = " + fmt(result.forces.side) + " N (Seitenkraft, nur bei Schiebewinkel != 0 ungleich 0)",
    "D_p = cd_Druck * q * A = " + fmt(result.cd_pressure) + " * " + fmt(q) + " * " + fmt(A) +
      " = " + fmt(result.drag_pressure) + " N",
    "D_f = cd_Reibung * q * A = " + fmt(result.cd_friction) + " * " + fmt(q) + " * " + fmt(A) +
      " = " + fmt(result.drag_friction) + " N",
    "",
    "Mx = CMx * q * A * l = " + fmt(result.moments.cmx) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.mx) + " Nm",
    "My = CMy * q * A * l = " + fmt(result.moments.cmy) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.my) + " Nm",
    "Mz = CMz * q * A * l = " + fmt(result.moments.cmz) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.mz) + " Nm",
  ];
  if (result.mass != null) {
    lines.push(
      "",
      "G = Masse * g = " + fmt(result.mass) + " * 9.80665 = " + fmt(result.weight) +
        " N (Gewichtskraft, Material: " + (MATERIAL_LABELS[result.material] || result.material) + ")",
    );
  }
  document.getElementById("calculation-steps-text").textContent = lines.join("\n");
}

function renderResult(result, jobId) {
  currentResultJobId = jobId;
  setResultPanelVisible(true);
  document.getElementById("cl-value").textContent = result.cl.toFixed(4);
  document.getElementById("cd-value").textContent = result.cd.toFixed(4);
  document.getElementById("yplus-value").textContent = result.mean_y_plus.toFixed(2);
  document.getElementById("tau-mean-value").textContent = result.mean_wall_shear_stress.toPrecision(3);
  document.getElementById("tau-max-value").textContent = result.max_wall_shear_stress.toPrecision(3);
  document.getElementById("drag-pressure-value").textContent = result.drag_pressure.toPrecision(3);
  document.getElementById("drag-friction-value").textContent = result.drag_friction.toPrecision(3);
  document.getElementById("area-value").textContent = result.forces.reference_area.toPrecision(3);
  document.getElementById("frontal-area-value").textContent = result.frontal_area.toPrecision(3);
  document.getElementById("cl-frontal-value").textContent =
    result.cl_frontal == null ? "-" : result.cl_frontal.toPrecision(3);
  document.getElementById("cd-frontal-value").textContent =
    result.cd_frontal == null ? "-" : result.cd_frontal.toPrecision(3);
  document.getElementById("ref-this-run-value").textContent =
    result.cd_frontal == null ? "nicht verfuegbar" : result.cd_frontal.toPrecision(3);
  document.getElementById("q-value").textContent = result.dynamic_pressure.toFixed(1);
  document.getElementById("re-value").textContent = result.reynolds_number.toExponential(2);
  // toPrecision(3), not toFixed(2): forces span orders of magnitude
  // between a small validation geometry (micro-Newton range) and a
  // real part (hundreds to thousands of Newtons). toFixed(2) would
  // round a tiny but real force down to a misleading "0.00" instead of
  // showing it.
  document.getElementById("lift-value").textContent = result.forces.lift.toPrecision(3);
  document.getElementById("drag-value").textContent = result.forces.drag.toPrecision(3);
  document.getElementById("side-value").textContent = result.forces.side.toPrecision(3);
  document.getElementById("resultant-value").textContent = result.forces.resultant.toPrecision(3);
  document.getElementById("resultant-angle-value").textContent = result.forces.resultant_angle_deg.toFixed(1) + "°";
  document.getElementById("glide-ratio-value").textContent =
    result.forces.glide_ratio == null ? "-" : result.forces.glide_ratio.toFixed(2);
  document.getElementById("mx-value").textContent = result.moments.mx.toPrecision(3);
  document.getElementById("my-value").textContent = result.moments.my.toPrecision(3);
  document.getElementById("mz-value").textContent = result.moments.mz.toPrecision(3);
  const origin = result.moments.moment_origin;
  document.getElementById("moment-origin-hint").textContent =
    "Momenten-Bezugspunkt (aktuell fest, noch nicht waehlbar): x=" + origin[0].toPrecision(3) +
    " m, y=" + origin[1].toPrecision(3) + " m, z=" + origin[2].toPrecision(3) +
    " m (Mitte der Sehne/Spannweite).";
  const com = result.center_of_mass;
  document.getElementById("center-of-mass-hint").textContent =
    "Geometrischer Schwerpunkt (aus der STEP-Geometrie berechnet, nimmt homogenes Material an): x=" +
    com[0].toPrecision(3) + " m, y=" + com[1].toPrecision(3) + " m, z=" + com[2].toPrecision(3) + " m.";
  document.getElementById("volume-value").textContent = result.volume.toPrecision(3);
  document.getElementById("material-value").textContent =
    result.material == null ? "-" : (MATERIAL_LABELS[result.material] || result.material);
  document.getElementById("mass-value").textContent =
    result.mass == null ? "-" : result.mass.toPrecision(3);
  document.getElementById("weight-value").textContent =
    result.weight == null ? "-" : result.weight.toPrecision(3);
  renderCalculationSteps(result);

  const badge = document.getElementById("convergence-badge");
  const conv = result.convergence;
  let cls = "bad", text = "Nicht konvergiert";
  if (conv.converged) { cls = "ok"; text = "Konvergiert"; }
  else if (conv.is_plateaued) { cls = "warn"; text = "Plateau, vermutlich nicht loesbar durch mehr Iterationen"; }
  badge.innerHTML = '<span class="badge ' + cls + '">' + text + '</span>';
  document.getElementById("convergence-msg").textContent = conv.message;

  renderSurface3D(result);
  drawFreeBodyDiagram(result);
  drawCpChart(result.surface);
}

function formatDuration(seconds) {
  if (seconds == null || !isFinite(seconds) || seconds < 0) return "unbekannt";
  seconds = Math.round(seconds);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m + ":" + String(s).padStart(2, "0");
}

function setStep(id, state) {
  // state: "pending" | "current" | "done" | "failed"
  const el = document.getElementById(id);
  el.className = state === "pending" ? "" : state;
  el.querySelector(".dot").textContent = state === "done" ? "✓" : state === "failed" ? "✕" : "";
}

function renderProgress(job) {
  const panel = document.getElementById("console-panel");
  const fill = document.getElementById("progress-fill");
  const label = document.getElementById("progress-label");
  const etaEl = document.getElementById("progress-eta");

  const summaryEl = document.getElementById("console-summary");

  if (job.status === "done") {
    panel.hidden = true;
    document.getElementById("console-toggle-icon").innerHTML = "&#9656;";
    summaryEl.textContent = "";
    return;
  }

  panel.hidden = false;

  if (job.status === "pending") {
    setStep("step-geometry", "current");
    setStep("step-meshing", "pending");
    setStep("step-solving", "pending");
    fill.className = "progress-fill indeterminate";
    label.textContent = "Wird gestartet ...";
    etaEl.textContent = "";
    summaryEl.textContent = "· " + label.textContent;
    return;
  }

  if (job.status === "failed") {
    const failedAt = job.stage;
    // Ordinal lookup, not a chain of ternaries: _execute_job (app.py)
    // can also set stage="unknown" for any exception PipelineError did
    // not already categorize. An unrecognized stage must not make every
    // step fall through to "done" (the old chain's bug: "unknown" never
    // matched any of the three literal comparisons, so geometry/meshing/
    // solving all rendered as succeeded right next to a failure message,
    // actively misleading, exactly what CLAUDE.md's "no sugar-coating"
    // rule forbids).
    const stageOrder = ["geometry", "meshing", "solving"];
    const failedIndex = stageOrder.indexOf(failedAt);
    stageOrder.forEach((name, i) => {
      const elId = "step-" + name;
      if (failedIndex === -1) {
        setStep(elId, "pending"); // unknown stage: claim nothing was done
      } else if (i < failedIndex) {
        setStep(elId, "done");
      } else if (i === failedIndex) {
        setStep(elId, "failed");
      } else {
        setStep(elId, "pending");
      }
    });
    fill.className = "progress-fill";
    fill.style.width = "0%";
    label.textContent = "Fehlgeschlagen in Phase '" + failedAt + "'";
    etaEl.textContent = "";
    summaryEl.textContent = "· " + label.textContent;
    return;
  }

  // status === "running"
  const progress = job.progress;
  const phase = progress ? progress.phase : "meshing";
  setStep("step-geometry", "done");

  if (phase === "meshing") {
    setStep("step-meshing", "current");
    setStep("step-solving", "pending");
    fill.className = "progress-fill indeterminate";
    // Gmsh reports no progress percentage FOSAS can read while it runs,
    // so this phase honestly shows elapsed time only, not a guessed ETA.
    label.textContent = "Vernetzung laeuft (" + formatDuration(progress ? progress.elapsed_seconds : null) + ")";
    etaEl.textContent = "";
  } else {
    setStep("step-meshing", "done");
    setStep("step-solving", "current");
    fill.className = "progress-fill";
    const pct = progress && progress.percent != null ? progress.percent : 0;
    fill.style.width = pct.toFixed(1) + "%";
    const cur = progress ? progress.current_iteration : 0;
    const max = progress ? progress.max_iterations : "?";
    label.textContent = "Iteration " + cur + " / " + max + " (" + pct.toFixed(1) + "%)";
    etaEl.textContent = progress && progress.eta_seconds != null
      ? "noch ca. " + formatDuration(progress.eta_seconds)
      : "Restzeit noch unbekannt";
  }
  summaryEl.textContent = "· " + label.textContent;
}

function reloadToRefreshToken() {
  // The engine issues a new random token on every start (see
  // docs/ARCHITECTURE.md); an old page kept open across a restart is
  // still holding the previous one. Reloading re-fetches "/", which
  // serves the current token, while the job id stays in the URL, so
  // the reload lands right back on the same job's status instead of
  // an empty form, see docs/RISKS.md R14.
  window.location.reload();
}

let activePollToken = 0;

async function pollJob(jobId) {
  // Selecting a different job from the jobs list while one is already
  // being polled must not leave two loops racing to update the same DOM
  // (whichever request happened to resolve last would silently "win").
  // Each call claims a token; a loop that is no longer the current one
  // quietly stops instead of continuing to render.
  const myToken = ++activePollToken;
  // Invalidate any still-in-flight geometry auto-preview fetch (see
  // autoPreviewUploadedGeometry): once a job starts, its own result
  // owns the viewer3d container from here on, a late-resolving preview
  // must not overwrite it.
  activePreviewToken++;
  const statusEl = document.getElementById("status");
  expandConsole(); // the console is where the step-by-step progress lives now, see the shell redesign
  while (true) {
    const res = await fetch("/jobs/" + jobId, { headers: authHeaders() });
    if (myToken !== activePollToken) return;
    if (res.status === 401) {
      statusEl.textContent = "Token abgelaufen (Engine wurde neu gestartet), lade Seite neu ...";
      reloadToRefreshToken();
      return;
    }
    if (!res.ok) { setError("Fehler beim Abfragen des Jobs (" + res.status + ")"); return; }
    const job = await res.json();
    if (myToken !== activePollToken) return;
    renderProgress(job);
    if (job.status === "pending" || job.status === "running") {
      statusEl.textContent = "Job " + jobId;
      await new Promise(r => setTimeout(r, 2000));
      if (myToken !== activePollToken) return;
      continue;
    }
    if (job.status === "failed") {
      statusEl.textContent = "";
      setError("Fehlgeschlagen in Phase '" + job.stage + "': " + job.error);
      return;
    }
    statusEl.textContent = "Fertig.";
    renderResult(job.result, job.id);
    return;
  }
}

function formatRelativeTime(isoString) {
  const diffSeconds = Math.round((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diffSeconds < 60) return "gerade eben";
  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return "vor " + diffMinutes + " Min.";
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return "vor " + diffHours + " Std.";
  return "vor " + Math.round(diffHours / 24) + " Tg.";
}

function statusLabel(job) {
  if (job.status === "running") {
    if (job.progress && job.progress.phase === "solving" && job.progress.percent != null) {
      return "laeuft (" + job.progress.percent.toFixed(0) + "%)";
    }
    return "laeuft (Vernetzung)";
  }
  return { pending: "wartet", done: "fertig", failed: "fehlgeschlagen" }[job.status] || job.status;
}

function selectJob(jobId) {
  closeArchive();
  history.replaceState(null, "", "?job=" + jobId);
  setResultPanelVisible(false);
  // Without this, switching away from a finished job (which has a live
  // WebGLRenderer + requestAnimationFrame loop from renderSurface3D)
  // to one with no result yet left that renderer running every frame
  // into a now-hidden canvas until the next finished job happened to
  // call renderSurface3D again (which disposes the previous one itself).
  disposeViewer3D();
  setError(null);
  document.getElementById("status").textContent = "Lade Status von Job " + jobId + " ...";
  pollJob(jobId);
}

let showingArchived = false;

async function resumeJob(jobId) {
  // Reuses the same work_dir (mesh and any SU2 restart checkpoint it
  // already has, see docs/RISKS.md R14/R17), not a fresh run from
  // scratch, and jumps straight to that job's status view.
  await fetch("/jobs/" + jobId + "/resume", { method: "POST", headers: authHeaders() });
  selectJob(jobId);
}

async function archiveJob(jobId) {
  await fetch("/jobs/" + jobId + "/archive", { method: "POST", headers: authHeaders() });
  loadArchiveList();
}

async function unarchiveJob(jobId) {
  await fetch("/jobs/" + jobId + "/unarchive", { method: "POST", headers: authHeaders() });
  loadArchiveList();
}

async function deleteJobPrompt(jobId, filename) {
  if (!confirm("Auftrag \"" + filename + "\" endgueltig loeschen? Das entfernt auch alle zugehoerigen Dateien (Netz, Ergebnisse) und kann nicht rueckgaengig gemacht werden.")) {
    return;
  }
  await fetch("/jobs/" + jobId, { method: "DELETE", headers: authHeaders() });
  loadArchiveList();
}

document.getElementById("archive-toggle-btn").addEventListener("click", () => {
  showingArchived = !showingArchived;
  document.getElementById("archive-toggle-btn").className = "archive-toggle-btn" + (showingArchived ? " active" : "");
  document.getElementById("archive-toggle-btn").textContent = showingArchived ? "Aktuelle anzeigen" : "Archivierte anzeigen";
  loadArchiveList();
});

function openArchive() {
  document.getElementById("archive-overlay").hidden = false;
  loadArchiveList();
}

function closeArchive() {
  document.getElementById("archive-overlay").hidden = true;
}

document.getElementById("topbar-archive-btn").addEventListener("click", openArchive);
document.getElementById("archive-close-btn").addEventListener("click", closeArchive);
document.getElementById("archive-overlay").addEventListener("click", (e) => {
  if (e.target.id === "archive-overlay") closeArchive(); // click on the dim backdrop, not the panel itself
});

function buildJobArchiveRow(job) {
  const row = document.createElement("div");
  row.className = "job-row";

  const dot = document.createElement("span");
  dot.className = "job-status-dot " + job.status;

  const main = document.createElement("div");
  main.className = "job-main";
  const fileEl = document.createElement("div");
  fileEl.className = "job-file";
  fileEl.textContent = job.step_filename; // textContent, not innerHTML: this is a user-supplied filename
  const metaEl = document.createElement("div");
  metaEl.className = "job-meta";
  metaEl.textContent = "Einzelpunkt · " + statusLabel(job) + " · " + formatRelativeTime(job.created_at);
  main.appendChild(fileEl);
  main.appendChild(metaEl);

  const actions = document.createElement("div");
  actions.className = "job-actions";
  const canModify = job.status === "done" || job.status === "failed";
  if (canModify) {
    if (job.status === "failed") {
      const resumeBtn = document.createElement("button");
      resumeBtn.type = "button";
      resumeBtn.className = "job-action-btn";
      resumeBtn.textContent = "Fortsetzen";
      resumeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        resumeJob(job.id);
      });
      actions.appendChild(resumeBtn);
    }
    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "job-action-btn";
    toggleBtn.textContent = showingArchived ? "Wiederherstellen" : "Archivieren";
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      showingArchived ? unarchiveJob(job.id) : archiveJob(job.id);
    });
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "job-action-btn danger";
    deleteBtn.textContent = "Loeschen";
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteJobPrompt(job.id, job.step_filename);
    });
    actions.appendChild(toggleBtn);
    actions.appendChild(deleteBtn);
  }

  row.appendChild(dot);
  row.appendChild(main);
  row.appendChild(actions);
  row.addEventListener("click", () => selectJob(job.id)); // selectJob itself closes the archive overlay
  return row;
}

function statusDotClass(status) {
  // Same four-value status space as a Job (see jobs.JobStatus), reused
  // as-is for both study kinds' aggregate status.
  return "job-status-dot " + status;
}

function statusLabelText(status) {
  // A simpler sibling of statusLabel(job) above: polar/GCI points and
  // levels only carry a bare status string, not a full Job with its
  // own progress sub-object, so the "running (NN%)" detail statusLabel
  // renders for a job is not available here.
  if (status === "running") return "laeuft";
  return { pending: "wartet", done: "fertig", failed: "fehlgeschlagen" }[status] || status;
}

function formatStudyRow(title, status, detailText, onToggle) {
  const row = document.createElement("div");
  row.className = "job-row";
  const dot = document.createElement("span");
  dot.className = statusDotClass(status);
  const main = document.createElement("div");
  main.className = "job-main";
  const titleEl = document.createElement("div");
  titleEl.className = "job-file";
  titleEl.textContent = title; // textContent: title may embed a user-supplied filename
  const metaEl = document.createElement("div");
  metaEl.className = "job-meta";
  metaEl.textContent = detailText;
  main.appendChild(titleEl);
  main.appendChild(metaEl);
  row.appendChild(dot);
  row.appendChild(main);
  row.addEventListener("click", onToggle);
  return row;
}

function formatStudyDetail(study, pointsLabel) {
  const total = study[pointsLabel].length;
  const done = study[pointsLabel].filter((p) => p.status === "done").length;
  return study.step_filename + " · " + done + " von " + total + " fertig · " + formatRelativeTime(study.created_at);
}

function populateStudySelect(selectId, studies) {
  const select = document.getElementById(selectId);
  const previousValue = select.value;
  select.innerHTML = "";
  for (const study of studies) {
    const option = document.createElement("option");
    option.value = study.id;
    option.textContent = study.step_filename + " (" + study.id.slice(0, 8) + ")";
    select.appendChild(option);
  }
  if (studies.some((s) => s.id === previousValue)) {
    select.value = previousValue; // keep the user's choice across a poll refresh
  }
}

// Builds the archive rows for one polar study (the row itself, plus,
// if expanded, the cl/cd-over-AoA charts, the per-point table, and the
// report button) - appended directly into the shared #archive-list by
// loadArchiveList below, same rendering as before the UI unification,
// just no longer its own permanently-visible page panel.
function buildPolarArchiveRows(study) {
  const nodes = [];
  const key = "polar:" + study.id;
  const expanded = expandedArchiveEntries.has(key);
  const row = formatStudyRow(study.step_filename, study.status, "Polare · " + formatStudyDetail(study, "points"), () => {
    expandedArchiveEntries.has(key) ? expandedArchiveEntries.delete(key) : expandedArchiveEntries.add(key);
    loadArchiveList();
  });
  nodes.push(row);
  if (expanded) {
    const anyPlotted = study.points.some((p) => p.cl != null && p.cd != null);
    if (anyPlotted) {
      const { wrap, svgCl, svgCd } = buildDualChartPair();
      nodes.push(wrap);
      drawXYChart(svgCl, study.points, "aoa_deg", "cl", "Anstellwinkel (Grad)", "cl", "#4f8cff");
      drawXYChart(svgCd, study.points, "aoa_deg", "cd", "Anstellwinkel (Grad)", "cd", "#e0a72f");
    }

    const table = document.createElement("table");
    table.className = "study-detail-table";
    const header = table.insertRow();
    ["AoA (Grad)", "Status", "cl", "cd"].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      header.appendChild(th);
    });
    for (const point of study.points) {
      const tr = table.insertRow();
      [point.aoa_deg, statusLabelText(point.status), point.cl, point.cd].forEach((value) => {
        const td = tr.insertCell();
        td.textContent = value === null || value === undefined ? "-" : value;
      });
    }
    nodes.push(table);

    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.className = "job-action-btn";
    reportBtn.textContent = "Bericht (PDF)";
    reportBtn.addEventListener("click", () => downloadPolarReport(study.id, study.step_filename));
    nodes.push(reportBtn);
  }
  return nodes;
}

async function downloadPolarReport(studyId, stepFilename) {
  // The report route needs the bearer token as a header, not a query
  // param, so a plain <a href> link cannot carry auth - fetch the PDF
  // as a blob and trigger the browser's own save dialog instead.
  try {
    const res = await fetch("/polar-studies/" + studyId + "/report", { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) { alert("Bericht konnte nicht erzeugt werden (" + res.status + ")."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "polar_report_" + stepFilename.replace(/\.[^.]+$/, "") + ".pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Bericht konnte nicht geladen werden.");
  }
}

// Same idea as buildPolarArchiveRows above, for a GCI mesh-quality
// study: row plus, if expanded, the cl/cd-over-element-count charts,
// the per-resolution table, the GCI result message, and the report
// button.
function buildGciArchiveRows(study) {
  const nodes = [];
  const key = "gci:" + study.id;
  const expanded = expandedArchiveEntries.has(key);
  const row = formatStudyRow(study.step_filename, study.status, "Netzqualitaet geprueft · " + formatStudyDetail(study, "levels"), () => {
    expandedArchiveEntries.has(key) ? expandedArchiveEntries.delete(key) : expandedArchiveEntries.add(key);
    loadArchiveList();
  });
  nodes.push(row);
  if (expanded) {
    const anyPlotted = study.levels.some((l) => l.element_count != null && l.cl != null);
    if (anyPlotted) {
      const { wrap, svgCl, svgCd } = buildDualChartPair();
      nodes.push(wrap);
      drawXYChart(svgCl, study.levels, "element_count", "cl", "Elementanzahl", "cl", "#4f8cff");
      drawXYChart(svgCd, study.levels, "element_count", "cd", "Elementanzahl", "cd", "#e0a72f");
    }

    const table = document.createElement("table");
    table.className = "study-detail-table";
    const header = table.insertRow();
    ["Aufloesung", "Status", "Elemente", "cl", "cd"].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      header.appendChild(th);
    });
    for (const level of study.levels) {
      const tr = table.insertRow();
      [level.resolution, statusLabelText(level.status), level.element_count, level.cl, level.cd].forEach((value) => {
        const td = tr.insertCell();
        td.textContent = value === null || value === undefined ? "-" : value;
      });
    }
    nodes.push(table);
    if (study.result) {
      const resultEl = document.createElement("p");
      resultEl.className = "hint";
      resultEl.textContent = "cl: " + study.result.cl.message + " / cd: " + study.result.cd.message;
      nodes.push(resultEl);
    } else if (study.result_error) {
      const errEl = document.createElement("p");
      errEl.className = "hint";
      errEl.textContent = "GCI konnte nicht berechnet werden: " + study.result_error;
      nodes.push(errEl);
    }

    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.className = "job-action-btn";
    reportBtn.textContent = "Bericht (PDF)";
    reportBtn.addEventListener("click", () => downloadGciReport(study.id, study.step_filename));
    nodes.push(reportBtn);
  }
  return nodes;
}

async function downloadGciReport(studyId, stepFilename) {
  try {
    const res = await fetch("/gci-studies/" + studyId + "/report", { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) { alert("Bericht konnte nicht erzeugt werden (" + res.status + ")."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "gci_report_" + stepFilename.replace(/\.[^.]+$/, "") + ".pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Bericht konnte nicht geladen werden.");
  }
}

const expandedArchiveEntries = new Set();

// Unified archive (docs/ARCHITECTURE.md "virtueller Windkanal, nicht
// drei Tools"): one list merging all three request kinds FOSAS can run
// (single job, polar study, GCI mesh-quality study), sorted by
// creation time, instead of three permanently-visible separate list
// panels. Also keeps the combined-report dropdowns (in the report
// popover) populated, same as the three old loaders did.
async function loadArchiveList() {
  const listEl = document.getElementById("archive-list");
  let jobs = [], polarStudies = [], gciStudies = [];
  try {
    const archivedParam = "?archived=" + showingArchived;
    const [jobsRes, polarRes, gciRes] = await Promise.all([
      fetch("/jobs" + archivedParam, { headers: authHeaders() }),
      fetch("/polar-studies" + archivedParam, { headers: authHeaders() }),
      fetch("/gci-studies" + archivedParam, { headers: authHeaders() }),
    ]);
    if (jobsRes.status === 401 || polarRes.status === 401 || gciRes.status === 401) {
      reloadToRefreshToken();
      return;
    }
    if (jobsRes.ok) jobs = await jobsRes.json();
    if (polarRes.ok) polarStudies = await polarRes.json();
    if (gciRes.ok) gciStudies = await gciRes.json();
  } catch (err) {
    return; // offline for a moment: leave the previously shown list as-is
  }

  // Combined-report dropdowns always reflect the non-archived lists
  // (same as before unification: archiving a study does not remove it
  // from being reportable, but there is no reason to default-select an
  // archived one either - keeps today's behaviour exactly).
  if (!showingArchived) {
    populateStudySelect("combined-report-polar-select", polarStudies);
    populateStudySelect("combined-report-gci-select", gciStudies);
  }

  const entries = [
    ...jobs.map((j) => ({ kind: "job", data: j })),
    ...polarStudies.map((s) => ({ kind: "polar", data: s })),
    ...gciStudies.map((s) => ({ kind: "gci", data: s })),
  ];

  if (entries.length === 0) {
    listEl.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "jobs-empty";
    empty.textContent = showingArchived ? "Archiv ist leer." : "Noch keine Berechnungen.";
    listEl.appendChild(empty);
    return;
  }

  entries.sort((a, b) => new Date(b.data.created_at) - new Date(a.data.created_at));
  listEl.innerHTML = "";
  for (const entry of entries) {
    if (entry.kind === "job") {
      listEl.appendChild(buildJobArchiveRow(entry.data));
    } else if (entry.kind === "polar") {
      for (const node of buildPolarArchiveRows(entry.data)) listEl.appendChild(node);
    } else {
      for (const node of buildGciArchiveRows(entry.data)) listEl.appendChild(node);
    }
  }
}

loadArchiveList();
setInterval(loadArchiveList, 4000);

document.getElementById("topbar-report-btn").addEventListener("click", () => {
  const pop = document.getElementById("report-popover");
  pop.hidden = !pop.hidden;
});
document.addEventListener("click", (e) => {
  const pop = document.getElementById("report-popover");
  if (!pop.hidden && !pop.contains(e.target) && e.target.id !== "topbar-report-btn") {
    pop.hidden = true;
  }
});

document.getElementById("combined-report-btn").addEventListener("click", async () => {
  const polarId = document.getElementById("combined-report-polar-select").value;
  const gciId = document.getElementById("combined-report-gci-select").value;
  if (!polarId || !gciId) { alert("Bitte eine Polarstudie und eine GCI-Netzstudie auswaehlen."); return; }
  try {
    const res = await fetch(
      "/reports/combined?polar_study_id=" + polarId + "&gci_study_id=" + gciId,
      { headers: authHeaders() }
    );
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) { alert("Bericht konnte nicht erzeugt werden (" + res.status + ")."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "combined_report.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Bericht konnte nicht geladen werden.");
  }
});

// Center-panel tabs (3D-Ansicht/Freikoerperbild/cp-Verteilung): plain
// show/hide, same content as before unification, just one visible at
// a time instead of stacked one after another on a long page.
document.querySelectorAll(".center-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".center-tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".center-tab-content").forEach((c) => { c.hidden = true; });
    btn.classList.add("active");
    document.getElementById("center-tab-" + btn.dataset.tab).hidden = false;
  });
});

// Console (bottom bar): collapsed by default, same progress-panel
// content as before unification (steps list/progress bar/ETA), just
// relocated and foldable instead of always taking up page space.
document.getElementById("console-bar").addEventListener("click", () => {
  const panel = document.getElementById("console-panel");
  panel.hidden = !panel.hidden;
  document.getElementById("console-toggle-icon").innerHTML = panel.hidden ? "&#9656;" : "&#9662;";
});

function expandConsole() {
  document.getElementById("console-panel").hidden = false;
  document.getElementById("console-toggle-icon").innerHTML = "&#9662;";
}

// --- Seitenpanels: ein-/ausklappbar + per Zieh-Griff groessenverstellbar
// (eine Achse je Griff), wie bei Inventor/Photoshop. Auf schmalen
// Bildschirmen werden dieselben links/rechts-Panels per Media-Query zu
// Schubladen-Overlays (siehe CSS) - dieselben "left-collapsed"/
// "right-collapsed"-Klassen steuern beide Darstellungen einheitlich.
const MOBILE_BREAKPOINT_QUERY = window.matchMedia("(max-width: 860px)");
const appShellEl = document.getElementById("app-shell");

function isLeftOpen() { return !appShellEl.classList.contains("left-collapsed"); }
function isRightOpen() { return !appShellEl.classList.contains("right-collapsed"); }

function updatePanelBackdrop() {
  const backdrop = document.getElementById("panel-backdrop");
  // The backdrop (tap-outside-to-close) only makes sense while a panel
  // is shown as a mobile overlay drawer, not for the desktop grid
  // columns - a backdrop over the whole page would block clicking into
  // the center/result panels on desktop for no reason.
  const mobile = MOBILE_BREAKPOINT_QUERY.matches;
  backdrop.hidden = !(mobile && (isLeftOpen() || isRightOpen()));
}

function setLeftPanelOpen(open) {
  appShellEl.classList.toggle("left-collapsed", !open);
  document.getElementById("toggle-left-btn").classList.toggle("active", open);
  updatePanelBackdrop();
}

function setRightPanelOpen(open) {
  appShellEl.classList.toggle("right-collapsed", !open);
  document.getElementById("toggle-right-btn").classList.toggle("active", open);
  updatePanelBackdrop();
}

// Shared by every place that shows/hides the result panel (a real
// result exists, or not) - the "Ergebnis" toggle button only makes
// sense once there is something to show, so it stays disabled and
// closed until then, rather than opening onto an empty panel.
function setResultPanelVisible(visible) {
  document.getElementById("result-panel").hidden = !visible;
  document.getElementById("toggle-right-btn").disabled = !visible;
  if (visible) {
    setRightPanelOpen(!MOBILE_BREAKPOINT_QUERY.matches); // auto-open on desktop, stays closed-by-default on mobile
  } else {
    setRightPanelOpen(false);
  }
}

document.getElementById("toggle-left-btn").addEventListener("click", () => setLeftPanelOpen(!isLeftOpen()));
document.getElementById("toggle-right-btn").addEventListener("click", () => setRightPanelOpen(!isRightOpen()));
document.getElementById("panel-backdrop").addEventListener("click", () => {
  setLeftPanelOpen(false);
  setRightPanelOpen(false);
});

function applyResponsiveDefaults() {
  if (MOBILE_BREAKPOINT_QUERY.matches) {
    setLeftPanelOpen(false);
    setRightPanelOpen(false);
  } else {
    setLeftPanelOpen(true);
    // Right panel still follows "only open if there is a result" even
    // on desktop - do not force it open onto nothing.
    setRightPanelOpen(!document.getElementById("result-panel").hidden);
  }
}
applyResponsiveDefaults();
// A resize across the breakpoint (rotating a tablet, resizing a
// desktop window) re-applies the right default instead of leaving a
// mobile-opened drawer stuck in a now-desktop layout or vice versa.
MOBILE_BREAKPOINT_QUERY.addEventListener("change", applyResponsiveDefaults);

// Zieh-Griffe: eine Pointer-Drag-Funktion fuer alle drei (links/rechts
// Breite, Konsole Hoehe), da das Prinzip identisch ist - nur welche
// CSS-Variable geschrieben wird und in welche Richtung unterscheidet
// sich. pointermove/up werden bewusst auf window gebunden (nicht auf
// den Griff selbst), weil der Zeiger beim schnellen Ziehen den schmalen
// 5px-Griff leicht verlassen kann.
function setupResizeHandle(handleId, { axis, cssVar, min, max, invert }) {
  const handle = document.getElementById(handleId);
  let dragStart = 0;
  let startSize = 0;

  function currentSize() {
    const raw = getComputedStyle(appShellEl).getPropertyValue(cssVar).trim();
    const parsed = parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : min;
  }

  function onMove(e) {
    const pos = axis === "x" ? e.clientX : e.clientY;
    const delta = (pos - dragStart) * (invert ? -1 : 1);
    const size = Math.min(max, Math.max(min, startSize + delta));
    appShellEl.style.setProperty(cssVar, size + "px");
  }
  function onUp() {
    handle.classList.remove("dragging");
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
  }
  handle.addEventListener("pointerdown", (e) => {
    dragStart = axis === "x" ? e.clientX : e.clientY;
    startSize = currentSize();
    handle.classList.add("dragging");
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    e.preventDefault();
  });
}
setupResizeHandle("resize-handle-left", { axis: "x", cssVar: "--left-w", min: 220, max: 600, invert: false });
setupResizeHandle("resize-handle-right", { axis: "x", cssVar: "--right-w", min: 220, max: 600, invert: true });
setupResizeHandle("resize-handle-console", { axis: "y", cssVar: "--console-h", min: 120, max: 560, invert: true });

// --- Vollbild: frueher ein Link, der /viewer?job=... in einem neuen Tab
// oeffnete - auf dem Handy wirkte das wie "die Seite laedt neu" (neuer
// Tab nicht offensichtlich erkennbar/fokussiert). Jetzt die echte
// Fullscreen-API direkt auf dem Center-Panel (3D-Ansicht/FBD/cp bleiben
// im Vollbild umschaltbar), funktioniert auf Desktop und Handy gleich.
const fullscreenBtn = document.getElementById("fullscreen-btn");
fullscreenBtn.addEventListener("click", () => {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    document.getElementById("center-panel").requestFullscreen().catch((err) => {
      setError("Vollbild nicht verfuegbar: " + err.message);
    });
  }
});
document.addEventListener("fullscreenchange", () => {
  const isFullscreen = document.fullscreenElement === document.getElementById("center-panel");
  fullscreenBtn.textContent = isFullscreen ? "Vollbild verlassen" : "Vollbild ↗";
  // The three.js canvas has a fixed pixel size computed from its
  // container at creation time - entering/leaving fullscreen resizes
  // that container without firing a window "resize" event, so the
  // existing onResize handlers (bound to window) never fire on their
  // own. A fake resize event nudges them; a second one a frame later
  // covers browsers where the fullscreen transition has not finished
  // laying out yet when fullscreenchange itself fires (same class of
  // issue as the documented one in renderSurface3D's own onResize).
  window.dispatchEvent(new Event("resize"));
  requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
});

// Custom-styled STEP-file picker (see the .file-input-* CSS): the
// native input stays functional and focusable, just visually hidden,
// with this label mirroring the chosen filename - form.reset() below
// clears the input itself but does not reliably fire "change" for a
// file input in every browser, so the label is also reset explicitly.
function updateFileInputName() {
  const files = document.getElementById("step_file").files;
  document.getElementById("step_file-name").textContent =
    files.length ? files[0].name : "Keine Datei gewaehlt";
  document.getElementById("geometry-preview-btn").hidden = !files.length;
  // A stored preview_id refers to specifically the bytes that were
  // uploaded to /geometry/preview, not "whatever file is in the input
  // right now" - any change to the file selection (a different file, or
  // a programmatic reset after a submission) invalidates it. This is
  // the single place every such change already passes through.
  activeGeometryPreview = null;
  document.getElementById("geometry-preview-status").textContent = "";
}
document.getElementById("step_file").addEventListener("change", () => {
  updateFileInputName();
  const files = document.getElementById("step_file").files;
  if (files.length) autoPreviewUploadedGeometry(files[0]);
});

// Passive confirmation right after choosing a file, before any job is
// submitted: "did the right geometry load, in the right orientation?"
// (user-requested - previously nothing at all was shown between
// choosing a file and a finished result). A network/parse problem here
// is only a hint, never blocking - the real submission still reports
// any genuine problem properly, this is just an early, optional look.
//
// activePreviewToken guards against a real (if unlikely) race: if this
// fetch is still in flight when a job on the SAME viewer3d container
// already finished and rendered its real result (a very fast job, or
// the user picked a second file while this one was still loading), the
// stale preview must not overwrite that real result when it resolves.
// Same pattern as pollJob's activePollToken above.
let activePreviewToken = 0;

async function autoPreviewUploadedGeometry(file) {
  const myToken = ++activePreviewToken;
  const form = new FormData();
  form.append("step_file", file);
  let res;
  try {
    res = await fetch("/geometry/preview", { method: "POST", headers: authHeaders(), body: form });
  } catch (err) {
    return;
  }
  if (myToken !== activePreviewToken) return;
  if (res.status === 401) { reloadToRefreshToken(); return; }
  if (!res.ok) {
    const note = document.getElementById("viewer3d-note");
    note.hidden = false;
    note.textContent = "Konnte keine Geometrie-Vorschau laden (" + res.status + ") - Absenden ist trotzdem moeglich.";
    document.getElementById("colorbar-row").hidden = true;
    return;
  }
  const data = await res.json();
  if (myToken !== activePreviewToken) return;
  const label = data.suggested_label || "identity";
  const variant = data.variants.find((v) => v.label === label);
  if (variant) renderGeometryPreviewInMainViewer(variant, data.confident);
}

// --- Geometry preview/rotate tool (ADR-0020 Teil B): upload once, see
// all 6 possible axis orientations in 3D, pick one, then submit without
// re-uploading (preview_id + manual_rotation_label instead of
// step_file). See fosas_engine.app POST /geometry/preview.
const ROTATION_LABEL_TEXT = {
  identity: "Unveraendert (wie hochgeladen)",
  rot_x90: "90° um X gedreht",
  rot_y90: "90° um Y gedreht",
  rot_z90: "90° um Z gedreht",
  rot_x90_then_z90: "90° um X, danach 90° um Z gedreht",
  rot_z90_then_x90: "90° um Z, danach 90° um X gedreht",
};

let currentPreviewData = null; // last /geometry/preview response, while the overlay is open
let selectedPreviewLabel = null; // which candidate is currently shown/highlighted in the overlay
let activeGeometryPreview = null; // { previewId, label }, only after "Anwenden" was clicked

// Shared by submitSingleJob/submitGciStudy/submitPolarStudy: a
// submission either uploads the chosen file fresh, or - if the preview
// tool was used and its result applied - reuses the already-uploaded
// geometry plus the chosen rotation instead (see POST /jobs etc.'s
// preview_id/manual_rotation_label fields).
function appendStepFileOrPreview(form, fileInput) {
  if (activeGeometryPreview) {
    form.append("preview_id", activeGeometryPreview.previewId);
    form.append("manual_rotation_label", activeGeometryPreview.label);
  } else {
    form.append("step_file", fileInput.files[0]);
  }
}

function renderRotationCandidates(data, selectedLabel) {
  const container = document.getElementById("rotation-preview-candidates");
  container.innerHTML = "";
  for (const candidate of data.candidates) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "rotation-candidate-btn" + (candidate.label === selectedLabel ? " active" : "");

    const title = document.createElement("div");
    title.className = "candidate-title";
    const dot = document.createElement("span");
    dot.className = "candidate-dot " + (candidate.plausible ? "plausible" : "implausible");
    title.appendChild(dot);
    const labelText = (ROTATION_LABEL_TEXT[candidate.label] || candidate.label)
      + (candidate.label === data.suggested_label ? " (Vorschlag)" : "");
    title.appendChild(document.createTextNode(labelText));
    btn.appendChild(title);

    const numbers = document.createElement("div");
    numbers.className = "candidate-numbers";
    numbers.textContent =
      "Sehne=" + candidate.chord.toFixed(1) + " mm · Spannweite=" + candidate.span.toFixed(1) +
      " mm · Dicke=" + candidate.thickness.toFixed(1) + " mm · Dicke/Sehne=" +
      (candidate.thickness_ratio * 100).toFixed(0) + "%";
    btn.appendChild(numbers);

    btn.addEventListener("click", () => selectRotationCandidate(data, candidate.label));
    container.appendChild(btn);
  }
}

function selectRotationCandidate(data, label) {
  selectedPreviewLabel = label;
  renderRotationCandidates(data, label);
  const variant = data.variants.find((v) => v.label === label);
  if (variant) renderRotationPreviewVariant(variant);
}

async function openGeometryPreview() {
  const fileInput = document.getElementById("step_file");
  if (!fileInput.files.length) return;

  document.getElementById("rotation-preview-overlay").hidden = false;
  document.getElementById("rotation-preview-status").textContent =
    "Lade Geometrie und berechne alle moeglichen Ausrichtungen ...";
  document.getElementById("rotation-preview-candidates").innerHTML = "";
  disposeRotationPreview3D();
  currentPreviewData = null;
  selectedPreviewLabel = null;

  const form = new FormData();
  form.append("step_file", fileInput.files[0]);

  let res;
  try {
    res = await fetch("/geometry/preview", { method: "POST", headers: authHeaders(), body: form });
  } catch (err) {
    document.getElementById("rotation-preview-status").textContent = "Netzwerkfehler: " + err;
    return;
  }
  if (res.status === 401) { reloadToRefreshToken(); return; }
  if (!res.ok) {
    const detail = await res.text();
    document.getElementById("rotation-preview-status").textContent =
      "Konnte Geometrie nicht laden (" + res.status + "): " + detail;
    return;
  }

  const data = await res.json();
  currentPreviewData = data;
  const initialLabel = data.suggested_label || "identity";
  document.getElementById("rotation-preview-status").textContent = data.confident
    ? "Automatisch erkannt: " + (ROTATION_LABEL_TEXT[initialLabel] || initialLabel) +
      ". Bei Bedarf unten eine andere Ausrichtung waehlen."
    : "Keine Ausrichtung konnte automatisch sicher bestimmt werden - bitte unten anhand der " +
      "3D-Vorschau die passende Ausrichtung waehlen.";
  selectRotationCandidate(data, initialLabel);
}

function closeGeometryPreview() {
  document.getElementById("rotation-preview-overlay").hidden = true;
  disposeRotationPreview3D();
}

document.getElementById("geometry-preview-btn").addEventListener("click", openGeometryPreview);
document.getElementById("rotation-preview-close-btn").addEventListener("click", closeGeometryPreview);
document.getElementById("rotation-preview-cancel-btn").addEventListener("click", closeGeometryPreview);
document.getElementById("rotation-preview-overlay").addEventListener("click", (e) => {
  if (e.target.id === "rotation-preview-overlay") closeGeometryPreview();
});
document.getElementById("rotation-preview-apply-btn").addEventListener("click", () => {
  if (!currentPreviewData || !selectedPreviewLabel) return;
  activeGeometryPreview = { previewId: currentPreviewData.preview_id, label: selectedPreviewLabel };
  document.getElementById("geometry-preview-status").textContent =
    "Ausrichtung gewaehlt: " + (ROTATION_LABEL_TEXT[selectedPreviewLabel] || selectedPreviewLabel);
  closeGeometryPreview();
});

// "Neue Berechnung" (topbar): resets the one unified form back to its
// defaults and clears the current result, same as reloading used to
// implicitly do before there was a persistent single-window shell.
document.getElementById("topbar-new-btn").addEventListener("click", () => {
  document.getElementById("case-form").reset();
  updateFileInputName();
  updateGciCheckAvailability();
  history.replaceState(null, "", window.location.pathname);
  setResultPanelVisible(false);
  document.getElementById("console-panel").hidden = true;
  document.getElementById("console-toggle-icon").innerHTML = "&#9656;";
  setError(null);
  document.getElementById("status").textContent = "";
  disposeViewer3D();
  closeGeometryPreview();
});

// One text field accepts either a single angle ("5") or a comma-
// separated list ("0, 5, 10") - see docs/ARCHITECTURE.md "virtueller
// Windkanal, nicht drei Tools": which of the three existing endpoints
// (/jobs, /polar-studies, /gci-studies) gets called is decided from
// this plus the GCI checkbox below, the user never explicitly picks a
// "tool". A GCI mesh-quality check only exists today for a single
// angle (gci-studies has no aoa_values-list equivalent), so entering
// more than one angle disables the checkbox rather than silently
// ignoring it.
function parseAoaValues() {
  return document.getElementById("aoa_input").value
    .split(",").map((s) => s.trim()).filter((s) => s.length > 0);
}

let gciCheckWasAutoDisabled = false;

function updateGciCheckAvailability() {
  const multiple = parseAoaValues().length > 1;
  const checkbox = document.getElementById("gci_check");
  document.getElementById("gci-disabled-hint").hidden = !multiple;
  if (multiple && !checkbox.disabled) {
    checkbox.disabled = true;
    checkbox.checked = false;
    gciCheckWasAutoDisabled = true;
  } else if (!multiple && checkbox.disabled) {
    checkbox.disabled = false;
    if (gciCheckWasAutoDisabled) checkbox.checked = true; // restore the sensible default, not a user choice
    gciCheckWasAutoDisabled = false;
  }
}
document.getElementById("aoa_input").addEventListener("input", updateGciCheckAvailability);
updateGciCheckAvailability();

function getJobIdFromUrl() {
  return new URLSearchParams(window.location.search).get("job");
}

const resumeJobId = getJobIdFromUrl();
if (resumeJobId) {
  // Reopening a link (another device, or the same tab after closing it)
  // shows the status of the existing job right away instead of an empty
  // upload form, see docs/RISKS.md R14.
  document.getElementById("status").textContent = "Lade Status von Job " + resumeJobId + " ...";
  pollJob(resumeJobId);
}

// One unified submit handler replaces the three former form handlers
// (single job / polar study / GCI study) - see docs/ARCHITECTURE.md
// "virtueller Windkanal, nicht drei Tools": the user only fills in one
// form, how many angles and whether the GCI checkbox is on (and
// available at all) decide which of the three unchanged, existing
// endpoints actually gets called. No backend change: this is a pure
// client-side routing decision over /jobs, /polar-studies, /gci-studies.
document.getElementById("case-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError(null);
  const btn = document.getElementById("submit-btn");
  btn.disabled = true;

  try {
    const fileInput = document.getElementById("step_file");
    if (!fileInput.files.length) { setError("Bitte eine STEP-Datei waehlen."); return; }

    const aoaValues = parseAoaValues();
    if (aoaValues.length === 0) { setError("Bitte mindestens einen Anstellwinkel angeben."); return; }

    const gciCheckbox = document.getElementById("gci_check");
    const gciChecked = gciCheckbox.checked && !gciCheckbox.disabled;
    // Defensive, not just UI-prevented (CLAUDE.md: no silent fallbacks):
    // there is no endpoint for "GCI at several angles at once" today, so
    // this impossible combination is refused loudly rather than quietly
    // picking one of the two meanings for the user.
    if (gciChecked && aoaValues.length > 1) {
      setError("Netzqualitaetspruefung ist nur fuer einen einzelnen Anstellwinkel verfuegbar. Bitte entweder nur einen Winkel angeben oder den Haken entfernen.");
      return;
    }

    if (aoaValues.length > 1) {
      await submitPolarStudy(fileInput, aoaValues);
    } else if (gciChecked) {
      await submitGciStudy(fileInput, aoaValues[0]);
    } else {
      await submitSingleJob(fileInput, aoaValues[0]);
    }
  } catch (err) {
    setError("Unerwarteter Fehler: " + err);
  } finally {
    btn.disabled = false;
  }
});

async function submitSingleJob(fileInput, aoaDeg) {
  setResultPanelVisible(false);
  document.getElementById("console-panel").hidden = true;
  document.getElementById("status").textContent = "Lade Datei hoch und starte Berechnung ...";

  const form = new FormData();
  appendStepFileOrPreview(form, fileInput);
  form.append("velocity", document.getElementById("velocity").value);
  form.append("aoa_deg", aoaDeg);
  form.append("sideslip_deg", document.getElementById("sideslip_deg").value);
  appendAdvancedParams(form);

  const res = await fetch("/jobs", { method: "POST", headers: authHeaders(), body: form });
  if (res.status === 401) {
    document.getElementById("status").textContent = "Token abgelaufen (Engine wurde neu gestartet), lade Seite neu ...";
    reloadToRefreshToken();
    return;
  }
  if (!res.ok) {
    const detail = await res.text();
    setError("Konnte Berechnung nicht starten (" + res.status + "): " + detail);
    return;
  }
  const job = await res.json();
  // Put the job id in the address bar so this exact status page can be
  // reopened from any device by reusing the link, and survives closing
  // this tab, see docs/RISKS.md R14.
  history.replaceState(null, "", "?job=" + job.id);
  document.getElementById("status").textContent = "Berechnung " + job.id + " gestartet.";
  loadArchiveList();
  await pollJob(job.id);
}

async function submitGciStudy(fileInput, aoaDeg) {
  document.getElementById("status").textContent = "Lade Datei hoch und starte Netzqualitaetspruefung (3 Aufloesungen) ...";

  const form = new FormData();
  appendStepFileOrPreview(form, fileInput);
  form.append("velocity", document.getElementById("velocity").value);
  form.append("aoa_deg", aoaDeg);
  form.append("sideslip_deg", document.getElementById("sideslip_deg").value);
  form.append("refinement_ratio", document.getElementById("refinement_ratio").value);
  appendAdvancedParams(form);

  const res = await fetch("/gci-studies", { method: "POST", headers: authHeaders(), body: form });
  if (res.status === 401) { reloadToRefreshToken(); return; }
  if (!res.ok) {
    const detail = await res.text();
    setError("Konnte Netzqualitaetspruefung nicht starten (" + res.status + "): " + detail);
    return;
  }
  const study = await res.json();
  document.getElementById("status").textContent =
    "Netzqualitaetspruefung gestartet (3 Aufloesungen, dauert deutlich laenger als eine Einzelrechnung) - Fortschritt im Archiv.";
  fileInput.value = "";
  updateFileInputName(); // programmatic .value reset fires no "change" event
  expandedArchiveEntries.add("gci:" + study.id);
  openArchive();
}

async function submitPolarStudy(fileInput, aoaValues) {
  document.getElementById("status").textContent = "Lade Datei hoch und starte Polare (" + aoaValues.length + " Winkel) ...";

  const form = new FormData();
  appendStepFileOrPreview(form, fileInput);
  form.append("velocity", document.getElementById("velocity").value);
  for (const v of aoaValues) form.append("aoa_values", v);
  form.append("sideslip_deg", document.getElementById("sideslip_deg").value);
  appendAdvancedParams(form);

  const res = await fetch("/polar-studies", { method: "POST", headers: authHeaders(), body: form });
  if (res.status === 401) { reloadToRefreshToken(); return; }
  if (!res.ok) {
    const detail = await res.text();
    setError("Konnte Polare nicht starten (" + res.status + "): " + detail);
    return;
  }
  const study = await res.json();
  document.getElementById("status").textContent =
    "Polare gestartet (" + aoaValues.length + " Winkel) - Fortschritt im Archiv.";
  fileInput.value = "";
  updateFileInputName(); // programmatic .value reset fires no "change" event
  expandedArchiveEntries.add("polar:" + study.id);
  openArchive();
}
