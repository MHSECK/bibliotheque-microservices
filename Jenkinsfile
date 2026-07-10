// ==========================================================================
// Pipeline CI/CD - Plateforme Bibliothèque Numérique (microservices)
// Étapes : récupération du code -> build des images Docker -> déploiement
// ==========================================================================

pipeline {
    agent any

    environment {
        // URL du dépôt GitHub contenant le projet (à adapter si besoin)
        REPO_URL = 'https://github.com/<votre-utilisateur>/bibliotheque-microservices.git'
        REPO_BRANCH = 'main'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Récupération du code source depuis GitHub...'
                git branch: "${REPO_BRANCH}", url: "${REPO_URL}"
            }
        }

        stage('Build des images Docker') {
            steps {
                echo 'Construction des images Docker pour les 4 conteneurs applicatifs...'
                sh 'docker compose build'
            }
        }

        stage('Déploiement') {
            steps {
                echo 'Déploiement de la stack avec docker-compose...'
                sh 'docker compose up -d'
            }
        }

        stage('Vérification') {
            steps {
                echo 'Vérification que les conteneurs sont bien démarrés...'
                sh 'docker compose ps'
            }
        }
    }

    post {
        success {
            echo 'Pipeline exécuté avec succès : la plateforme est déployée.'
        }
        failure {
            echo 'Le pipeline a échoué. Consultez les logs ci-dessus pour diagnostiquer le problème.'
        }
    }
}
