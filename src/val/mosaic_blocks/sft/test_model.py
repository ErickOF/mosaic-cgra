"""Focused standalone Python checks for packaging, exactness and profile guards."""
import unittest
from sft.model import Architecture, context, pack, rounded, FIELDS, required
from contract import DEFAULTS, profile, validate, connectivity


class ModelTests(unittest.TestCase):
    def setUp(self):self.p=profile(LUT_ADDRESS_WIDTH=2,LUT_BANKS=2,POLY_BANKS=2)

    def test_header_fields_do_not_overlap(self):
        used=set()
        for offset,width in FIELDS.values():
            bits=set(range(offset,offset+width))
            self.assertFalse(used & bits)
            self.assertLessEqual(offset+width,512)
            used |= bits

    def test_pack_round_trip(self):
        c=context(self.p,operation=2,bank=1)
        value=pack(self.p,c)
        for name,(offset,width) in FIELDS.items():
            self.assertEqual(value >> offset & ((1 << width)-1),c[name] & ((1 << width)-1))

    def test_all_profiles_have_exact_sumsq(self):
        for fu in range(4):
            p=profile(FU_PROFILE=fu)
            self.assertEqual(validate(p),p)
            self.assertGreaterEqual(p['REDUCTION_ACC_WIDTH'],2*p['REDUCTION_ELEMENT_WIDTH']+p['MAX_REDUCTION_ELEMENTS'].bit_length())

    def test_queue_credits(self):
        with self.assertRaises(ValueError):validate(self.p | {'RESULT_QUEUE_DEPTH':1})

    def test_truncating_reduction_rejected(self):
        with self.assertRaises(ValueError):validate(self.p | {'REDUCTION_ACC_WIDTH':32})

    def test_missing_image_rejected(self):
        with self.assertRaises(ValueError):validate(self.p | {'CONFIG_WORD_COUNT':1})

    def test_unavailable_profiles_rejected(self):
        for key,value in [('SUPPORT_FP16',1),('SUPPORT_BF16',1),('SYNC_PROFILE',1)]:
            with self.assertRaises(ValueError):validate(self.p | {key:value})

    def test_connectivity_feature_removal(self):
        self.assertNotIn('rf_a',connectivity(self.p | {'BYPASS_PROFILE':0})['operand_a'])
        self.assertNotIn('previous',connectivity(self.p)['operand_a'])
        self.assertIn('previous',connectivity(self.p | {'BYPASS_PROFILE':2})['operand_a'])

    def test_rounding_negative_ties(self):
        for value,expected in [(5,2),(7,4),(-5,-2),(-7,-4)]:
            self.assertEqual(rounded(value,1,True)[0],expected)

    def test_unsigned_sumsq_full_range(self):
        m=Architecture(self.p)
        c=context(self.p,operation=7,reduction=1)
        payload=(1 << 64)-1
        result=m.evaluate(c,{0:(payload,0)},True,0)
        self.assertEqual(result['data'],4*65535**2)

    def test_persistent_sumsq(self):
        m=Architecture(self.p)
        c=context(self.p,operation=7,reduction=1,dynamic_phase=1)
        payload=sum((i+1) << (16*i) for i in range(4))
        m.evaluate(c,{0:(payload,0)},True,2 << 32)
        result=m.evaluate(c,{0:(payload,0)},True,4 << 32)
        self.assertEqual((result['data'],result['count']),(60,8))

    def test_false_has_no_local_effects(self):
        m=Architecture(self.p)
        result=m.evaluate(context(self.p,write_rf=1,write_acc=1),{},False,0)
        self.assertTrue(result['suppress'])
        self.assertEqual(m.rf,{})
        self.assertIsNone(m.accumulator)

    def test_unused_scalar_operand_is_not_consumed(self):
        self.assertEqual(required(context(self.p,opcode=17,source_a=0,source_b=1)),[1])
        self.assertEqual(required(context(self.p,opcode=16,source_a=0,source_b=1)),[0])

    def test_rtl_parameter_defaults(self):
        from pathlib import Path
        import re
        source=(Path(__file__).resolve().parents[3]/'rtl/mosaic_blocks/sft.sv').read_text()
        declarations={key:int(value) for key,value in re.findall(
            r'^    parameter (\w+) = (\d+),',source,re.M)}
        for key,value in declarations.items():self.assertEqual(DEFAULTS[key],value,key)

    def test_public_ports_match_shell_contract(self):
        from pathlib import Path
        import re
        from contract import PORTS
        source=(Path(__file__).resolve().parents[3]/'rtl/mosaic_blocks/sft.sv').read_text()
        header=source.split(') (',1)[1].split(');',1)[0]
        names=re.findall(r'(?:input|output)\s+(?:logic|wire)\s+(?:\[[^\]]+\]\s+)?(\w+)',header)
        self.assertEqual(set(names),set(PORTS))

    def test_minimal_has_no_coefficient_image(self):
        from contract import package_words
        p=profile(FU_PROFILE=0,LUT_ADDRESS_WIDTH=1,OUTPUT_WIDTH=8)
        self.assertEqual(p['CONFIG_WORD_COUNT'],package_words(p))
        self.assertEqual(p['CONFIG_WORD_COUNT'],9)

    def test_generated_profile_is_reproducible(self):
        import tempfile
        from pathlib import Path
        import importlib.util
        path=Path(__file__).resolve().parents[3]/'gen/sft/generate.py'
        spec=importlib.util.spec_from_file_location('sft_generate',path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'profile.json'
            a=module.generate(self.p,out)
            b=module.generate(self.p,out)
            self.assertEqual(a,b)
            self.assertNotIn('reciprocal',a['fu_inventory'])
