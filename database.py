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

            # 1. Table Utilisateurs
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
                BEGIN
                    CREATE TABLE users (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(64) NOT NULL,
                        nom_complet VARCHAR(100) NULL,
                        role VARCHAR(50) DEFAULT 'Manager',
                        department VARCHAR(100) NULL
                    )
                END
            """)

            # 2. Table Affectations (Manager -> Employés)
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'user_assignments')
                BEGIN
                    CREATE TABLE user_assignments (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        evaluator_username VARCHAR(50) NOT NULL,
                        target_matricule VARCHAR(50) NOT NULL,
                        CONSTRAINT UQ_evaluator_target UNIQUE (evaluator_username, target_matricule)
                    )
                END
            """)

            # 3. Table Configuration RH Trimestrielle (Coefficient Usine)
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'rh_quarter_config')
                BEGIN
                    CREATE TABLE rh_quarter_config (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        year INT NOT NULL,
                        quarter INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
                        coef_usine DECIMAL(5, 2) NOT NULL,
                        updated_by VARCHAR(50) NULL,
                        created_at DATETIME DEFAULT GETDATE(),
                        updated_at DATETIME DEFAULT GETDATE(),
                        CONSTRAINT UQ_rh_quarter_year UNIQUE (year, quarter)
                    )
                END
            """)

            # 4. Table des Évaluations enregistrées par les Managers
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'evaluations')
                BEGIN
                    CREATE TABLE evaluations (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        target_matricule VARCHAR(50) NOT NULL,
                        evaluator_username VARCHAR(50) NOT NULL,
                        year INT NOT NULL,
                        quarter INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
                        note_totale DECIMAL(4, 2) NOT NULL,
                        coef_usine_applique DECIMAL(5, 2) NOT NULL,
                        base_salary DECIMAL(18, 2) DEFAULT 0.0,
                        prime_finale DECIMAL(18, 2) NOT NULL,
                        created_at DATETIME DEFAULT GETDATE(),
                        updated_at DATETIME DEFAULT GETDATE(),
                        CONSTRAINT UQ_emp_eval_quarter UNIQUE (target_matricule, year, quarter)
                    )
                END
            """)

            conn.commit()

            # Création automatique du compte DG001 si non existant (Mot de passe par défaut: 123456)
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("DG001",))
            if cursor.fetchone()[0] == 0:
                pwd_hash = hashlib.sha256("123456".encode()).hexdigest()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ("DG001", pwd_hash, "Administrateur")
                )
                conn.commit()

        except Exception as e:
            print(f"Erreur init_db: {e}")
        finally:
            conn.close()

# --- FONCTIONS DE GESTION DU COEFFICIENT RH ---
def get_coef_usine_by_quarter(year: int, quarter: int) -> float:
    """Récupère le Coef Usine RH du trimestre (4.0% par défaut si non paramétré)."""
    conn = get_connection()
    val = 4.0
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT coef_usine FROM rh_quarter_config WHERE year = ? AND quarter = ?",
                (year, quarter),
            )
            row = cursor.fetchone()
            if row:
                val = float(row[0])
        except Exception as e:
            print(f"Erreur lecture coef usine: {e}")
        finally:
            conn.close()
    return val

def save_coef_usine_by_quarter(year: int, quarter: int, coef_usine: float, username: str = None):
    """Enregistre ou met à jour le Coef Usine RH pour un trimestre."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                MERGE rh_quarter_config AS target
                USING (SELECT ? AS year, ? AS quarter) AS source
                ON (target.year = source.year AND target.quarter = source.quarter)
                WHEN MATCHED THEN
                    UPDATE SET coef_usine = ?, updated_by = ?, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (year, quarter, coef_usine, updated_by)
                    VALUES (?, ?, ?, ?);
            """,
                (
                    year,
                    quarter,
                    coef_usine,
                    username,
                    year,
                    quarter,
                    coef_usine,
                    username,
                ),
            )
            conn.commit()
        except Exception as e:
            print(f"Erreur enregistrement coef usine: {e}")
        finally:
            conn.close()

def get_active_quarter_config():
    """Récupère l'année et le trimestre actifs depuis rh_quarter_config."""
    conn = get_connection()
    config = {"year": 2026, "quarter": 3}  # Valeurs de secours
    if conn:
        try:
            cursor = conn.cursor()
            query = "SELECT TOP 1 year, quarter FROM dbo.rh_quarter_config ORDER BY updated_at DESC"
            cursor.execute(query)
            row = cursor.fetchone()
            if row:
                config["year"] = row[0]
                config["quarter"] = row[1]
        except Exception as e:
            print(f"Erreur SQL Config Quarter: {e}")
        finally:
            conn.close()
    return config

