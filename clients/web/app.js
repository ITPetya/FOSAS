const TOKEN = "__FOSAS_TOKEN__";

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
  aoa_deg: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Anstellwinkel (Angle of Attack)</h4>
    <p>Der Winkel zwischen der Sehnenlinie des Profils (gerade Linie von
    Vorder- zu Hinterkante) und der ankommenden Luftstroemung.</p>
    <p>Groesserer Anstellwinkel erzeugt normalerweise mehr Auftrieb, aber
    auch mehr Widerstand, bis zu einem Punkt (Stroemungsabriss/Stall),
    ab dem der Auftrieb einbricht. FOSAS erkennt einen Stall nicht
    automatisch, ein stationaerer Loeser wie dieser kann in der Naehe
    eines Stalls zusaetzlich schlechter konvergieren.</p>
  `,
  aoa_values: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Anstellwinkel-Liste</h4>
    <p>Mehrere Anstellwinkel durch Komma getrennt, z. B. "0, 5, 10, 15".
    Fuer jeden Wert wird ein eigenstaendiger, unabhaengiger Auftrag
    gestartet (siehe docs/DECISIONS.md ADR-0017); die Ergebnisse werden
    danach gemeinsam als Polare (cl/cd ueber Anstellwinkel) dargestellt.</p>
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
  resultant_force: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Resultierende R</h4>
    <p>R = Wurzel(L^2 + D^2), die geometrische Summe aus Auftrieb und
    Widerstand, dieselbe Vektoraddition wie bei jedem zentralen
    Kraeftesystem in der Technischen Mechanik. Der Winkel dieser
    Resultierenden zur Anstroemrichtung ergibt sich aus
    atan2(L, D).</p>
  `,
  resultant_angle: `
    <span class="tag gesichert">Gesichert</span>
    <h4>Winkel der Resultierenden</h4>
    <p>Winkel zwischen der Resultierenden R und der Anstroemrichtung
    (= Widerstandsrichtung), berechnet per atan2(L, D). 0 Grad hiesse:
    die gesamte Kraft zeigt genau in Widerstandsrichtung, kein Auftrieb.
    90 Grad hiesse: reiner Auftrieb, kein Widerstand. Ueblich fuer ein
    Fluegelprofil im normalen Betriebsbereich ist ein Wert nahe 90 Grad
    (viel Auftrieb, wenig Widerstand im Vergleich).</p>
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
    Reibungsanteil ist ebenfalls noch nicht umgesetzt (braucht eine
    echte Flaechenintegration ueber alle Netzzellen, nicht nur diese
    punktweisen Werte).</p>
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

function paramFields() {
  return [
    "velocity", "aoa_deg", "density", "dynamic_viscosity", "temperature",
    "target_y_plus", "growth_ratio", "bl_thickness_factor", "span_layers",
    "n_profile_points", "max_iterations", "mpi_ranks", "time_discretization",
    "residual_threshold",
  ];
}

// The "Erweiterte Einstellungen" field set shared by all three forms
// (single job, polar study, GCI study) - everything except the fields
// each form handles on its own (velocity, aoa_deg/aoa_values,
// refinement_ratio). Used with an id prefix ("polar-"/"gci-") on the
// two new study forms to avoid id collisions with the original,
// unprefixed #case-form fields.
function advancedParamFieldNames() {
  return [
    "density", "dynamic_viscosity", "temperature", "target_y_plus",
    "growth_ratio", "bl_thickness_factor", "span_layers", "n_profile_points",
    "max_iterations", "mpi_ranks", "time_discretization", "residual_threshold",
  ];
}

function appendAdvancedParams(form, idPrefix) {
  for (const name of advancedParamFieldNames()) {
    form.append(name, document.getElementById(idPrefix + name).value);
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
  const maxMag = Math.max(Math.abs(lift), Math.abs(drag), resultant, 1e-12);
  // Fixed pixel length for the largest force arrow, independent of the
  // drawing's own px-per-metre scale: a force arrow is a separate,
  // schematic quantity, not something drawn to the same physical scale
  // as the body outline (see INFO_TEXT.free_body_diagram).
  const maxArrowPx = Math.min(W, H) * 0.3;

  function drawArrow(dirBody, signedMag, color, label) {
    const mag = Math.abs(signedMag);
    if (mag < 1e-12) return;
    const sign = signedMag < 0 ? -1 : 1;
    const lengthPx = (mag / maxMag) * maxArrowPx;
    const dx = dirBody.x * sign, dz = dirBody.z * sign;
    const normLen = Math.hypot(dx, dz) || 1;
    // Flip z for pixels (same sy() convention: +z body is "up", up is
    // smaller SVG y).
    const endX = originPx.x + (dx / normLen) * lengthPx;
    const endY = originPx.y - (dz / normLen) * lengthPx;

    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", originPx.x); line.setAttribute("y1", originPx.y);
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

  drawArrow(dragDir, drag, "#e0a72f", "D = " + drag.toPrecision(3) + " N");
  drawArrow(liftDir, lift, "#4f8cff", "L = " + lift.toPrecision(3) + " N");
  const resVec = { x: dragDir.x * drag + liftDir.x * lift, z: dragDir.z * drag + liftDir.z * lift };
  drawArrow(resVec, resultant, "#eeeeee", "R = " + resultant.toPrecision(3) + " N");

  document.getElementById("fbd-legend").textContent =
    "Grauer Punkt: Momenten-Bezugspunkt (Pfeile setzen dort an, nicht am tatsaechlichen Druckpunkt). " +
    "Pfeillaenge nur relativ zueinander massstabsgetreu, nicht zur Koerpergroesse.";
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

  const coordLayer = buildCoordLayer(result.aoa_deg);
  scene.add(coordLayer);

  const momentOriginScene = bodyPointToScene(
    result.moments.moment_origin[0], result.moments.moment_origin[1], result.moments.moment_origin[2],
    cx, cy, cz, extent,
  );
  const forcesLayer = buildForcesLayer(result, momentOriginScene);
  scene.add(forcesLayer);

  // Exact colors THREE.AxesHelper itself renders (pure red/green/blue
  // vertex colors), not just a similar-looking tone, so the legend text
  // and the 3D lines are unambiguously the same color to the eye.
  document.getElementById("viewer3d-overlay-legend").innerHTML =
    "Achsen: <span style=\"color:#ff3333\">X</span> stromab, " +
    "<span style=\"color:#33ff33\">Y</span> Spannweite, " +
    "<span style=\"color:#3366ff\">Z</span> vertikal, " +
    "<span style=\"color:#eeeeee\">weiss</span> Windachse (α=" + result.aoa_deg.toFixed(1) + "°) &middot; " +
    "Kraftpfeile: <span style=\"color:#e0a72f\">D</span>=" + result.forces.drag.toPrecision(3) + " N, " +
    "<span style=\"color:#4f8cff\">L</span>=" + result.forces.lift.toPrecision(3) + " N, " +
    "<span style=\"color:#eeeeee\">R</span>=" + result.forces.resultant.toPrecision(3) + " N";

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

// Simple colored-line coordinate triad (body axes) plus the wind-axis
// direction arrow and an angle arc for alpha, all anchored at the scene
// origin (the body's own bounding-box center, same point the old
// AxesHelper used). No sideslip angle arc: beta is not modelled by
// fosas_core yet, see INFO_TEXT.viewer_layer_coord.
function buildCoordLayer(aoaDeg) {
  const group = new THREE.Group();
  group.add(new THREE.AxesHelper(0.7));

  const aoaRad = (aoaDeg * Math.PI) / 180;
  const windDirBody = { x: Math.cos(aoaRad), y: 0, z: Math.sin(aoaRad) };
  const windDirScene = bodyDirToScene(windDirBody.x, windDirBody.y, windDirBody.z).normalize();
  const windArrow = new THREE.ArrowHelper(windDirScene, new THREE.Vector3(0, 0, 0), 0.9, 0xeeeeee, 0.12, 0.06);
  group.add(windArrow);

  // Angle arc between the body +X axis and the wind direction, swept
  // through the actual aoa_deg (not just a fixed decorative arc), same
  // X-Z body plane since there is no sideslip.
  const arcRadius = 0.35;
  const arcSteps = 24;
  const arcPoints = [];
  for (let i = 0; i <= arcSteps; i++) {
    const t = (aoaRad * i) / arcSteps;
    arcPoints.push(bodyDirToScene(Math.cos(t) * arcRadius, 0, Math.sin(t) * arcRadius));
  }
  const arcGeometry = new THREE.BufferGeometry().setFromPoints(arcPoints);
  const arcLine = new THREE.Line(arcGeometry, new THREE.LineBasicMaterial({ color: 0xeeeeee }));
  group.add(arcLine);

  return group;
}

// Force arrows (D along the wind direction, L perpendicular to it, R as
// their vector sum), anchored at the moment reference point (not the
// true center of pressure, see INFO_TEXT.viewer_layer_forces), scaled so
// the largest of the three has a fixed visual length regardless of the
// forces' actual physical magnitude (otherwise a small validation case's
// micro-Newton forces would render as invisible, zero-length arrows).
function buildForcesLayer(result, originScene) {
  const group = new THREE.Group();
  const aoaRad = (result.aoa_deg * Math.PI) / 180;
  const dragDirBody = { x: Math.cos(aoaRad), y: 0, z: Math.sin(aoaRad) };
  // +90 degrees from the drag/wind direction in the body X-Z plane; at
  // alpha=0 this is body +Z ("up"), matching the usual lift convention.
  const liftDirBody = { x: -Math.sin(aoaRad), y: 0, z: Math.cos(aoaRad) };

  const lift = result.forces.lift, drag = result.forces.drag, resultant = result.forces.resultant;
  const maxMag = Math.max(Math.abs(lift), Math.abs(drag), resultant, 1e-12);
  const visualScale = 0.9 / maxMag;

  function addArrow(dirBody, signedMagnitude, color) {
    const mag = Math.abs(signedMagnitude);
    if (mag < 1e-12) return; // zero-length ArrowHelper direction is undefined, skip instead
    const sign = signedMagnitude < 0 ? -1 : 1;
    const dirScene = bodyDirToScene(dirBody.x * sign, dirBody.y * sign, dirBody.z * sign).normalize();
    group.add(new THREE.ArrowHelper(dirScene, originScene, mag * visualScale, color, 0.1, 0.05));
  }

  addArrow(dragDirBody, drag, 0xe0a72f);
  addArrow(liftDirBody, lift, 0x4f8cff);

  const resultantVecBody = {
    x: dragDirBody.x * drag + liftDirBody.x * lift,
    y: 0,
    z: dragDirBody.z * drag + liftDirBody.z * lift,
  };
  addArrow(resultantVecBody, resultant, 0xeeeeee);

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
    "",
    "Mx = CMx * q * A * l = " + fmt(result.moments.cmx) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.mx) + " Nm",
    "My = CMy * q * A * l = " + fmt(result.moments.cmy) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.my) + " Nm",
    "Mz = CMz * q * A * l = " + fmt(result.moments.cmz) + " * " + fmt(q) + " * " +
      fmt(A) + " * " + fmt(l) + " = " + fmt(result.moments.mz) + " Nm",
  ];
  document.getElementById("calculation-steps-text").textContent = lines.join("\n");
}

function renderResult(result, jobId) {
  currentResultJobId = jobId;
  document.getElementById("fullscreen-link").href = "/viewer?job=" + jobId;
  document.getElementById("result-panel").hidden = false;
  document.getElementById("cl-value").textContent = result.cl.toFixed(4);
  document.getElementById("cd-value").textContent = result.cd.toFixed(4);
  document.getElementById("yplus-value").textContent = result.mean_y_plus.toFixed(2);
  document.getElementById("tau-mean-value").textContent = result.mean_wall_shear_stress.toPrecision(3);
  document.getElementById("tau-max-value").textContent = result.max_wall_shear_stress.toPrecision(3);
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
  const panel = document.getElementById("progress-panel");
  const fill = document.getElementById("progress-fill");
  const label = document.getElementById("progress-label");
  const etaEl = document.getElementById("progress-eta");

  if (job.status === "done") {
    panel.hidden = true;
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
  const statusEl = document.getElementById("status");
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
  history.replaceState(null, "", "?job=" + jobId);
  document.getElementById("result-panel").hidden = true;
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
  loadJobsList();
}

async function unarchiveJob(jobId) {
  await fetch("/jobs/" + jobId + "/unarchive", { method: "POST", headers: authHeaders() });
  loadJobsList();
}

async function deleteJobPrompt(jobId, filename) {
  if (!confirm("Auftrag \"" + filename + "\" endgueltig loeschen? Das entfernt auch alle zugehoerigen Dateien (Netz, Ergebnisse) und kann nicht rueckgaengig gemacht werden.")) {
    return;
  }
  await fetch("/jobs/" + jobId, { method: "DELETE", headers: authHeaders() });
  loadJobsList();
}

document.getElementById("archive-toggle-btn").addEventListener("click", () => {
  showingArchived = !showingArchived;
  document.getElementById("archive-toggle-btn").className = "archive-toggle-btn" + (showingArchived ? " active" : "");
  document.getElementById("jobs-title").textContent = showingArchived ? "Archiv" : "Auftraege";
  loadJobsList();
});

async function loadJobsList() {
  const listEl = document.getElementById("jobs-list");
  let jobs;
  try {
    const url = showingArchived ? "/jobs?archived=true" : "/jobs";
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) return; // transient hiccup: leave the previously shown list as-is
    jobs = await res.json();
  } catch (err) {
    return; // offline for a moment: same, do not clobber the visible list
  }

  if (jobs.length === 0) {
    listEl.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "jobs-empty";
    empty.textContent = showingArchived ? "Archiv ist leer." : "Noch keine Auftraege.";
    listEl.appendChild(empty);
    return;
  }

  jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  listEl.innerHTML = "";
  for (const job of jobs) {
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
    metaEl.textContent = statusLabel(job) + " · " + formatRelativeTime(job.created_at);
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
    row.addEventListener("click", () => selectJob(job.id));
    listEl.appendChild(row);
  }
}

loadJobsList();
setInterval(loadJobsList, 4000);

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

async function loadPolarStudiesList() {
  const listEl = document.getElementById("polar-studies-list");
  let studies;
  try {
    const res = await fetch("/polar-studies", { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) return;
    studies = await res.json();
  } catch (err) {
    return;
  }

  populateStudySelect("combined-report-polar-select", studies);

  if (studies.length === 0) {
    listEl.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "jobs-empty";
    empty.textContent = "Noch keine Polarstudien.";
    listEl.appendChild(empty);
    return;
  }

  studies.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  listEl.innerHTML = "";
  for (const study of studies) {
    const expanded = expandedStudies.has(study.id);
    const row = formatStudyRow(study.step_filename, study.status, formatStudyDetail(study, "points"), () => {
      expandedStudies.has(study.id) ? expandedStudies.delete(study.id) : expandedStudies.add(study.id);
      loadPolarStudiesList();
    });
    listEl.appendChild(row);
    if (expanded) {
      const anyPlotted = study.points.some((p) => p.cl != null && p.cd != null);
      if (anyPlotted) {
        const { wrap, svgCl, svgCd } = buildDualChartPair();
        listEl.appendChild(wrap);
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
      listEl.appendChild(table);

      const reportBtn = document.createElement("button");
      reportBtn.type = "button";
      reportBtn.className = "job-action-btn";
      reportBtn.textContent = "Bericht (PDF)";
      reportBtn.addEventListener("click", () => downloadPolarReport(study.id, study.step_filename));
      listEl.appendChild(reportBtn);
    }
  }
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

async function loadGciStudiesList() {
  const listEl = document.getElementById("gci-studies-list");
  let studies;
  try {
    const res = await fetch("/gci-studies", { headers: authHeaders() });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) return;
    studies = await res.json();
  } catch (err) {
    return;
  }

  populateStudySelect("combined-report-gci-select", studies);

  if (studies.length === 0) {
    listEl.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "jobs-empty";
    empty.textContent = "Noch keine GCI-Netzstudien.";
    listEl.appendChild(empty);
    return;
  }

  studies.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  listEl.innerHTML = "";
  for (const study of studies) {
    const expanded = expandedStudies.has(study.id);
    const row = formatStudyRow(study.step_filename, study.status, formatStudyDetail(study, "levels"), () => {
      expandedStudies.has(study.id) ? expandedStudies.delete(study.id) : expandedStudies.add(study.id);
      loadGciStudiesList();
    });
    listEl.appendChild(row);
    if (expanded) {
      const anyPlotted = study.levels.some((l) => l.element_count != null && l.cl != null);
      if (anyPlotted) {
        const { wrap, svgCl, svgCd } = buildDualChartPair();
        listEl.appendChild(wrap);
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
      listEl.appendChild(table);
      if (study.result) {
        const resultEl = document.createElement("p");
        resultEl.className = "hint";
        resultEl.textContent = "cl: " + study.result.cl.message + " / cd: " + study.result.cd.message;
        listEl.appendChild(resultEl);
      } else if (study.result_error) {
        const errEl = document.createElement("p");
        errEl.className = "hint";
        errEl.textContent = "GCI konnte nicht berechnet werden: " + study.result_error;
        listEl.appendChild(errEl);
      }

      const reportBtn = document.createElement("button");
      reportBtn.type = "button";
      reportBtn.className = "job-action-btn";
      reportBtn.textContent = "Bericht (PDF)";
      reportBtn.addEventListener("click", () => downloadGciReport(study.id, study.step_filename));
      listEl.appendChild(reportBtn);
    }
  }
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

const expandedStudies = new Set();
loadPolarStudiesList();
loadGciStudiesList();
setInterval(loadPolarStudiesList, 4000);
setInterval(loadGciStudiesList, 4000);

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

document.getElementById("case-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError(null);
  document.getElementById("result-panel").hidden = true;
  document.getElementById("progress-panel").hidden = true;
  const btn = document.getElementById("submit-btn");
  btn.disabled = true;
  document.getElementById("status").textContent = "Lade Datei hoch und starte Job ...";

  try {
    const fileInput = document.getElementById("step_file");
    if (!fileInput.files.length) { setError("Bitte eine STEP-Datei waehlen."); return; }

    const form = new FormData();
    form.append("step_file", fileInput.files[0]);
    for (const name of paramFields()) {
      form.append(name, document.getElementById(name).value);
    }

    const res = await fetch("/jobs", { method: "POST", headers: authHeaders(), body: form });
    if (res.status === 401) {
      document.getElementById("status").textContent = "Token abgelaufen (Engine wurde neu gestartet), lade Seite neu ...";
      reloadToRefreshToken();
      return;
    }
    if (!res.ok) {
      const detail = await res.text();
      setError("Konnte Job nicht starten (" + res.status + "): " + detail);
      return;
    }
    const job = await res.json();
    // Put the job id in the address bar so this exact status page can be
    // reopened from any device by reusing the link, and survives closing
    // this tab, see docs/RISKS.md R14.
    history.replaceState(null, "", "?job=" + job.id);
    document.getElementById("status").textContent = "Job " + job.id + " gestartet.";
    loadJobsList();
    await pollJob(job.id);
  } catch (err) {
    setError("Unerwarteter Fehler: " + err);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("polar-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setFormError("polar-error", null);
  const btn = document.getElementById("polar-submit-btn");
  btn.disabled = true;
  document.getElementById("polar-status").textContent = "Lade Datei hoch und starte Polarstudie ...";

  try {
    const fileInput = document.getElementById("polar-step_file");
    if (!fileInput.files.length) { setFormError("polar-error", "Bitte eine STEP-Datei waehlen."); return; }

    const aoaText = document.getElementById("polar-aoa_values").value;
    const aoaValues = aoaText.split(",").map((s) => s.trim()).filter((s) => s.length > 0);
    if (aoaValues.length === 0) {
      setFormError("polar-error", "Bitte mindestens einen Anstellwinkel angeben.");
      return;
    }

    const form = new FormData();
    form.append("step_file", fileInput.files[0]);
    form.append("velocity", document.getElementById("polar-velocity").value);
    for (const v of aoaValues) form.append("aoa_values", v);
    appendAdvancedParams(form, "polar-");

    const res = await fetch("/polar-studies", { method: "POST", headers: authHeaders(), body: form });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) {
      const detail = await res.text();
      setFormError("polar-error", "Konnte Polarstudie nicht starten (" + res.status + "): " + detail);
      return;
    }
    document.getElementById("polar-status").textContent = "Polarstudie gestartet.";
    fileInput.value = "";
    loadPolarStudiesList();
  } catch (err) {
    setFormError("polar-error", "Unerwarteter Fehler: " + err);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("gci-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setFormError("gci-error", null);
  const btn = document.getElementById("gci-submit-btn");
  btn.disabled = true;
  document.getElementById("gci-status").textContent = "Lade Datei hoch und starte GCI-Studie ...";

  try {
    const fileInput = document.getElementById("gci-step_file");
    if (!fileInput.files.length) { setFormError("gci-error", "Bitte eine STEP-Datei waehlen."); return; }

    const form = new FormData();
    form.append("step_file", fileInput.files[0]);
    form.append("velocity", document.getElementById("gci-velocity").value);
    form.append("aoa_deg", document.getElementById("gci-aoa_deg").value);
    form.append("refinement_ratio", document.getElementById("gci-refinement_ratio").value);
    appendAdvancedParams(form, "gci-");

    const res = await fetch("/gci-studies", { method: "POST", headers: authHeaders(), body: form });
    if (res.status === 401) { reloadToRefreshToken(); return; }
    if (!res.ok) {
      const detail = await res.text();
      setFormError("gci-error", "Konnte GCI-Studie nicht starten (" + res.status + "): " + detail);
      return;
    }
    document.getElementById("gci-status").textContent = "GCI-Studie gestartet.";
    fileInput.value = "";
    loadGciStudiesList();
  } catch (err) {
    setFormError("gci-error", "Unerwarteter Fehler: " + err);
  } finally {
    btn.disabled = false;
  }
});
