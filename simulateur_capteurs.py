#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import random
import paho.mqtt.client as mqtt
from datetime import datetime
import math

# Constantes physiques et paramètres initiaux
R = 8.314  # Constante des gaz parfaits (J/mol·K)
T0 = 450  # Température initiale (°C)
P0 = 1.8  # Pression initiale (MPa)
N0 = 40  # Niveau initial de coke (%)
C0 = 2  # Concentration initiale de H2S (ppm)
Q_in = 5000  # Chaleur injectée (J/s)
Cp = 2000  # Capacité calorifique (J/kg·K)
m = 1000  # Masse du matériau (kg)
k_coke = 0.01  # Constante de formation du coke
E_a = 50000  # Énergie d'activation pour H2S (J/mol)
n = 100  # Nombre de moles de gaz
V = 10  # Volume du tambour (m³)

# Phases du processus de cokéfaction
PHASES = ["prechauffage", "reaction", "refroidissement", "decharge"]
phase_actuelle = "prechauffage"
phase_timer = 0
phase_duree = {"prechauffage": 60, "reaction": 120, "refroidissement": 90, "decharge": 30}  # durées en secondes pour la simulation

# Configuration des seuils des capteurs
CAPTEURS = {
    "temp_four": {
        "min": 480,
        "max": 500,
        "alarme": 500,
        "unite": "°C",
        "variation": 5
    },
    "pression_tambour": {
        "min": 1.5,
        "max": 2.3,
        "alarme": 2.5,
        "unite": "MPa",
        "variation": 0.2
    },
    "niveau_coke": {
        "min": 30,
        "max": 85,
        "alarme": 90,
        "unite": "%",
        "variation": 5
    },
    "debit_charge": {
        "min": 100,
        "max": 120,
        "alarme_min": 90,  # -10% de 100
        "alarme_max": 132,  # +10% de 120
        "unite": "m³/h",
        "variation": 8
    },
    "concentration_h2s": {
        "min": 0,
        "max": 5,
        "alarme": 10,
        "unite": "ppm",
        "variation": 1.5
    }
}

# Configuration
MACHINE_ID = "cokefaction_unit_01"
MQTT_TOPIC_PREFIX = "sensors"
MQTT_BROKER = "mqtt"  # Nom du service dans docker-compose
MQTT_PORT = 1883

# Variables globales pour suivre l'évolution des paramètres
temps_ecoule = 0
T_moyenne = T0
simulation_temps = 0

