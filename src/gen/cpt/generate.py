"""Publish the actual CPT composition and its reproducible source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from cpt_contract import profile, validate, FIELDS, META, RECORD
from cpt_sources import SOURCES

ROOT=Path(__file__).resolve().parents[3]


def generate(parameters,output):
    p=validate(parameters)
    result=dict(schema='mosaic-cpt-local-v1',parameters=p,
        inventory=['tile_shell','predicate_unit','scalar_alu','loop_controller',
            'event_barrier','register_file','round_robin_arbiter','tile_shell_queue',
            'performance_counters','packer','stream_join']+(['tagged_actions','timeout_counters'] if p['FU_PROFILE'] else []),
        issue=dict(slots_per_cycle=1,execution='one reserved command; concurrent native event/loop/action engines',
            ordering='command acceptance order; independent egress class arbitration'),
        context_fields=FIELDS,command_metadata=META,event_fields=RECORD,
        connectivity=[['tile_shell.data','stream_join','command_slot'],
            ['command_slot','predicate_unit/scalar_alu/register_file'],
            ['command_slot','event_barrier/loop_controller/tagged_actions'],
            ['tile_shell.events','event_input_fifo','sequence_checker','event_barrier/actions'],
            ['loop_controller','packer','tile_shell.data'],
            ['native_sources','class_queues','bounded_arbiter','event_fifo','tile_shell.events'],
            ['tile_shell.public_final_delivery','loop_controller.iteration_ready']],
        actual_action_reservations=p['MAX_OUTSTANDING_ACTIONS'] if p['FU_PROFILE'] else 0,
        event_record_bits=256,event_policy='shell envelope; exact per-source sequence; no sequence wrap within an epoch',
        action_policy='safe-point collection plus authoritative commit; timeout queries without replay',
        loop_policy='header and selected index/ordinal beats; advance after final public delivery',
        unsupported=['CPT-Adaptive/checkpoint','multiple namespaces','predicate-file and body-control protection',
            'retention/power-off','asynchronous body reset'],
        signoff=dict(python_simulation='see regression summary',synthesis='Design Compiler (deferred)',
            lint='NOT_RUN',formal='NOT_RUN',physical='NOT_RUN',power='NOT_RUN'))
    result['rtl_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*(ROOT/f'src/rtl/{name}.sv' for name in SOURCES),ROOT/'src/rtl/mosaic_blocks/cpt.sv']}
    result['contract_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('generated')/'profile.json')
    args=parser.parse_args()
    generate(profile(),args.output)
    print('Generated',args.output)
