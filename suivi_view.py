import streamlit as st
import pandas as pd
import database as db

# 1. POP-UP DES DÉTAILS DE L'ÉVALUATION (@st.dialog)
@st.dialog("📋 Détails de l'évaluation", width="large")
def show_evaluation_details(matricule, nom_complet, year, quarter):
    st.markdown(f"**Collaborateur :** {nom_complet} (`{matricule}`)")
    st.markdown(f"**Période :** {quarter} - Année {year}")
    st.markdown("---")

    conn = db.get_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Récupération de l'entête de l'évaluation
            cursor.execute("""
                SELECT id, note_totale, prime_finale, base_salary, coef_usine_applique, commentaire, evaluator_username
                FROM dbo.evaluations
                WHERE target_matricule = ? AND year = ? AND quarter = ?
            """, (matricule, year, quarter))
            eval_data = cursor.fetchone()

            if eval_data:
                eval_id, note_totale, prime_finale, base_salary, coef_usine, commentaire, evaluator = eval_data

                # Métriques synthétiques
                c1, c2, c3 = st.columns(3)
                c1.metric("Note Totale", f"{note_totale:.2f} / 4.00" if note_totale is not None else "-")
                c2.metric("Prime finale", f"{prime_finale:,.2f} Ar" if prime_finale is not None else "-")
                c3.metric("Évaluateur", evaluator or "N/A")

                st.markdown("---")
                st.subheader("📌 Critères évalués")

                # Récupération des détails des critères dans dbo.evaluation_details
                cursor.execute("""
                    SELECT code_critere, titre_critere, description_critere, note, poids_applique
                    FROM dbo.evaluation_details
                    WHERE evaluation_id = ?
                    ORDER BY id ASC
                """, (eval_id,))
                details = cursor.fetchall()

                if details:
                    for code, titre, desc, note, poids in details:
                        with st.container(border=True):
                            col_info, col_note = st.columns([4, 1])
                            col_info.markdown(f"**{titre or code}** *(Poids : {poids})*")
                            if desc:
                                col_info.caption(desc)
                            col_note.markdown(f"### `{note:.2f} / 4`")
                else:
                    st.info("Aucun détail de critère enregistré pour cette évaluation.")

                if commentaire:
                    st.markdown("---")
                    st.markdown("**💬 Commentaire global :**")
                    st.info(commentaire)
            else:
                st.warning("Aucune évaluation enregistrée pour ce collaborateur.")

        except Exception as e:
            st.error(f"Erreur lors de la récupération des détails : {e}")
        finally:
            conn.close()


# ==============================================================================
# 2. PAGE PRINCIPALE DE SUIVI
# ==============================================================================
def render_suivi_page():
    st.title("📋 Suivi de mes Collaborateurs")

    # --- Filtres de période ---
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_year = st.number_input("Année", min_value=2020, max_value=2030, value=2026, step=1)
    with col_f2:
        selected_quarter = st.selectbox("Trimestre", options=["T1", "T2", "T3", "T4"], index=0)

    # --- Chargement des données depuis la BDD ---
    conn = db.get_connection()
    df_collaborateurs = pd.DataFrame()

    if conn:
        try:
            # Requête SQL pour charger les collaborateurs et leur évaluation
            query = """
                SELECT 
                    e.matricule,
                    e.nom_complet,
                    e.department,
                    CASE 
                        WHEN ev.id IS NOT NULL THEN 'Fait'
                        ELSE 'En attente'
                    END AS statut,
                    ev.note_totale,
                    ev.prime_finale
                FROM dbo.employes e
                LEFT JOIN dbo.evaluations ev 
                    ON e.matricule = ev.target_matricule 
                    AND ev.year = ? 
                    AND ev.quarter = ?
            """
            df_collaborateurs = pd.read_sql(query, conn, params=[selected_year, selected_quarter])
        except Exception as e:
            st.error(f"Erreur chargement des collaborateurs : {e}")
        finally:
            conn.close()

    if df_collaborateurs.empty:
        st.info("Aucun collaborateur trouvé.")
        return

    st.caption("💡 *Cliquez sur une ligne pour afficher la fiche de détails.*")

    # --- Tableau interactif ---
    event = st.dataframe(
        df_collaborateurs,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # --- Déclenchement au clic sur une ligne ---
    selected_rows = event.selection.rows
    if selected_rows:
        selected_index = selected_rows[0]
        selected_row = df_collaborateurs.iloc[selected_index]

        # Ouverture du pop-up
        show_evaluation_details(
            matricule=str(selected_row['matricule']),
            nom_complet=selected_row['nom_complet'],
            year=selected_year,
            quarter=selected_quarter
        )