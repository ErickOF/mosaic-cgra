"""Exhaustively check the dimension-order channel-dependency graphs of test profiles.

A vertex is a directed physical link and VC. Consecutive links of every legal
source/destination path introduce edges. A topological sort proves this finite
resource graph acyclic; it does not prove endpoint protocol or temporal liveness.
"""

import argparse
from collections import defaultdict, deque
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from run_noc_router_regression import PROFILES


def analyze(p):
    mx, my = p['MESH_X'], p['MESH_Y']
    routing, vcs = p['ROUTING_ALGORITHM'], p['NUM_VCS']
    vw = max(1, (vcs - 1).bit_length())
    classes = p['NUM_TRAFFIC_CLASSES']
    mapping = [(p['TRAFFIC_CLASS_TO_VC'] >> (tc * vw)) & ((1 << vw) - 1) for tc in range(classes)]
    if routing not in (0, 1) or not all(0 <= vc < vcs for vc in mapping):
        raise ValueError('Unsupported dimension order or class-to-VC map')
    edges = defaultdict(set)
    vertices = set()
    paths = 0
    for source in range(mx * my):
        for destination in range(mx * my):
            dx, dy = destination % mx, destination // mx
            for vc in sorted(set(mapping)):
                x, y = source % mx, source // mx
                path = []
                while (x, y) != (dx, dy):
                    previous = y * mx + x
                    if (routing == 0 and x != dx) or y == dy:
                        x += 1 if dx > x else -1
                    else:
                        y += 1 if dy > y else -1
                    assert 0 <= x < mx and 0 <= y < my
                    channel = (previous, y * mx + x, vc)
                    vertices.add(channel)
                    path.append(channel)
                    assert len(path) <= mx + my - 2, 'Route failed to reduce distance'
                for first, second in zip(path, path[1:]):
                    edges[first].add(second)
                paths += 1
    indegree = dict.fromkeys(vertices, 0)
    for followers in edges.values():
        for channel in followers:
            indegree[channel] += 1
    ready = deque(channel for channel, count in indegree.items() if count == 0)
    visited = 0
    while ready:
        channel = ready.popleft()
        visited += 1
        for follower in edges[channel]:
            indegree[follower] -= 1
            if indegree[follower] == 0:
                ready.append(follower)
    assert visited == len(vertices), 'Cyclic channel dependency graph'
    return dict(
        status='PASS',
        mesh=[mx, my],
        routing=routing,
        class_to_vc=mapping,
        paths=paths,
        channels=len(vertices),
        dependencies=sum(map(len, edges.values())),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [dict(profile=name, **analyze(p)) for name, p in PROFILES]
    summary = dict(
        status='PASS',
        analysis='exhaustive channel-dependency DAG',
        profiles=rows,
        profile_count=len(rows),
        finished_at_utc=datetime.now(UTC).isoformat(),
        analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        assumptions=[
            'One uniform routing order in each mesh',
            'VC identity is preserved at every hop',
            'Endpoints eventually consume ejected packets',
        ],
        endpoint_protocol_liveness='NOT_RUN',
        temporal_formal='NOT_RUN',
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Channel-dependency analysis: PASS ({len(rows)} profiles), {args.output}')


if __name__ == '__main__':
    main()
