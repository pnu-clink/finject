"""Stable repository paths shared by the three application domains."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / 'src' / 'finarch'
VIEWER = PROJECT / 'viewer'
