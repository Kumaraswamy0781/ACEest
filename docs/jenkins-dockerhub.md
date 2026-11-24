# Jenkins Docker Hub publishing

Jenkins publishes to `bitspilani12/aceest` only after compilation, pytest with
coverage, the SonarQube quality gate, container tests and startup checks pass.
The publishing script tags the already validated local image; it does not rebuild it.

## Jenkins credential

Create a Global **Username with password** credential with ID `aceest-dockerhub`.
Username: `bitspilani12`. Password: a Docker Hub PAT with repository Read & Write
permission. Keep the token in Jenkins Credentials, outside Git and shell commands.

## Tags and deployment evidence

- `sha-<first 12 commit characters>` links an image to its source revision.
- `jenkins-<build number>` identifies this job's build. These build tags assume a
  single publishing job; use a job-specific prefix if more publishing jobs are added.
- Existing release tag `3.4.0` and `latest` are not modified by this pipeline.
- Rebuilding the same commit can change its image when dependencies or the base
  image change. Use the recorded `repository@sha256:...` digest for exact deployment.

After both pushes succeed, Jenkins archives
`acetest-flask-app/reports/docker-image.txt` with the full commit, both tags and
the registry digest. This is the image reference to use for the Kubernetes increment.
Pushes are sequential: if the second push fails, the first tag may already exist;
Jenkins still fails the build and does not produce a successful publication report.

The helper uses `--password-stdin`, disables shell tracing, and removes its private
temporary Docker config on exit. It also removes the two local publication tags.
The existing Jenkins post action removes the local CI tag. Registry images remain.

## Verification

1. Push this increment to `assignment2`; SCM polling can start the build, or use Build Now.
2. Confirm all validation stages pass before **Publish validated image to Docker Hub**.
3. Confirm both pushes report a digest and Jenkins finishes with SUCCESS.
4. Download `docker-image.txt` from Build Artifacts.
5. Verify both tags in Docker Hub. They should identify the same image digest.
6. Pull the `deployment_image` digest recorded in the artifact to verify registry access.

The Flask app release remains `3.4.0`. No registry token is stored in these files.
