-- Création de l'extension TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Table pour les mesures filtrées
CREATE TABLE IF NOT EXISTS mesures_filtrees (
    timestamp TIMESTAMP NOT NULL,
    machine_id VARCHAR(50),
    valeur FLOAT,
    type_capteur VARCHAR(50)
);

-- Conversion en table hypertable
SELECT create_hypertable('mesures_filtrees', 'timestamp');

-- Table pour les KPI
CREATE TABLE IF NOT EXISTS kpi_indicateurs (
    timestamp TIMESTAMP NOT NULL,
    type_kpi VARCHAR(50),
    valeur FLOAT,
    unite VARCHAR(10)
);

-- Conversion en table hypertable
SELECT create_hypertable('kpi_indicateurs', 'timestamp'); 