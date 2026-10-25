"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from scratchpad_bank.agent import ScratchpadBankAgent
from scratchpad_bank.coverage import ScratchpadBankCoverage
from scratchpad_bank.scoreboard import ScratchpadBankScoreboard


class ScratchpadBankEnv(VerificationEnv):
    agent_type = ScratchpadBankAgent
    scoreboard_type = ScratchpadBankScoreboard
    coverage_type = ScratchpadBankCoverage