def get_dashboard_data_by_role(user_role, username, year, quarter):
    """Récupère les collaborateurs et leurs notes avec gestion des espaces et secours SQL."""
    conn = get_connection()
    results = []
    if conn:
        try:
            cursor = conn.cursor()

            # Extraction de la valeur numérique du trimestre (ex: '3')
            q_clean = str(quarter).replace("T", "").strip()
            user_clean = str(username).strip()

            if user_role == "Manager":
                # Recherche des collaborateurs assignés au Manager
                query = """
                    SELECT 
                        u.matricule, 
                        u.nom_complet, 
                        u.department, 
                        e.note_totale, 
                        e.prime_finale, 
                        e.updated_at
                    FROM dbo.user_assignments ua
                    JOIN dbo.users u 
                        ON LTRIM(RTRIM(CAST(ua.target_matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(u.matricule AS VARCHAR)))
                    LEFT JOIN dbo.evaluations e 
                        ON LTRIM(RTRIM(CAST(u.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                       AND CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                       AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                    WHERE LTRIM(RTRIM(CAST(ua.evaluator_username AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR)))
                """
                cursor.execute(query, (year, q_clean, user_clean))
                rows = cursor.fetchall()

                # FALLBACK MANAGER : Si aucune affectation n'est trouvée dans user_assignments,
                # on affiche au moins les employés où il apparaît comme évaluateur dans evaluations
                if not rows:
                    query_fallback = """
                        SELECT 
                            u.matricule, 
                            u.nom_complet, 
                            u.department, 
                            e.note_totale, 
                            e.prime_finale, 
                            e.updated_at
                        FROM dbo.evaluations e
                        JOIN dbo.users u 
                            ON LTRIM(RTRIM(CAST(u.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                        WHERE CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                          AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                          AND LTRIM(RTRIM(CAST(e.evaluator_username AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR)))
                    """
                    cursor.execute(query_fallback, (year, q_clean, user_clean))
                    rows = cursor.fetchall()

            elif user_role == "RH":
                query = """
                    SELECT 
                        u.matricule, 
                        u.nom_complet, 
                        u.department, 
                        e.note_totale, 
                        e.prime_finale, 
                        e.updated_at
                    FROM dbo.users u
                    LEFT JOIN dbo.evaluations e 
                        ON LTRIM(RTRIM(CAST(u.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                       AND CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                       AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                    WHERE u.role NOT IN ('Administrateur', 'DG')
                """
                cursor.execute(query, (year, q_clean))
                rows = cursor.fetchall()

            else:  # DG / Administrateur
                query = """
                    SELECT 
                        u.matricule, 
                        u.nom_complet, 
                        u.department, 
                        e.note_totale, 
                        e.prime_finale, 
                        e.updated_at
                    FROM dbo.users u
                    LEFT JOIN dbo.evaluations e 
                        ON LTRIM(RTRIM(CAST(u.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                       AND CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                       AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                """
                cursor.execute(query, (year, q_clean))
                rows = cursor.fetchall()

            for r in rows:
                results.append(
                    {
                        "matricule": r[0],
                        "nom_complet": r[1],
                        "department": r[2] or "N/A",
                        "note_totale": r[3],
                        "prime_finale": r[4],
                        "statut": (
                            "✅ Fait" if r[3] is not None else "❌ Non fait"
                        ),
                        "date_evaluation": r[5],
                    }
                )

        except Exception as e:
            print(f"Erreur SQL Dashboard: {e}")
        finally:
            conn.close()

    return results

def get_evolution_scores(matricule):
    """Récupère l'historique des notes trimestrielles d'un employé."""
    conn = get_connection()
    history = []
    if conn:
        try:
            cursor = conn.cursor()
            query = """
                SELECT year, quarter, note_totale, prime_finale
                FROM dbo.evaluations
                WHERE target_matricule = ?
                ORDER BY year ASC, quarter ASC
            """
            cursor.execute(query, (matricule,))
            for r in cursor.fetchall():
                history.append(
                    {
                        "Periode": f"{r[0]} - T{str(r[1]).replace('T', '')}",
                        "Note": float(r[2]) if r[2] is not None else 0.0,
                        "Prime": float(r[3]) if r[3] is not None else 0.0,
                    }
                )
        except Exception as e:
            print(f"Erreur SQL Evolution: {e}")
        finally:
            conn.close()
    return history