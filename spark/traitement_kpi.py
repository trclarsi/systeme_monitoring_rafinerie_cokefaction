from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, window, avg, expr, lit
from pyspark.sql.types import StructType, StringType, FloatType, BooleanType, TimestampType

# 1. Définir le schéma du message JSON pour correspondre au format du simulateur
schema = StructType() \
    .add("timestamp", StringType()) \
    .add("machine_id", StringType()) \
    .add("type_capteur", StringType()) \
    .add("valeur", FloatType()) \
    .add("unite", StringType()) \
    .add("alarme", BooleanType())

# 2. Initialiser la session Spark avec accès à MinIO
spark = SparkSession.builder \
    .appName("raffinerie-iot") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,org.postgresql:postgresql:42.6.0") \
    .config("spark.hadoop.fs.s3a.access.key", "minio") \
    .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

# 3. Lire les données depuis Kafka
df = spark.readStream.format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "sensor-data") \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

# 4. Convertir les messages JSON
json_df = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# Convertir le timestamp en format TimestampType
json_df = json_df.withColumn("timestamp", expr("to_timestamp(timestamp)"))

# Afficher le schéma pour vérification
print("Schéma des données reçues de Kafka:")
json_df.printSchema()

# 5. Sauvegarde brute dans MinIO (au format JSON compressé)
minio_query = json_df.writeStream \
    .format("json") \
    .option("path", "s3a://raffinerie-raw") \
    .option("checkpointLocation", "/app/data/checkpoint_minio") \
    .outputMode("append") \
    .start()

print("Écriture vers MinIO configurée")

# 6. Fonction batch pour enregistrer toutes les mesures dans TimescaleDB (table mesures)
def save_to_mesures(batch_df, batch_id):
    if batch_df.count() > 0:
        print(f"Écriture du batch {batch_id} dans la table mesures ({batch_df.count()} lignes)")
        batch_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://timescaledb:5432/iotdb") \
            .option("dbtable", "mesures") \
            .option("user", "admin") \
            .option("password", "admin") \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
        print(f"Batch {batch_id} écrit avec succès dans TimescaleDB (mesures)")
    else:
        print(f"Batch {batch_id} vide, rien à écrire")

# 7. Écriture batch des données dans la table mesures
mesures_query = json_df.writeStream \
    .foreachBatch(save_to_mesures) \
    .outputMode("append") \
    .option("checkpointLocation", "/app/data/checkpoint_mesures") \
    .start()

print("Écriture vers TimescaleDB (mesures) configurée")

# 8. Calcul KPI : moyenne glissante sur 1 minute par type de capteur
# Créer une table temporaire pour stocker les unités par type de capteur
# et les utiliser plus tard lors de l'agrégation
kpi = json_df.withColumn("ts", col("timestamp")) \
    .withWatermark("ts", "30 seconds") \
    .groupBy(window("ts", "1 minute"), "type_capteur") \
    .agg(
        avg("valeur").alias("valeur"),
        expr("first(unite)").alias("unite_capteur")  # Capture l'unité pour chaque groupe
    ) \
    .withColumn("type_kpi", col("type_capteur")) \
    .selectExpr("window.start as timestamp", "type_kpi", "valeur", "unite_capteur as unite")

# 9. Fonction batch pour enregistrer les KPI dans TimescaleDB
def save_kpi_to_pg(batch_df, batch_id):
    if batch_df.count() > 0:
        print(f"Écriture du batch KPI {batch_id} dans la table kpi_indicateurs")
        batch_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://timescaledb:5432/iotdb") \
            .option("dbtable", "kpi_indicateurs") \
            .option("user", "admin") \
            .option("password", "admin") \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
        print(f"KPI du batch {batch_id} écrits avec succès")
    else:
        print(f"Batch KPI {batch_id} vide, rien à écrire")

# 10. Écriture batch des KPI
kpi_query = kpi.writeStream \
    .foreachBatch(save_kpi_to_pg) \
    .outputMode("append") \
    .option("checkpointLocation", "/app/data/checkpoint_kpi") \
    .start()

print("Écriture des KPI configurée")
print("En attente de données...")

# 11. Attendre la fin des traitements
spark.streams.awaitAnyTermination()
