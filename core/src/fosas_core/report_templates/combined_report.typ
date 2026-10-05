// Kombiniertes Vorlagen-Template: Polare + GCI-Netzstudie derselben
// Geometrie in einem PDF (Phase 2, siehe docs/ARCHITECTURE.md Zeile
// 185, "Typst-Bericht mit GCI-Netzstudie"). Absichtlich ohne
// "@preview"-Paket-Import, siehe fosas_core.report fuer die
// Begruendung. Bewusst eigenstaendig statt die beiden Einzel-Templates
// per Datei-Import wiederzuverwenden (deliberately narrow erste
// Fassung, siehe Projekt-Dokumentation zu Phase 2).
//
// Erwartet "/data.json" (verschachtelt: "polar" und "gci"),
// "/polar_chart.png" und "/gci_chart.png".

#set page(margin: 2cm)
#set text(size: 11pt, lang: "de")

#let data = json("/data.json")
#let polar = data.polar
#let gci = data.gci

= FOSAS Kombinierter Bericht (Polare + GCI-Netzstudie)

*Datei (Polare):* #polar.title \
*Datei (GCI-Studie):* #gci.title \
*Erzeugt:* #data.generated_at \
*Verfeinerungsverhaeltnis (GCI):* #str(gci.refinement_ratio)

#if polar.title != gci.title [
  #block(fill: rgb("#d1ecf1"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Die beiden kombinierten Studien wurden mit
    unterschiedlichen Dateinamen angelegt. Pruefen, ob sie tatsaechlich
    dieselbe Geometrie/Konfiguration betreffen, bevor dieser Bericht
    als zusammenhaengende Aussage verwendet wird.
  ]
]

Automatisch erzeugter Bericht (Phase 2). Dieser Bericht enthaelt
ausschliesslich die unten gelisteten Rechenzustaende; er ersetzt nicht
die Einordnung in der Projekt-Dokumentation (insbesondere offene
Risiken, siehe docs/RISKS.md, u. a. R20 zur Interpretierbarkeit bei
nahe-Null-Kraftbeiwerten).

= Polare

#if polar.any_not_converged [
  #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Mindestens ein Zustand dieser Polare ist nicht
    konvergiert oder fehlgeschlagen. Die zugehoerigen Werte in der
    Tabelle unten sind entsprechend markiert und nicht als belastbares
    Ergebnis zu verstehen.
  ]
]

#image("/polar_chart.png", width: 100%)

#table(
  columns: 5,
  [*Anstellwinkel (Grad)*], [*Status*], [*Konvergiert*], [*cl*], [*cd*],
  ..polar.points.map(p => (
    str(p.aoa_deg),
    p.status,
    if p.converged == none { "-" } else if p.converged { "ja" } else { "nein" },
    if p.cl == none { "-" } else { str(p.cl) },
    if p.cd == none { "-" } else { str(p.cd) },
  )).flatten()
)

= GCI-Netzstudie

#if gci.any_level_not_done [
  #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Mindestens eine Netzaufloesung dieser Studie ist nicht
    fertig oder fehlgeschlagen. Die GCI-Kennzahl unten ist dadurch
    moeglicherweise nicht berechnet oder nicht vollstaendig belastbar.
  ]
]

#image("/gci_chart.png", width: 100%)

#table(
  columns: 5,
  [*Aufloesung*], [*Status*], [*Elemente*], [*cl*], [*cd*],
  ..gci.levels.map(l => (
    l.resolution,
    l.status,
    if l.element_count == none { "-" } else { str(l.element_count) },
    if l.cl == none { "-" } else { str(l.cl) },
    if l.cd == none { "-" } else { str(l.cd) },
  )).flatten()
)

== GCI-Kennzahlen

#if gci.result_error != none [
  #block(fill: rgb("#f8d7da"), inset: 8pt, radius: 4pt, width: 100%)[
    *GCI konnte nicht berechnet werden:* #gci.result_error
  ]
] else if gci.cl_metric == none or gci.cd_metric == none [
  Noch keine vollstaendigen Ergebnisse fuer alle drei Netzstufen
  vorhanden.
] else [
  #table(
    columns: 2,
    [*cl*], [#gci.cl_metric.message],
    [*cd*], [#gci.cd_metric.message],
  )

  #if gci.cl_metric.oscillatory or gci.cd_metric.oscillatory [
    #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
      *Hinweis:* Mindestens eine der beiden Kennzahlen zeigt
      oszillierende statt monotoner Konvergenz. Die scheinbare
      Konvergenzordnung und die GCI-Prozentzahl sind in diesem Fall
      kein verlaessliches Mass fuer den Diskretisierungsfehler.
    ]
  ]
]
