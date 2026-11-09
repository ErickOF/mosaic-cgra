"""PyUVM campaigns for arbitrary FU subsets, reusing native agents and oracles.

Legacy profiles retain their full existing campaigns. Custom subsets additionally
prove that each unavailable operation is rejected and each selected FU executes
seeded traffic through public shell ports with the existing numerical scoreboard.
"""

import os

# Independent test expectations for the RTL's legacy profile defaults.
DEFAULT_ENABLES = {
    "BCT": dict(ENABLE_ALU=0, ENABLE_MULTIPLIER=1, ENABLE_MAC=2),
    "MST": dict(ENABLE_LOAD=0, ENABLE_STORE=0),
    "VCT": dict(ENABLE_LANE_ALU=0, ENABLE_REDUCTION=1, ENABLE_DOT_PRODUCT=2),
    "SFT": dict(ENABLE_ALU=0, ENABLE_MULTIPLIER=1, ENABLE_LUT=0, ENABLE_POLYNOMIAL=1,
                ENABLE_RECIPROCAL=2, ENABLE_RSQRT=2, ENABLE_EXPONENTIAL=3,
                ENABLE_REDUCTION=0, ENABLE_FORMATTER=0, ENABLE_ACCUMULATOR=0),
    "CPT": dict(ENABLE_PREDICATE=0, ENABLE_LOOP_CONTROLLER=0, ENABLE_EVENT_BARRIER=0,
                ENABLE_ACTIONS=1),
}


def environment_enables(kind, parameters):
    profile = parameters.get("FU_PROFILE", 1)
    return {name: int(os.getenv(f"{kind}_{name}", str(int(profile >= minimum))), 0)
            for name, minimum in DEFAULT_ENABLES[kind].items()}


def custom_selection(kind, config):
    return any(config.parameters[name] != int(config.parameters.get("FU_PROFILE", 1) >= minimum)
               for name, minimum in DEFAULT_ENABLES[kind].items())


def selected_sequence(kind, base):
    class SelectionSequence(base):
        async def body(self):
            if not custom_selection(kind, self.c):
                return await super().body()
            self.coverage.selection_goals = {"selected_fu_traffic", "quiescent_after_reset"}
            check_elaboration(kind, self)
            await CAMPAIGNS[kind](self)
            await self.reset()
            await self.idle(20)
            from tile_shell.model import number
            assert not number(self.last["o_status_fatal_error"])
            self.coverage.hit("quiescent_after_reset")
            self.coverage.random_cycles = self.c.random_cycles
            self.coverage.hit("selected_fu_traffic")
    return SelectionSequence


def selection_report(coverage):
    if not hasattr(coverage, "selection_goals"):
        return None
    hits = getattr(coverage, "hits", getattr(coverage, "bins", {}))
    checks = {goal: goal in hits for goal in sorted(coverage.selection_goals)}
    return dict(status="PASS" if all(checks.values()) else "FAIL", framework="PyUVM",
                parameters=coverage.config.parameters, seed=coverage.config.seed,
                random_transactions=coverage.config.random_cycles, goals=checks,
                cycles=getattr(coverage, "cycles", 0), hdl_assertions="NOT_RUN", lint="NOT_RUN",
                synthesis="Design Compiler (deferred)")


def goal(sequence, name):
    sequence.coverage.selection_goals.add(name)
    sequence.coverage.hit(name)


