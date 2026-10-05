// Statisches Vorlagen-Template fuer den FOSAS-GCI-Bericht (Phase 2,
// siehe docs/ARCHITECTURE.md). Absichtlich ohne jeglichen
// "@preview"-Paket-Import, siehe fosas_core.report fuer die
// Begruendung (kein Netzzugriff zur Compile-Zeit noetig).
//
// Erwartet zwei weitere Dateien im selben root-Verzeichnis:
// "/data.json" (Metadaten, Netzstufen, GCI-Kennzahlen) und
// "/chart.png" (vorgerendertes cl/cd-ueber-Elementanzahl-Diagramm).

#set page(margin: 2cm)
#set text(size: 11pt, lang: "de")

#let data = json("/data.json")

= FOSAS GCI-Netzstudienbericht

*Datei:* #data.title \
*Erzeugt:* #data.generated_at \
*Verfeinerungsverhaeltnis:* #str(data.refinement_ratio)

Automatisch erzeugter Bericht (Phase 2). Dieser Bericht enthaelt
ausschliesslich die unten gelisteten Rechenzustaende und die daraus
berechnete Grid-Convergence-Index-Kennzahl (Celik et al. 2008); er
ersetzt nicht die Einordnung in der Projekt-Dokumentation (insbesondere
offene Risiken, siehe docs/RISKS.md, u. a. R20 zur Interpretierbarkeit
bei nahe-Null-Kraftbeiwerten).

#if data.any_level_not_done [
  #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
    *Hinweis:* Mindestens eine Netzaufloesung dieser Studie ist nicht
    fertig oder fehlgeschlagen. Die GCI-Kennzahl unten ist dadurch
    moeglicherweise nicht berechnet oder nicht vollstaendig belastbar.
  ]
]

== Diagramm

#image("/chart.png", width: 100%)

== Netzstufen

#table(
  columns: 5,
  [*Aufloesung*], [*Status*], [*Elemente*], [*cl*], [*cd*],
  ..data.levels.map(l => (
    l.resolution,
    l.status,
    if l.element_count == none { "-" } else { str(l.element_count) },
    if l.cl == none { "-" } else { str(l.cl) },
    if l.cd == none { "-" } else { str(l.cd) },
  )).flatten()
)

== GCI-Kennzahlen

#if data.result_error != none [
  #block(fill: rgb("#f8d7da"), inset: 8pt, radius: 4pt, width: 100%)[
    *GCI konnte nicht berechnet werden:* #data.result_error
  ]
] else if data.cl_metric == none or data.cd_metric == none [
  Noch keine vollstaendigen Ergebnisse fuer alle drei Netzstufen
  vorhanden.
] else [
  #table(
    columns: 2,
    [*cl*], [#data.cl_metric.message],
    [*cd*], [#data.cd_metric.message],
  )

  #if data.cl_metric.oscillatory or data.cd_metric.oscillatory [
    #block(fill: rgb("#fff3cd"), inset: 8pt, radius: 4pt, width: 100%)[
      *Hinweis:* Mindestens eine der beiden Kennzahlen zeigt
      oszillierende statt monotoner Konvergenz. Die scheinbare
      Konvergenzordnung und die GCI-Prozentzahl sind in diesem Fall
      kein verlaessliches Mass fuer den Diskretisierungsfehler.
    ]
  ]
]
