import os
import shutil

import pytest


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
