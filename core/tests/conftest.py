import os
import shutil

import pytest


@pytest.fixture(scope="session")
def gmsh_executable():
    path = os.environ.get("FOSAS_GMSH_EXECUTABLE") or shutil.which("gmsh")
    if not path:
        pytest.skip("gmsh executable not found; set FOSAS_GMSH_EXECUTABLE to its path")
    return path
