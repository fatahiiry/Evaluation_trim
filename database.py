import os
import pyodbc
import hashlib
from crypto_utils import decrypt_salary, encrypt_salary
from dotenv import load_dotenv

#load_dotenv()

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

def save_or_update_employee(matricule, nom_complet, poste, department, evaluator_username):
    """Insère ou met à jour un employé dans la table dbo.employees."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            query = """
                IF EXISTS (SELECT 1 FROM dbo.employees WHERE LTRIM(RTRIM(CAST(matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR))))
                BEGIN
                    UPDATE dbo.employees
                    SET nom_complet = ?, poste = ?, department = ?, evaluator_username = ?, updated_at = GETDATE()
                    WHERE LTRIM(RTRIM(CAST(matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR)))
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.employees (matricule, nom_complet, poste, department, evaluator_username)
                    VALUES (?, ?, ?, ?, ?)
                END
            """
            mat = str(matricule).strip()
            nom = str(nom_complet).strip()
            pst = str(poste).strip() if poste else ""
            dept = str(department).strip() if department else ""
            eval_usr = (
                str(evaluator_username).strip() if evaluator_username else ""
            )

            cursor.execute(
                query,
                (
                    mat,
                    nom,
                    pst,
                    dept,
                    eval_usr,
                    mat,
                    mat,
                    nom,
                    pst,
                    dept,
                    eval_usr,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Erreur SQL save_employee: {e}")
            return False
        finally:
            conn.close()
    return False

def get_dashboard_data_by_role(user_role, username, year, quarter):
    """Récupère les évaluations en effectuant le LEFT JOIN sur dbo.employees."""
    conn = get_connection()
    results = []
    if conn:
        try:
            cursor = conn.cursor()
            q_clean = str(quarter).replace("T", "").strip()
            user_clean = str(username).strip()

            if user_role == "Manager":
                query = """
                    SELECT 
                        e.target_matricule, 
                        ISNULL(emp.nom_complet, 'Employé ' + CAST(e.target_matricule AS VARCHAR)), 
                        ISNULL(emp.department, 'N/A'), 
                        e.note_totale, 
                        e.prime_finale, 
                        e.updated_at
                    FROM dbo.evaluations e
                    LEFT JOIN dbo.employees emp 
                        ON LTRIM(RTRIM(CAST(emp.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                    WHERE CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                      AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                      AND (
                          LTRIM(RTRIM(CAST(e.evaluator_username AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR)))
                          OR LTRIM(RTRIM(CAST(emp.evaluator_username AS VARCHAR))) = LTRIM(RTRIM(CAST(? AS VARCHAR)))
                      )
                """
                cursor.execute(query, (year, q_clean, user_clean, user_clean))
            else:
                # RH / DG / Administrateur
                query = """
                    SELECT 
                        e.target_matricule, 
                        ISNULL(emp.nom_complet, 'Employé ' + CAST(e.target_matricule AS VARCHAR)), 
                        ISNULL(emp.department, 'N/A'), 
                        e.note_totale, 
                        e.prime_finale, 
                        e.updated_at
                    FROM dbo.evaluations e
                    LEFT JOIN dbo.employees emp 
                        ON LTRIM(RTRIM(CAST(emp.matricule AS VARCHAR))) = LTRIM(RTRIM(CAST(e.target_matricule AS VARCHAR)))
                    WHERE CAST(e.year AS VARCHAR) = CAST(? AS VARCHAR) 
                      AND CAST(e.quarter AS VARCHAR) = CAST(? AS VARCHAR)
                """
                cursor.execute(query, (year, q_clean))

            rows = cursor.fetchall()
            for r in rows:
                results.append(
                    {
                        "matricule": r[0],
                        "nom_complet": r[1],
                        "department": r[2],
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

def save_employee_salary(matricule: str, amount: float):
    """Insère ou met à jour un salaire chiffré en BDD."""
    encrypted_val = encrypt_salary(amount)
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                MERGE dbo.salaires_chiffres AS target
                USING (SELECT ? AS target_matricule) AS source
                ON (target.target_matricule = source.target_matricule)
                WHEN MATCHED THEN
                    UPDATE SET salaire_encrypted = ?, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (target_matricule, salaire_encrypted) VALUES (?, ?);
            """,
                (
                    str(matricule).strip(),
                    encrypted_val,
                    str(matricule).strip(),
                    encrypted_val,
                ),
            )
            conn.commit()
        finally:
            conn.close()

def get_employee_salary(matricule: str) -> float:
    """Récupère et déchiffre le salaire d'un employé depuis la BDD."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT salaire_encrypted FROM dbo.salaires_chiffres WHERE target_matricule = ?",
                (str(matricule).strip(),),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return decrypt_salary(row[0])
        finally:
            conn.close()
    return 0.0

def get_criteres_actifs(is_director: bool = False):
    """Récupère les critères actifs depuis SQL Server."""
    conn = get_connection()
    criteres = []
    if conn:
        try:
            cursor = conn.cursor()
            query = """
                SELECT code_critere, titre, description, poids, type_critere, cible_role 
                FROM dbo.criteres 
                WHERE is_active = 1 AND (cible_role = 'ALL' OR (? = 1 AND cible_role = 'DIRECTEUR'))
                ORDER BY type_critere DESC, id ASC
            """
            cursor.execute(query, (1 if is_director else 0,))
            rows = cursor.fetchall()
            for r in rows:
                criteres.append(
                    {
                        "code_critere": r[0],
                        "titre": r[1],
                        "description": r[2],
                        "poids": float(r[3]),
                        "type_critere": r[4],
                        "cible_role": r[5],
                    }
                )
        except Exception as e:
            print(f"Erreur lors de la récupération des critères : {e}")
        finally:
            conn.close()
    return criteres

def get_criteres_for_target(is_grand_responsable=False, target_matricule=None):
    conn = get_connection()
    criteres = []
    if conn:
        try:
            cursor = conn.cursor()

            # Utilisation de ISNULL / COALESCE pour gérer les matricules spécifiques
            query = """
                SELECT code_critere, titre, description, poids, type_critere 
                FROM dbo.criteres 
                WHERE (cible_role = 'ALL' AND target_matricule IS NULL)
                   OR (? = 1 AND cible_role = 'CADRE_DIRIGEANT' AND target_matricule IS NULL)
                   OR (target_matricule = ?)
            """

            is_leader_flag = 1 if is_grand_responsable else 0
            clean_mat = str(target_matricule).strip() if target_matricule else ""

            cursor.execute(query, (is_leader_flag, clean_mat))

            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                criteres.append(dict(zip(columns, row)))
        except Exception as e:
            print(f"Erreur SQL get_criteres_for_target : {e}")
        finally:
            conn.close()

    return criteres

def add_extra_critere(code_critere, titre, description, poids, type_critere, target_matricule=None, cible_role="CADRE_DIRIGEANT"):
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dbo.criteres (code_critere, titre, description, poids, type_critere, cible_role, target_matricule)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code_critere, titre, description, poids, type_critere, cible_role, target_matricule))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def update_critere(code_critere, titre, description, poids, type_critere):
    """Met à jour un critère existant et sa pondération."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dbo.criteres
                SET titre = ?, description = ?, poids = ?, type_critere = ?
                WHERE code_critere = ?
            """, (titre, description, poids, type_critere, code_critere))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def delete_critere(code_critere):
    """Supprime un critère spécifique."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dbo.criteres WHERE code_critere = ?", (code_critere,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def init_db():
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Création de la table des détails des critères si elle n'existe pas
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.evaluation_details') AND type in (N'U'))
                BEGIN
                    CREATE TABLE dbo.evaluation_details (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        evaluation_id INT NOT NULL,
                        code_critere NVARCHAR(50) NOT NULL,
                        titre_critere NVARCHAR(255) NULL,
                        description_critere NVARCHAR(MAX) NULL,
                        note FLOAT NOT NULL,
                        poids_applique FLOAT NOT NULL,
                        created_at DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (evaluation_id) REFERENCES dbo.evaluations(id) ON DELETE CASCADE
                    );
                END
            """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()