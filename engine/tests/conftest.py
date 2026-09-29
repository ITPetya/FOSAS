import os
import shutil
import sys
from pathlib import Path

import pytest

# Make the core package's test fixtures (tests.fixtures.naca0012_wing_step,
# etc.) importable as `tests.fixtures`, without publishing them as part
# of fosas_core itself. core/tests is a package (has __init__.py), whose
# fixtures.py uses a relative import, so its parent (core/) has to be on
# sys.path, not core/tests itself.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))


@pytest.fixture(scope="session")
def gmsh_executable():
    path = os.environ.get("FOSAS_GMSH_EXECUTABLE") or shutil.which("gmsh")
    if not path:
        pytest.skip("gmsh executable not found; set FOSAS_GMSH_EXECUTABLE to its path")
    return path


@pytest.fixture(scope="session")
def su2_executable():
    path = os.environ.get("FOSAS_SU2_EXECUTABLE") or shutil.which("SU2_CFD")
    if not path:
        pytest.skip("SU2_CFD executable not found; set FOSAS_SU2_EXECUTABLE to its path")
    return path


@pytest.fixture(scope="session")
def mpirun_executable():
    return os.environ.get("FOSAS_MPIRUN_EXECUTABLE") or shutil.which("mpirun") or "mpirun"
