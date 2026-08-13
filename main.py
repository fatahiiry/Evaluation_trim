import pandas as pd
import streamlit as st
import auth
from auth_view import render_login_page
import database as db
import excel_loader as el
import evaluation_view
from ui_styles import apply_custom_styles, reset_password_dialog,inject_modern_css

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

# Charger les employés Excel
df_employees = el.load_excel_employees()

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
    is_admin = user_role == "Administrateur"

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

    # --- SECTION ADMINISTRATION (ADMIN UNIQUEMENT) ---
    if is_admin:
        st.sidebar.markdown("---")
        st.sidebar.title("🛠️ Administration")

        # --- SECTION 1 : CRÉATION D'UTILISATEUR ---
        with st.sidebar.expander("➕ Créer un utilisateur / Manager"):
            new_u = st.text_input("Identifiant / Matricule", key="admin_new_u")
            new_nom = st.text_input(
                "Nom complet (Ex: Jean Dupont)", key="admin_new_nom"
            )
            new_p = st.text_input(
                "Mot de passe", type="password", key="admin_new_p"
            )
            new_role = st.selectbox(
                "Rôle :",
                options=["Manager", "Administrateur"],
                key="admin_new_role",
            )

            deps_list = []
            if not df_employees.empty and "Département" in df_employees.columns:
                deps_list = (
                    df_employees["Département"].dropna().unique().tolist()
                )

            selected_dept = st.selectbox(
                "Département assigné :",
                options=["(Aucun / Admin)"] + deps_list,
                key="admin_new_dept",
            )

            if st.button("Créer le compte", use_container_width=True):
                if new_u and new_p:
                    dept_val = (
                        None
                        if selected_dept == "(Aucun / Admin)"
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

        # --- SECTION 2 : AFFECTATION DES EMPLOIÉS ---
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
                    st.warning("Colonnes 'Matricule' ou 'Employé' manquantes dans Excel.")

        # --- SECTION 3 : APERÇU DES EFFECTIFS PAR MANAGER ---
        with st.sidebar.expander("📊 Vue d'ensemble des effectifs"):
            st.markdown("### Total employés par Manager")
            summary_data = []
            users_list = auth.get_all_users()

            for u in users_list:
                m_dept = auth.get_user_department(u)

                # Charger affectations BDD pour cet utilisateur
                conn = db.get_connection()
                u_mats = []
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT target_matricule FROM user_assignments WHERE evaluator_username = ?",
                            (u,),
                        )
                        u_mats = [str(r[0]) for r in cursor.fetchall()]
                    except Exception:
                        pass
                    finally:
                        conn.close()

                # Calcul sécurisé du total
                if not df_employees.empty:
                    c1 = (
                        df_employees["Département"]
                        .astype(str)
                        .str.strip()
                        .str.upper()
                        == str(m_dept).strip().upper()
                        if (m_dept and "Département" in df_employees.columns)
                        else pd.Series(False, index=df_employees.index)
                    )

                    c2 = (
                        df_employees["Matricule"].astype(str).isin(u_mats)
                        if (u_mats and "Matricule" in df_employees.columns)
                        else pd.Series(False, index=df_employees.index)
                    )

                    res_df = df_employees[c1 | c2]

                    if "Matricule" in res_df.columns:
                        res_df = res_df[
                            res_df["Matricule"].astype(str) != str(u)
                            ]

                    total_count = len(res_df)
                else:
                    total_count = 0

                summary_data.append(
                    {
                        "Manager": u,
                        "Département": m_dept or "N/A",
                        "Effectif": total_count,
                    }
                )

            st.dataframe(
                summary_data, hide_index=True, use_container_width=True
            )

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

        # --- SECTION : IMPORT TEMPORAIRE DES SALAIRES (ADMIN) ---
        with st.sidebar.expander("💰 Import Temporaire des Salaires"):
                    st.caption(
                        "Chargement en mémoire vive (non sauvegardé en BDD pour confidentialité)."
                    )
                    salaires_file = st.file_uploader(
                        "Fichier Excel des salaires (Colonnes : Matricule, Salaire)",
                        type=["xlsx", "xls"],
                        key="salaires_uploader",
                    )

                    if salaires_file is not None:
                        try:
                            df_sal = pd.read_excel(salaires_file)

                            # Standardisation des noms de colonnes
                            df_sal.columns = [c.strip().lower() for c in df_sal.columns]

                            # Détection des colonnes Matricule et Salaire
                            col_mat = next(
                                (c for c in df_sal.columns if "mat" in c), None
                            )
                            col_sal = next(
                                (c for c in df_sal.columns if "sal" in c), None
                            )

                            if col_mat and col_sal:
                                # Stockage sous forme de dictionnaire {Matricule: Salaire}
                                df_sal[col_mat] = df_sal[col_mat].astype(str).str.strip()
                                st.session_state["salaires_temp"] = dict(
                                    zip(df_sal[col_mat], df_sal[col_sal])
                                )
                                st.success(
                                    f"✅ {len(st.session_state['salaires_temp'])} salaires chargés en mémoire !"
                                )
                            else:
                                st.error(
                                    "Le fichier doit contenir au moins une colonne 'Matricule' et 'Salaire'."
                                )
                        except Exception as e:
                            st.error(f"Erreur lors de la lecture du fichier : {e}")

                    # Bouton de vidage de la mémoire des salaires
                    if "salaires_temp" in st.session_state and st.session_state["salaires_temp"]:
                        if st.button("🗑️ Vider les salaires en mémoire", use_container_width=True):
                            del st.session_state["salaires_temp"]
                            st.rerun()

    # --- ENTÊTE PRINCIPAL STYLISÉ ---
    st.markdown(
        """
        <div class="main-header">
            <h1>📋 Portail d'Évaluation RH</h1>
            <p>Gestion et suivi des performances des collaborateurs</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # --- NAVIGATION PAR ONGLETS ---
    tab_eval, tab_dash = st.tabs(
        ["📝 Faire une évaluation", "📊 Dashboard & Suivi Global"]
    )

    # --- ONGLET 1 : FAIRE UNE ÉVALUATION ---
    with tab_eval:
        if df_employees.empty:
            st.warning(
                "Aucun employé trouvé. Veuillez vérifier que le fichier 'employes.xlsx' est présent."
            )
        else:
            # 1. Récupérer les matricules affectés en BDD
            conn = db.get_connection()
            explicit_mats = []
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT target_matricule FROM user_assignments WHERE evaluator_username = ?",
                        (current_user,),
                    )
                    rows = cursor.fetchall()
                    explicit_mats = [str(r[0]) for r in rows]
                except Exception:
                    pass
                finally:
                    conn.close()

            # 2. Filtrage CUMULATIF (Département + Affectations)
            if is_admin:
                filtered_df = df_employees.copy()
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

                cond_assigned = (
                    df_employees["Matricule"].astype(str).isin(explicit_mats)
                    if (explicit_mats and "Matricule" in df_employees.columns)
                    else pd.Series(False, index=df_employees.index)
                )

                filtered_df = df_employees[cond_dept | cond_assigned]

            # Exclure le manager connecté
            if "Matricule" in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df["Matricule"].astype(str) != str(current_user)
                    ]

            employes_list = (
                filtered_df["Employé"].tolist()
                if "Employé" in filtered_df.columns
                else []
            )

            # 3. MISE EN PAGE EN COLONNES (EFFECTIF + SELECTION)
            col_metric, col_select = st.columns([1, 2])

            with col_metric:
                st.metric(
                    label="👥 Effectif à évaluer :",
                    value=f"{len(employes_list)} agent(s)",
                )

            with col_select:
                if employes_list:
                    selected_emp = st.selectbox(
                        "🔍 Sélectionner le collaborateur :", employes_list
                    )
                else:
                    selected_emp = None
                    st.info("Aucun employé à évaluer trouvé.")

            # 4. FICHE ET FORMULAIRE D'ÉVALUATION (APPEL MODULE EVALUATION_VIEW)
            if selected_emp:
                emp_info = filtered_df[
                    filtered_df["Employé"] == selected_emp
                    ].iloc[0]

                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Matricule :** `{emp_info.get('Matricule', 'N/A')}`")
                c2.markdown(f"**Poste :** `{emp_info.get('Poste', 'N/A')}`")
                c3.markdown(
                    f"**Département :** `{emp_info.get('Département', 'N/A')}`"
                )
                st.markdown("---")

                # --- RÉCUPÉRATION SÉCURISÉE DU SALAIRE (TEMPORAIRE / EXCEL) ---
                current_mat = str(emp_info.get("Matricule", "")).strip()

                # Priorité 1 : Fichier temporaire chargé par l'Admin en session
                salaires_map = st.session_state.get("salaires_temp", {})
                sal_val = salaires_map.get(current_mat)

                # Priorité 2 : Fichier employés standard s'il contient déjà le salaire
                if sal_val is None:
                    sal_val = (
                            emp_info.get("Salaire_Base")
                            or emp_info.get("Salaire")
                            or emp_info.get("Salaire de base")
                            or 0.0
                    )

                try:
                    sal_val = float(sal_val)
                except (ValueError, TypeError):
                    sal_val = 0.0

                # --- APPEL DE LA VUE D'ÉVALUATION ---
                evaluation_view.render_evaluation_page(
                    target_name=selected_emp,
                    base_salary=sal_val,
                    is_admin=is_admin,  # Transmet le rôle pour gérer le masquage ou l'affichage
                )

    # --- ONGLET 2 : DASHBOARD & SUIVI ---
    with tab_dash:
        st.subheader("📊 Tableau de bord des évaluations")
        st.info("Module de suivi prêt à être raccordé aux sauvegardes BDD.")