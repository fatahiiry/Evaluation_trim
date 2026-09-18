# dashboard_view.py
import database as db
import pandas as pd
import streamlit as st


def render_dashboard_page(user_role="Manager", username=""):
    # 1. Extraction et nettoyage strict du username
    if isinstance(username, (tuple, list)):
        clean_username = str(username[0]).strip() if len(username) > 0 else ""
    else:
        clean_username = str(username or "").strip()

    # 2. Récupération dynamique de la période active
    config = db.get_active_quarter_config()
    current_year = config["year"]
    current_quarter = config["quarter"]

    st.markdown(
        f"## 📊 Tableau de Bord & Suivi Global (T{current_quarter} {current_year})"
    )

    # 3. Chargement des évaluations enregistrées
    data_eval = db.get_dashboard_data_by_role(
        user_role=user_role,
        username=clean_username,
        year=current_year,
        quarter=current_quarter,
    )
    df_eval = pd.DataFrame(data_eval) if data_eval else pd.DataFrame()

    # 4. Chargement de l'effectif TOTAL selon le rôle
    df_all_emp = pd.DataFrame()
    conn = db.get_connection()

    if conn:
        try:
            cursor = conn.cursor()
            if user_role in ["RH", "DG", "Administrateur"]:
                query = "SELECT matricule, nom_complet, department FROM dbo.employees"
                cursor.execute(query)
            else:
                # Utilisation directe du curseur pyodbc avec la variable nettoyée
                query = "SELECT matricule, nom_complet, department FROM dbo.employees WHERE evaluator_username = ?"
                cursor.execute(query, clean_username)

            rows = cursor.fetchall()
            if rows:
                cols = [column[0] for column in cursor.description]
                df_all_emp = pd.DataFrame.from_records(rows, columns=cols)
        except Exception as e:
            st.error(f"Erreur lors du chargement des collaborateurs : {e}")
        finally:
            conn.close()

    # Fallback si df_all_emp est vide
    if df_all_emp.empty and not df_eval.empty:
        df_all_emp = df_eval.copy()

    if df_all_emp.empty:
        st.warning(
            "⚠️ Aucun collaborateur trouvé pour votre profil ou votre périmètre."
        )
        return

    # Normalisation
    if "department" in df_all_emp.columns:
        df_all_emp["department"] = (
            df_all_emp["department"].fillna("Non défini").astype(str).str.strip()
        )
    df_all_emp["matricule"] = df_all_emp["matricule"].astype(str).str.strip()

    # Identification des matricules évalués
    evaluated_mats = set()
    if not df_eval.empty and "matricule" in df_eval.columns:
        done_mask = df_eval["statut"].isin(["✅ Fait", "Terminé", "Fait"])
        evaluated_mats = set(
            df_eval[done_mask]["matricule"].astype(str).str.strip().tolist()
        )

    # 5. Calcul des KPIs
    total_collab = len(df_all_emp)
    mats_in_scope = set(df_all_emp["matricule"].tolist())

    faits_count = len(mats_in_scope.intersection(evaluated_mats))
    non_faits_count = max(0, total_collab - faits_count)
    taux_avancement = (
        (faits_count / total_collab * 100) if total_collab > 0 else 0.0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Total à évaluer", total_collab)
    col2.metric("✅ Évaluations faites", faits_count)
    col3.metric("⏳ En attente", non_faits_count)
    col4.metric("📈 Taux de réalisation", f"{taux_avancement:.1f} %")

    st.divider()

    # 6. Synthèse par Département (RH / DG / Admin)
    if user_role in ["RH", "DG", "Administrateur"]:
        st.subheader("🏢 Statistiques du suivi par Département")
        dept_summary = []
        departments = sorted(df_all_emp["department"].dropna().unique())

        for dept in departments:
            emp_in_dept = df_all_emp[df_all_emp["department"] == dept]
            total_dept = len(emp_in_dept)
            mats_in_dept = set(emp_in_dept["matricule"].tolist())
            faites_dept = len(mats_in_dept.intersection(evaluated_mats))
            attente_dept = max(0, total_dept - faites_dept)
            pct_dept = (
                (faites_dept / total_dept * 100) if total_dept > 0 else 0.0
            )

            statut_dept = (
                "🟢 Terminé"
                if pct_dept == 100
                else ("🔵 En cours" if pct_dept > 0 else "🔴 Non démarré")
            )

            dept_summary.append(
                {
                    "Département": dept,
                    "Total à évaluer": total_dept,
                    "Évaluations faites": faites_dept,
                    "En attente": attente_dept,
                    "% Réalisation": f"{pct_dept:.1f}%",
                    "Statut": statut_dept,
                }
            )

        st.dataframe(pd.DataFrame(dept_summary), use_container_width=True, hide_index=True)
        st.divider()

    # 7. Tableau détaillé
    st.subheader(
        "📋 Liste des Évaluations"
        if user_role in ["RH", "DG", "Administrateur"]
        else "📋 Suivi de mes Collaborateurs"
    )

    if not df_eval.empty:
        cols_to_display = [
            "matricule",
            "nom_complet",
            "department",
            "statut",
            "note_totale",
            "prime_finale",
        ]
        available_cols = [c for c in cols_to_display if c in df_eval.columns]
        st.dataframe(df_eval[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Aucune évaluation enregistrée pour cette période.")