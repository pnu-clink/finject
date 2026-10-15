"""Compatibility entry for callers of the former stage dispatcher."""
from importlib import import_module
execute = import_module("finarch.dataset.01-preparation.prepare_run").execute
