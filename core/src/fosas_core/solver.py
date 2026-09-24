"""SU2 solver adapter.

SU2 is invoked as an external process (SU2_CFD, optionally under mpirun),
matching the same architecture as the Gmsh adapter. Unlike Gmsh, a broken
SU2 config reliably produces a non-zero process exit code (confirmed by
deliberately running a config with an invalid option key), so the exit
code is the primary failure signal here, not a full-log text scan. The
exact text of a genuine SU2 config error looks like:

    Error in "void CConfig::SetConfig_Parsing(std::istream&)":
    -------------------------------------------------------------------------
    Line 2 SOME_OPTION: invalid option name. ...
    ------------------------------ Error Exit -------------------------------

which is extracted for the exception message when available.

Only the incompressible RANS solver path (INC_RANS) is implemented, since
that is what the project's low-Mach external aerodynamics scope needs.
The numerics scheme (upwind FDS, Venkatakrishnan limiter, FGMRES/JACOBI
linear solver) is fixed to the combination validated in the Phase 1 spike
(see docs/RISKS.md R10), not exposed as configuration, to avoid an
untested combinatorial surface.

This module deliberately does not attempt automatic convergence
detection via SU2's CONV_FIELD config option: the mapping from a config
field name (e.g. RMS_PRESSURE) to the actual history CSV column name
(e.g. "rms[P]") is solver- and case-dependent, and guessing it wrong
already caused one silently-ignored warning during the spike phase.
Instead, the full iteration history is returned, and the caller decides
what "converged" means for their case.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class SolverError(Exception):
    """Raised when SU2 fails to run or exits with an error."""


@dataclass(frozen=True)
class FreestreamConditions:
    density: float
    velocity: tuple[float, float, float]
    temperature: float
    dynamic_viscosity: float

    def __post_init__(self):
        if self.density <= 0:
            raise ValueError("density must be positive (kg/m^3)")
        if self.dynamic_viscosity <= 0:
            raise ValueError("dynamic_viscosity must be positive (Pa*s)")
        if self.temperature <= 0:
            raise ValueError("temperature must be positive (K)")


@dataclass(frozen=True)
class ReferenceValues:
    length: float
    area: float
    moment_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self):
        if self.length <= 0:
            raise ValueError("length must be positive (m)")
        if self.area <= 0:
            raise ValueError("area must be positive (m^2)")


@dataclass(frozen=True)
class SolverParams:
    mesh_su2_path: Path
    freestream: FreestreamConditions
    reference: ReferenceValues
    wall_marker: str = "airfoil"
    farfield_marker: str = "farfield"
    turbulence_model: str = "SA"
    max_iterations: int = 500
    cfl_number: float = 5.0
    time_discretization: str = "EULER_IMPLICIT"
    restart_solution_path: Path | None = None

    def __post_init__(self):
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.cfl_number <= 0:
            raise ValueError("cfl_number must be positive")


@dataclass(frozen=True)
class IterationHistory:
    columns: dict[str, tuple[float, ...]] = field(default_factory=dict)

    def column(self, name: str) -> tuple[float, ...]:
        if name not in self.columns:
            raise KeyError(f"Column '{name}' not in history. Available: {sorted(self.columns)}")
        return self.columns[name]

    @property
    def num_iterations(self) -> int:
        return len(next(iter(self.columns.values()), ()))


@dataclass(frozen=True)
class SolverResult:
    history: IterationHistory
    output_dir: Path
    config_path: Path

    def final(self, column: str) -> float:
        return self.history.column(column)[-1]


def generate_config(params: SolverParams, output_dir: Path) -> str:
    """Build an SU2 config for incompressible RANS around the given mesh.

    ITER is the only stopping criterion (see module docstring); the
    caller inspects the returned history to judge convergence.
    """
    vx, vy, vz = params.freestream.velocity
    ox, oy, oz = params.reference.moment_origin
    restart_lines = "RESTART_SOL= NO"
    if params.restart_solution_path is not None:
        restart_lines = f"RESTART_SOL= YES\nSOLUTION_FILENAME= {params.restart_solution_path}"

    return f"""SOLVER= INC_RANS
KIND_TURB_MODEL= {params.turbulence_model}
MATH_PROBLEM= DIRECT
{restart_lines}

INC_DENSITY_MODEL= CONSTANT
INC_DENSITY_INIT= {params.freestream.density!r}
INC_VELOCITY_INIT= ( {vx!r}, {vy!r}, {vz!r} )
INC_TEMPERATURE_INIT= {params.freestream.temperature!r}
INC_NONDIM= DIMENSIONAL

