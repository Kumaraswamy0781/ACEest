# Assignment 2 Implementation Plan

## Student

- Name: Kumaraswamy H S
- Student ID: 2025TM93079

## Existing Project

- Repository: https://github.com/Kumaraswamy0781/ACEest
- Application directory: acetest-flask-app
- Baseline source commit: 8fff338
- Baseline application version: 3.2.4

## Verified Baseline

The existing application was validated on the remote Linux machine
before starting Assignment 2.

- Operating system: Rocky Linux 9.5, x86_64
- Host Python: 3.12.16
- Docker Engine: 27.5.1
- Source compilation: passed
- Local pytest execution: 29 passed
- Docker image build: passed
- Container pytest execution: 29 passed
- Local baseline image: aceest:a2-baseline

The repository already contains a Jenkinsfile and a GitHub Actions
workflow from Assignment 1.

## Planned Increments

1. Record the baseline and exclude local environment files.
2. Add configurable application release and build metadata with tests.
3. Prepare shared database and session configuration for multiple instances.
4. Build, test and publish versioned images to Docker Hub.
5. Add coverage reporting and SonarQube quality gate enforcement.
6. Configure automatic Jenkins builds and tested image publishing.
7. Add Kubernetes application, database and networking manifests.
8. Create a distinct candidate application release.
9. Demonstrate rolling updates and rollback.
10. Demonstrate blue-green deployment.
11. Demonstrate canary release.
12. Demonstrate A/B routing.
13. Demonstrate shadow deployment using read-only requests.
14. Automate deployment validation and recovery through Jenkins.
15. Complete setup instructions, evidence and the submission report.

## Commit and Release Approach

Each working increment will be committed separately after its
verification passes. Application releases will be tagged at meaningful
milestones. Infrastructure-only changes do not require a new application
version.

Docker image tags and build metadata will identify the corresponding
source revision. Previously verified images will be retained for rollback.

## Completion Evidence

- Meaningful incremental Git commits and release tags
- Successful automatic Jenkins runs
- SonarQube analysis and quality gate results
- Versioned Docker Hub images
- Running Kubernetes workloads and an accessible application endpoint
- Evidence for all five deployment strategies
- Failed deployment detection and successful recovery
- A two to three page report covering architecture, challenges and outcomes
