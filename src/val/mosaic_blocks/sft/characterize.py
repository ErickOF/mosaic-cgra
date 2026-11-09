"""Reproducible 80-digit scalar approximation samples, separate from RTL checks.

Bounds describe the sampled native primitive interval; they are not universal
application accuracy guarantees. Caller-programmed LUT/polynomial images require
an application function, interval and independent characterization of their own.
"""
from decimal import Decimal, localcontext
import hashlib
import json
from sft.model import Architecture, context, native_config


def characterize(parameters, output):
    p=parameters
    rows=[]
    with localcontext() as decimal_context:
        decimal_context.prec=80
        for operation in (4,5,6):
            if not p[{4: 'ENABLE_RECIPROCAL', 5: 'ENABLE_RSQRT', 6: 'ENABLE_EXPONENTIAL'}[operation]]:continue
            for quality in range(3 if operation!=6 else 1):
                c=context(p,operation=operation,quality=quality,iterations=quality,
                          rounding=1,interpolate=int(bool(p['SUPPORT_INTERPOLATION'])))
                integers=sorted({1,(1 << p['INPUT_WIDTH'])-1,
                    *(1 + i*((1 << p['INPUT_WIDTH'])-2)//255 for i in range(256))})
                if operation==6:
                    integers=list(range(-4*(1 << p['INPUT_FRAC_BITS']),1,
                                        max(1,(1 << p['INPUT_FRAC_BITS'])//32)))
                errors=[]
                for integer in integers:
                    x=Decimal(integer)/Decimal(1 << p['INPUT_FRAC_BITS'])
                    if operation==4:ideal=1/x
                    elif operation==5:ideal=1/x.sqrt()
                    else:ideal=x.exp()
                    result=Architecture(p).evaluate(c,{0:(integer % (1 << p['SHELL_DATA_WIDTH']),0)},True,0)
                    if result['flags']&0x0f:continue
                    actual=Decimal(result['data'])/Decimal(1 << p['OUTPUT_FRAC_BITS'])
                    absolute=abs(actual-ideal)
                    relative=absolute/abs(ideal) if ideal else Decimal(0)
                    errors.append((absolute,relative,integer,actual,ideal))
                if not errors:raise ValueError('No representable samples')
                worst=max(errors)
                ordered=sorted(row[0] for row in errors)
                rows.append(dict(operation=operation,quality=quality,
                    tested_input_integer_interval=[integers[0],integers[-1]],
                    samples=len(integers),representable_samples=len(errors),
                    max_absolute_error=str(worst[0]),max_relative_error=str(max(row[1] for row in errors)),
                    mean_absolute_error=str(sum(row[0] for row in errors)/len(errors)),
                    p99_absolute_error=str(ordered[(len(ordered)-1)*99//100]),
                    worst_witness=dict(input_integer=worst[2],actual=str(worst[3]),reference=str(worst[4]))))
    result=dict(schema='mosaic-sft-accuracy-samples-v1',reference='Python Decimal, precision 80',
        strategy='256 deterministic integer samples for reciprocal/rsqrt; 1/32 steps on [-4,0] for exp(e)',
        scope='sample characterization, not full-range or composite error signoff',parameters=p,rows=rows)
    result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result
