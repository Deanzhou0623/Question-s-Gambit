#!/usr/bin/env python3
"""Freeze 20 of the existing q50 questions; never performs retrieval or API calls."""
import argparse
import hashlib
import json
import random
from pathlib import Path


def prepare(source, destination, seed=42):
    rows = [line for line in source.read_text().splitlines() if line.strip()]
    ids = [line.split('\t', 1)[0] for line in rows]
    if len(rows) != 50 or len(set(ids)) != 50 or any('\t' not in x for x in rows):
        raise ValueError('Source must contain exactly 50 unique query_id<TAB>query rows')
    # Sort before sampling so a reordered source produces the same selection.
    rows.sort(key=lambda line: int(line.split('\t', 1)[0]))
    selected = random.Random(seed).sample(rows, 20)
    selected.sort(key=lambda line: int(line.split('\t', 1)[0]))
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'q20.tsv'
    text = '\n'.join(selected) + '\n'
    if target.exists() and target.read_text() != text:
        raise ValueError('Refusing to replace a previously frozen subset')
    target.write_text(text)
    (destination / 'smoke.tsv').write_text(selected[0] + '\n')
    (destination / 'remaining.tsv').write_text('\n'.join(selected[1:]) + '\n')
    manifest = {
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'seed': seed, 'algorithm': 'Python random.Random(seed).sample(numerically sorted q50 rows, 20); numeric output sort',
        'query_ids': [x.split('\t', 1)[0] for x in selected],
        'smoke_query_id': selected[0].split('\t', 1)[0],
        'subset_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'max_distinct_questions': 20,
    }
    (destination / 'subset.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/browsecomp-plus/queries/q50.tsv'))
    parser.add_argument('--output', type=Path, default=Path('runs/comparison20'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    prepare(args.source, args.output, args.seed)
