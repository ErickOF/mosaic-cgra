"""Independent word-merge and per-entry validity reference, with protocol checks."""

from context_memory.transaction import unpack


def address(value, depth):
    return int(value, 2) if set(value) <= {"0", "1"} and int(value, 2) < depth else None


def merge(old, new, mask, slice_width):
    """Replace selected string slices; never reuse HDL bit-address arithmetic."""
    return "".join(new[index:index + slice_width] if enabled == "1" else old[index:index + slice_width]
                   for index, enabled in zip(range(0, len(old), slice_width), mask))


def operations(config, ports):
    result = {}
    for kind in ("write", "commit", "invalidate"):
        active = ports[f"i_{kind}_enable"] == "1"
        if kind == "write":
            active &= "1" in ports["i_write_mask"]
        result[kind] = address(ports[f"i_{kind}_address"], config.depth) if active else None
    return result


def protocol_violations(config, ports):
    found = set()
    if ports["i_rstb"] not in ("0", "1"):
        found.add("i_rstb")
    for kind in ("write", "commit", "invalidate"):
        if ports[f"i_{kind}_enable"] not in ("0", "1"):
            found.add(f"{kind}_enable")
    if ports["i_write_enable"] == "1":
        if set(ports["i_write_mask"]) & {"x", "z"}:
            found.add("write_mask")
        if "1" in ports["i_write_mask"]:
            if address(ports["i_write_address"], config.depth) is None:
                found.add("write_address")
            for enabled, word in zip(unpack(ports["i_write_mask"], 1), unpack(ports["i_write_data"], config.slice_width)):
                if enabled == "1" and set(word) & {"x", "z"}:
                    found.add("write_data")
    for kind in ("commit", "invalidate"):
        if ports[f"i_{kind}_enable"] == "1" and address(ports[f"i_{kind}_address"], config.depth) is None:
            found.add(f"{kind}_address")
    for port, (enabled, raw, index) in enumerate(zip(unpack(ports["i_read_enable"], 1), unpack(ports["i_read_raw"], 1), unpack(ports["i_read_address"], config.address_width))):
        if enabled not in ("0", "1"):
            found.add(f"read_enable:{port}")
        if not config.raw and raw != "0":
            found.add(f"raw_forbidden:{port}")
        elif enabled == "1" and raw not in ("0", "1"):
            found.add(f"read_raw:{port}")
        if enabled == "1" and address(index, config.depth) is None:
            found.add(f"read_address:{port}")
    active = operations(config, ports)
    if active["commit"] is not None and active["commit"] == active["invalidate"]:
        found.add("commit_invalidate_collision")
    return frozenset(found)


class ContextModel:
    def __init__(self, config):
        self.config = config
        self.data = ["x" * config.width for _ in range(config.depth)]
        self.valid = ["x"] * config.depth
        self.clock = "0"

    def commit_violations(self, ports):
        config = self.config
        if self.clock != "0" or ports["i_clk"] != "1" or ports["i_rstb"] != "1":
            return frozenset()
        active = operations(config, ports)
        target = active["commit"]
        if target is None:
            return frozenset()
        candidate = self.data[target]
        if active["write"] == target:
            candidate = merge(candidate, ports["i_write_data"], ports["i_write_mask"], config.slice_width)
        return frozenset({"commit_data_unknown"}) if set(candidate) & {"x", "z"} else frozenset()

    def step(self, ports):
        config = self.config
        rising = self.clock == "0" and ports["i_clk"] == "1"
        active = operations(config, ports)
        if ports["i_rstb"] == "0" and (config.async_reset or rising):
            self.valid[:] = ["0"] * config.depth
        elif rising and ports["i_rstb"] == "1":
            target = active["write"]
            if target is not None:
                self.data[target] = merge(self.data[target], ports["i_write_data"], ports["i_write_mask"], config.slice_width)
                self.valid[target] = "0"
            if active["invalidate"] is not None:
                self.valid[active["invalidate"]] = "0"
            if active["commit"] is not None:
                self.valid[active["commit"]] = "1"
        self.clock = ports["i_clk"]
        return rising, active

    def reads(self, ports):
        config = self.config
        result = []
        for enabled, raw, index in zip(unpack(ports["i_read_enable"], 1), unpack(ports["i_read_raw"], 1), unpack(ports["i_read_address"], config.address_width)):
            target = address(index, config.depth)
            if enabled == "0" or target is None and set(index) <= {"0", "1"}:
                result.append(("0" * config.width, "0"))
            elif target is None:
                result.append(("x" * config.width, "x"))
            else:
                valid = self.valid[target] if ports["i_rstb"] == "1" else "0"
                data = self.data[target] if valid == "1" or config.raw and raw == "1" else "0" * config.width
                result.append((data, valid))
        return tuple(result)


def quiet_masks(config, old, new, *, rising=False):
    """Protect entries, slices, and ports unaffected by the current cause."""
    active = operations(config, new)
    reset = config.async_reset and old["i_rstb"] != "0" and new["i_rstb"] == "0" or rising and new["i_rstb"] == "0"
    masks = {name: 0 for name in ("o_read_data", "o_read_valid", "context_valid")}
    touched = {target for target in active.values() if target is not None} if rising and new["i_rstb"] == "1" else set()
    for entry in range(config.depth):
        name = f"context_data[{entry}]"
        mask = 0
        if not rising or new["i_rstb"] != "1" or active["write"] != entry:
            mask = (1 << config.width) - 1
        else:
            for slice_index, enable in enumerate(reversed(new["i_write_mask"])):
                if enable != "1":
                    mask |= ((1 << config.slice_width) - 1) << (slice_index * config.slice_width)
        masks[name] = mask
        if not reset and entry not in touched:
            masks["context_valid"] |= 1 << entry
    for port, (old_enable, enable, old_raw, raw, old_index, index) in enumerate(zip(
        unpack(old["i_read_enable"], 1), unpack(new["i_read_enable"], 1), unpack(old["i_read_raw"], 1), unpack(new["i_read_raw"], 1),
        unpack(old["i_read_address"], config.address_width), unpack(new["i_read_address"], config.address_width))):
        disabled = old_enable == enable == "0"
        stable = old_enable == enable and old_raw == raw and old_index == index and old["i_rstb"] == new["i_rstb"]
        target = address(index, config.depth)
        unaffected = stable and not reset and target not in touched
        if disabled or unaffected:
            masks["o_read_data"] |= ((1 << config.width) - 1) << (port * config.width)
            masks["o_read_valid"] |= 1 << port
    return masks