VISCOSITY_MODEL= CONSTANT_VISCOSITY
MU_CONSTANT= {params.freestream.dynamic_viscosity!r}

REF_ORIGIN_MOMENT_X= {ox!r}
REF_ORIGIN_MOMENT_Y= {oy!r}
REF_ORIGIN_MOMENT_Z= {oz!r}
REF_LENGTH= {params.reference.length!r}
REF_AREA= {params.reference.area!r}

MARKER_HEATFLUX= ( {params.wall_marker}, 0.0 )
MARKER_FAR= ( {params.farfield_marker} )
MARKER_PLOTTING= ( {params.wall_marker} )
MARKER_MONITORING= ( {params.wall_marker} )

NUM_METHOD_GRAD= GREEN_GAUSS
CFL_NUMBER= {params.cfl_number!r}
CFL_ADAPT= NO
ITER= {params.max_iterations}
TIME_DOMAIN= NO

LINEAR_SOLVER= FGMRES
LINEAR_SOLVER_PREC= JACOBI
LINEAR_SOLVER_ERROR= 1E-6
LINEAR_SOLVER_ITER= 10

CONV_NUM_METHOD_FLOW= FDS
MUSCL_FLOW= YES
SLOPE_LIMITER_FLOW= VENKATAKRISHNAN
CONV_NUM_METHOD_TURB= SCALAR_UPWIND
MUSCL_TURB= NO
TIME_DISCRE_FLOW= {params.time_discretization}
TIME_DISCRE_TURB= EULER_IMPLICIT

MESH_FILENAME= {params.mesh_su2_path}
MESH_FORMAT= SU2
TABULAR_FORMAT= CSV
CONV_FILENAME= {output_dir}/history
RESTART_FILENAME= {output_dir}/restart_flow.dat
VOLUME_FILENAME= {output_dir}/flow
SURFACE_FILENAME= {output_dir}/surface_flow
OUTPUT_WRT_FREQ= 100
SCREEN_OUTPUT= (INNER_ITER, RMS_PRESSURE, RMS_VELOCITY-X, RMS_NU_TILDE, LIFT, DRAG)
HISTORY_OUTPUT= (ITER, RMS_RES, AERO_COEFF)
"""


_ERROR_BLOCK_RE = re.compile(r'Error in ".*?".*?Error Exit -+', re.DOTALL)


def run_su2(
    config_text: str,
    output_dir: Path,
    su2_executable: str = "SU2_CFD",
    mpi_ranks: int = 1,
    mpirun_executable: str = "mpirun",
    timeout: float = 3600.0,
) -> SolverResult:
    """Write config_text to output_dir/config.cfg, run SU2, and parse the
    resulting history CSV. Raises SolverError if SU2 exits with a
    non-zero status (confirmed to reliably indicate a real failure, see
    module docstring), if it fails to start, or if it times out.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "config.cfg"
    config_path.write_text(config_text)

    if mpi_ranks < 1:
        raise ValueError("mpi_ranks must be at least 1")
    command = (
        [mpirun_executable, "-np", str(mpi_ranks), su2_executable, str(config_path)]
        if mpi_ranks > 1
        else [su2_executable, str(config_path)]
    )

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise SolverError(
            f"Could not start '{command[0]}'. Install SU2 (and MPI, if "
            "mpi_ranks > 1), or pass the correct executable path."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SolverError(
            f"SU2 did not finish within {timeout} seconds. Increase the "
            "timeout, reduce max_iterations, or check for a stalled run."
        ) from exc

    if result.returncode != 0:
        full_log = (result.stdout or "") + (result.stderr or "")
        match = _ERROR_BLOCK_RE.search(full_log)
        detail = match.group(0) if match else full_log[-4000:]
        raise SolverError(f"SU2 exited with code {result.returncode}:\n{detail}")

    history_path = output_dir / "history.csv"
    if not history_path.exists():
        raise SolverError(
            f"SU2 exited successfully but the expected history file "
            f"'{history_path}' was not created."
        )

    return SolverResult(
        history=_read_history_csv(history_path),
        output_dir=output_dir,
        config_path=config_path,
    )


def _read_history_csv(path: Path) -> IterationHistory:
    with open(path) as f:
        header_line = f.readline()
        column_names = [name.strip().strip('"') for name in header_line.split(",")]
        values: list[list[float]] = [[] for _ in column_names]
        for line in f:
            if not line.strip():
                continue
            for i, raw in enumerate(line.split(",")):
                values[i].append(float(raw))
    return IterationHistory(columns={name: tuple(vals) for name, vals in zip(column_names, values)})
