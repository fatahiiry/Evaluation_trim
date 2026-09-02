# employee_management_view.py
import database as db
import pandas as pd
import streamlit as st


def clean_str_value(val):
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    return val_str


def render_employee_management_page():
    st.title("👥 Gestion des Collaborateurs")

    tab_import, tab_manual, tab_purge = st.tabs(
        ["📥 Importation Excel", "✍️ Saisie Manuelle", "🗑️ Vider la Base"]
    )

    # --- ONGLET 1 : IMPORTATION EXCEL ---
    with tab_import:
        st.subheader("Importer une liste depuis un fichier Excel")
        st.info(
            "Le fichier Excel doit idéalement contenir les colonnes : `matricule`, `employé` (ou `nom_complet`), `poste`, `département`, `évaluateur`."
        )

        uploaded_file = st.file_uploader(
            "Choisir un fichier Excel (.xlsx, .xls)", type=["xlsx", "xls"]
        )

        if uploaded_file is not None:
            try:
                # Lecture en forçant le format texte pour éviter la création de float/décimales (.0)
                df = pd.read_excel(uploaded_file, dtype=str)

                # Nettoyage global de tout le dataframe pour supprimer les '.0' et les 'nan'
                for col in df.columns:
                    df[col] = df[col].apply(clean_str_value)

                st.write("🔍 **Aperçu des données nettoyées à importer :**")
                st.dataframe(df.head(10), use_container_width=True)

                if st.button("🚀 Lancer l'importation BDD", type="primary"):
                    success_count = 0
                    total_rows = len(df)

                    progress_bar = st.progress(0)

                    for idx, row in df.iterrows():
                        # Extraction et nettoyage individuel des colonnes
                        mat = clean_str_value(
                            row.get("matricule")
                            or row.get("Matricule")
                            or row.get("MATRICULE")
                        )
                        nom = clean_str_value(
                            row.get("employé")
                            or row.get("employe")
                            or row.get("nom_complet")
                            or row.get("Employé")
                        )
                        pst = clean_str_value(
                            row.get("poste")
                            or row.get("Poste")
                            or row.get("POSTE")
                        )
                        dept = clean_str_value(
                            row.get("département")
                            or row.get("departement")
                            or row.get("Département")
                        )
                        eval_usr = clean_str_value(
                            row.get("évaluateur")
                            or row.get("evaluateur")
                            or row.get("Évaluateur")
                        )

                        if mat and nom:
                            if db.save_or_update_employee(
                                mat, nom, pst, dept, eval_usr
                            ):
                                success_count += 1

                        progress_bar.progress((idx + 1) / total_rows)

                    st.success(
                        f"✅ Importation terminée : {success_count} / {total_rows} employés enregistrés ou mis à jour."
                    )
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")

    # --- ONGLET 2 : SAISIE MANUELLE ---
    with tab_manual:
        st.subheader("Ajouter ou modifier un collaborateur")

        with st.form("form_single_employee"):
            col1, col2 = st.columns(2)
            with col1:
                matricule = st.text_input("Matricule *")
                nom_complet = st.text_input("Nom & Prénom (Employé) *")
                poste = st.text_input("Poste")
            with col2:
                department = st.text_input("Département")
                evaluator_username = st.text_input("Username Évaluateur")

            submitted = st.form_submit_button("💾 Enregistrer l'employé")

            if submitted:
                # Nettoyage des saisies manuelles
                clean_mat = clean_str_value(matricule)
                clean_nom = nom_complet.strip()
                clean_pst = poste.strip()
                clean_dept = department.strip()
                clean_eval = clean_str_value(evaluator_username)

                if not clean_mat or not clean_nom:
                    st.warning("Veuillez remplir au moins le Matricule et le Nom.")
                else:
                    if db.save_or_update_employee(
                        clean_mat,
                        clean_nom,
                        clean_pst,
                        clean_dept,
                        clean_eval,
                    ):
                        st.success(
                            f" Employé `{clean_nom}` (Matricule: {clean_mat}) enregistré avec succès !"
                        )
                    else:
                        st.error("Erreur lors de l'enregistrement BDD.")

    # --- ONGLET 3 : VIDER LA BASE ---
    with tab_purge:
        st.subheader("⚠️ Zone de réinitialisation")
        st.warning(
            "Attention : Cette action va supprimer la totalité des employés enregistrés dans la base de données (`dbo.employees`)."
        )

        confirm_check = st.checkbox(
            "Je confirme vouloir supprimer l'intégralité de la liste des employés."
        )

        if st.button("🔥 Vider complètement la table des employés", type="secondary"):
            if not confirm_check:
                st.error("Veuillez cocher la case de confirmation ci-dessus.")
            else:
                conn = db.get_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM dbo.employees;")
                        conn.commit()
                        st.success("✅ La table des employés a été totalement vidée avec succès !")
                    except Exception as e:
                        st.error(f"Erreur lors de la suppression : {e}")
                    finally:
                        conn.close()