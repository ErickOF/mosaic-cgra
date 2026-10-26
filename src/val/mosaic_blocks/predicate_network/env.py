"""Separate stimulus, passive checking, and coverage responsibilities."""

from mosaic_uvm.components import VerificationEnv
from predicate_network.agent import PredicateAgent
from predicate_network.scoreboard import PredicateScoreboard
from predicate_network.coverage import PredicateCoverage


class PredicateEnv(VerificationEnv):
    agent_type = PredicateAgent
    scoreboard_type = PredicateScoreboard
    coverage_type = PredicateCoverage
