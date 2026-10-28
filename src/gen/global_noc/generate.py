"""Publish reproducible topology, binding layout and routing dependency evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from global_noc_contract import profile, signature, route, PORTS, validate
from global_noc_sources import SOURCES
ROOT=Path(__file__).resolve().parents[3]


def graph(p):
    # Directed physical VC channels only; endpoint/application dependencies are
    # explicit assumptions, not covered by this router-channel DAG certificate.
    edges=set()
    channels=set()
    for src in range(p['NUM_ROUTERS']):
        for dst in range(p['NUM_ROUTERS']):
            path=route(src,dst,p)
            for vc in range(p['NUM_VCS']):
                walk=[(s,port,vc) for s,port,_ in path]
                channels.update(walk)
                edges.update(zip(walk,walk[1:]))
    successors={node:set() for node in channels}
    indegree=dict.fromkeys(channels,0)
    for source,destination in edges:
        successors[source].add(destination)
        indegree[destination]+=1
    todo=[n for n,d in indegree.items() if d==0]
    count=0
    while todo:
        node=todo.pop();count+=1
        for successor in successors[node]:
            indegree[successor]-=1
            if indegree[successor]==0:todo.append(successor)
    if count!=len(channels):raise ValueError('Cyclic router-channel dependency')
    return dict(nodes=sorted(channels),edges=sorted(edges),acyclic=True,
        scope='router dimension-order channels only; external protocol proof deferred')


def generate(p,output):
    p=validate(p)
    if p['NUM_ROUTERS']!=p['NOC_X']*p['NOC_Y'] or p['NUM_ENDPOINTS']!=p['NUM_ROUTERS']:
        raise ValueError('Only full rectangular meshes with one endpoint per router are supported')
    nodes=[dict(id=n,x=n%p['NOC_X'],y=n//p['NOC_X'],endpoint=n,
                tx_channels=p['NUM_TX_CHANNELS_PER_ENDPOINT'],rx_channels=p['NUM_RX_CHANNELS_PER_ENDPOINT'])
           for n in range(p['NUM_ROUTERS'])]
    links=sorted({edge for src in range(p['NUM_ROUTERS']) for dst in range(p['NUM_ROUTERS'])
                  for edge in route(src,dst,p)})
    result=dict(schema='mosaic-global-noc-v1',parameters=p,layout_signature=signature(p),
        nodes=nodes,links=[dict(id=i,source=s,port=port,destination=d,
            flit_stages=p['LINK_PIPELINE_STAGES']+p['ENABLE_LINK_PARITY'],
            requested_extra_flit_stages=p['LINK_PIPELINE_STAGES'],
            protection_boundary_stages=p['ENABLE_LINK_PARITY'],credit_stages=p['CREDIT_RETURN_PIPELINE_STAGES'],
            clock_domain='noc',flow_control=p['FLOW_CONTROL']) for i,(s,port,d) in enumerate(links)],
        ports=PORTS,dependency_graph=graph(p),
        components=['noc_router','tile_network_interface','skid_buffer','dff',
                    'event_barrier_queue','fifo','counter','round_robin_arbiter','parity','ecc'],
        metadata=dict(flow_id=[0,16],allocation_generation=[16,16],execution_epoch=[32,8],
                      package_slot=[40,8],sequence=[48,16]),
        config=dict(words=2+p['NUM_ROUTERS']+4*p['MAX_ACTIVE_FLOWS'],
                    crc='CRC32C, reflected, init/final xor FFFFFFFF, little-endian words',
                    header=['layout_signature','protocol_id'],flow_words=4),
        assumptions=['response capacity reserved before request acceptance',
            'dedicated critical RX channel remains serviceable',
            'application fences wait for selected drain completion before acknowledgement',
            'endpoint consumption is eventually fair',
            'dedicated configuration hierarchy authenticates infrastructure control'],
        unsupported=['asynchronous endpoint clocks/reset','clock/power-domain switching',
            'control-state protection','trace','sparse topologies','adaptive routing',
            'beat segmentation beyond fixed envelope','hardware multicast/reduction',
            'autonomous request trackers/fence generation/response acknowledgements'],
        signoff=dict(python_simulation='see regression summary',hdl_assertions='NOT_RUN',
            formal='NOT_RUN',lint='NOT_RUN',synthesis='Design Compiler (deferred)',
            physical='NOT_RUN',power='NOT_RUN'))
    files=[*(ROOT/f'src/rtl/{n}.sv' for n in SOURCES),ROOT/'src/rtl/mosaic_blocks/global_noc.sv']
    result['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
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
