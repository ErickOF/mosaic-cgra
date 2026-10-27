"""Import the production parameter and public-port contract."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'gen/sft'))
from contract import DEFAULTS, PORTS
