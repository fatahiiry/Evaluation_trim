import os
import pyodbc
import hashlib
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    server = os.getenv("DB_SERVER", "172.31.221.249")
    database = os.getenv("DB_NAME", "Evaluation_RH")
    driver = os.getenv("DB_DRIVER", "{ODBC Driver 17 for SQL Server}")

    conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"Erreur connexion BDD: {e}")
        return None


def init_db():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
                BEGIN
                    CREATE TABLE users (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(64) NOT NULL
                    )
                END
            """)
            conn.commit()

            # Création automatique du compte DG001 si non existant (Mot de passe par défaut: 123456)
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("DG001",))
            if cursor.fetchone()[0] == 0:
                pwd_hash = hashlib.sha256("123456".encode()).hexdigest()
                cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    ("DG001", pwd_hash)
                )
                conn.commit()

        except Exception as e:
            print(f"Erreur init_db: {e}")
        finally:
            conn.close()