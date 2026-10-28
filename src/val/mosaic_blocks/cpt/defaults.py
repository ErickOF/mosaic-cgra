"""Consume the production public interface contract."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "gen/cpt"))
from cpt_contract import DEFAULTS, PORTS
