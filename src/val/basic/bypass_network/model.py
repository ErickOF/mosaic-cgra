"""Independent per-destination lookup and retained capture-state reference."""

from dataclasses import dataclass

from bypass_network.transaction import unpack


@dataclass(frozen=True)
class Request:
    destination: int
    enabled: str
    capture: str
    select: str
    source: int | None
    kind: str
    consumed: bool
    source_valid: str | None
    data: str | None


def requests(config, ports) -> tuple[Request, ...]:
    data = unpack(ports["i_source_data"], config.width)
    valid = unpack(ports["i_source_valid"], 1)
    enabled = unpack(ports["i_destination_enable"], 1)
    captures = unpack(ports["i_capture_enable"], 1)
    selections = unpack(ports["i_select"], config.select_width)
    result = []
    for destination, (enable, capture, select) in enumerate(zip(enabled, captures, selections)):
        source = int(select, 2) if set(select) <= {"0", "1"} else None
        kind = ("unknown_select" if source is None else "out_of_range" if source >= config.sources
                else "legal" if source in config.connected(destination) else "disconnected")
        consumed = enable == "1" and (not config.registered or capture == "1")
        in_range = source is not None and source < config.sources
        result.append(Request(destination, enable, capture, select, source, kind, consumed,
                              valid[source] if in_range else None, data[source] if in_range else None))
    return tuple(result)


def violations(config, ports, routes) -> frozenset[str]:
    """Ignore unconsumed select/data and invalid-source payloads explicitly."""
    found = set()
    if config.registered:
        for name in ("i_rstb", "i_flush"):
            if ports[name] not in ("0", "1"):
                found.add(name)
    for route in routes:
        destination = route.destination
        if route.enabled not in ("0", "1"):
            found.add(f"destination_enable:{destination}")
        if config.registered and route.enabled == "1" and route.capture not in ("0", "1"):
            found.add(f"capture_enable:{destination}")
        if route.consumed:
            if route.kind != "legal":
                found.add(f"{route.kind}:{destination}")
            elif route.source_valid not in ("0", "1"):
                found.add(f"source_valid:{destination}")
            elif route.source_valid == "1" and set(route.data) & {"x", "z"}:
                found.add(f"source_data:{destination}")
    return frozenset(found)


def clamp(data: str, valid: str, enable: str = "1") -> tuple[str, str]:
    if enable == "0" or valid == "0":
        return "0" * len(data), "0"
    if valid == "1" and enable == "1":
        return data, "1"
    # Four-state conditional merge with the invalid zero branch.
    return "".join("0" if bit == "0" else "x" for bit in data), "x"


class ForwardingModel:
    def __init__(self, config):
        self.config = config
        self.data = ["x" * config.width for _ in range(config.destinations)]
        self.valid = ["x"] * config.destinations
        self.clock = "0"

    def step(self, ports, routes):
        config = self.config
        rising = self.clock == "0" and ports["i_clk"] == "1"
        if config.registered:
            if ports["i_rstb"] == "0" and (config.async_reset or rising):
                self.valid[:] = ["0"] * config.destinations
            elif rising:
                if ports["i_flush"] == "1":
                    self.valid[:] = ["0"] * config.destinations
                else:
                    for route in routes:
                        if not route.consumed:
                            continue
                        destination = route.destination
                        if route.kind == "unknown_select":
                            self.valid[destination] = "x"
                        elif route.kind != "legal":
                            self.valid[destination] = "0"
                        else:
                            self.valid[destination] = route.source_valid
                            if route.source_valid == "1":
                                self.data[destination] = route.data
        self.clock = ports["i_clk"]
        return rising

    def outputs(self, routes):
        config = self.config
        result = []
        for route in routes:
            error = "0" if not route.consumed or route.kind == "legal" else "x" if route.kind == "unknown_select" else "1"
            if config.registered:
                data, valid = clamp(self.data[route.destination], self.valid[route.destination], route.enabled)
            elif not route.consumed:
                data, valid = "0" * config.width, "0"
            elif route.kind == "unknown_select":
                data, valid = "x" * config.width, "x"
            elif route.kind != "legal":
                data, valid = "0" * config.width, "0"
            else:
                data, valid = clamp(route.data, route.source_valid)
            result.append((data, valid, error))
        return tuple(result)


def quiet_masks(config, old, new, *, rising=False):
    """Causal waveform guards; do not use predicted output values in driving."""
    masks = {name: 0 for name in ("o_destination_data", "o_destination_valid", "o_selection_error", "registered_data", "registered_valid")}
    old_routes, new_routes = requests(config, old), requests(config, new)
    for before, after in zip(old_routes, new_routes):
        destination = after.destination
        disabled = before.enabled == after.enabled == "0"
        stable_select = before.select == after.select and before.enabled == after.enabled and (not config.registered or before.capture == after.capture)
        error_quiet = disabled or stable_select
        valid_reset = config.registered and (rising and (new["i_rstb"] == "0" or new["i_flush"] == "1")
                       or config.async_reset and old["i_rstb"] != "0" and new["i_rstb"] == "0")
        capture = config.registered and rising and after.consumed and new["i_rstb"] == "1" and new["i_flush"] == "0"
        if config.registered:
            output_quiet = disabled or before.enabled == after.enabled and not valid_reset and not capture
        else:
            inactive = not before.consumed and not after.consumed
            data_stable = stable_select and before.source_valid == after.source_valid and before.data == after.data
            unavailable = stable_select and before.kind == after.kind == "legal" and before.source_valid == after.source_valid == "0"
            illegal = stable_select and before.kind == after.kind and after.kind != "legal"
            output_quiet = disabled or inactive or data_stable or unavailable or illegal
        if output_quiet:
            masks["o_destination_data"] |= ((1 << config.width) - 1) << (destination * config.width)
            masks["o_destination_valid"] |= 1 << destination
        if error_quiet:
            masks["o_selection_error"] |= 1 << destination
        payload_capture = capture and after.kind == "legal" and after.source_valid == "1"
        if not payload_capture:
            masks["registered_data"] |= ((1 << config.width) - 1) << (destination * config.width)
        if not valid_reset and not capture:
            masks["registered_valid"] |= 1 << destination
    return masks
