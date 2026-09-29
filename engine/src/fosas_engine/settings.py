"""Engine configuration.

Executable paths are read from environment variables so the engine does
not hard-code any particular machine's layout (this project's own
sandbox needs FOSAS_GMSH_EXECUTABLE etc. set, see core/README.md; a real
install would have gmsh/SU2_CFD/mpirun on PATH).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    token: str
    work_root: Path
    gmsh_executable: str = field(default_factory=lambda: os.environ.get("FOSAS_GMSH_EXECUTABLE", "gmsh"))
    su2_executable: str = field(default_factory=lambda: os.environ.get("FOSAS_SU2_EXECUTABLE", "SU2_CFD"))
    mpirun_executable: str = field(default_factory=lambda: os.environ.get("FOSAS_MPIRUN_EXECUTABLE", "mpirun"))
    max_concurrent_jobs: int = 1
