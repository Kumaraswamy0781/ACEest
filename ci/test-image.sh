#!/bin/sh
# Run from the repository root against an image built from acetest-flask-app.
set -eu
image=${1:?Usage: sh ci/test-image.sh IMAGE}

docker run --rm "$image" python -m pytest -q

container_id=$(docker run -d --publish 127.0.0.1::8000 "$image")
cleanup() {
    docker logs "$container_id" || true
    docker rm -f "$container_id" >/dev/null || true
}
trap cleanup EXIT HUP INT TERM

address=$(docker port "$container_id" 8000/tcp)
python3 ci/smoke_test.py "http://$address"
