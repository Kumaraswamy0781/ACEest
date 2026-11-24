pipeline {
    agent any
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    triggers {
        pollSCM('H/5 * * * *')
    }
    environment {
        APP_DIR = 'acetest-flask-app'
        REGISTRY_IMAGE = 'bitspilani12/aceest'
    }
    stages {
        stage('Clean checkout') {
            steps {
                deleteDir()
                checkout scm
                script {
                    env.IMAGE_TAG = "aceest-ci:jenkins-${env.BUILD_NUMBER}"
                }
            }
        }
        stage('Build clean Python environment') {
            steps {
                dir(env.APP_DIR) {
                    sh '''
                        set -eu
                        python_bin=$(sh ../ci/select-python.sh)
                        "$python_bin" --version
                        "$python_bin" -m venv .venv
                        .venv/bin/python -m pip install --no-cache-dir -r requirements.txt
                    '''
                }
            }
        }
        stage('Compile source') {
            steps {
                dir(env.APP_DIR) {
                    sh '.venv/bin/python -m compileall -q app.py db.py services.py reports.py tests'
                }
            }
        }
        stage('Pytest quality gate') {
            steps {
                dir(env.APP_DIR) {
                    sh '''
                        set -eu
                        .venv/bin/python -m coverage run -m pytest -q --junitxml=reports/pytest.xml
                        .venv/bin/python -m coverage xml
                        .venv/bin/python -m coverage report
                    '''
                }
            }
        }
        stage('SonarQube analysis') {
            steps {
                dir(env.APP_DIR) {
                    withSonarQubeEnv('ACEest-SonarQube') {
                        script {
                            def scannerHome = tool 'SonarScanner'
                            withEnv(["SONAR_SCANNER_HOME=${scannerHome}", "SONAR_SCANNER_JAVA_OPTS=-Xmx512m"]) {
                                sh '''
                                    set +x
                                    set -eu
                                    export SONAR_TOKEN="$SONAR_AUTH_TOKEN"
                                    "$SONAR_SCANNER_HOME/bin/sonar-scanner"
                                '''
                            }
                        }
                    }
                }
            }
        }
        stage('SonarQube quality gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    script {
                        def gate = waitForQualityGate()
                        if (gate.status != 'OK') {
                            error "SonarQube quality gate failed: ${gate.status}"
                        }
                    }
                }
            }
        }
        stage('Build Docker image') {
            steps {
                dir(env.APP_DIR) {
                    sh 'docker build --pull --no-cache -t "$IMAGE_TAG" .'
                    script {
                        env.IMAGE_BUILT = 'true'
                    }
                }
            }
        }
        stage('Container tests and startup check') {
            steps {
                sh 'sh ci/test-image.sh "$IMAGE_TAG"'
            }
        }
        stage('Publish validated image to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'aceest-dockerhub',
                    usernameVariable: 'DOCKERHUB_USERNAME',
                    passwordVariable: 'DOCKERHUB_TOKEN'
                )]) {
                    sh '''
                        set +x
                        set -eu
                        aceest_commit=$(git rev-parse HEAD)
                        bash ci/push-image.sh "$IMAGE_TAG" "$REGISTRY_IMAGE" \
                            "$aceest_commit" "$BUILD_NUMBER" "$APP_DIR/reports"
                    '''
                }
            }
        }
    }
    post {
        always {
            script {
                if (fileExists('acetest-flask-app/reports/pytest.xml')) {
                    junit testResults: 'acetest-flask-app/reports/pytest.xml'
                    archiveArtifacts artifacts: 'acetest-flask-app/reports/*.xml'
                }
                if (fileExists('acetest-flask-app/reports/docker-image.txt')) {
                    archiveArtifacts artifacts: 'acetest-flask-app/reports/docker-image.txt'
                }
                if (env.IMAGE_BUILT == 'true') {
                    sh 'docker image rm "$IMAGE_TAG" || true'
                }
            }
        }
        cleanup {
            deleteDir()
        }
    }
}
