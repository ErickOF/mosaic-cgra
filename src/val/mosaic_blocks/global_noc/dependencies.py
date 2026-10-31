"""Consume the production contract and source closure."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'gen/global_noc'))
from global_noc_sources import SOURCES
from global_noc_contract import DEFAULTS, PORTS, profile, aliases
