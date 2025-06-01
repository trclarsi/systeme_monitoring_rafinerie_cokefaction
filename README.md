# Raffinerie IoT – Simulation et Traitement de Données Industrielles

Ce projet simule un environnement industriel de raffinerie avec génération de données capteurs, ingestion via MQTT, traitement temps réel avec Spark, stockage dans TimescaleDB et visualisation avec Grafana. L'ensemble s'appuie sur Docker Compose pour orchestrer les services.

## Table des matières

- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation et Lancement](#installation-et-lancement)
- [Description des Composants](#description-des-composants)
- [Schéma de Données](#schéma-de-données)
- [Utilisation](#utilisation)
- [Auteurs](#auteurs)

---

## Architecture

- **simulateur_capteurs.py** : Génère des données de capteurs simulant un tambour de cokéfaction, envoie les mesures sur MQTT.
- **mqtt_to_kafka.py** : Fait le pont entre MQTT et Kafka, transmettant les mesures vers un topic Kafka.
- **spark/traitement_kpi.py** : Pipeline Spark Streaming pour :
  - Stocker les données brutes dans MinIO (S3)
  - Insérer les mesures dans TimescaleDB
  - Calculer des KPI (moyennes glissantes) et les stocker dans TimescaleDB
- **sql/init.sql** : Script d'initialisation de la base TimescaleDB (tables, hypertables).
- **docker-compose.yml** : Orchestration des services (MQTT, Kafka, Zookeeper, Spark, MinIO, TimescaleDB, Grafana).

## Prérequis

- Docker & Docker Compose
- Python 3.8+
- (Optionnel) Java pour Spark local
- Accès internet pour télécharger les images Docker

## Installation et Lancement

1. **Cloner le dépôt**
   ```bash
   git clone <repo_url>
   cd raffinerie-iot
   ```

2. **Lancer l'infrastructure**
   ```bash
   docker-compose up -d
   ```

3. **Installer les dépendances Python**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialiser la base TimescaleDB**
   - Se connecter à la base (`localhost:5432`, user: `admin`, pass: `admin`, db: `iotdb`)
   - Exécuter le script `sql/init.sql`

5. **Lancer le simulateur de capteurs**
   ```bash
   python simulateur_capteurs.py
   ```

6. **Lancer le bridge MQTT → Kafka**
   ```bash
   python mqtt_to_kafka.py
   ```

7. **Lancer le traitement Spark**
   ```bash
   spark-submit \
   ```
  ```bash
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 \
  /app/traitement_kpi.py
   ```
si erreur effacer les  checkpoint avec
    ```bash 
rm -rf /app/data/checkpoint_* 
    ```
    Ensuite ressayez

8. **Accéder à Grafana**
   - URL : [http://localhost:3000](http://localhost:3000)
   - User/Pass par défaut : `admin` / `admin`

## Description des Composants

- **simulateur_capteurs.py** : Simule les mesures de température, pression, niveau de coke, débit de charge, concentration H2S. Publie sur MQTT.
- **mqtt_to_kafka.py** : Relaye les messages MQTT vers Kafka (`sensor-data`).
- **spark/traitement_kpi.py** : 
  - Consomme Kafka, écrit les données brutes dans MinIO.
  - Insère les mesures dans TimescaleDB (`mesures`).
  - Calcule des KPI (moyenne 1 min) dans `kpi_indicateurs`.
- **sql/init.sql** : Crée les tables hypertables pour les mesures filtrées et les KPI.
- **docker-compose.yml** : Décrit les services :
  - `mqtt` (Eclipse Mosquitto)
  - `zookeeper` & `kafka`
  - `spark-master`
  - `minio`
  - `timescaledb`
  - `grafana`

## Schéma de Données

- **mesures** (TimescaleDB) :
  - `timestamp`, `machine_id`, `type_capteur`, `valeur`, `unite`, `alarme`
- **kpi_indicateurs** (TimescaleDB) :
  - `timestamp`, `type_kpi`, `valeur`, `unite`

## Utilisation

- Modifier les paramètres des capteurs dans `simulateur_capteurs.py` pour tester différents scénarios.
- Visualiser les données et KPI dans Grafana (configurer la source PostgreSQL sur `timescaledb:5432`).

## Auteurs

- Projet pédagogique – [ILOKI Clarsi trésor]

--- 
