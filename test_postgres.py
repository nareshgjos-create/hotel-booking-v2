import psycopg
 
conn = psycopg.connect(
    "dbname=hotel_booking user=postgres password=password host=localhost port=5432"
)
 
print("Connected successfully")
 
conn.close()