import json
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

# -----------------------------
# Configuration
# -----------------------------
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
# Mise à jour des topics pour correspondre au simulateur de capteurs
MQTT_TOPICS = [
    "sensors.temp_four",
    "sensors.pression_tambour", 
    "sensors.niveau_coke", 
    "sensors.debit_charge", 
    "sensors.concentration_h2s"
]

KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "sensor-data"

# -----------------------------
# Création du topic Kafka (si non existant)
# -----------------------------
def creer_topic_kafka():
    try:
        admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
        topic = NewTopic(name=KAFKA_TOPIC, num_partitions=1, replication_factor=1)
        admin_client.create_topics(new_topics=[topic], validate_only=False)
        print(f"✅ Topic Kafka '{KAFKA_TOPIC}' créé.")
    except Exception as e:
        print(f"ℹ️ Topic existe déjà ou erreur ignorée : {e}")

# -----------------------------
# Initialisation du producteur Kafka
# -----------------------------
def init_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

# -----------------------------
# Callback exécutée lors de la réception d'un message MQTT
# -----------------------------
def on_message(client, userdata, msg):
    print(f"📥 [MQTT] Reçu sur {msg.topic} → {msg.payload.decode()}")
    try:
        data = json.loads(msg.payload.decode())
        kafka_producer.send(KAFKA_TOPIC, data)
        kafka_producer.flush()
        print(f"📤 MQTT → Kafka | {msg.topic} → {KAFKA_TOPIC}")
    except Exception as e:
        print(f"[ERREUR] JSON invalide : {e}")

# -----------------------------
# Connexion au broker MQTT et abonnement
# -----------------------------
def init_mqtt_client():
    client = mqtt.Client()
    
    # Tenter de se connecter d'abord au broker MQTT dans Docker
    try:
        client.connect("mqtt", MQTT_PORT)
        print(f"Connecté au broker MQTT: mqtt:{MQTT_PORT}")
    except Exception as e:
        print(f"Impossible de se connecter à mqtt:{MQTT_PORT}, tentative sur localhost...")
        try:
            client.connect(MQTT_BROKER, MQTT_PORT)
            print(f"Connecté au broker MQTT: {MQTT_BROKER}:{MQTT_PORT}")
        except Exception as e:
            print(f"ERREUR de connexion au broker MQTT: {e}")
            return None

    for topic in MQTT_TOPICS:
        client.subscribe(topic)
        print(f"Abonné au topic MQTT: {topic}")

    client.on_message = on_message
    return client

# -----------------------------
# Lancement du bridge
# -----------------------------
if __name__ == "__main__":
    creer_topic_kafka()
    kafka_producer = init_kafka_producer()
    mqtt_client = init_mqtt_client()
    
    if mqtt_client:
        print("🔁 Bridge MQTT → Kafka actif. En attente de messages...")
        mqtt_client.loop_forever()
    else:
        print("❌ Impossible de démarrer le bridge MQTT → Kafka. Vérifiez que le broker MQTT est actif.")
