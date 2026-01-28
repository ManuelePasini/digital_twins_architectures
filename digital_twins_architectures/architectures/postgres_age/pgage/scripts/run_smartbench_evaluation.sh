#!/bin/bashù

# -------------------------
# Validate environment variables
# -------------------------
: "${THREAD:?THREAD not set}"
: "${DATASET:?DATASET not set}"
: "${DATASET_SIZE:?DATASET_SIZE not set}"
: "${QUERY_SELECTIVITY:?QUERY_SELECTIVITY not set}"

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
        echo "=== Processing dataset: $DATASET ==="

        # Download dataset only if not present
        if [[ ! -d "/pgage/src/main/resources/dataset/smartbench/$DSET_SIZE" ]]; then
            echo "Downloading dataset $DSET_SIZE ..."
            ./scripts/download_dataset.sh "$DSET_SIZE" "$DSET"
        else
            echo "Dataset $DSET : $DSET_SIZE already present, skipping download."
        fi

        export DATASET_SIZE="$DSET_SIZE"

        for EVALTHREAD in "${THREADS[@]}"; do
            export THREAD="$EVALTHREAD"
            echo "Running ingestion test: dataset=$DATASET, dataset_size=$DSET_SIZE, threads=$THREAD"
            python3 src/main/${DSET}_ingestion.py
            for SELECTIVITY in "${QUERY_SELECTIVITIES[@]}"; do
                export QUERY_SELECTIVITY="$SELECTIVITY"
                echo "Running query test: dataset=$DATASET, dataset_size=$DSET_SIZE, threads=$THREAD, selectivity=$SELECTIVITY"
                python3 src/main/${DSET}_query.py --selectivity "$SELECTIVITY"
            done
        done
    done
done

echo "All datasets processed."
