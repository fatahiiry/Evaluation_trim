# evaluation_view.py
import database as db
import streamlit as st


def apply_slider_styles():
    """Injecte du CSS pour optimiser la lisibilité des sliders de notation."""
    st.markdown(
        """
        <style>
        div[data-baseweb="slider"] > div {
            height: 12px !important;
            padding-top: 15px !important;
            padding-bottom: 15px !important;
        }
        div[data-baseweb="slider"] div[role="slider"] {
            height: 24px !important;
            width: 24px !important;
            top: -6px !important;
            background-color: #2563eb !important;
            border-color: #2563eb !important;
        }
        div[data-baseweb="slider"] div {
            background-color: #3b82f6 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_evaluation_page(
    target_name="Employé",
    target_id="",
    is_admin=False,
    is_dg=False,
    is_rh=False,
    selected_year=None,
    selected_quarter=None,
    is_director=False,  # Paramètre optionnel pour filtrer les critères ciblés
):
    apply_slider_styles()

    st.markdown(f"## 📋 Grille d'Évaluation : **{target_name}**")

    clean_target_id = str(target_id).strip()

    # --- 1. RÉCUPÉRATION ET DÉCHIFFREMENT DU SALAIRE DEPUIS BDD ---
    real_salary = db.get_employee_salary(clean_target_id)

    # 🔒 Seuls Admin et DG ont accès aux données financières (RH exclu)
    has_financial_access = is_admin or is_dg

    # --- 2. VÉRIFICATION ET CHARGEMENT D'UNE ÉVALUATION EXISTANTE ---
    existing_eval = None
    existing_scores = {}
    existing_comment = ""

    conn = db.get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Récupération de l'évaluation globale
            cursor.execute(
                """
                SELECT id, note_totale, prime_finale, evaluator_username, commentaire 
                FROM dbo.evaluations 
                WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
                (clean_target_id, selected_year, selected_quarter),
            )
            existing_eval = cursor.fetchone()

            # Si elle existe, on récupère les notes détaillées par critère et le commentaire
            if existing_eval:
                eval_id = existing_eval[0]
                existing_comment = existing_eval[4] or ""

                cursor.execute(
                    """
                    SELECT code_critere, note FROM dbo.evaluation_details 
                    WHERE evaluation_id = ?
                """,
                    (eval_id,),
                )
                for row in cursor.fetchall():
                    existing_scores[row[0]] = int(row[1])
        except Exception as e:
            st.error(f"Erreur lors de la lecture BDD : {e}")
        finally:
            conn.close()

    eval_exists = existing_eval is not None

    # 🔒 RÈGLES D'ACCÈS POUR LA DIRECTION GÉNÉRALE (DG)
    if is_dg and not eval_exists:
        st.warning(
            "🔒 **Accès restreint (Direction Générale) :** Cet employé n'a pas encore été évalué par son manager. Vous pourrez ajuster l'évaluation une fois saisie."
        )
        form_disabled = True
    else:
        form_disabled = False

    if is_dg and eval_exists:
        st.info(
            f"✏️ **Mode Modification (DG) :** Évaluation réalisée à l'origine par `{existing_eval[3]}`. Vous pouvez modifier les notes et valider."
        )

    if selected_year and selected_quarter:
        coef_usine_val = db.get_coef_usine_by_quarter(
            selected_year, selected_quarter
        )
    else:
        coef_usine_val = 100.0

    clean_id = str(target_id or target_name).replace(" ", "_")

    SCORE_LABELS = {
        0: "0 - Insuffisant",
        1: "1 - Passable",
        2: "2 - Moyen",
        3: "3 - Bien",
        4: "4 - Excellent",
    }

    # --- 3. CHARGEMENT DYNAMIQUE DES CRITÈRES DEPUIS LA BDD ---
    criteres = db.get_criteres_actifs(is_director=is_director)

    scores = {}

    with st.form("evaluation_form", clear_on_submit=False):
        st.subheader("⚙️ Données de Base & Paramètres")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.text_input(
                "Coefficient Usine RH (%) :",
                value=f"{coef_usine_val:.2f} %",
                disabled=True,
            )
            coef_usine_pct = coef_usine_val / 100.0

        with col_s2:
            ponderation_base = st.number_input(
                "Pondération (0.1 à 4) :",
                min_value=0.1,
                max_value=4.0,
                value=4.0,
                step=0.5,
                disabled=form_disabled,
            )

        with col_s3:
            if real_salary == 0.0:
                st.caption(
                    f"⚠️ Aucun salaire chiffré enregistré pour le matricule `{clean_target_id}`."
                )

            # Masquage du salaire pour le rôle RH et Managers
            if has_financial_access:
                salary_input = st.number_input(
                    "Salaire de base (Ar) :",
                    min_value=0.0,
                    value=real_salary,
                    step=50000.0,
                    disabled=form_disabled,
                )
            else:
                st.text_input(
                    "Salaire de base :",
                    value="••••Ar (Confidentiel)",
                    disabled=True,
                    help="Le salaire est déchiffré en arrière-plan pour le calcul de la prime.",
                )
                salary_input = real_salary

        st.divider()

        # --- DÉCOUPAGE ET AFFICHAGE DYNAMIQUE DES CRITÈRES ---
        collectifs = [c for c in criteres if c["type_critere"] == "COLLECTIF"]
        individuels = [c for c in criteres if c["type_critere"] == "INDIVIDUEL"]

        # 1. CRITÈRES COLLECTIFS
        if collectifs:
            st.markdown("## 👥 **PERFORMANCE COLLECTIVE**")
            for crit in collectifs:
                code = crit["code_critere"]
                default_val = existing_scores.get(code, None)

                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    scores[code] = st.select_slider(
                        crit["description"],
                        options=[0, 1, 2, 3, 4],
                        value=default_val,
                        disabled=form_disabled,
                        format_func=lambda x: (
                            SCORE_LABELS[x]
                            if x is not None
                            else "-- Sélectionner une note --"
                        ),
                        key=f"note_{code}_{clean_id}",
                    )
                with col_c2:
                    st.metric("Pondération", f"{int(crit['poids'] * 100)}%")

            st.divider()

        # 2. CRITÈRES INDIVIDUELS
        if individuels:
            st.markdown("## 👤 **CRITÈRES INDIVIDUELS**")
            for crit in individuels:
                code = crit["code_critere"]
                default_val = existing_scores.get(code, None)

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"### 🎯 **{crit['titre']}**")
                    st.markdown(f"👉 **_{crit['description']}_**")
                    scores[code] = st.select_slider(
                        "",
                        options=[0, 1, 2, 3, 4],
                        value=default_val,
                        disabled=form_disabled,
                        format_func=lambda x: (
                            SCORE_LABELS[x]
                            if x is not None
                            else "-- Sélectionner une note --"
                        ),
                        key=f"note_{code}_{clean_id}",
                    )
                with col2:
                    st.metric("Pondération", f"{int(crit['poids'] * 100)}%")

        commentaire = st.text_area(
            "💬 Commentaire / Remarques sur l'évaluation :",
            value=existing_comment,
            placeholder="Saisissez ici les observations ou justifications...",
            key="eval_comment_input",
            disabled=form_disabled,
        )

        submitted = st.form_submit_button(
            "💾 Calculer et Enregistrer",
            type="primary",
            use_container_width=True,
            disabled=form_disabled,
        )

    # --- 4. CALCULS & SAUVEGARDE TRANSACTIONNELLE DANS SQL SERVER ---
    if submitted and not form_disabled:
        missing_notes = [k for k, v in scores.items() if v is None]

        if missing_notes:
            st.error(
                f"⚠️ Veuillez renseigner tous les critères ({len(missing_notes)} note(s) manquante(s))."
            )
        else:
            total_note = 0.0
            for crit in criteres:
                code = crit["code_critere"]
                poids = crit["poids"]
                note = scores[code]
                total_note += note * poids

            base_prime = (salary_input / ponderation_base) * coef_usine_pct
            prime_trimestrielle = base_prime * (total_note / 4.0)
            pct_prime = (
                (prime_trimestrielle / base_prime) * 100
                if salary_input > 0
                else 0.0
            )

            conn = db.get_connection()
            save_success = False
            if conn:
                try:
                    cursor = conn.cursor()
                    evaluator = st.session_state.get("username", "System")

                    # A. Upsert sur l'évaluation globale
                    cursor.execute(
                        """
                        MERGE dbo.evaluations AS target
                        USING (SELECT ? AS target_matricule, ? AS year, ? AS quarter) AS source
                        ON (target.target_matricule = source.target_matricule AND target.year = source.year AND target.quarter = source.quarter)
                        WHEN MATCHED THEN
                            UPDATE SET evaluator_username = ?, note_totale = ?, coef_usine_applique = ?, prime_finale = ?, commentaire = ?, updated_at = GETDATE()
                        WHEN NOT MATCHED THEN
                            INSERT (target_matricule, evaluator_username, year, quarter, note_totale, coef_usine_applique, prime_finale, commentaire)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                        (
                            clean_target_id,
                            selected_year,
                            selected_quarter,
                            evaluator,
                            total_note,
                            coef_usine_val,
                            prime_trimestrielle,
                            commentaire,
                            clean_target_id,
                            evaluator,
                            selected_year,
                            selected_quarter,
                            total_note,
                            coef_usine_val,
                            prime_trimestrielle,
                            commentaire,
                        ),
                    )

                    # B. Récupération de l'ID enregistré
                    cursor.execute(
                        """
                        SELECT id FROM dbo.evaluations 
                        WHERE target_matricule = ? AND year = ? AND quarter = ?
                    """,
                        (clean_target_id, selected_year, selected_quarter),
                    )
                    eval_id = cursor.fetchone()[0]

                    # C. Upsert du détail de chaque critère
                    for crit in criteres:
                        code = crit["code_critere"]
                        note = scores[code]
                        poids = crit["poids"]

                        cursor.execute(
                            """
                            MERGE dbo.evaluation_details AS target
                            USING (SELECT ? AS evaluation_id, ? AS code_critere) AS source
                            ON (target.evaluation_id = source.evaluation_id AND target.code_critere = source.code_critere)
                            WHEN MATCHED THEN
                                UPDATE SET note = ?, poids_applique = ?
                            WHEN NOT MATCHED THEN
                                INSERT (evaluation_id, code_critere, note, poids_applique)
                                VALUES (?, ?, ?, ?);
                        """,
                            (
                                eval_id,
                                code,
                                note,
                                poids,
                                eval_id,
                                code,
                                note,
                                poids,
                            ),
                        )

                    conn.commit()
                    save_success = True
                    st.success(
                        "✅ Évaluation et détails des critères enregistrés avec succès !"
                    )
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erreur lors de la sauvegarde SQL : {e}")
                finally:
                    conn.close()

            # --- AFFICHAGE DES RÉSULTATS DE LA PRIME ---
            if not has_financial_access:
                st.markdown("### 📊 Résultats du Calcul")
                st.metric("Note Totale", f"{total_note:.2f} / 4")
            else:
                res_c1, res_c2, res_c3, res_c4 = st.columns(4)
                res_c1.metric("Note Totale", f"{total_note:.2f} / 4")
                res_c2.metric("Base de Prime", f"{base_prime:,.2f} Ar")
                res_c3.metric("Prime du Trimestre", f"{prime_trimestrielle:,.2f} Ar")
                res_c4.metric("% de Prime", f"{pct_prime:.2f} %")

            if save_success:
                st.rerun()