def check_elaboration(kind, sequence):
    """Check generate choices as well as behavior; disabled FUs must be omitted."""
    import cocotb
    body = getattr(cocotb.top, "g_" + kind.lower()).u_body
    c = sequence.c
    branches = {
        "BCT": [("ENABLE_ALU", "alu")],
        "VCT": [("ENABLE_REDUCTION", "reduction"), ("ENABLE_DOT_PRODUCT", "dot")],
        "SFT": [("ENABLE_LUT", "lut"), ("ENABLE_POLYNOMIAL", "polynomial"),
                ("ENABLE_RECIPROCAL", "reciprocal"), ("ENABLE_RSQRT", "rsqrt"),
                ("ENABLE_EXPONENTIAL", "exponential")],
        "CPT": [("ENABLE_PREDICATE", "predicate"), ("ENABLE_LOOP_CONTROLLER", "loop"),
                ("ENABLE_EVENT_BARRIER", "events"), ("ENABLE_ACTIONS", "actions")],
        "MST": [],
    }
    for flag, branch in branches[kind]:
        enabled = bool(c.parameters[flag])
        assert hasattr(body, "g_" + branch) == enabled, (flag, enabled)
        assert hasattr(body, "g_no_" + branch) != enabled, (flag, enabled)
    if kind == "BCT":
        has_product = bool(c.ENABLE_MULTIPLIER or c.ENABLE_MAC)
        assert hasattr(body, "g_multiply") == has_product
        if has_product:
            assert hasattr(body.g_multiply, "g_mac") == bool(c.ENABLE_MAC)
    if kind == "VCT":
        lane = body.g_lane[0].u_lane.g_lane
        assert hasattr(lane, "g_alu") == bool(c.ENABLE_LANE_ALU)
        assert hasattr(lane, "g_mul") == bool(c.SUPPORT_MUL)
        assert hasattr(lane, "g_mac") == bool(c.SUPPORT_MAC)
    if kind == "MST":
        for index in range(c.NUM_LOAD_CHANNELS + c.NUM_STORE_CHANNELS):
            enabled = c.ENABLE_LOAD if index < c.NUM_LOAD_CHANNELS else c.ENABLE_STORE
            assert hasattr(body.g_channel[index], "g_worker") == bool(enabled)
    goal(sequence, "elaborated_fu_selection")


