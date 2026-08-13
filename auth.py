import hashlib
from database import get_connection


def check_user_db(username, password):
    """Vérifie les identifiants en BDD SQL Server et renvoie le rôle."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password_hash, role FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            if row:
                db_hash, role = row[0], row[1]
                input_hash = hashlib.sha256(password.encode()).hexdigest()
                if input_hash == db_hash:
                    return role if role else "Manager"
        except Exception as e:
            print(f"Erreur check_user_db: {e}")
        finally:
            conn.close()
    return None


def create_user(
    username, password, nom_complet=None, role="Manager", department=None
):
    """Crée un utilisateur dans la table 'users'."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Vérification d'existence
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?", (username,)
        )
        if cursor.fetchone()[0] > 0:
            return False

        if not nom_complet:
            nom_complet = username

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, nom_complet, role, department)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, password_hash, nom_complet, role, department),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False
    finally:
        conn.close()


def get_user_department(username):
    """Récupère le département associé à un identifiant utilisateur."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT department FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        except Exception as e:
            print(f"Erreur get_user_department: {e}")
        finally:
            conn.close()
    return None


def get_all_users():
    """Retourne la liste simple des identifiants (usernames) pour correspondre à votre main.py."""
    conn = get_connection()
    users = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users ORDER BY username")
            rows = cursor.fetchall()
            users = [r[0] for r in rows]
        except Exception as e:
            print(f"Erreur get_all_users: {e}")
        finally:
            conn.close()
    return users


def create_assignments_table_if_not_exists(cursor):
    """S'assure que la table d'affectation existe sous SQL Server (T-SQL)."""
    cursor.execute(
        """
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'user_assignments')
        BEGIN
            CREATE TABLE user_assignments (
                evaluator_username VARCHAR(50),
                target_matricule VARCHAR(50),
                PRIMARY KEY (evaluator_username, target_matricule)
            )
        END
        """
    )


def save_user_assignments(evaluator, selected_matricules):
    """Met à jour les matricules assignés à un évaluateur dans 'user_assignments'."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            create_assignments_table_if_not_exists(cursor)

            cursor.execute(
                "DELETE FROM user_assignments WHERE evaluator_username = ?",
                (evaluator,),
            )
            for target in selected_matricules:
                cursor.execute(
                    "INSERT INTO user_assignments (evaluator_username, target_matricule) VALUES (?, ?)",
                    (evaluator, target),
                )
            conn.commit()
            return True
        except Exception as e:
            print(f"Erreur save_user_assignments: {e}")
        finally:
            conn.close()
    return False


def get_allowed_matricules(evaluator_username):
    """Récupère la liste des matricules explicitement autorisés pour un évaluateur."""
    conn = get_connection()
    matricules = []
    if conn:
        try:
            cursor = conn.cursor()
            create_assignments_table_if_not_exists(cursor)
            conn.commit()

            cursor.execute(
                "SELECT target_matricule FROM user_assignments WHERE evaluator_username = ?",
                (evaluator_username,),
            )
            rows = cursor.fetchall()
            matricules = [str(r[0]) for r in rows]
        except Exception as e:
            print(f"Erreur get_allowed_matricules: {e}")
        finally:
            conn.close()
    return matricules


def admin_reset_password(target_username, new_password):
    """Re-hache et réinitialise le mot de passe d'un utilisateur."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, target_username),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Erreur admin_reset_password: {e}")
        finally:
            conn.close()
    return False