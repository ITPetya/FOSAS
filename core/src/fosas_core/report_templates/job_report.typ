// Einzelauftrags-Bericht (Phase 3, Punkt 11 der Technische-Mechanik-
// Visualisierung, siehe docs/ARCHITECTURE.md). Spiegelt das
// Ergebnis-Panel der Hauptseite auf Papier, gleiches Vorgehen wie die
// anderen Berichte: Diagramme komplett in Python (matplotlib)
// vorgerendert, kein "@preview"-Paket-Import, siehe fosas_core.report
// fuer die Begruendung.
//
// Erwartet "/data.json", "/cp_chart.png" und "/fbd_chart.png" im
// selben root-Verzeichnis.

#set page(margin: 2cm)
#set text(size: 11pt, lang: "de")

#let data = json("/data.json")

#let fmt_num(x, digits: 4) = if x == none { "-" } else { str(calc.round(x, digits: digits)) }
#let header_fill = rgb("#e9ecef")
#let table_fill(col, row) = if row == 0 { header_fill } else { white }

= FOSAS Einzelauftrags-Bericht

*Datei:* #data.step_filename \
*Erzeugt:* #data.generated_at \
*Anstellwinkel:* #fmt_num(data.aoa_deg, digits: 2) Grad

Automatisch erzeugter Bericht. Dieser Bericht enthaelt ausschliesslich
diesen einen Rechenzustand; er ersetzt nicht die Einordnung in der
Projekt-Dokumentation (insbesondere offene Risiken, siehe
docs/RISKS.md, u. a. R10 zur Konvergenzfrage).

#if not data.converged [
  #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Dieser Zustand ist nicht konvergiert. #data.convergence_message
    Die Werte unten sind entsprechend nicht als belastbares Endergebnis
    zu verstehen.
  ]
]

== Kraftbeiwerte und Anstroemung

#table(
  columns: 4,
  fill: table_fill,
  [*cl*], [*cd*], [*Staudruck q (Pa)*], [*Reynolds-Zahl*],
  fmt_num(data.cl), fmt_num(data.cd), fmt_num(data.dynamic_pressure, digits: 2),
  str(calc.round(data.reynolds_number, digits: 0)),
)

== Kraeftesystem (Windachsen)

*Bezugsflaeche A:* #fmt_num(data.reference_area, digits: 6) m^2 (Grundrissflaeche, Sehnenlaenge \* Spannweite)

#table(
  columns: 5,
  fill: table_fill,
  [*Auftrieb L (N)*], [*Widerstand D (N)*], [*Resultierende R (N)*], [*Gleitzahl L/D*], [*Winkel R (Grad)*],
  fmt_num(data.lift, digits: 6), fmt_num(data.drag, digits: 6), fmt_num(data.resultant, digits: 6),
  fmt_num(data.glide_ratio, digits: 3), fmt_num(data.resultant_angle_deg, digits: 2),
)

== Momente

*Bezugspunkt (aktuell fest, noch nicht waehlbar):* x=#fmt_num(data.moment_origin.at(0), digits: 4) m,
y=#fmt_num(data.moment_origin.at(1), digits: 4) m, z=#fmt_num(data.moment_origin.at(2), digits: 4) m \
*Bezugslaenge l:* #fmt_num(data.reference_length, digits: 4) m

#table(
  columns: 6,
  fill: table_fill,
  [*cmx*], [*cmy*], [*cmz*], [*Mx (Nm)*], [*My (Nm)*], [*Mz (Nm)*],
  fmt_num(data.cmx, digits: 4), fmt_num(data.cmy, digits: 4), fmt_num(data.cmz, digits: 4),
  fmt_num(data.mx, digits: 6), fmt_num(data.my, digits: 6), fmt_num(data.mz, digits: 6),
)

#block(fill: rgb("#d1ecf1"), inset: 8pt, radius: 4pt, width: 100%)[
  *Hinweis:* Mx und Mz sind bei einem Koerper mit konstantem Querschnitt
  entlang der Spannweite physikalisch meist klein; ein von null
  abweichender Wert ist hier oft Netzaufloesungs-Rauschen, keine reale
  Kraftwirkung (siehe docs/ARCHITECTURE.md).
]

== Rechenweg

Dieselben Formeln wie oben, hier mit den tatsaechlichen Zahlen dieser
Rechnung aufgeschrieben (F = c \* q \* A, M = cm \* q \* A \* l):

#block[
  L = CL \* q \* A = #fmt_num(data.cl) \* #fmt_num(data.dynamic_pressure, digits: 2) \* #fmt_num(data.reference_area, digits: 6) = #fmt_num(data.lift, digits: 6) N \
  D = CD \* q \* A = #fmt_num(data.cd) \* #fmt_num(data.dynamic_pressure, digits: 2) \* #fmt_num(data.reference_area, digits: 6) = #fmt_num(data.drag, digits: 6) N \
  Mx = CMx \* q \* A \* l = #fmt_num(data.cmx) \* #fmt_num(data.dynamic_pressure, digits: 2) \* #fmt_num(data.reference_area, digits: 6) \* #fmt_num(data.reference_length, digits: 4) = #fmt_num(data.mx, digits: 6) Nm \
  My = CMy \* q \* A \* l = #fmt_num(data.cmy) \* #fmt_num(data.dynamic_pressure, digits: 2) \* #fmt_num(data.reference_area, digits: 6) \* #fmt_num(data.reference_length, digits: 4) = #fmt_num(data.my, digits: 6) Nm \
  Mz = CMz \* q \* A \* l = #fmt_num(data.cmz) \* #fmt_num(data.dynamic_pressure, digits: 2) \* #fmt_num(data.reference_area, digits: 6) \* #fmt_num(data.reference_length, digits: 4) = #fmt_num(data.mz, digits: 6) Nm
]

== Freikoerperbild

#image("/fbd_chart.png", width: 90%)

Grauer Punkt: Momenten-Bezugspunkt. Pfeillaenge nur relativ zueinander
massstabsgetreu, nicht zur Koerpergroesse.

== Oberflaeche

*Wandschubspannung:* Mittel #fmt_num(data.mean_wall_shear_stress, digits: 3) Pa,
Maximum #fmt_num(data.max_wall_shear_stress, digits: 3) Pa \
*y+:* Mittel #fmt_num(data.mean_y_plus, digits: 2), Maximum #fmt_num(data.max_y_plus, digits: 2)

#image("/cp_chart.png", width: 90%)
