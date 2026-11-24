# ACEest on Minikube

This lab deploys the ACEest image validated by Jenkins build 3. The Docker Hub
tags `jenkins-3` and `sha-8c181ec03093` identify the digest pinned in
`app.yaml`. Compare that digest and full commit with the same Jenkins build's
`docker-image.txt` artifact. The app publishes the commit and pod name in
`/health`.

The `aceest` Minikube profile runs one app replica and one PostgreSQL 17
instance in the `aceest` namespace. The database starts fresh on a 2 GiB
persistent volume. It is separate from the database used by SonarQube and the
previous Docker Compose setup.

## Start the cluster

Run commands as your normal user on the remote Rocky Linux VM. Check the host
while Jenkins is idle.

```bash
nproc
free -h
df -h /
docker stats --no-stream
docker info --format '{{.ServerVersion}}'
```

This lab allocates 2 CPUs and 3072 MiB to Minikube. Allow memory for Jenkins,
SonarQube and the host beyond that allocation. Minikube lists 20 GB of free disk
space in its [installation prerequisites](https://minikube.sigs.k8s.io/docs/start/).

If Minikube is absent, install the official Linux amd64 binary.

```bash
mkdir -p "$HOME/.cache/aceest"
minikube_bin="$HOME/.cache/aceest/minikube-linux-amd64"
curl -fL https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64 \
  -o "$minikube_bin" && sudo install -m 0755 "$minikube_bin" /usr/local/bin/minikube
```

```bash
minikube start -p aceest --driver=docker --cpus=2 --memory=3072
minikube -p aceest status
k() { minikube -p aceest kubectl -- --context=aceest "$@"; }
k get nodes
k get storageclass
```

Look for a Ready node and a default storage class. Run the `k()` line again
when opening a new terminal. Minikube provides a matching kubectl version
through [minikube kubectl](https://minikube.sigs.k8s.io/docs/commands/kubectl/).

## Apply the manifests

From the repository root, run each command in order. Wait for PostgreSQL before
applying the app.

```bash
k apply -f k8s/minikube/namespace.yaml
bash k8s/minikube/create-secret.sh
k apply -f k8s/minikube/postgres.yaml
k -n aceest rollout status statefulset/aceest-postgres --timeout=300s
k -n aceest get pvc
```

The secret helper generates the PostgreSQL password, database URL and Flask
session key for the cluster. It reuses the existing Secret on subsequent runs.
PostgreSQL initializes the database password when its data directory is empty.
Retain its Secret with the volume for restarts.

```bash
k apply -f k8s/minikube/app.yaml
k -n aceest rollout status deployment/aceest --timeout=300s
k -n aceest get pods,svc,pvc
k -n aceest get deployment aceest -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
k -n aceest exec aceest-postgres-0 -- psql -U aceest -d aceest \
  -c "SELECT to_regclass('public.users') AS app_users_table;"
```

Both pods should be `1/1 Running` and the PVC should be `Bound`. The Deployment
image must match the Jenkins digest and the database query must return `users`.
Gunicorn initializes the app schema during startup.

## Open and verify the app

On the remote VM, leave this command running in one terminal.

```bash
k -n aceest port-forward --address 127.0.0.1 svc/aceest 8081:80
```

In another remote terminal at the repository root:

```bash
curl -fsS http://127.0.0.1:8081/health | python3 -m json.tool
python3 ci/smoke_test.py http://127.0.0.1:8081
```

Expect status `ok`, version `3.4.0` and build SHA
`8c181ec0309328026e4a43023da129b6d036ef36`. Open
[the app on the remote desktop](http://127.0.0.1:8081) while the port forward
runs. This address is local to the remote VM.

To sign in, optionally create a lab admin account. Flask prompts for the
password interactively.

```bash
k -n aceest exec -it deployment/aceest -- flask --app app create-user admin
```

## Commit and record evidence

Capture the pod and PVC status, the pinned image reference, and the `/health`
response. Commit `k8s/minikube/` on `assignment2` with the message
`deploy: run the validated ACEest image on Minikube`. The next increment
can automate deployment from Jenkins.

For troubleshooting:

```bash
k -n aceest get events --sort-by=.metadata.creationTimestamp
k -n aceest logs statefulset/aceest-postgres --tail=80
k -n aceest logs deployment/aceest --tail=80
```
