pipeline {
    agent any

    triggers {
        cron('H/10 * * * *')
    }

    environment {
        // สร้าง credential แบบ "Username with password" ใน Jenkins ชื่อ id: thaitracking-api
        THAITRACKING_CRED = credentials('thaitracking-api')
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    if ! python3 -m venv --help > /dev/null 2>&1; then
                        apt-get install -y python3-venv python3-full 2>/dev/null || true
                    fi

                    python3 -m venv venv
                    venv/bin/pip install --upgrade pip --quiet
                    venv/bin/pip install -r requirements.txt --quiet
                '''
            }
        }

        stage('Run GPS Sync') {
            steps {
                sh '''
                    export THAITRACKING_USERNAME="$THAITRACKING_CRED_USR"
                    export THAITRACKING_PASSWORD="$THAITRACKING_CRED_PSW"
                    venv/bin/python main.py
                '''
            }
        }
    }

    post {
        success {
            echo '✅ thaitracking GPS sync completed successfully'
        }
        failure {
            echo '❌ thaitracking GPS sync failed'
        }
    }
}
