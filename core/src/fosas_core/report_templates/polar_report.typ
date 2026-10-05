// Statisches Vorlagen-Template fuer den ersten FOSAS-Polaren-Bericht
// (Phase 2, siehe docs/ARCHITECTURE.md). Absichtlich ohne jeglichen
// "@preview"-Paket-Import: der Diagramm-Teil wird komplett in Python
// (matplotlib) vorgerendert und hier nur als Bild eingebunden, siehe
// fosas_core.report fuer die Begruendung (kein Netzzugriff zur
// Compile-Zeit noetig).
//
// Erwartet zwei weitere Dateien im selben root-Verzeichnis:
// "/data.json" (Metadaten + Tabellenzeilen) und "/chart.png"
// (vorgerendertes cl/cd-ueber-AoA-Diagramm).

#set page(margin: 2cm)
#set text(size: 11pt, lang: "de")

#let data = json("/data.json")

// Gerundete Anzeige statt roher Fliesskommazahlen (Feinschliff, Phase
// 2): rundet nur fuer die Darstellung, die zugrunde liegenden Werte in
// data.json bleiben unveraendert/unverkuerzt.
#let fmt_num(x, digits: 4) = if x == none { "-" } else { str(calc.round(x, digits: digits)) }
#let header_fill = rgb("#e9ecef")
#let table_fill(col, row) = if row == 0 { header_fill } else { white }

= FOSAS Polarenbericht

*Datei:* #data.title \
*Erzeugt:* #data.generated_at

Automatisch erzeugter Bericht (Phase 2). Dieser Bericht enthaelt
ausschliesslich die unten gelisteten Rechenzustaende; er ersetzt nicht
die Einordnung in der Projekt-Dokumentation (insbesondere offene
Risiken, siehe docs/RISKS.md).

#if data.any_not_converged [
  #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Mindestens ein Zustand dieser Polare ist nicht
    konvergiert oder fehlgeschlagen. Die zugehoerigen Werte in der
    Tabelle unten sind entsprechend markiert und nicht als belastbares
    Ergebnis zu verstehen.
  ]
]

== Diagramm

#image("/chart.png", width: 100%)

== Tabelle

#table(
  columns: 5,
  fill: table_fill,
  [*Anstellwinkel (Grad)*], [*Status*], [*Konvergiert*], [*cl*], [*cd*],
  ..data.points.map(p => (
    str(p.aoa_deg),
    p.status,
    if p.converged == none { "-" } else if p.converged { "ja" } else { "nein" },
    fmt_num(p.cl),
    fmt_num(p.cd),
  )).flatten()
)
