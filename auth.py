import hashlib
import re
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


def verify_password(username, password):
    """Vérifie le mot de passe actuel d'un utilisateur (utilisé lors du changement de mot de passe)."""
    if not username or not password:
        return False

    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                db_hash = row[0]
                input_hash = hashlib.sha256(password.encode()).hexdigest()
                return input_hash == db_hash
        except Exception as e:
            print(f"Erreur verify_password: {e}")
        finally:
            conn.close()
    return False


def update_password(username, new_password):
    """Met à jour le mot de passe d'un utilisateur en BDD après vérification."""
    if not username or not new_password:
        return False, "Nom d'utilisateur ou mot de passe manquant."

    # Validation des règles de sécurité (8 char, 1 maj, 1 min, 1 chiffre)
    is_valid, msg = is_password_strong(new_password)
    if not is_valid:
        return False, msg

    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username),
            )
            conn.commit()
            return True, "Mot de passe modifié avec succès !"
        except Exception as e:
            print(f"Erreur update_password: {e}")
            return False, "Erreur serveur lors de la mise à jour."
        finally:
            conn.close()
    return False, "Erreur de connexion à la base de données."


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


def is_password_strong(password: str) -> tuple[bool, str]:
    """
    Vérifie les exigences de sécurité du mot de passe :
    - Au moins 8 caractères
    - Au moins 1 lettre majuscule
    - Au moins 1 lettre minuscule
    - Au moins 1 chiffre

    Retourne (True, "") si valide, sinon (False, "Message d'erreur").
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    if not re.search(r"[A-Z]", password):
        return False, "Le mot de passe doit contenir au moins une lettre majuscule."
    if not re.search(r"[a-z]", password):
        return False, "Le mot de passe doit contenir au moins une lettre minuscule."
    if not re.search(r"\d", password):
        return False, "Le mot de passe doit contenir au moins un chiffre."

    return True, ""


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


def create_user(
    username, password, nom_complet=None, role="Manager", department=None
):
    """Crée un utilisateur dans la table 'users' après validation du mot de passe."""
    conn = get_connection()
    if not conn:
        return False, "Erreur de connexion à la base de données."

    # Validation du mot de passe
    is_valid, msg = is_password_strong(password)
    if not is_valid:
        return False, msg

    try:
        cursor = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Vérification d'existence
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?", (username,)
        )
        if cursor.fetchone()[0] > 0:
            return False, f"L'utilisateur '{username}' existe déjà."

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
        return True, f"Compte '{username}' ({role}) créé avec succès !"
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return False, "Erreur serveur lors de la création de l'utilisateur."
    finally:
        conn.close()


def admin_reset_password(target_username, new_password):
    """Re-hache et réinitialise le mot de passe d'un utilisateur par l'admin."""
    if not target_username or not new_password:
        return False, "Nom d'utilisateur ou mot de passe manquant."

    # Validation du mot de passe
    is_valid, msg = is_password_strong(new_password)
    if not is_valid:
        return False, msg

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
            return True, f"Mot de passe de '{target_username}' réinitialisé avec succès !"
        except Exception as e:
            print(f"Erreur admin_reset_password: {e}")
            return False, "Erreur lors de la réinitialisation en BDD."
        finally:
            conn.close()
    return False, "Erreur de connexion à la base de données."


def get_user_details(username):
    """
    Récupère le nom complet, le département et le rôle d'un utilisateur depuis la table users.
    """
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT nom_complet, department, role FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            if row:
                nom_complet = row[0] if row[0] and row[0].strip() else username
                dept = row[1]
                role = row[2]
                return {
                    "nom_complet": nom_complet,
                    "department": dept,
                    "role": role
                }
        except Exception as e:
            print(f"Erreur get_user_details: {e}")
        finally:
            conn.close()
    return {"nom_complet": username, "department": None, "role": None}


def update_user_role(username, new_role):
    """Met à jour le rôle d'un utilisateur dans la table dbo.users."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            query = """
                UPDATE dbo.users 
                SET role = ? 
                WHERE LTRIM(RTRIM(username)) = ?
            """
            cursor.execute(query, (new_role, username.strip()))
            conn.commit()
            return True
        except Exception as e:
            print(f"Erreur update_user_role: {e}")
            return False
        finally:
            conn.close()
    return False


def get_users_list_for_management(current_logged_username=None):
    """Récupère tous les utilisateurs et compare le statut en ligne avec comparaison stricte/nettoyée."""
    conn = get_connection()
    users = []
    if conn:
        try:
            cursor = conn.cursor()

            query = """
                SELECT 
                    LTRIM(RTRIM(u.username)) AS matricule,
                    ISNULL(u.nom_complet, u.username) AS utilisateur,
                    ISNULL(u.role, 'Manager') AS role,
                    ISNULL(u.department, 'RH') AS department,
                    COUNT(e.matricule) AS nb_collaborateurs
                FROM dbo.users u
                LEFT JOIN dbo.employees e 
                    ON LTRIM(RTRIM(u.username)) = LTRIM(RTRIM(e.evaluator_username))
                GROUP BY u.username, u.nom_complet, u.role, u.department
                ORDER BY u.role ASC, u.username ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            # Nettoyage de l'utilisateur courant pour la comparaison
            clean_current_user = (
                str(current_logged_username).strip().lower()
                if current_logged_username
                else ""
            )

            for r in rows:
                matricule = str(r[0]).strip() if r[0] else ""
                utilisateur = str(r[1]).strip() if r[1] else matricule
                role_val = str(r[2]).strip() if r[2] else "Manager"
                department_val = str(r[3]).strip() if r[3] else "RH"
                nb_collabs = r[4]

                # Comparaison exacte sans tenir compte des majuscules/minuscules ou espaces
                is_online = (
                    clean_current_user != ""
                    and matricule.lower() == clean_current_user
                )

                users.append(
                    {
                        "matricule": matricule,
                        "utilisateur": utilisateur,
                        "role": role_val,
                        "department": department_val,
                        "statut": "Actif",
                        "is_online": is_online,
                        "nb_collaborateurs": nb_collabs,
                    }
                )
        except Exception as e:
            print(f"Erreur get_users_list_for_management: {e}")
        finally:
            conn.close()

    return users
