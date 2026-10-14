"""Compare exact code layout/classification and independent SECDED guarantees."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from ecc.model import check_unknown_decode, check_unknown_encode, decode, encode, known, syndrome
from ecc.transaction import Activity, DECODE_OUTPUTS


class EccScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def write(self, observation):
        if isinstance(observation, Activity):
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.activity[observation.name] += 1
            return
        config, p, item = self.config, observation.ports, observation.item
        assert p['i_encode_data'] == item.encode and p['i_decode_codeword'] == item.received, 'Stimulus was coerced'
        if known(item.encode):
            expected = encode(config, int(item.encode, 2))
            assert p['o_encoded_codeword'] == bits(expected, config.code_width), 'Encode assertion failed: codeword layout or parity'
            assert syndrome(config, expected) == 0 and expected.bit_count() % 2 == 0, 'Encoded parity assertion failed'
        else:
            check_unknown_encode(config, item.encode, p['o_encoded_codeword'])
        if known(item.received):
            expected = decode(config, int(item.received, 2))
            for name in DECODE_OUTPUTS:
                assert p[name] == expected[name], f'Decode assertion failed: {item.get_name()}/{observation.stage}: {name}={p[name]}, expected={expected[name]}'
            assert sum(int(p[name]) for name in ('o_no_error','o_corrected','o_uncorrectable')) == 1, 'Status one-hot assertion failed'
            if config.check_internals:
                mask = (1 << int(expected['o_error_position'], 2)) if expected['o_corrected'] == '1' else 0
                assert observation.internals['correction_mask'] == bits(mask, config.code_width), 'Correction-mask assertion failed'
            if item.base is not None:
                original = encode(config, item.base)
                assert int(item.received, 2) == original ^ sum(1 << bit for bit in item.faults), 'Fault injection did not match the recorded base and mask'
                if len(item.faults) < 2:
                    assert int(p['o_decoded_data'],2) == item.base and int(p['o_corrected_codeword'],2) == original, 'SECDED restoration assertion failed'
                    assert p['o_no_error'] == str(int(not item.faults)) and p['o_corrected'] == str(int(bool(item.faults))), 'SECDED status assertion failed'
                    if item.faults:
                        assert int(p['o_error_position'],2) == item.faults[0], 'Corrected-position assertion failed'
                elif len(item.faults) == 2:
                    assert p['o_uncorrectable'] == '1' and p['o_corrected'] == p['o_scrub_required'] == '0', 'Double-error guarantee assertion failed'
        else:
            check_unknown_decode(config, item.received, p)
        self.coverage.sample(observation)
