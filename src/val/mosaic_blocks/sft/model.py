"""Independent unbounded-integer SFT context, routing and architectural oracle."""
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "building_blocks"))
from polynomial_unit.model import rounded, signed, clamp
from reciprocal_unit.model import evaluate as reciprocal
from rsqrt_unit.model import evaluate as rsqrt
from exp_unit.model import predict as exponential

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "gen/sft"))
from contract import FIELDS


def context(p, **changes):
    result = dict.fromkeys(FIELDS, 0)
    result.update(schema=1, datatype=2, steps=1, terminal=1, source_b=6, output_mask=1,
                  mask=(1 << p['REDUCTION_LANES']) - 1, monitor=1,
                  x_min=-(1 << (p['INPUT_WIDTH'] - 1)),
                  x_max=(1 << (p['INPUT_WIDTH'] - 1)) - 1)
    result.update(changes)
    result['model'] = changes.get('model', 0x53460000 | result['quality'] << 8 | result['operation'])
    return result


def assets(p, c):
    # A programmable affine table and a polynomial deliberately differ by bank.
    tables = c.get('tables', [[(bank + 1) * 17 + 3 * i for i in range(1 << p['LUT_ADDRESS_WIDTH'])]
                             for bank in range(p['LUT_BANKS'])])
    coefficients = c.get('coefficients', [[(bank + 1) << p['INPUT_FRAC_BITS'],
        *[max(1,1 << max(0,p['INPUT_FRAC_BITS']-j)) for j in range(1,p['POLY_MAX_DEGREE']+1)]]
        for bank in range(p['POLY_BANKS'])])
    tables=[[value & ((1 << p['OUTPUT_WIDTH'])-1) for value in bank] for bank in tables]
    return tables, coefficients


def pack(p, c):
    value = sum((c.get(name, 0) & ((1 << width) - 1)) << offset
                for name, (offset, width) in FIELDS.items())
    tables, coefficients = assets(p, c)
    offset = 512
    for bank in [tables[c['bank'] % len(tables)]]:
        assert len(bank) == 1 << p['LUT_ADDRESS_WIDTH']
        for data in bank:
            value |= (data & ((1 << p['OUTPUT_WIDTH']) - 1)) << offset
            offset += p['OUTPUT_WIDTH']
    if p.get('ENABLE_POLYNOMIAL', p['FU_PROFILE'] >= 1):
        for bank in [coefficients[c['bank'] % len(coefficients)]]:
            assert len(bank) == p['POLY_MAX_DEGREE'] + 1
            for data in bank:
                value |= (data & ((1 << p['POLY_COEFFICIENT_WIDTH']) - 1)) << offset
                offset += p['POLY_COEFFICIENT_WIDTH']
    assert value.bit_length() <= p['CONFIG_WORD_COUNT'] * 64
    return value


def required(c):
    need_a = not (c['operation'] == 0 and c['opcode'] == 17) and not (c['operation'] == 9 and c['opcode'] in (0, 3))
    need_b = c['operation'] == 1 or (c['operation'] == 0 and c['opcode'] not in (5, 16, 20))
    return sorted({source for source, used in ((c['source_a'], need_a), (c['source_b'], need_b))
                   if used and source < 2})


def native_config(p, operation):
    common = dict(INPUT_WIDTH=p['INPUT_WIDTH'], INPUT_FRACTION_WIDTH=p['INPUT_FRAC_BITS'],
                  OUTPUT_WIDTH=p['OUTPUT_WIDTH'], OUTPUT_FRACTION_WIDTH=p['OUTPUT_FRAC_BITS'],
                  ZERO_RESULT_MODE=0, SEED_PROTECTION=p['TABLE_PROTECTION'])
    if operation == 4:
        common.update(INTERNAL_WIDTH=p['RECIP_INTERNAL_WIDTH'],
            INTERNAL_FRACTION_WIDTH=p['RECIP_INTERNAL_FRAC_BITS'],
            SEED_ADDRESS_WIDTH=p['RECIP_SEED_ADDRESS_WIDTH'], MAX_ITERATIONS=p['RECIP_MAX_ITERATIONS'])
    elif operation == 5:
        common.update(INTERNAL_WIDTH=p['RSQRT_INTERNAL_WIDTH'],
            INTERNAL_FRACTION_WIDTH=p['RSQRT_INTERNAL_FRAC_BITS'],
            SEED_MANTISSA_ADDRESS_WIDTH=p['RSQRT_SEED_ADDRESS_WIDTH'],
            MAX_ITERATIONS=p['RSQRT_MAX_ITERATIONS'], SUPPORT_EPSILON=1)
    else:
        common.update(INTERNAL_WIDTH=p['INTERNAL_WIDTH'],
            INTERNAL_FRACTION_WIDTH=p['INTERNAL_FRAC_BITS'], RANGE_WIDTH=p['EXP_RANGE_WIDTH'],
            RANGE_FRACTION_WIDTH=20, LOG2E_FRACTION_WIDTH=24,
            TABLE_ADDRESS_WIDTH=p['EXP_TABLE_ADDRESS_WIDTH'], SUPPORT_EXP_E=1, SUPPORT_EXP2=1,
            SUPPORT_INTERPOLATION=1)
    return SimpleNamespace(**common, parameters=common)


