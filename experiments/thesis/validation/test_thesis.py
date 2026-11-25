"""PyUVM entry point; the environment owns execution and observed evidence."""

from pathlib import Path
import sys

from pyuvm import test, uvm_test

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validation.executor import ThesisExecutor


@test(timeout_time=20, timeout_unit="ms")
class ThesisTest(uvm_test):
    def build_phase(self):
        self.executor = ThesisExecutor("executor", self)
