# main.py
import os
import pandas as pd
import streamlit as st

import auth
from auth_view import render_login_page
import dashboard_view
import database as db
import employee_management_view
import evaluation_view
import quarter_utils
import rh_config_view
import rh_salary_view
from suivi_view import render_suivi_page
from ui_styles import apply_custom_styles, inject_modern_css, reset_password_dialog

# ------------------------------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE & STYLES
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Portail EVALUATION RH",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialisation BDD & Styles CSS
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


# ------------------------------------------------------------------------------
# 2. MIRE DE CONNEXION
# ------------------------------------------------------------------------------
if not st.session_state["authenticated"]:
    render_login_page()


# ------------------------------------------------------------------------------
# 3. APPLICATION PRINCIPALE (UTILISATEUR CONNECTÉ)
# ------------------------------------------------------------------------------
else:
    st.markdown(
        "<style>[data-testid='stSidebar'] {display: block !important;}</style>",
        unsafe_allow_html=True,
    )

    current_user = st.session_state["username"]
    user_role = st.session_state["role"]

    # --- HÉRARCHIE ET MATRICE DES DROITS ---
    is_admin = user_role == "Administrateur"
    is_rh = user_role in ["RH", "Administrateur"]  # Accès métiers RH
    is_dg = user_role == "DG"

    # Récupération du département de l'utilisateur connecté
    user_dept = auth.get_user_department(current_user)

    # --------------------------------------------------------------------------
    # SIDEBAR : PROFIL
    # --------------------------------------------------------------------------
    with st.sidebar:
        if os.path.exists("Logo.png"):
            st.image("Logo.png", use_container_width=True)

        st.divider()

        role_color = (
            "#2563eb"
            if user_role in ["RH", "DG", "Administrateur"]
            else "#059669"
        )

        # Récupération automatique en BDD si la clé n'existe pas en session
        if (
            "nom_complet" not in st.session_state
            or not st.session_state["nom_complet"]
        ):
            user_info = auth.get_user_details(current_user)
            st.session_state["nom_complet"] = user_info["nom_complet"]

        nom_complet = st.session_state.get("nom_complet", current_user)
        user_matricule = st.session_state.get("matricule", current_user)
        dept_info = f" • {user_dept}" if user_dept else ""

        st.markdown(
            f"""
            <div style="background-color: #f1f5f9; padding: 12px 16px; border-radius: 12px; margin-bottom: 15px;">
                <div style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Utilisateur Connecté</div>
                <div style="font-size: 1rem; font-weight: 700; color: #0f172a; margin-top: 4px;">👤 {nom_complet}</div>
                <div style="font-size: 0.8rem; color: #475569; font-weight: 600; margin-top: 2px;">🆔 Matricule : {user_matricule}</div>
                <div style="margin-top: 8px;">
                    <span style="background-color: {role_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600;">
                        {user_role}{dept_info}
                    </span>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        col_pwd, col_logout = st.columns(2)
        with col_pwd:
            if st.button(
                "🔑 Pass",
                use_container_width=True,
                help="Changer le mot de passe",
            ):
                reset_password_dialog()
        with col_logout:
            if st.button("🚪 Sortir", use_container_width=True, help="Déconnexion"):
                st.session_state["authenticated"] = False
                st.session_state["username"] = None
                st.session_state["role"] = None
                st.session_state["nom_complet"] = None
                st.session_state["matricule"] = None
                st.session_state["department"] = None
                st.rerun()

    # Charger la liste globale des employés depuis SQL Server
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

    # --------------------------------------------------------------------------
    # ACCÈS ADMINISTRATEUR SEULEMENT (SIDEBAR)
    # --------------------------------------------------------------------------
    if is_admin or is_rh:
        with st.sidebar:
            st.divider()
            st.markdown("### ⚙️ Administration Système")

            # 1. PARAMÉTRAGE DU COEFFICIENT USINE
            with st.expander("🏭 Coefficient Usine Trimestriel"):
                rh_config_view.render_rh_config_view()

            # 2. CRÉATION D'UTILISATEUR
            with st.expander("➕ Créer un utilisateur"):
                new_u = st.text_input(
                    "Identifiant / Matricule", key="admin_new_u"
                )
                new_nom = st.text_input("Nom complet", key="admin_new_nom")
                new_p = st.text_input(
                    "Mot de passe", type="password", key="admin_new_p"
                )
                new_role = st.selectbox(
                    "Rôle :",
                    options=["Manager", "RH", "DG", "Administrateur"],
                    key="admin_new_role",
                )

                deps_list = []
                if (
                    not df_employees.empty
                    and "Département" in df_employees.columns
                ):
                    deps_list = (
                        df_employees["Département"]
                        .dropna()
                        .unique()
                        .tolist()
                    )

                selected_dept = st.selectbox(
                    "Département assigné :",
                    options=["(Aucun / RH / DG / Admin)"] + deps_list,
                    key="admin_new_dept",
                )

                if st.button(
                    "Créer le compte", use_container_width=True, type="primary"
                ):
                    if new_u and new_p:
                        dept_val = (
                            None
                            if selected_dept == "(Aucun / RH / DG / Admin)"
                            else selected_dept
                        )
                        nom_val = new_nom.strip() if new_nom else new_u.strip()

                        success, msg = auth.create_user(
                            username=new_u.strip(),
                            password=new_p,
                            nom_complet=nom_val,
                            role=new_role,
                            department=dept_val,
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning(
                            "Veuillez remplir au moins l'identifiant et le mot de passe."
                        )

            # 3. AFFECTATION DES EMPLOIÉS
            with st.expander("🎯 Affecter des employés"):
                all_users = auth.get_all_users()

                if all_users:
                    selected_evaluator = st.selectbox(
                        "Manager / Évaluateur :",
                        options=all_users,
                        key="admin_select_eval",
                    )

                    if (
                        not df_employees.empty
                        and "Matricule" in df_employees.columns
                    ):
                        df_temp = df_employees.copy()
                        df_temp["Matricule_Str"] = df_temp["Matricule"].astype(
                            str
                        )

                        df_temp["Display_Label"] = df_temp.apply(
                            lambda row: f"{row['Employé']} - {row.get('Département', 'N/A')} ({row['Matricule_Str']})",
                            axis=1,
                        )

                        label_to_matricule = dict(
                            zip(
                                df_temp["Display_Label"],
                                df_temp["Matricule_Str"],
                            )
                        )
                        matricule_to_label = dict(
                            zip(
                                df_temp["Matricule_Str"],
                                df_temp["Display_Label"],
                            )
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
                                current_allowed_mats = [
                                    str(r[0]) for r in rows
                                ]
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
                            f"Employés de {selected_evaluator} :",
                            options=all_display_options,
                            default=default_selected_labels,
                            key=f"mats_{selected_evaluator}",
                        )

                        selected_mats_to_save = [
                            label_to_matricule[label]
                            for label in selected_labels
                        ]

                        if st.button(
                            "Enregistrer les affectations",
                            use_container_width=True,
                        ):
                            if auth.save_user_assignments(
                                selected_evaluator, selected_mats_to_save
                            ):
                                st.success("Affectations enregistrées !")
                            else:
                                st.error("Erreur d'enregistrement.")
                    else:
                        st.warning("Aucun employé en BDD SQL.")

    # --------------------------------------------------------------------------
    # ENTÊTE PRINCIPAL
    # --------------------------------------------------------------------------
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 22px 28px; border-radius: 14px; color: white; margin-bottom: 25px;">
            <h1 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 700;">📋 Portail d'Évaluation RH</h1>
            <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 0.95rem;">
                Gestion, cotation et suivi des performances trimestrielles des collaborateurs
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------------------
    # FONCTIONS INTERNES POUR LES ONGLETS
    # --------------------------------------------------------------------------
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
                            for d in filtered_df["Département"]
                            .dropna()
                            .unique()
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
                    df_employees["Matricule"]
                    .astype(str)
                    .str.strip()
                    .isin(explicit_mats)
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
                        evaluated_mats.add(
                            str(row.get("matricule", "")).strip()
                        )

            # --- FILTRE PAR STATUT D'ÉVALUATION ---
            if is_dg or is_admin:
                status_filter = st.radio(
                    "📌 Statut d'évaluation :",
                    options=["Tous", "✅ Évalués", "⏳ En attente"],
                    horizontal=True,
                    key="dg_status_filter",
                )

                if status_filter == "✅ Évalués":
                    selectable_df = filtered_df[
                        filtered_df["Matricule"]
                        .astype(str)
                        .str.strip()
                        .isin(evaluated_mats)
                    ].copy()
                elif status_filter == "⏳ En attente":
                    selectable_df = filtered_df[
                        ~filtered_df["Matricule"]
                        .astype(str)
                        .str.strip()
                        .isin(evaluated_mats)
                    ].copy()
                else:
                    selectable_df = filtered_df.copy()
            else:
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

                    def format_emp_option(row):
                        mat = str(row.get("Matricule", "")).strip()
                        nom = row.get("Employé", "")
                        statut_icon = (
                            "✅ (Évalué)"
                            if mat in evaluated_mats
                            else "⏳ (En attente)"
                        )
                        return (
                            f"{nom} - {statut_icon}"
                            if (is_dg or is_admin)
                            else nom
                        )

                    selectable_df["Display_Option"] = selectable_df.apply(
                        format_emp_option, axis=1
                    )

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
                    st.info(
                        "ℹ️ Aucun collaborateur ne correspond à ce filtre."
                    )

            if selected_emp:
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.markdown(
                    f"**Matricule :** `{emp_info.get('Matricule', 'N/A')}`"
                )
                c2.markdown(f"**Poste :** `{emp_info.get('Poste', 'N/A')}`")
                c3.markdown(
                    f"**Département :** `{emp_info.get('Département', 'N/A')}`"
                )
                st.markdown("---")

                current_mat = str(emp_info.get("Matricule", "")).strip()
                target_job_title = str(emp_info.get("Poste", "")).strip()

                evaluation_view.render_evaluation_page(
                    target_name=selected_emp,
                    target_id=current_mat,
                    target_job_title=target_job_title,
                    is_admin=is_admin,
                    is_dg=is_dg,
                    is_rh=is_rh,
                    selected_year=selected_year,
                    selected_quarter=selected_quarter,
                )


    def render_admin_users_management_tab():
        st.subheader("👥 Suivi des Comptes & Gestion des Rôles")

        # Récupérer l'utilisateur courant depuis session_state
        current_user_id = st.session_state.get(
            "username", st.session_state.get("user", "")
        )

        data = auth.get_users_list_for_management(
            current_logged_username=current_user_id
        )
        df = pd.DataFrame(data)

        st.markdown(
            """
            <style>
            .custom-table-header {
                font-weight: 700;
                color: #334155;
                font-size: 0.85rem;
                padding: 8px 0px;
                border-bottom: 2px solid #cbd5e1;
            }
            .badge-online {
                background-color: #dbeafe;
                color: #1d4ed8;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.72rem;
                font-weight: 700;
                margin-left: 6px;
                display: inline-block;
            }
            .badge-offline {
                background-color: #f1f5f9;
                color: #64748b;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.72rem;
                font-weight: 600;
                margin-left: 6px;
                display: inline-block;
            }
            </style>
        """,
            unsafe_allow_html=True,
        )

        h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1.5, 2.5, 1.5, 2.0, 1.2])
        h_col1.markdown(
            "<div class='custom-table-header'>Matricule</div>",
            unsafe_allow_html=True,
        )
        h_col2.markdown(
            "<div class='custom-table-header'>Utilisateur</div>",
            unsafe_allow_html=True,
        )
        h_col3.markdown(
            "<div class='custom-table-header'>Équipe</div>",
            unsafe_allow_html=True,
        )
        h_col4.markdown(
            "<div class='custom-table-header'>Rôle Modifier</div>",
            unsafe_allow_html=True,
        )
        h_col5.markdown(
            "<div class='custom-table-header' style='text-align: center;'>Actions</div>",
            unsafe_allow_html=True,
        )

        st.divider()

        if df.empty:
            st.info("Aucun compte utilisateur trouvé.")
        else:
            for idx, row in df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1.5, 2.5, 1.5, 2.0, 1.2])

                c1.write(f"**{row['matricule']}**")

                # Statut En ligne / Hors ligne
                if row["is_online"]:
                    status_online_tag = (
                        ' <span class="badge-online">🟢 En ligne</span>'
                    )
                else:
                    status_online_tag = (
                        ' <span class="badge-offline">⚪ Hors ligne</span>'
                    )

                c2.markdown(
                    f"**{row['utilisateur']}**{status_online_tag}",
                    unsafe_allow_html=True,
                )
                c3.caption(f"👥 {row['nb_collaborateurs']} agent(s)")

                # Modification directe du rôle
                roles_options = ["Manager", "Évaluateur", "Administrateur", "RH"]
                current_role_index = (
                    roles_options.index(row["role"])
                    if row["role"] in roles_options
                    else 0
                )

                new_selected_role = c4.selectbox(
                    label=f"role_{row['matricule']}",
                    options=roles_options,
                    index=current_role_index,
                    key=f"select_role_{row['matricule']}",
                    label_visibility="collapsed",
                )

                if new_selected_role != row["role"]:
                    if auth.update_user_role(row["matricule"], new_selected_role):
                        st.toast(
                            f"Rôle de {row['matricule']} mis à jour en {new_selected_role} !",
                            icon="✅",
                        )
                        st.rerun()

                # Actions : Bouton pour ouvrir le formulaire de réinitialisation
                with c5:
                    if st.button(
                            "🔑 Réinitialiser",
                            key=f"btn_reset_{row['matricule']}",
                            help=f"Réinitialiser le mot de passe pour {row['matricule']}",
                    ):
                        if (
                                st.session_state.get("reset_target_user")
                                == row["matricule"]
                        ):
                            st.session_state["reset_target_user"] = None
                        else:
                            st.session_state["reset_target_user"] = row[
                                "matricule"
                            ]
                        st.rerun()

                # Zone de formulaire contextuelle sous la ligne du tableau
                if (
                        st.session_state.get("reset_target_user")
                        == row["matricule"]
                ):
                    with st.expander(
                            f"🔐 Réinitialiser le mot de passe de **{row['utilisateur']} ({row['matricule']})**",
                            expanded=True,
                    ):
                        col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                        with col_p1:
                            new_pwd = st.text_input(
                                "Nouveau mot de passe",
                                type="password",
                                key=f"new_pwd_{row['matricule']}",
                            )
                        with col_p2:
                            confirm_pwd = st.text_input(
                                "Confirmer le mot de passe",
                                type="password",
                                key=f"confirm_pwd_{row['matricule']}",
                            )
                        with col_p3:
                            st.write("")
                            st.write("")
                            if st.button(
                                    "Valider", key=f"submit_pwd_{row['matricule']}"
                            ):
                                if new_pwd != confirm_pwd:
                                    st.error(
                                        "Les mots de passe ne correspondent pas !"
                                    )
                                else:
                                    # Apport direct de votre fonction auth.update_password
                                    success, message = auth.update_password(
                                        row["matricule"], new_pwd
                                    )
                                    if success:
                                        st.success(message)
                                        st.session_state[
                                            "reset_target_user"
                                        ] = None
                                        st.rerun()
                                    else:
                                        st.error(message)

                st.markdown(
                    "<hr style='margin: 4px 0px; border-top: 1px solid #f1f5f9;'>",
                    unsafe_allow_html=True,
                )

    def render_admin_criteres_tab():
        st.subheader("⚙️ Modification et Pondération des Critères")
        st.caption(
            "Ajustez les titres, descriptions, types et coefficients (poids) applicables aux évaluations."
        )

        conn = db.get_connection()
        all_criteres = []
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT code_critere, titre, description, poids, type_critere, cible_role, target_matricule 
                    FROM dbo.criteres
                    ORDER BY code_critere ASC
                """)
                columns = [col[0] for col in cursor.description]
                all_criteres = [
                    dict(zip(columns, row)) for row in cursor.fetchall()
                ]
            except Exception as e:
                st.error(f"Erreur lors de la récupération des critères : {e}")
            finally:
                conn.close()

        if not all_criteres:
            st.info("Aucun critère enregistré en base de données.")
            return

        for crit in all_criteres:
            code = crit["code_critere"]
            cible = (
                crit["target_matricule"]
                if crit["target_matricule"]
                else crit["cible_role"]
            )

            with st.expander(
                f"🔹 `{code}` — {crit['titre']} (Cible : {cible})"
            ):
                with st.form(key=f"form_edit_crit_{code}"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        new_titre = st.text_input(
                            "Titre du critère",
                            value=crit["titre"],
                            key=f"t_{code}",
                        )
                        new_desc = st.text_area(
                            "Description / Attentes",
                            value=crit["description"] or "",
                            key=f"d_{code}",
                        )

                    with col2:
                        new_poids = st.number_input(
                            "Pondération (Poids)",
                            min_value=0.01,
                            max_value=1.0,
                            value=float(crit["poids"])
                            if crit["poids"] is not None
                            else 0.1,
                            step=0.05,
                            key=f"p_{code}",
                        )
                        current_type_idx = (
                            0 if crit["type_critere"] == "INDIVIDUEL" else 1
                        )
                        new_type = st.selectbox(
                            "Type de critère",
                            options=["INDIVIDUEL", "COLLECTIF"],
                            index=current_type_idx,
                            key=f"tp_{code}",
                        )

                    if st.form_submit_button(
                        "💾 Enregistrer les modifications", type="primary"
                    ):
                        try:
                            db.update_critere(
                                code_critere=code,
                                titre=new_titre,
                                description=new_desc,
                                poids=new_poids,
                                type_critere=new_type,
                            )
                            st.success(
                                f"✅ Critère `{code}` mis à jour avec succès !"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur de mise à jour : {e}")

    # --------------------------------------------------------------------------
    # NAVIGATION PAR ONGLETS (ST.TABS)
    # --------------------------------------------------------------------------
    tabs_list = ["📝 Faire une évaluation", "📊 Dashboard & Suivi Global"]

    # Accès exclusif de gestion des comptes et critères réservé à l'Admin
    if is_admin:
        tabs_list.append("👥 Gestion des Comptes")
        tabs_list.append("⚙️ Gestion des Critères")

    # Accès métiers RH
    if is_rh:
        tabs_list.extend(
            ["👥 Gestion Collaborateurs", "🔒 Salaires Confidentiels"]
        )

    created_tabs = st.tabs(tabs_list)

    # Contenu des onglets
    with created_tabs[0]:
        render_evaluation_tab_content()

    with created_tabs[1]:
        username_val = str(st.session_state.get("username", "")).strip()
        dashboard_view.render_dashboard_page(
            user_role=user_role, username=username_val
        )

    idx = 2
    if is_admin:
        with created_tabs[idx]:
            render_admin_users_management_tab()
        idx += 1

        with created_tabs[idx]:
            render_admin_criteres_tab()
        idx += 1

    if is_rh:
        with created_tabs[idx]:
            employee_management_view.render_employee_management_page()
        idx += 1

        with created_tabs[idx]:
            rh_salary_view.render_rh_salary_management()