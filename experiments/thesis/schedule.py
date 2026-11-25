"""A deterministic phase scheduler; decisions are prepared before execution."""


def domains(descriptor):
    compute = [t["id"] for t in descriptor["tiles"] if t["class"] in ("BCT", "VCT")]
    return dict(model="RTL supply acknowledgements; native OFF clears private state",
        power_intent_status="NOT_RUN", retention=False,
        always_on=dict(instances=["u_clock_gate", "u_scratchpad", "u_router_*",
            "u_memory_*", "u_tile_*.u_shell (configuration/wakeup)"] +
            [f"u_tile_{t['id']}" for t in descriptor["tiles"] if t["class"] == "MST"]),
        compute=dict(tiles=compute,
            instances=[f"u_tile_{i}.u_body" for i in compute],
            boundary=dict(request="i_tile_ID_power_request_state",
                enable="o_tile_ID_body_power_enable", isolate="o_tile_ID_body_isolate",
                power_good="i_tile_ID_body_power_good", ack="i_tile_ID_body_isolation_ack",
                clamp="native shell blocks handshakes and clamps body boundaries"),
            recovery="No retained RF/accumulators: restart contexts with external operands"))


def grouping_candidates(descriptor):
    """Two frozen grouping rules on the same composition, not VCT-count changes.

    These are grouping descriptors only. Energy/UPF evaluation of their separate
    group controls is pending and cannot inherit D0's aggregate-domain result.
    """
    compute = [t for t in descriptor["tiles"] if t["class"] in ("BCT", "VCT")]
    msts = [t for t in descriptor["tiles"] if t["class"] == "MST"]
    size = len(compute) // 2
    distance = lambda t: min(abs(t["row"] - m["row"]) + abs(t["col"] - m["col"]) for m in msts)
    resource = sorted(compute, key=lambda t: (t["class"], distance(t), t["row"], t["col"]))
    used = [next(t["id"] for t in compute if t["class"] == "BCT")]
    used += [t["id"] for t in compute if t["class"] == "VCT"][:1]
    activity = sorted(compute, key=lambda t: (t["id"] not in used, t["id"]))
    return [dict(criterion=name, status="NOT_RUN", energy_status="BLOCKED",
                 groups=[[t["id"] for t in ordered[:size]], [t["id"] for t in ordered[size:]]],
                 active_dependency_tiles=used, rule=rule)
            for name, ordered, rule in (
                ("resource_proximity", resource, "class, nearest MST distance, row, column"),
                ("simultaneous_dependencies", activity,
                 "co-locate the mapped BCT/VCT pair, then fill by tile ID"))]


def schedule(case, policy, mapping):
    if policy not in ("always_on", "phase_aware"):
        raise ValueError(f"Unknown scheduling policy: {policy}")
    actions = [dict(action="configure", domain="always_on")]
    if policy == "phase_aware":
        actions += [dict(action="close_admission", domain="compute"),
                    dict(action="drain", domain="compute"),
                    dict(action="power_off", domain="compute")]
    actions.append(dict(action="execute_copy" if case["workload"] == "copy" else "idle",
                        domain="always_on", cycles=16))
    if case["workload"] != "copy":
        if policy == "phase_aware":
            actions += [dict(action="wake", domain="compute"),
                        dict(action="restart_external_operand_contexts", domain="compute")]
        actions.append(dict(action="execute_axpy", domain="compute",
            pending_off_probe=policy == "phase_aware"))
    actions.append(dict(action="verify_committed_output", domain="always_on"))
    return dict(policy=policy, decision_mode="offline_phase_schedule_v1",
                mapping=mapping, actions=actions)
