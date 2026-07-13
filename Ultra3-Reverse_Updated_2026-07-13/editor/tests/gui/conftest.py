from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ultra3_editor.gui.app import create_application


@pytest.fixture(scope="session")
def qapp():
    return create_application([])
