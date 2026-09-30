# Engine

FastAPI service wrapping `fosas_core.pipeline.run_case` as an
asynchronous job. Local-only for now: binds `127.0.0.1`, requires a
bearer token generated fresh at every startup and printed to stdout
(never written to a file). See `../docs/ARCHITECTURE.md`.

## Scope of this version

- REST only, no WebSocket yet. A running job's progress (phase, current
  iteration, percent, ETA) is still available: `GET /jobs/{id}` computes
  it on every call by reading the job's own files (mesh.su2's existence,
  history.csv's growing row count), see `fosas_engine/progress.py`. No
  progress percentage for the meshing phase, since Gmsh reports none.
- No cache integration yet (`fosas_core.cache` exists but is not wired
  into job execution).
- Jobs run in-process; state is mirrored to `job_meta.json` in each
  job's work_dir, so a restart resumes rather than loses job history
  (see `../docs/ARCHITECTURE.md`, "Job-Persistenz und geteilte
  Sitzung"). Still single-server, no per-job access control, no
  multi-user mode.
- Same V1 assumptions as `fosas_core.pipeline`: geometry already in the
  X chordwise / Y spanwise / Z vertical convention, constant
  cross-section only.

## Einrichtung

Core und Engine teilen sich sinnvollerweise eine Umgebung:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../core
pip install -e .[dev]
```

## Starten

```
export FOSAS_GMSH_EXECUTABLE=/pfad/zu/gmsh
export FOSAS_SU2_EXECUTABLE=/pfad/zu/SU2_CFD
export FOSAS_MPIRUN_EXECUTABLE=/pfad/zu/mpirun   # nur falls mpi_ranks > 1 genutzt wird
python -m fosas_engine.server
```

Gibt URL und Token auf der Konsole aus. Die interaktive Dokumentation
unter `/docs` ist die vorgesehene erste Testflaeche, bevor eine
richtige Web-UI existiert (siehe `../core/README.md`), Anfragen dort
brauchen den Header `Authorization: Bearer <token>`.

## Tests

```
pytest tests/                # inklusive echtem Gmsh/SU2-Lauf ueber die API
pytest tests/ -m "not slow"  # nur die schnellen
```
