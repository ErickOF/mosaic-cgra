"""Assert exact parity layout, four-state results, fault guarantees and limits."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from parity.model import check, encode, expected_fault_vector, generate, known
from parity.transaction import Activity, CHECK_OUTPUTS


class ParityScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.previous_source = None

    def write(self, observation):
        if isinstance(observation, Activity):
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.activity[observation.name] += 1
            return
        config, ports, item = self.config, observation.ports, observation.item
        assert (ports['i_generate_data'], ports['i_check_data'], ports['i_check_parity']) == (item.source, item.data, item.parity), 'Stimulus was coerced'
        assert ports['o_generated_parity'] == generate(config, item.source), 'Generation assertion failed: granule layout or parity'
        expected = check(config, item.data, item.parity)
        for name in CHECK_OUTPUTS:
            assert ports[name] == expected[name], f'Check assertion failed: {name}: {ports[name]} != {expected[name]} ({item.get_name()}, {observation.stage})'
        if known(item.source):
            for start, bit in zip(range(0, config.width, config.granule_width), ports['o_generated_parity']):
                assert (item.source[start:start + config.granule_width].count('1') + int(bit)) % 2 == 0, 'Generated even-parity assertion failed'
        if known(item.data + item.parity):
            assert ports['o_no_error'] != ports['o_any_error'] and known(''.join(ports[name] for name in CHECK_OUTPUTS)), 'Known-status complementarity assertion failed'
            assert int(ports['o_checked_data'], 2) == (0 if ports['o_any_error'] == '1' else int(item.data, 2)), 'Fail-closed/passthrough assertion failed'
        if item.base is not None:
            assert len(set(item.faults)) == len(item.faults), 'Duplicate fault locations invalidate the weight assumption'
            received = int(item.parity + item.data, 2)
            assert received == encode(config, item.base) ^ sum(1 << bit for bit in item.faults), 'Fault injection provenance assertion failed'
            vector = expected_fault_vector(config, item.faults)
            assert ports['o_error_vector'] == vector, 'Fault-weight/granule mapping assertion failed'
            if len(item.faults) == 1:
                assert vector.count('1') == 1 and ports['o_any_error'] == '1', 'Single-fault detection assertion failed'
            if item.faults and '1' not in vector:
                # Expected limitation: even-weight corruption is passed as
                # received, never silently described as corrected or repaired.
                assert ports['o_no_error'] == '1' and ports['o_checked_data'] == item.data, 'Expected-undetected even-fault assertion failed'
        if item.selection is not None:
            assert item.previous_source is not None and known(item.source)
            if observation.stage == 'settled':
                assert self.previous_source == bits(item.previous_source, config.width), 'Partial-write baseline was not observed'
            previous = bits(item.previous_source, config.width)
            old_parity = generate(config, previous)
            for granule in range(config.parity_width):
                if not item.selection & (1 << granule):
                    shift = granule * config.granule_width
                    assert ((int(item.source, 2) ^ item.previous_source) >> shift) & ((1 << config.granule_width) - 1) == 0, 'Unselected write-granule changed'
                    assert ports['o_generated_parity'][-granule-1] == old_parity[-granule-1], 'Unselected parity granule changed'
        self.coverage.sample(observation)
        if observation.stage == 'settled':
            self.previous_source = item.source
