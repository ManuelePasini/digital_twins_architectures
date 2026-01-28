#!/bin/bash
set -euo pipefail

# -------------------------
# Validate environment variables
# -------------------------
: "${THREAD:?THREAD not set}"
: "${DATASET:?DATASET not set}"
: "${DATASET_SIZE:?DATASET_SIZE not set}"
: "${QUERY_SELECTIVITY:?QUERY_SELECTIVITY not set}"
: "${QUERY_ITERATIONS:?QUERY_ITERATIONS not set}"

IFS=',' read -r -a THREADS <<< "$THREAD"
IFS=',' read -r -a DATASET_SIZES <<< "$DATASET_SIZE"
IFS=',' read -r -a QUERY_SELECTIVITIES <<< "$QUERY_SELECTIVITY"
IFS=',' read -r -a DSETS <<< "$DATASET"

# -------------------------
# Main loop: dataset -> selectivity -> threads
# -------------------------
for DSET in "${DSETS[@]}"; do
    export DATASET=$DSET
    for DSET_SIZE in "${DATASET_SIZES[@]}"; do
        echo "=== Processing dataset: $DSET_SIZE ==="

        export DATASET_SIZE="$DSET_SIZE"

        # Download dataset only if not present
        if [[ ! -d "/neo4j/neo4j/resources/dataset/smartbench/$DSET_SIZE" ]]; then
            echo "Downloading dataset $DSET_SIZE ..."
            ./neo4j/scripts/download_dataset.sh "$DSET_SIZE" "$DSET"
        else
            echo "Dataset $DSET_SIZE already present, skipping download."
        fi
        for EVALTHREAD in "${THREADS[@]}"; do

            export THREAD="$EVALTHREAD"
                echo "Running ingestion test: dataset=$DATASET, threads=$THREAD"
                python3 /neo4j/neo4j/neo4j_ingestion.py

            for SELECTIVITY in "${QUERY_SELECTIVITIES[@]}"; do
                export QUERY_SELECTIVITY="$SELECTIVITY"
                echo "Running query test: dataset=$DSET_SIZE, threads=$THREAD, selectivity=$SELECTIVITY"
                python3 /neo4j/neo4j/neo4j_query.py --selectivity "$SELECTIVITY"
            done
        done
    done
done

echo "All datasets processed."