# Connexion au broker MQTT
try:
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print(f"Connecté au broker MQTT: {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"ERREUR de connexion au broker MQTT: {str(e)}")
    print("Tentative de connexion à localhost...")
    try:
        client = mqtt.Client()
        client.connect("localhost", MQTT_PORT, 60)
        print("Connecté au broker MQTT: localhost:1883")
    except Exception as e:
        print(f"ERREUR de connexion au broker MQTT local: {str(e)}")
        print("Assurez-vous que le broker MQTT est en cours d'exécution.")
        exit(1)

def update_phase():
    """Met à jour la phase actuelle du processus"""
    global phase_actuelle, phase_timer, T0, P0, N0, C0, Q_in
    
    phase_timer += 5  # Incrémentation de 5 secondes à chaque appel
    
    # Vérifier si on doit passer à la phase suivante
    if phase_timer >= phase_duree[phase_actuelle]:
        phase_timer = 0
        phase_index = PHASES.index(phase_actuelle)
        phase_actuelle = PHASES[(phase_index + 1) % len(PHASES)]
        
        # Ajuster les paramètres en fonction de la nouvelle phase
        if phase_actuelle == "prechauffage":
            T0 = 450
            P0 = 1.8
            N0 = 40
            C0 = 2
            Q_in = 5000
        elif phase_actuelle == "reaction":
            T0 = 480
            P0 = 2.0
            Q_in = 6000
        elif phase_actuelle == "refroidissement":
            T0 = 500
            P0 = 2.2
            Q_in = 1000
        elif phase_actuelle == "decharge":
            T0 = 300
            P0 = 1.5
            Q_in = 0
            
    return phase_actuelle

def calculer_temperature(t):
    """Calcule la température selon le modèle thermique"""
    global T_moyenne
    
    # T(t) = T0 + (Qin / (Cp * m)) * t
    delta_T = (Q_in / (Cp * m)) * t
    temperature = T0 + delta_T
    
    # Ajouter une variation aléatoire
    variation = random.uniform(-CAPTEURS["temp_four"]["variation"], CAPTEURS["temp_four"]["variation"])
    temperature += variation
    
    # Mettre à jour la température moyenne
    T_moyenne = (T_moyenne * 0.8) + (temperature * 0.2)  # moyenne mobile pondérée
    
    return round(temperature, 2)

def calculer_pression(t, temperature):
    """Calcule la pression selon la loi des gaz parfaits"""
    # P = nRT/V (convertir en MPa)
    pression = (n * R * (temperature + 273.15)) / (V * 1000000)
    
    # Ajouter une variation aléatoire
    variation = random.uniform(-CAPTEURS["pression_tambour"]["variation"], CAPTEURS["pression_tambour"]["variation"])
    pression += variation
    
    return round(pression, 2)

def calculer_niveau_coke(t):
    """Calcule le niveau de coke selon le modèle"""
    # N(t) = N0 + k_coke * (T_moyenne - T0) * t
    niveau = N0 + k_coke * (T_moyenne - T0) * t
    
    # Ajouter une variation aléatoire
    variation = random.uniform(-CAPTEURS["niveau_coke"]["variation"], CAPTEURS["niveau_coke"]["variation"])
    niveau += variation
    
    # Limiter entre 0 et 100%
    niveau = max(0, min(100, niveau))
    
    return round(niveau, 2)

def calculer_concentration_h2s(t, temperature):
    """Calcule la concentration de H2S selon le modèle cinétique"""
    # C_H2S = C0 * e^(-Ea/(R*T) * t)
    # Convertir température en Kelvin
    T_kelvin = temperature + 273.15
    concentration = C0 * math.exp(-(E_a / (R * T_kelvin)) * t)
    
    # Ajouter une variation aléatoire
    variation = random.uniform(-CAPTEURS["concentration_h2s"]["variation"], CAPTEURS["concentration_h2s"]["variation"])
    concentration += variation
    
    # Limiter à des valeurs positives
    concentration = max(0, concentration)
    
    return round(concentration, 2)

def calculer_debit_charge():
    """Calcule le débit de charge en fonction de la phase"""
    base_debit = CAPTEURS["debit_charge"]["min"]
    
    if phase_actuelle == "prechauffage":
        base_debit = 115
    elif phase_actuelle == "reaction":
        base_debit = 120
    elif phase_actuelle == "refroidissement":
        base_debit = 105
    elif phase_actuelle == "decharge":
        base_debit = 95
    
    # Ajouter une variation aléatoire
    variation = random.uniform(-CAPTEURS["debit_charge"]["variation"], CAPTEURS["debit_charge"]["variation"])
    debit = base_debit + variation
    
    return round(debit, 2)

def verifier_alarme(capteur, valeur):
    """Vérifie si la valeur dépasse le seuil d'alarme"""
    config = CAPTEURS[capteur]
    
    if capteur == "debit_charge":
        return valeur < config["alarme_min"] or valeur > config["alarme_max"]
    else:
        return valeur > config.get("alarme", float('inf')) or valeur < config.get("alarme_min", float('-inf'))

# Affichage des informations sur les capteurs
print("=== Simulateur de capteurs pour l'unité de cokéfaction retardée ===")
print("Flux de données: MQTT -> Kafka -> Spark -> MinIO/TimescaleDB")
print("\nCapteurs surveillés:")
for capteur, config in CAPTEURS.items():
    plage = f"{config['min']}-{config['max']} {config['unite']}"
    if capteur == "debit_charge":
        seuil = f"< {config['alarme_min']} ou > {config['alarme_max']} {config['unite']}"
    else:
        seuil = f"> {config.get('alarme', 'N/A')} {config['unite']}"
    print(f"- {capteur}: plage normale {plage}, alarme si {seuil}")

print(f"\nTopic MQTT: {MQTT_TOPIC_PREFIX}.<type_capteur>")
print("\nDémarrage de la simulation (Ctrl+C pour arrêter)...")

# Boucle d'envoi des données
try:
    while True:
        # Mettre à jour le temps de simulation
        simulation_temps += 5  # 5 secondes par itération
        temps_ecoule = simulation_temps / 60  # temps en minutes pour les modèles
        
        # Mettre à jour la phase du processus
        phase_actuelle = update_phase()
        
        # Timestamp ISO 8601
        timestamp = datetime.now().isoformat()
        
        # Calculer les valeurs des capteurs selon les modèles
        temperature = calculer_temperature(temps_ecoule)
        pression = calculer_pression(temps_ecoule, temperature)
        niveau_coke = calculer_niveau_coke(temps_ecoule)
        concentration_h2s = calculer_concentration_h2s(temps_ecoule, temperature)
        debit_charge = calculer_debit_charge()
        
        # Créer un identifiant avec la phase
        machine_id_avec_phase = f"{MACHINE_ID}_{phase_actuelle}"
        
        # Pour chaque capteur, vérifier l'alarme et envoyer les données
        capteurs_data = {
            "temp_four": temperature,
            "pression_tambour": pression,
            "niveau_coke": niveau_coke,
            "concentration_h2s": concentration_h2s,
            "debit_charge": debit_charge
        }
        
        for capteur, valeur in capteurs_data.items():
            alarme = verifier_alarme(capteur, valeur)
            
            # Afficher une alerte si nécessaire
            if alarme:
                print(f"ALARME: {capteur} = {valeur} {CAPTEURS[capteur]['unite']} (seuil dépassé)")
            
            # Préparer le message au format standardisé pour MQTT
            message_mqtt = {
                "timestamp": timestamp,
                "machine_id": machine_id_avec_phase,
                "type_capteur": capteur,
                "valeur": valeur,
                "unite": CAPTEURS[capteur]["unite"],
                "alarme": alarme
            }
            
            # Envoyer au broker MQTT
            mqtt_topic = f"{MQTT_TOPIC_PREFIX}.{capteur}"
            client.publish(mqtt_topic, json.dumps(message_mqtt))
            print(f"Message envoyé sur {mqtt_topic}: {json.dumps(message_mqtt)}")
        
        # Pause de 5 secondes
        time.sleep(5)
except KeyboardInterrupt:
    print("\nSimulation arrêtée")
    client.disconnect()
