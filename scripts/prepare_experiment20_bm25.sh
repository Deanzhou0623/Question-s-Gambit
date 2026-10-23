#!/usr/bin/env bash
# Local non-LLM preparation of the repository's q50 strata; explicitly authorized.
set -euo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME=/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p data/browsecomp-plus/source runs/comparison20
[[ $(wc -l < data/browsecomp-plus/queries/browsecomp_plus_all.tsv) -eq 830 ]] || { echo "Ground-truth preparation is incomplete" >&2; exit 1; }
cp data/browsecomp-plus/queries/browsecomp_plus_all.tsv data/browsecomp-plus/source/queries.tsv
java -cp vendor/anserini/anserini-1.6.0-fatjar.jar io.anserini.search.SearchCollection \
  -topicReader TsvString -topics data/browsecomp-plus/source/queries.tsv \
  -index indexes/browsecomp-plus-bm25-tevatron \
  -output data/browsecomp-plus/source/bm25_pure.trec -bm25 -hits 1000 -threads 8
python3 scripts/generate_browsecomp_plus_query_slices.py \
  --queries data/browsecomp-plus/source/queries.tsv \
  --qrels data/browsecomp-plus/qrels/qrel_evidence.txt \
  --bm25-run data/browsecomp-plus/source/bm25_pure.trec \
  --output-dir data/browsecomp-plus/queries --seed 42 --slices q50
python3 scripts/prepare_experiment20.py --seed 42
