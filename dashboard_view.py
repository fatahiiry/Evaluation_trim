import database as db
import pandas as pd
import streamlit as st

# 1. POP-UP DES DÉTAILS DE L'ÉVALUATION
@st.dialog("📋 Détails de l'évaluation", width="large")
def show_evaluation_details(matricule, nom_complet, year, quarter, user_role="Manager"):
    st.markdown(f"**Collaborateur :** {nom_complet} (`{matricule}`)")
    st.markdown(f"**Période :** Trimestre {quarter} - Année {year}")
    st.markdown("---")

    conn = db.get_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Récupération de l'entête dans dbo.evaluations
            cursor.execute(
                """
                SELECT id, note_totale, prime_finale, base_salary, coef_usine_applique, commentaire, evaluator_username
                FROM dbo.evaluations
                WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
                (matricule, year, quarter),
            )
            eval_data = cursor.fetchone()

            if eval_data:
                (
                    eval_id,
                    note_totale,
                    prime_finale,
                    base_salary,
                    coef_usine,
                    commentaire,
                    evaluator,
                ) = eval_data

                # Synthèse visuelle (Masquage de la prime pour le Manager)
                if user_role in ["RH", "DG", "Administrateur"]:
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "Note Totale",
                        f"{note_totale:.2f} / 4.00" if note_totale is not None else "-",
                    )
                    c2.metric(
                        "Prime finale",
                        f"{prime_finale:,.2f} Ar" if prime_finale is not None else "-",
                    )
                    c3.metric("Évaluateur", evaluator or "Non renseigné")
                else:
                    c1, c2 = st.columns(2)
                    c1.metric(
                        "Note Totale",
                        f"{note_totale:.2f} / 4.00" if note_totale is not None else "-",
                    )
                    c2.metric("Évaluateur", evaluator or "Non renseigné")

                st.markdown("---")
                st.subheader("📌 Critères évalués")

                # Récupération des détails dans dbo.evaluation_details
                cursor.execute(
                    """
                    SELECT code_critere, titre_critere, description_critere, note, poids_applique
                    FROM dbo.evaluation_details
                    WHERE evaluation_id = ?
                    ORDER BY id ASC
                """,
                    (eval_id,),
                )
                details = cursor.fetchall()

                if details:
                    # Construction d'un DataFrame structuré pour les critères
                    table_critere_data = []
                    for code, titre, desc, note, poids in details:
                        # Formatage du poids en pourcentage
                        if poids is not None:
                            # Note: si en BDD le poids est stocké en décimal (ex: 0.2 pour 20%), faites (poids * 100)
                            poids_display = f"{poids * 100:.0f}%" if poids <= 1 else f"{poids:.0f}%"
                        else:
                            poids_display = "-"

                        table_critere_data.append(
                            {
                                "Code / Critère": titre or code or "-",
                                "Description": desc or "-",
                                "Poids": poids_display,
                                "Note / 4": note,
                            }
                        )

                    df_criteres = pd.DataFrame(table_critere_data)

                    # Styling pour surligner en rouge les notes < 2.0
                    def highlight_critere_note(val):
                        if isinstance(val, (int, float)) and val < 2.0:
                            return "background-color: #ffcccc; color: #900c3f; font-weight: bold;"
                        return ""

                    styled_criteres = df_criteres.style.map(
                        highlight_critere_note, subset=["Note / 4"]
                    ).format({"Note / 4": "{:.2f}"})

                    st.dataframe(
                        styled_criteres,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "Aucun détail de critère enregistré pour cette évaluation."
                    )

                # Affichage explicite du commentaire global
                st.markdown("---")
                st.subheader("💬 Commentaire global")
                if commentaire and str(commentaire).strip():
                    st.info(commentaire)
                else:
                    st.caption("*Aucun commentaire rédigé pour cette évaluation.*")

            else:
                st.warning(
                    "Aucune évaluation enregistrée pour ce collaborateur sur cette période."
                )

        except Exception as e:
            st.error(f"Erreur lors du chargement des détails : {e}")
        finally:
            conn.close()

# 2. PAGE DASHBOARD & SUIVI GLOBAL
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

        st.dataframe(
            pd.DataFrame(dept_summary), use_container_width=True, hide_index=True
        )
        st.divider()

    # 7. Tableau détaillé avec sélection de ligne et Pop-up
    st.subheader(
        "📋 Liste des Évaluations"
        if user_role in ["RH", "DG", "Administrateur"]
        else "📋 Suivi de mes Collaborateurs"
    )

    if not df_eval.empty:
        st.caption(
            "💡 *Cliquez sur une ligne du tableau pour ouvrir la fiche détaillée d'évaluation.*"
        )

        # Filtrage des colonnes selon le rôle (Exclusion de prime_finale pour le Manager)
        if user_role in ["RH", "DG", "Administrateur"]:
            cols_to_display = [
                "matricule",
                "nom_complet",
                "department",
                "statut",
                "note_totale",
                "prime_finale",
            ]
        else:
            cols_to_display = [
                "matricule",
                "nom_complet",
                "department",
                "statut",
                "note_totale",
            ]

        available_cols = [c for c in cols_to_display if c in df_eval.columns]
        df_filtered = df_eval[available_cols].copy()

        # Fonction pour surligner en rouge les lignes où la note totale < 2.0
        def highlight_low_scores(row):
            note = row.get("note_totale")
            if pd.notnull(note) and note < 2.0:
                return ["background-color: #ffcccc; color: #900c3f; font-weight: bold;"] * len(row)
            return [""] * len(row)

        styled_df = df_filtered.style.apply(highlight_low_scores, axis=1)

        # Formateurs de colonnes
        column_formats = {}
        if "note_totale" in available_cols:
            column_formats["note_totale"] = "{:.2f}"
        if "prime_finale" in available_cols:
            column_formats["prime_finale"] = "{:,.2f} Ar"

        if column_formats:
            styled_df = styled_df.format(column_formats)

        # Tableau interactif
        event = st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        # Interception du clic
        selected_rows = event.selection.rows
        if selected_rows:
            selected_index = selected_rows[0]
            selected_row = df_eval.iloc[selected_index]

            # Affichage de la boîte modale avec le rôle passé pour le filtrage
            show_evaluation_details(
                matricule=str(selected_row["matricule"]),
                nom_complet=selected_row.get("nom_complet", ""),
                year=current_year,
                quarter=current_quarter,
                user_role=user_role,
            )
    else:
        st.info("Aucune évaluation enregistrée pour cette période.")