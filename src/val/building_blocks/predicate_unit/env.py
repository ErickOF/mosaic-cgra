"""Separate stimulus, checking and functional coverage through shared UVM wiring."""

from mosaic_uvm.components import VerificationEnv

from predicate_unit.agent import PredicateAgent
from predicate_unit.coverage import PredicateCoverage
from predicate_unit.scoreboard import PredicateScoreboard


class PredicateEnv(VerificationEnv):
    agent_type = PredicateAgent
    scoreboard_type = PredicateScoreboard
    coverage_type = PredicateCoverage
