"""Import the production source closure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "gen/cpt"))
from cpt_sources import SOURCES as DEPENDENCIES