class Architecture:
    def __init__(self, p):
        self.p = p
        self.reset()

    def reset(self):
        self.rf = {}
        self.accumulator = None
        self.previous = None
        self.reductions = {}

    def source(self, source, inputs, c):
        if source < 2:
            return inputs[source][0]
        if source in (2, 3):
            return self.rf[c['rf_a' if source == 2 else 'rf_b']]
        if source == 4:
            assert self.accumulator is not None
            return self.accumulator
        if source == 5:
            assert self.previous is not None
            return self.previous
        return c['immediate'] if source == 6 else 0

    def evaluate(self, c, inputs, predicate, metadata):
        p, d, op = self.p, self.p['SHELL_DATA_WIDTH'], c['operation']
        mask = (1 << d) - 1
        if not predicate:
            return dict(data=0, flags=512, count=0, empty=False, suppress=not c['false_token'])
        a = self.source(c['source_a'], inputs, c) if not (op == 0 and c['opcode'] == 17) and not (op == 9 and c['opcode'] in (0, 3)) else 0
        b = self.source(c['source_b'], inputs, c) if op == 1 or op == 0 and c['opcode'] not in (5, 16, 20) else 0
        av, bv = (signed(a, d), signed(b, d)) if c['signed_data'] else (a, b)
        value = flags = count = 0
        empty = suppress = False
        if op == 0:
            code = c['opcode']
            shift = min(b,d)
            choices = {0: av+bv, 1: av-bv, 2: a&b, 3: a|b, 4: a^b, 5: ~a,
                6: a << shift, 7: a >> shift, 8: signed(a,d) >> shift,
                9: int(av==bv), 10: int(av!=bv), 11: int(av<bv), 12: int(av<=bv),
                13: int(av>bv), 14: int(av>=bv), 15: a if c['select_condition'] else b,
                16: a, 17: b, 18: min(av,bv), 19: max(av,bv), 20: abs(av)}
            value = choices[code]
            if code in (0, 1, 20):
                lo, hi = (-(1 << (d-1)), (1 << (d-1))-1) if c['signed_data'] else (0,mask)
                overflow = value < lo or value > hi
                flags |= int(overflow and c['signed_data']) << 1 | int(overflow and c['saturate']) << 3
                if c['saturate']: value = min(hi,max(lo,value))
        elif op == 1:
            value = av * bv
        elif op == 2:
            table = assets(p,c)[0][c['bank']]
            coordinate = signed(a, 1+p['LUT_ADDRESS_WIDTH']+p['LUT_INDEX_FRACTION_WIDTH']) if c['signed_data'] else a
            limit = (len(table)-1) << p['LUT_INDEX_FRACTION_WIDTH']
            low, high = coordinate < 0, coordinate > limit
            coordinate = max(0,min(limit,coordinate))
            index, fraction = divmod(coordinate, 1 << p['LUT_INDEX_FRACTION_WIDTH'])
            data = signed(table[index],p['OUTPUT_WIDTH']) if c['signed_data'] else table[index]
            if c['interpolate'] and fraction and index+1<len(table):
                other = signed(table[index+1],p['OUTPUT_WIDTH']) if c['signed_data'] else table[index+1]
                data += rounded((other-data)*fraction,p['LUT_INDEX_FRACTION_WIDTH'],c['rounding'])[0]
            value = data
            flags = int(low)<<6 | int(high)<<7 | int(c['interpolate'] and fraction != 0 and not high and not low)<<5
            if c['range_error'] and (low or high):value=0;flags|=1
        elif op == 3:
            x = signed(a & ((1 << p['INPUT_WIDTH'])-1),p['INPUT_WIDTH'])
            low, high = x < c['x_min'], x > c['x_max']
            if (low or high) and c['range_error']:
                flags = 1
            else:
                x = min(c['x_max'],max(c['x_min'],x))
                coeff = assets(p,c)[1][c['bank']]
                value = signed(coeff[c['degree']] & ((1 << p['POLY_COEFFICIENT_WIDTH'])-1),p['POLY_COEFFICIENT_WIDTH'])
                inexact = saturated = False
                for k in range(c['degree']-1,-1,-1):
                    term, lost, _ = rounded(value*x,p['INPUT_FRAC_BITS'],c['rounding'])
                    value, clipped = clamp(term+coeff[k],p['INTERNAL_WIDTH'])
                    inexact |= lost
                    saturated |= clipped
                value, lost, _ = rounded(value,c['shift'],c['rounding'])
                value, clipped = clamp(value,p['OUTPUT_WIDTH'])
                flags = int(low)<<6 | int(high)<<7 | int(inexact or lost)<<4 | int(clipped)<<3 | int(saturated)<<1
        elif op in (4,5,6):
            config = native_config(p,op)
            request = dict(operand=a & ((1 << p['INPUT_WIDTH'])-1), signed=c['signed_data'],
                input_signed=c['signed_data'], output_signed=c['signed_data'], iterations=c['iterations'],
                round_mode=c['rounding'], predicate=1, context_id=0, tag=0,
                add_epsilon=int(c['epsilon']!=0),epsilon=c['epsilon'])
            if op==6:
                request={f'i_request_{k}':v for k,v in request.items()}
                request.update(i_request_base=c['base'],i_request_interpolate=c['interpolate'])
                result,_=exponential(config,request)
                result={k.removeprefix('o_result_'):v for k,v in result.items()}
            else: result,_=(reciprocal if op==4 else rsqrt)(config,request)
            value = result['data']
            if c['signed_data']: value=signed(value,p['OUTPUT_WIDTH'])
            flags = sum(int(result.get(key,0)) << bit for key,bit in (
                ('error',0),('overflow',1),('underflow',2),('saturated',3),('rounded',4),
                ('approximate',5),('divide_by_zero' if op==4 else 'zero_input',6)))
        elif op == 7:
            phase = metadata >> 32 & 7 if c['dynamic_phase'] else c['phase']
            elements = [(a >> (lane*p['REDUCTION_ELEMENT_WIDTH'])) & ((1 << p['REDUCTION_ELEMENT_WIDTH'])-1)
                for lane in range(p['REDUCTION_LANES']) if c['mask'] >> lane & 1]
            if c['signed_data']: elements=[signed(x,p['REDUCTION_ELEMENT_WIDTH']) for x in elements]
            count=len(elements)
            reduction=c['reduction']
            value=(sum(elements) if reduction==0 else sum(x*x for x in elements) if reduction==1
                   else (min if reduction==2 else max)(elements) if elements else 0)
            if phase in (3,4,5):
                old,old_count,old_op=self.reductions[c['state_id']]
                assert old_op==reduction
                if phase==5: value,count=old,old_count
                else:
                    value=(old+value if reduction<2 else value if old_count==0 else old if count==0
                           else (min if reduction==2 else max)(old,value))
                    count+=old_count
            if phase==1: value=count=0
            assert count<=p['MAX_REDUCTION_ELEMENTS']
            empty=count==0
            flags=int(empty)<<8 | int(empty and c['empty_policy']==1 and phase!=1)
            suppress=phase in (1,2,3) or empty and c['empty_policy']==2
            if phase in (1,2,3,4) and not flags&1:
                if phase==1:self.reductions.pop(c['state_id'],None)
                else:self.reductions[c['state_id']]=(value,count,reduction)
        elif op == 8:
            value,lost,_=rounded(av,c['shift'],c['rounding'])
            lo,hi=(-(1 << (p['OUTPUT_WIDTH']-1)),(1 << (p['OUTPUT_WIDTH']-1))-1) if c['signed_data'] else (0,(1 << p['OUTPUT_WIDTH'])-1)
            overflow=value<lo or value>hi
            if c['saturate']:value=min(hi,max(lo,value))
            value &= (1 << p['OUTPUT_WIDTH'])-1
            if c['signed_data']:value=signed(value,p['OUTPUT_WIDTH'])
            flags=int(overflow)<<1 | int(overflow and c['saturate'])<<3 | int(lost)<<4
        elif op == 9:
            value=0 if c['opcode']==0 else a if c['opcode']==1 else self.accumulator
            if c['opcode']==2:
                acc=signed(self.accumulator,d) if c['signed_data'] else self.accumulator
                value=acc+av
                lo,hi=(-(1 << (d-1)),(1 << (d-1))-1) if c['signed_data'] else (0,mask)
                overflow=value<lo or value>hi
                flags=int(overflow and c['signed_data'])<<1 | int(overflow and c['saturate'])<<3
                if c['saturate']:value=min(hi,max(lo,value))
        value &= mask
        if not flags&1:
            self.previous=value
            if c['write_rf']:self.rf[c['rf_write']]=value
            if c['write_acc'] or op==9 and c['opcode']!=3:self.accumulator=value
        return dict(data=value,flags=flags,count=count,empty=empty,suppress=bool(suppress))
