# dashboard_view.py
import database as db
import pandas as pd
import streamlit as st


def render_dashboard_page(user_role="Manager", username=""):
    # 1. Récupération dynamique de la période active
    config = db.get_active_quarter_config()
    current_year = config["year"]
    current_quarter = config["quarter"]

    st.markdown(
        f"## 📊 Tableau de Bord & Suivi Global (T{current_quarter} {current_year})"
    )

    # 2. Chargement des évaluations filtrées par rôle (périmètre manager ou global)
    data_eval = db.get_dashboard_data_by_role(
        user_role=user_role,
        username=username,
        year=current_year,
        quarter=current_quarter,
    )
    df_eval = pd.DataFrame(data_eval) if data_eval else pd.DataFrame()

    # 3. Chargement de l'effectif à évaluer selon le rôle
    df_all_emp = pd.DataFrame()

    if user_role in ["RH", "DG", "Administrateur"]:
        # Pour la Direction / RH : chargement de TOUS les employés
        conn = db.get_connection()
        if conn:
            try:
                query_emp = "SELECT matricule, nom_complet, department FROM dbo.employees"
                df_all_emp = pd.read_sql(query_emp, conn)
            except Exception:
                pass
            finally:
                conn.close()

        if df_all_emp.empty and not df_eval.empty:
            df_all_emp = df_eval.copy()
    else:
        # Pour les Managers : l'effectif correspond à leur périmètre uniquement
        df_all_emp = df_eval.copy()

    if df_all_emp.empty:
        st.warning("⚠️ Aucun collaborateur trouvé pour votre profil ou votre périmètre.")
        return

    # Normalisation des données
    if "department" in df_all_emp.columns:
        df_all_emp["department"] = (
            df_all_emp["department"].fillna("Non défini").astype(str).str.strip()
        )
    df_all_emp["matricule"] = df_all_emp["matricule"].astype(str).str.strip()

    # Identification des matricules déjà évalués
    evaluated_mats = set()
    if not df_eval.empty and "matricule" in df_eval.columns:
        evaluated_mats = set(
            df_eval[df_eval["statut"] == "✅ Fait"]["matricule"]
            .astype(str)
            .str.strip()
            .tolist()
        )

    # 4. Métriques KPIs adaptées au rôle
    total_collab = len(df_all_emp)

    if user_role in ["RH", "DG", "Administrateur"]:
        faits_count = len(evaluated_mats)
    else:
        faits_count = len(df_eval[df_eval["statut"] == "✅ Fait"]) if not df_eval.empty else 0

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

    # 5. Synthèse Statistiques par Département (Uniquement pour RH, DG, Administrateur)
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
            pct_dept = (faites_dept / total_dept * 100) if total_dept > 0 else 0.0

            if pct_dept == 100:
                statut_dept = "🟢 Terminé"
            elif pct_dept > 0:
                statut_dept = "🟠 En cours"
            else:
                statut_dept = "🔴 Non démarré"

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

        df_summary = pd.DataFrame(dept_summary)

        st.dataframe(
            df_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total à évaluer": st.column_config.NumberColumn(
                    "Total à évaluer", format="%d"
                ),
                "Évaluations faites": st.column_config.NumberColumn(
                    "Évaluations faites", format="%d"
                ),
                "En attente": st.column_config.NumberColumn(
                    "En attente", format="%d"
                ),
                "% Réalisation": st.column_config.TextColumn("% Réalisation"),
                "Statut": st.column_config.TextColumn("Statut"),
            },
        )
        st.divider()

    # 6. Liste détaillée des collaborateurs
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

        st.dataframe(
            df_eval[available_cols],
            column_config={
                "matricule": "Matricule",
                "nom_complet": "Nom & Prénom",
                "department": "Département",
                "statut": "Statut",
                "note_totale": st.column_config.NumberColumn(
                    "Note (/4)", format="%.2f"
                ),
                "prime_finale": st.column_config.NumberColumn(
                    "Prime (Ar)", format="%d Ar"
                ),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Aucune évaluation enregistrée pour cette période.")