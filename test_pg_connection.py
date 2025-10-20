import psycopg2

try:
    conn = psycopg2.connect(
        dbname="sysfinance_django",
        user="postgres",
        password="matrix@102550",
        host="localhost",
        port="5432"
    )
    print("Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print("Erro na conexão:", e)