async def bct(s):
    from bct.model import sources
    c = s.c
    src = sources(c.parameters)
    enabled = [c.ENABLE_ALU, c.ENABLE_MULTIPLIER, c.ENABLE_MAC]
    count = max(4, (c.random_cycles + sum(enabled) - 1) // max(1, sum(enabled)))
    for fu, available in enumerate(enabled):
        ctx = s.context(fu=fu, opcode=0, source_a=0, source_b=1,
                        source_c=src["one"] if fu == 2 else src["zero"], iterations=count)
        if not available:
            await s.reset()
            await s.runtime(0)
            await s.provision(ctx, activate=False, error=True)
            goal(s, f"fu_{fu}_rejected")
            continue
        await s.setup_case(ctx)
        values = [[s.rng.randrange(1 << min(8, c.MULTIPLY_OPERAND_WIDTH))
                   for _ in range(c.DATA_INPUT_PORTS)] for _ in range(count)]
        await s.traffic(ctx, values, limit=300 + count * 30)
        goal(s, f"fu_{fu}_numeric_results")
    if not any(enabled):
        await s.idle(c.random_cycles)


async def vct(s):
    c = s.c
    cases = [(0, 0, c.ENABLE_LANE_ALU, 0), (0, 20, c.SUPPORT_MUL, 1),
             (0, 21, c.SUPPORT_MAC, 2), (1, 0, c.ENABLE_REDUCTION, 4),
             (2, 0, c.ENABLE_DOT_PRODUCT, 4)]
    count = max(4, (c.random_cycles + sum(x[2] for x in cases) - 1) //
                max(1, sum(x[2] for x in cases)))
    for fu, opcode, available, fmt in cases:
        ctx = s.context(fu=fu, opcode=opcode, result_format=fmt, iterations=count)
        if available:
            await s.run_mapping(ctx, count=count, limit=500 + count * 30)
            goal(s, f"fu_{fu}_opcode_{opcode}_numeric_results")
        else:
            await s.reset()
            await s.runtime(0)
            await s.provision(ctx, activate=False, error=True)
            goal(s, f"fu_{fu}_opcode_{opcode}_rejected")
    if not any(x[2] for x in cases):
        await s.idle(c.random_cycles)


async def sft(s):
    c = s.c
    flags = ("ENABLE_ALU", "ENABLE_MULTIPLIER", "ENABLE_LUT", "ENABLE_POLYNOMIAL",
             "ENABLE_RECIPROCAL", "ENABLE_RSQRT", "ENABLE_EXPONENTIAL", "ENABLE_REDUCTION",
             "ENABLE_FORMATTER", "ENABLE_ACCUMULATOR")
    available_count = sum(c.parameters[name] for name in flags)
    count = max(4, (c.random_cycles + available_count - 1) // max(1, available_count))
    for operation, flag in enumerate(flags):
        ctx = s.context(operation=operation, source_b=1, signed_data=int(operation == 3),
                        opcode=1 if operation == 9 else 0)
        if not c.parameters[flag]:
            await s.reset()
            await s.runtime(0)
            await s.provision(ctx, activate=False, error=True)
            goal(s, f"operation_{operation}_rejected")
            continue
        # Banked LUT/poly and nonlinear FUs use their established numerical oracle.
        values = [(s.rng.randrange(1 << min(7, c.INPUT_WIDTH - 1)),
                   s.rng.randrange(16)) for _ in range(count)]
        await s.case(ctx, values, blocked=12)
        goal(s, f"operation_{operation}_numeric_results")
    if not available_count:
        await s.idle(c.random_cycles)


async def cpt(s):
    c = s.c
    await s.setup()
    # Dispatch commands for missing units must report errors without native effects.
    for flag, cls, opcode in (("ENABLE_PREDICATE", 0, 1),
                              ("ENABLE_LOOP_CONTROLLER", 3, 0),
                              ("ENABLE_EVENT_BARRIER", 4, 0), ("ENABLE_ACTIONS", 6, 0)):
        if not c.parameters[flag]:
            await s.send(cls, opcode, error=True)
            goal(s, f"class_{cls}_rejected")
    if c.ENABLE_PREDICATE:
        for _ in range(c.random_cycles):
            a, b = s.rng.getrandbits(32), s.rng.getrandbits(32)
            await s.send(1, 0, a, b, expected=0 if a != b else
                         (1 << c.PREDICATE_WIDTH) - 1)
        goal(s, "predicate_numeric_results")
    else:
        # The status/register path is always part of the command shell.
        for _ in range(c.random_cycles):
            value = s.rng.getrandbits(32)
            await s.send(7, 1, value, destination=0, register_type=1, error=False)
            await s.send(7, 0, source_a=0, register_type=1, expected=value, error=False)
    if c.ENABLE_LOOP_CONTROLLER:
        await s.setup(levels=[(0, 0, 1, 3, 0, 0)] +
                      [(0, 0, 0, 0, 0, 0)] * (c.MAX_LOOP_DEPTH - 1))
        await s.send(3, 0, tag=91, error=False, blocked=12)
        await s.idle(300)
        assert len(s.active["loops"]) == 9, s.active["loops"]
        goal(s, "loop_numeric_results")
    if c.ENABLE_EVENT_BARRIER:
        await s.setup()
        await s.send(4, 0, object_id=0, error=False)
        await s.send(7, 3, object_id=0, expected=1)
        goal(s, "event_numeric_results")
    if c.ENABLE_ACTIONS:
        await s.setup()
        await s.send(6, 0, tag=85, error=False)
        await s.idle(20)
        assert any(e >> 32 & 15 == 5 for e in s.active["events"])
        goal(s, "action_request")


async def mst(s):
    c = s.c
    await s.setup()
    for available, mode in ((c.ENABLE_LOAD, 0), (c.ENABLE_STORE, 1)):
        if not available:
            await s.submit(s.descriptor(mode, count=1), error=4)
            goal(s, f"transfer_{mode}_rejected")
    modes = [mode for available, mode in ((c.ENABLE_LOAD, 0), (c.ENABLE_STORE, 1)) if available]
    for _ in range(c.random_cycles):
        if modes:
            mode = s.rng.choice(modes)
            d = s.descriptor(mode, count=s.rng.randrange(1, 5),
                             source=128 + 16 * s.rng.randrange(8),
                             destination=1024 + 16 * s.rng.randrange(8))
            await s.transfer(d)
            goal(s, f"transfer_{mode}_numeric_results")
        else:
            await s.idle(1)


CAMPAIGNS = dict(BCT=bct, VCT=vct, SFT=sft, CPT=cpt, MST=mst)
