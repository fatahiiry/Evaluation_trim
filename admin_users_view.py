import streamlit as st
from auth import create_user, get_all_users
from database import get_connection


def save_assignments(evaluator, selected_matricules):
    """Enregistre dans la BDD les matricules qu'un évaluateur a le droit d'évaluer."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Création de la table si elle n'existe pas encore
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_assignments (
                    evaluator_username VARCHAR(50),
                    target_matricule VARCHAR(50),
                    PRIMARY KEY (evaluator_username, target_matricule)
                )
            """
            )

            # Supprimer les anciennes affectations
            cursor.execute(
                "DELETE FROM user_assignments WHERE evaluator_username = ?",
                (evaluator,),
            )

            # Insérer les nouvelles affectations
            for target in selected_matricules:
                cursor.execute(
                    "INSERT INTO user_assignments (evaluator_username, target_matricule) VALUES (?, ?)",
                    (evaluator, target),
                )

            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erreur lors de l'enregistrement : {e}")
        finally:
            conn.close()
    return False

import streamlit as st
import auth


def render_user_management_page():
    st.title("👤 Administration des Utilisateurs & Affectations")
    st.markdown("---")

    tab1, tab2 = st.tabs(
        ["➕ Création d'Utilisateur", "🎯 Filtrage / Affectation des Matricules"]
    )

    # --- ONGLET 1 : CRÉATION D'UTILISATEUR ---
    with tab1:
        st.subheader("Créer un nouvel utilisateur / Manager")

        with st.form("create_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input(
                    "Matricule / Identifiant *", placeholder="Ex : EMP005"
                )
                new_role = st.selectbox(
                    "Rôle *",
                    ["Manager", "Administrateur"],
                )
            with col2:
                new_password = st.text_input(
                    "Mot de passe *", type="password"
                )
                confirm_password = st.text_input(
                    "Confirmer mot de passe *", type="password"
                )

            submit_create = st.form_submit_button(
                "Créer l'utilisateur", type="primary"
            )

            if submit_create:
                if (
                    not new_username.strip()
                    or not new_password
                    or not confirm_password
                ):
                    st.warning("Veuillez remplir tous les champs obligatoires.")
                elif new_password != confirm_password:
                    st.error("Les mots de passe ne correspondent pas.")
                else:
                    if auth.create_user(
                        username=new_username.strip(),
                        password=new_password,
                        role=new_role,
                    ):
                        st.success(
                            f"L'utilisateur **{new_username.strip()}** ({new_role}) a été créé avec succès !"
                        )
                        st.rerun()
                    else:
                        st.error(
                            "Erreur lors de la création (Matricule existant ou problème BDD)."
                        )

        # Liste récapitulative
        st.markdown("### Liste des Utilisateurs")
        user_list = auth.get_all_users()
        if user_list:
            st.dataframe(
                [{"Identifiant": u} for u in user_list],
                use_container_width=True,
            )

    # --- ONGLET 2 : AFFECTATION DES MATRICULES ---
    with tab2:
        st.subheader("Définir les matricules assignés à un Manager")

        user_list = auth.get_all_users()
        if not user_list:
            st.info("Aucun utilisateur disponible.")
            return

        selected_evaluator = st.selectbox(
            "Sélectionner le Manager", user_list
        )

        available_targets = [u for u in user_list if u != selected_evaluator]
        current_allowed = auth.get_allowed_matricules(selected_evaluator)

        selected_targets = st.multiselect(
            f"Matricules à évaluer par {selected_evaluator} :",
            options=available_targets,
            default=[m for m in current_allowed if m in available_targets],
        )

        if st.button("Enregistrer les affectations", type="primary"):
            if auth.save_user_assignments(selected_evaluator, selected_targets):
                st.success("Affectations enregistrées avec succès !")
            else:
                st.error("Échec de l'enregistrement.")