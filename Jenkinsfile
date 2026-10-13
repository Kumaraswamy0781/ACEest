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
                        python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is required"'
                        python3 -m venv .venv
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
                    sh '.venv/bin/python -m pytest -q --junitxml=reports/pytest.xml'
                }
            }
        }
        stage('Build Docker image') {
            steps {
                dir(env.APP_DIR) {
                    sh 'docker build --pull --no-cache -t "$IMAGE_TAG" .'
                }
            }
        }
        stage('Container tests and startup check') {
            steps {
                sh 'sh ci/test-image.sh "$IMAGE_TAG"'
            }
        }
    }
    post {
        always {
            junit testResults: 'acetest-flask-app/reports/pytest.xml', allowEmptyResults: true
            archiveArtifacts artifacts: 'acetest-flask-app/reports/pytest.xml', allowEmptyArchive: true
            sh '''
                if [ -n "${IMAGE_TAG:-}" ]; then
                    docker image rm "$IMAGE_TAG" || true
                fi
            '''
        }
        cleanup {
            deleteDir()
        }
    }
}
