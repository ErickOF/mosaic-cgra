"""Independent context, full-product, reduction and mask oracle unit checks."""
import unittest
from vct.defaults import DEFAULTS
from vct.model import pack, unpack, layout, compute, payload

class ModelTests(unittest.TestCase):
    def test_context_roundtrip(self):
        for lanes in (2,4,8):
            p = DEFAULTS | dict(NUM_LANES=lanes)
            fields = {n: (1 << w) - 1 for n, (_,w) in layout(p).items()}
            self.assertEqual(unpack(p, pack(p, fields)), fields)

    def test_exact_products(self):
        p = DEFAULTS | dict(NUM_LANES=2, ELEMENT_WIDTH=4, ACC_WIDTH=16)
        c = dict(fu=0, opcode=20, signed_mode=0, saturate=0, result_format=1)
        for a in range(16):
            for b in range(16):
                result, *_ = compute(p, c, payload([a,a],4), payload([b,b],4), 0, 3)
                self.assertEqual(result, payload([a*b,a*b],8))

    def test_reductions_and_masks(self):
        p = DEFAULTS | dict(NUM_LANES=2, ELEMENT_WIDTH=4, ACC_WIDTH=16)
        for left in range(16):
            for right in range(16):
                for mask in range(4):
                    active = [n for lane,n in enumerate((left,right)) if mask >> lane & 1]
                    for op in (0,1,2,3,4):
                        if not active and op in (1,2): continue
                        c = dict(fu=1,opcode=op,signed_mode=0,saturate=0,
                                 result_format=4 if op==0 else 3,accumulate=0)
                        expected = sum(active) if op==0 else min(active) if op==1 else max(active) if op==2 else 15 if op==3 else 0
                        if op==3:
                            for value in active: expected &= value
                        if op==4:
                            for value in active: expected |= value
                        self.assertEqual(compute(p,c,payload([left,right],4),0,0,mask)[0], expected if mask else 0)

    def test_signed_dot_accumulation(self):
        p = DEFAULTS | dict(NUM_LANES=2,ELEMENT_WIDTH=4,ACC_WIDTH=16)
        for a in range(16):
            for b in range(16):
                for mask in range(4):
                    c = dict(fu=2,opcode=0,signed_mode=1,saturate=0,result_format=4,accumulate=1)
                    left = a if a<8 else a-16
                    right = b if b<8 else b-16
                    expected = (left*right*mask.bit_count()+13)&65535 if mask else 0
                    self.assertEqual(compute(p,c,payload([a,a],4),payload([b,b],4),13,mask)[0],expected)
