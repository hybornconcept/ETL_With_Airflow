from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task
from airflow.utils.dates import days_ago
import requests
import json

# Latitude and longitude for the desired location (London in this case)
LATITUDE = '8.3417'
LONGITUDE = '4.9757'
POSTGRES_CONN_ID='postgres_default'
API_CONN_ID='open_meteo_api'

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
}

with DAG(
    dag_id ='weather_etl_piepline',
    default_args=default_args,
    description='ETL DAG for weather data',
    schedule_interval='@daily',
    # tags=['weather', 'ETL'],
    catchup=False
) as dag:

    @task
    def extract_weather_data():
        """
        Extracts weather data from the Open Meteo API.
        """
        http_hook = HttpHook(method='GET', http_conn_id=API_CONN_ID)
        # The correct endpoint should include /v1/forecast
         ## get the API ENDPOINT
        # http://api.open-meteo.com/v1/forecast?latitude=8.3417&longitude=4.9757&current_weather=true
        response = http_hook.run(endpoint=f'/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch weather data: {response.status_code}")
        # This print statement is unreachable because of the return/raise above
        # print(response.json())
        
    @task()
    def transform_weather_data(weather_data):
        """Transform the extracted weather data."""
        current_weather = weather_data['current_weather']
        transformed_data = {
            'latitude': LATITUDE,
            'longitude': LONGITUDE,
            'temperature': current_weather['temperature'],
            'windspeed': current_weather['windspeed'],
            'winddirection': current_weather['winddirection'],
            'weathercode': current_weather['weathercode']
        }
        return transformed_data
    
    @task()
    def load_weather_data(transformed_data):
        """Load transformed data into PostgreSQL."""
        pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            windspeed FLOAT,
            winddirection FLOAT,
            weathercode INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Insert transformed data into the table
        cursor.execute("""
        INSERT INTO weather_data (latitude, longitude, temperature, windspeed, winddirection, weathercode)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            transformed_data['latitude'],
            transformed_data['longitude'],
            transformed_data['temperature'],
            transformed_data['windspeed'],
            transformed_data['winddirection'],
            transformed_data['weathercode']
        ))

        conn.commit()
        cursor.close()

    ## DAG Worflow- ETL Pipeline
    weather_data= extract_weather_data()
    transformed_data=transform_weather_data(weather_data)
    load_weather_data(transformed_data)

    

