# dashboard_view.py
import database as db
import pandas as pd
import streamlit as st


def render_dashboard_page(user_role="Manager", username=""):
    # 1. Récupération dynamique de la période active depuis la BDD
    config = db.get_active_quarter_config()
    current_year = config["year"]
    current_quarter = config["quarter"]

    st.markdown(
        f"## 📊 Tableau de Bord & Suivi Global (T{current_quarter} {current_year})"
    )

    # 2. Chargement des données selon la période dynamique
    data = db.get_dashboard_data_by_role(
        user_role=user_role,
        username=username,
        year=current_year,
        quarter=current_quarter,
    )

    if not data:
        st.warning(
            "⚠️ Aucun collaborateur trouvé pour votre profil ou votre périmètre."
        )
        return

    df = pd.DataFrame(data)

    # 3. Métriques KPIs
    total_collab = len(df)
    faits_count = len(df[df["statut"] == "✅ Fait"])
    non_faits_count = len(df[df["statut"] == "❌ Non fait"])
    taux_avancement = (
        (faits_count / total_collab * 100) if total_collab > 0 else 0.0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Collaborateurs", total_collab)
    col2.metric("Évaluations Faite(s)", faits_count)
    col3.metric("Évaluations Non Faite(s)", non_faits_count)
    col4.metric("Taux d'Avancement", f"{taux_avancement:.1f} %")

    st.divider()

    # Vue Synthétique par Département pour les RH
    if user_role == "RH":
        st.subheader("🏢 Synthèse Fait / Non Fait par Département")
        dept_summary = (
            df.groupby(["department", "statut"]).size().unstack(fill_value=0)
        )
        for col in ["✅ Fait", "❌ Non fait"]:
            if col not in dept_summary.columns:
                dept_summary[col] = 0
        st.dataframe(
            dept_summary[["✅ Fait", "❌ Non fait"]], use_container_width=True
        )
        st.divider()

    # Liste détaillée des collaborateurs
    st.subheader(
        "📋 Liste des Évaluations"
        if user_role in ["DG", "Administrateur"]
        else "📋 Suivi de mes Collaborateurs"
    )

    st.dataframe(
        df[
            [
                "matricule",
                "nom_complet",
                "department",
                "statut",
                "note_totale",
                "prime_finale",
            ]
        ],
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

    # Graphique d'Évolution Trimestrielle
    st.divider()
    st.subheader("📈 Graphique d'Évolution Trimestrielle")

    eval_faits = df[df["statut"] == "✅ Fait"]["nom_complet"].tolist()
    if eval_faits:
        selected_emp = st.selectbox(
            "Sélectionner un employé évalué :", eval_faits
        )
        selected_row = df[df["nom_complet"] == selected_emp].iloc[0]
        history = db.get_evolution_scores(selected_row["matricule"])

        if history:
            df_hist = pd.DataFrame(history)
            c1, c2 = st.columns([2, 1])
            with c1:
                st.line_chart(df_hist.set_index("Periode")["Note"])
            with c2:
                st.dataframe(df_hist, hide_index=True, use_container_width=True)
        else:
            st.info("Aucun historique antérieur enregistré.")
    else:
        st.info("💡 Aucune évaluation validée pour la période en cours.")