# main.py
import pandas as pd
import streamlit as st
import auth
from auth_view import render_login_page
import database as db
import evaluation_view
import rh_config_view
import quarter_utils
import dashboard_view
import employee_management_view
import rh_salary_view
from ui_styles import apply_custom_styles, reset_password_dialog, inject_modern_css

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Portail EVALUATION RH", page_icon="📋", layout="wide"
)

# Initialisation BDD & Application des styles
db.init_db()
apply_custom_styles()
inject_modern_css()

# Gestion de l'état de session
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None

# --- 1. MIRE DE CONNEXION ---
if not st.session_state["authenticated"]:
    render_login_page()

# --- 2. APPLICATION PRINCIPALE (UTILISATEUR CONNECTÉ) ---
else:
    st.markdown(
        "<style>[data-testid='stSidebar'] {display: block !important;}</style>",
        unsafe_allow_html=True,
    )

    current_user = st.session_state["username"]
    user_role = st.session_state["role"]

    # --- HÉRARCHIE ET MATRICE DES DROITS ---
    is_admin = user_role == "Administrateur"
    is_rh = user_role in ["RH", "Administrateur"]  # Accès administration RH
    is_dg = user_role == "DG"

    # Récupération du département de l'utilisateur connecté
    user_dept = auth.get_user_department(current_user)

    st.sidebar.title("👤 Profil Utilisateur")

    # Affichage des infos du profil
    info_text = f"**Identifiant :** {current_user}\n\n**Rôle :** {user_role}"
    if user_dept:
        info_text += f"\n\n**Département :** {user_dept}"
    st.sidebar.info(info_text)

    # Bouton "Changer le mot de passe"
    if st.sidebar.button("🔑 Changer le mot de passe", use_container_width=True):
        reset_password_dialog()

    # Bouton de déconnexion
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["role"] = None
        st.rerun()

    # Charger la liste globale des employés depuis SQL Server pour les menus d'admin
    conn = db.get_connection()
    df_employees = pd.DataFrame()
    if conn:
        try:
            df_employees = pd.read_sql(
                "SELECT matricule AS Matricule, nom_complet AS Employé, poste AS Poste, department AS Département, evaluator_username FROM dbo.employees",
                conn,
            )
        except Exception:
            pass
        finally:
            conn.close()

    # --- SECTION RH ET ADMINISTRATION (ACCESSIBLE AUX RH ET ADMIN) ---
    if is_rh:
        st.sidebar.markdown("---")
        st.sidebar.title("⚙️ Administration & RH")

        # 1. PARAMÉTRAGE DU COEFFICIENT USINE
        with st.sidebar.expander("🏭 Coefficient Usine Trimestriel"):
            rh_config_view.render_rh_config_view()

        # 2. CRÉATION D'UTILISATEUR
        with st.sidebar.expander("➕ Créer un utilisateur"):
            new_u = st.text_input("Identifiant / Matricule", key="admin_new_u")
            new_nom = st.text_input(
                "Nom complet (Ex: Jean Dupont)", key="admin_new_nom"
            )
            new_p = st.text_input(
                "Mot de passe", type="password", key="admin_new_p"
            )
            new_role = st.selectbox(
                "Rôle :",
                options=["Manager", "RH", "DG", "Administrateur"],
                key="admin_new_role",
            )

            deps_list = []
            if not df_employees.empty and "Département" in df_employees.columns:
                deps_list = (
                    df_employees["Département"].dropna().unique().tolist()
                )

            selected_dept = st.selectbox(
                "Département assigné :",
                options=["(Aucun / RH / DG / Admin)"] + deps_list,
                key="admin_new_dept",
            )

            if st.button("Créer le compte", use_container_width=True):
                if new_u and new_p:
                    dept_val = (
                        None
                        if selected_dept == "(Aucun / RH / DG / Admin)"
                        else selected_dept
                    )
                    nom_val = new_nom.strip() if new_nom else new_u.strip()

                    if auth.create_user(
                        username=new_u.strip(),
                        password=new_p,
                        nom_complet=nom_val,
                        role=new_role,
                        department=dept_val,
                    ):
                        st.success(
                            f"Compte '{new_u}' ({new_role}) créé avec succès !"
                        )
                    else:
                        st.error("L'utilisateur existe déjà ou erreur BDD.")
                else:
                    st.warning(
                        "Veuillez remplir au moins l'identifiant et le mot de passe."
                    )

        # 3. AFFECTATION DES EMPLOIÉS
        with st.sidebar.expander("🎯 Affecter des employés à un Manager"):
            all_users = auth.get_all_users()

            if all_users:
                selected_evaluator = st.selectbox(
                    "Choisir le Manager :", options=all_users, key="admin_select_eval"
                )

                if (
                    not df_employees.empty
                    and "Matricule" in df_employees.columns
                    and "Employé" in df_employees.columns
                ):
                    df_temp = df_employees.copy()
                    df_temp["Matricule_Str"] = df_temp["Matricule"].astype(str)

                    df_temp["Display_Label"] = df_temp.apply(
                        lambda row: f"{row['Employé']} - {row.get('Département', 'N/A')} ({row['Matricule_Str']})",
                        axis=1,
                    )

                    label_to_matricule = dict(
                        zip(df_temp["Display_Label"], df_temp["Matricule_Str"])
                    )
                    matricule_to_label = dict(
                        zip(df_temp["Matricule_Str"], df_temp["Display_Label"])
                    )

                    all_display_options = df_temp["Display_Label"].tolist()

                    conn = db.get_connection()
                    current_allowed_mats = []
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT target_matricule FROM user_assignments WHERE evaluator_username = ?",
                                (selected_evaluator,),
                            )
                            rows = cursor.fetchall()
                            current_allowed_mats = [str(r[0]) for r in rows]
                        except Exception:
                            pass
                        finally:
                            conn.close()

                    default_selected_labels = [
                        matricule_to_label[m]
                        for m in current_allowed_mats
                        if m in matricule_to_label
                    ]

                    selected_labels = st.multiselect(
                        f"Employés affectés à {selected_evaluator} :",
                        options=all_display_options,
                        default=default_selected_labels,
                        key=f"mats_{selected_evaluator}",
                    )

                    selected_mats_to_save = [
                        label_to_matricule[label] for label in selected_labels
                    ]

                    if st.button(
                        "Enregistrer les affectations", use_container_width=True
                    ):
                        if auth.save_user_assignments(
                            selected_evaluator, selected_mats_to_save
                        ):
                            st.success("Affectations enregistrées !")
                        else:
                            st.error("Erreur lors de l'enregistrement.")
                else:
                    st.warning("Aucun employé trouvé en BDD SQL.")

        # 4. RÉINITIALISATION DU MOT DE PASSE
        with st.sidebar.expander("🔑 Réinitialiser un mot de passe"):
            all_users_list = auth.get_all_users()
            if all_users_list:
                user_to_reset = st.selectbox(
                    "Sélectionner l'utilisateur :",
                    options=all_users_list,
                    key="admin_reset_user_select",
                )
                temp_password = st.text_input(
                    "Nouveau mot de passe temporaire :",
                    type="password",
                    key="admin_temp_pass_input",
                )

                if st.button(
                    "Réinitialiser le mot de passe", use_container_width=True
                ):
                    if user_to_reset and temp_password:
                        if auth.admin_reset_password(
                            user_to_reset, temp_password
                        ):
                            st.success(
                                f"Mot de passe de '{user_to_reset}' réinitialisé !"
                            )
                        else:
                            st.error("Erreur lors de la réinitialisation.")
                    else:
                        st.warning("Veuillez saisir un mot de passe.")

    # --- ENTÊTE PRINCIPAL STYLISÉ ---
    st.markdown(
        """
        <div class="main-header">
            <h1>📋 Portail d'Évaluation RH</h1>
            <p>Gestion et suivi des performances trimestrielles des collaborateurs</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # --- FONCTION INTERNE DE RENDU DU FORMULAIRE D'ÉVALUATION ---
    def render_evaluation_tab_content():
        config = db.get_active_quarter_config()
        selected_year = config["year"]
        selected_quarter = config["quarter"]

        st.caption(
            f"🗓️ Période d'évaluation active : **Trimestre {selected_quarter} - {selected_year}**"
        )
        st.divider()

        if df_employees.empty:
            st.warning(
                "⚠️ Aucun collaborateur trouvé en base de données. Veuillez ajouter des employés via l'onglet 'Gestion Collaborateurs'."
            )
        else:
            conn = db.get_connection()
            explicit_mats = []
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT target_matricule FROM dbo.user_assignments WHERE LTRIM(RTRIM(CAST(evaluator_username AS VARCHAR))) = ?",
                        (str(current_user).strip(),),
                    )
                    rows = cursor.fetchall()
                    explicit_mats = [str(r[0]).strip() for r in rows]
                except Exception:
                    pass
                finally:
                    conn.close()

            # --- FILTRAGE DU PÉRIMÈTRE PAR DÉPARTEMENT ---
            if is_dg or is_admin:
                filtered_df = df_employees.copy()

                if "Département" in filtered_df.columns:
                    list_depts = sorted(
                        [
                            d
                            for d in filtered_df["Département"].dropna().unique()
                            if str(d).strip() != ""
                        ]
                    )
                    selected_dept_filter = st.selectbox(
                        "🏢 Filtrer par Département :",
                        options=["Tous les départements"] + list_depts,
                        key="dg_dept_filter",
                    )

                    if selected_dept_filter != "Tous les départements":
                        filtered_df = filtered_df[
                            filtered_df["Département"] == selected_dept_filter
                            ]
            else:
                cond_dept = (
                    df_employees["Département"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    == str(user_dept).strip().upper()
                    if (user_dept and "Département" in df_employees.columns)
                    else pd.Series(False, index=df_employees.index)
                )

                cond_assigned_assignment = (
                    df_employees["Matricule"].astype(str).str.strip().isin(explicit_mats)
                    if explicit_mats
                    else pd.Series(False, index=df_employees.index)
                )

                cond_assigned_direct = (
                    df_employees["evaluator_username"]
                    .astype(str)
                    .str.strip()
                    == str(current_user).strip()
                    if "evaluator_username" in df_employees.columns
                    else pd.Series(False, index=df_employees.index)
                )

                filtered_df = df_employees[
                    cond_dept | cond_assigned_assignment | cond_assigned_direct
                    ]

            if "Matricule" in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df["Matricule"].astype(str).str.strip()
                    != str(current_user).strip()
                    ]

            # --- RÉCUPÉRATION DES COLLABORATEURS DÉJÀ ÉVALUÉS ---
            role_to_pass = (
                "DG" if is_dg else ("Administrateur" if is_admin else "Manager")
            )
            data_eval = db.get_dashboard_data_by_role(
                user_role=role_to_pass,
                username=str(current_user).strip(),
                year=selected_year,
                quarter=selected_quarter,
            )

            evaluated_mats = set()
            if data_eval:
                for row in data_eval:
                    statut = str(row.get("statut", "")).strip()
                    if statut in ["✅ Fait", "Terminé", "Fait"]:
                        evaluated_mats.add(str(row.get("matricule", "")).strip())

            # --- NOUVEAU FILTRE : STATUT D'ÉVALUATION (DG / ADMIN) ---
            if is_dg or is_admin:
                status_filter = st.radio(
                    "📌 Statut d'évaluation :",
                    options=["Tous", "✅ Évalués", "⏳ En attente"],
                    horizontal=True,
                    key="dg_status_filter",
                )

                if status_filter == "✅ Évalués":
                    selectable_df = filtered_df[
                        filtered_df["Matricule"].astype(str).str.strip().isin(evaluated_mats)
                    ].copy()
                elif status_filter == "⏳ En attente":
                    selectable_df = filtered_df[
                        ~filtered_df["Matricule"].astype(str).str.strip().isin(evaluated_mats)
                    ].copy()
                else:
                    selectable_df = filtered_df.copy()
            else:
                # Les managers ne voient toujours que les employés non évalués
                if "Matricule" in filtered_df.columns:
                    selectable_df = filtered_df[
                        ~filtered_df["Matricule"]
                        .astype(str)
                        .str.strip()
                        .isin(evaluated_mats)
                    ].copy()
                else:
                    selectable_df = filtered_df.copy()

            col_metric, col_select = st.columns([1, 2])

            # Nombre de personnes restant à évaluer dans le périmètre
            nb_restants = len(
                filtered_df[
                    ~filtered_df["Matricule"]
                    .astype(str)
                    .str.strip()
                    .isin(evaluated_mats)
                ]
            )

            with col_metric:
                st.metric(
                    label="⏳ Reste à évaluer :",
                    value=f"{nb_restants} agent(s)",
                )

            with col_select:
                if not selectable_df.empty:
                    # Fonction de formatage pour ajouter un statut visuel
                    def format_emp_option(row):
                        mat = str(row.get("Matricule", "")).strip()
                        nom = row.get("Employé", "")
                        statut_icon = "✅ (Évalué)" if mat in evaluated_mats else "⏳ (En attente)"
                        return f"{nom} - {statut_icon}" if (is_dg or is_admin) else nom

                    selectable_df["Display_Option"] = selectable_df.apply(format_emp_option, axis=1)

                    selected_option = st.selectbox(
                        "🔍 Sélectionner le collaborateur :",
                        options=selectable_df["Display_Option"].tolist(),
                        key="select_emp_eval",
                    )

                    emp_info = selectable_df[
                        selectable_df["Display_Option"] == selected_option
                        ].iloc[0]
                    selected_emp = emp_info.get("Employé")
                else:
                    selected_emp = None
                    st.info("ℹ️ Aucun collaborateur ne correspond à ce filtre.")

            if selected_emp:
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Matricule :** `{emp_info.get('Matricule', 'N/A')}`")
                c2.markdown(f"**Poste :** `{emp_info.get('Poste', 'N/A')}`")
                c3.markdown(
                    f"**Département :** `{emp_info.get('Département', 'N/A')}`"
                )
                st.markdown("---")

                current_mat = str(emp_info.get("Matricule", "")).strip()

                evaluation_view.render_evaluation_page(
                    target_name=selected_emp,
                    target_id=current_mat,
                    is_admin=is_admin,
                    is_dg=is_dg,
                    is_rh=is_rh,
                    selected_year=selected_year,
                    selected_quarter=selected_quarter,
                )

    # --- NAVIGATION PAR ONGLETS SELON LES RÔLES ---
    if is_rh:
        tab_eval, tab_dash, tab_emp, tab_salaires = st.tabs(
            [
                "📝 Faire une évaluation",
                "📊 Dashboard & Suivi Global",
                "👥 Gestion Collaborateurs",
                "🔒 Salaires Confidentiels",
            ]
        )

        with tab_eval:
            render_evaluation_tab_content()

        with tab_dash:
            dashboard_view.render_dashboard_page(
                user_role=user_role, username=st.session_state.get("username")
            )

        with tab_emp:
            employee_management_view.render_employee_management_page()

        with tab_salaires:
            rh_salary_view.render_rh_salary_management()

    else:
        tab_eval, tab_dash = st.tabs(
            [
                "📝 Faire une évaluation",
                "📊 Dashboard & Suivi Global",
            ]
        )

        with tab_eval:
            render_evaluation_tab_content()

        with tab_dash:
            username_val = str(st.session_state.get("username", "")).strip()
            dashboard_view.render_dashboard_page(
                user_role=user_role, username=username_val
            )