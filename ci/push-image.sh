#!/usr/bin/env bash
# Publish the existing validated image; never rebuild it in this script.
set +x
set -euo pipefail

if [ "$#" -ne 5 ]; then
    echo "Usage: push-image.sh LOCAL_IMAGE REPOSITORY FULL_COMMIT BUILD_NUMBER REPORT_DIR" >&2
    exit 2
fi

aceest_local_image=$1
aceest_repository=$2
aceest_commit=$3
aceest_build_number=$4
aceest_report_dir=$5

: "${DOCKERHUB_USERNAME:?Bind the aceest-dockerhub username in Jenkins}"
: "${DOCKERHUB_TOKEN:?Bind the aceest-dockerhub token in Jenkins}"

if ! [[ "$aceest_commit" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]]; then
    echo "Expected a full Git commit hash." >&2
    exit 2
fi
if ! [[ "$aceest_build_number" =~ ^[0-9]+$ ]]; then
    echo "Expected a numeric Jenkins build number." >&2
    exit 2
fi

aceest_short_commit=${aceest_commit:0:12}
aceest_sha_image="$aceest_repository:sha-$aceest_short_commit"
aceest_build_image="$aceest_repository:jenkins-$aceest_build_number"

# Verify the tested local image exists before creating credentials or logging in.
docker image inspect "$aceest_local_image" >/dev/null
mkdir -p "$aceest_report_dir"
rm -f "$aceest_report_dir/docker-image.txt"
aceest_docker_config=$(mktemp -d "${TMPDIR:-/tmp}/aceest-docker-config.XXXXXX")
export DOCKER_CONFIG="$aceest_docker_config"
aceest_sha_tagged=false
aceest_build_tagged=false

cleanup() {
    if [ "$aceest_sha_tagged" = true ]; then
        docker image rm "$aceest_sha_image" >/dev/null 2>&1 || true
    fi
    if [ "$aceest_build_tagged" = true ]; then
        docker image rm "$aceest_build_image" >/dev/null 2>&1 || true
    fi
    rm -rf "$aceest_docker_config"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# Keep the token out of command arguments and use a private temporary Docker config.
printf '%s' "$DOCKERHUB_TOKEN" |
    docker login --username "$DOCKERHUB_USERNAME" --password-stdin docker.io

docker tag "$aceest_local_image" "$aceest_sha_image"
aceest_sha_tagged=true
docker tag "$aceest_local_image" "$aceest_build_image"
aceest_build_tagged=true
docker push "$aceest_sha_image"
docker push "$aceest_build_image"

aceest_digest_ref=$(docker image inspect \
    --format '{{range .RepoDigests}}{{println .}}{{end}}' "$aceest_sha_image" |
    awk -v prefix="$aceest_repository@sha256:" 'index($0, prefix) == 1 { print; exit }')
if ! [[ "$aceest_digest_ref" =~ ^${aceest_repository}@sha256:[0-9a-f]{64}$ ]]; then
    echo "Push completed but the registry digest could not be verified." >&2
    exit 1
fi

{
    printf 'commit=%s\n' "$aceest_commit"
    printf 'commit_image=%s\n' "$aceest_sha_image"
    printf 'build_image=%s\n' "$aceest_build_image"
    printf 'deployment_image=%s\n' "$aceest_digest_ref"
} > "$aceest_report_dir/docker-image.txt"
cat "$aceest_report_dir/docker-image.txt"
