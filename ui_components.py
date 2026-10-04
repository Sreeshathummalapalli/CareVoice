"""Compatibility wrapper for the UI component helpers.

The tests and verification scripts import ui_components from the project root,
while the implementation lives under frontend/ui_components.py. Re-export the
real functions here so both import paths work consistently.
"""

from frontend.ui_components import *  # noqa: F401,F403
