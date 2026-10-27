"""Use the production source closure; do not keep a second dependency list."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'gen/sft'))
from sft_sources import SOURCES as DEPENDENCIES
