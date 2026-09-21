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
    target_job_title="",
    is_admin=False,
    is_dg=False,
    is_rh=False,
    selected_year=None,
    selected_quarter=None,
    is_director=False,
):
    if "success_msg" in st.session_state and st.session_state["success_msg"]:
        st.success(st.session_state["success_msg"])
        st.session_state["success_msg"] = None  # Réinitialise pour ne pas l'afficher indéfiniment
    apply_slider_styles()

    clean_target_id = str(target_id).strip()
    clean_id = str(target_id or target_name).replace(" ", "_").strip()

    st.markdown(f"## 📋 Grille d'Évaluation : **{target_name}** (`{clean_target_id}`)")

    # --- 1. DÉTECTION GRAND RESPONSABLE ---
    # Tous les mots-clés impérativement en MAJUSCULES
    mots_cles_dirigeants = [
        "CHEF DE DÉPARTEMENT",
        "CHEF DEPRT",
        "DIRECTEUR",
        "DIRECTRICE",
        "RESPONSABLE",
    ]

    # Titre du poste nettoyé et passé en majuscules
    clean_job_title = str(target_job_title or "").strip().upper()

    # Vérification par sous-chaîne (Ex: "DIRECTRICE" est bien dans "DIRECTRICE ADJ ERP")
    is_grand_responsable = is_director or any(
        keyword in clean_job_title for keyword in mots_cles_dirigeants
    )

    # Chargement adapté des critères
    # Chargement des critères globaux + spécifiques à CET employé
    criteres = db.get_criteres_for_target(
        is_grand_responsable=is_grand_responsable,
        target_matricule=clean_target_id
    )

    # --- 2. SECTION AJOUT DE CRITÈRE SPÉCIFIQUE (DG + GRAND RESPONSABLE SEULEMENT) ---
    # 🔒 N'apparaît QUE si la personne évaluée est un Grand Responsable
    if is_dg and is_grand_responsable:
        with st.expander("➕ Ajouter un critère d'évaluation spécifique (Grands Responsables)"):
            with st.form("form_add_extra_critere_inline", clear_on_submit=True):
                titre_crit = st.text_input("Titre du critère (ex: Vision Stratégique)")
                desc_crit = st.text_area("Description / Attentes pour le critère")

                col_ac1, col_ac2, col_ac3 = st.columns(3)
                with col_ac1:
                    code_crit = st.text_input("Code Critère (ex: EXEC_STRAT)").upper().strip()
                with col_ac2:
                    poids_crit = st.number_input(
                        "Poids (ex: 0.10 pour 10%)",
                        min_value=0.01,
                        max_value=1.0,
                        value=0.10,
                        step=0.05,
                    )
                with col_ac3:
                    type_crit = st.selectbox("Type", ["INDIVIDUEL", "COLLECTIF"])

                submit_crit = st.form_submit_button("💾 Créer et activer ce critère", type="primary")

                # Traitement de la création / activation du critère
                if submit_crit:
                    if code_crit and titre_crit:
                        try:
                            db.add_extra_critere(
                                code_critere=code_crit,
                                titre=titre_crit,
                                description=desc_crit,
                                poids=poids_crit,
                                type_critere=type_crit,
                                target_matricule=clean_target_id,
                                cible_role="CADRE_DIRIGEANT",
                            )
                            # 1. On stocke le message de succès dans la session
                            st.session_state[
                                "success_msg"] = f"✅ Critère '{titre_crit}' ajouté et activé avec succès pour {target_name} ({clean_target_id}) !"

                            # 2. On recharge la page pour mettre à jour les critères
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur lors de l'ajout du critère : {e}")

    # --- 3. RÉCUPÉRATION SALAIRE ET DONNÉES BDD ---
    real_salary = db.get_employee_salary(clean_target_id)
    has_financial_access = is_admin or is_dg

    existing_eval = None
    existing_scores = {}
    existing_comment = ""

    conn = db.get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, note_totale, prime_finale, evaluator_username, commentaire 
                FROM dbo.evaluations 
                WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
                (clean_target_id, selected_year, selected_quarter),
            )
            existing_eval = cursor.fetchone()

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

    # --- 4. GESTION DES ACCÈS ET DES SITES GRISÉS ---
    if is_dg and not eval_exists and not is_grand_responsable:
        st.warning(
            "ℹ️ **Information (Direction Générale) :** Cet employé n'est pas un grand responsable et n'a pas encore été évalué par son manager."
        )
        # On force à False pour enlever le grisage et débloquer les champs
        form_disabled = False
    else:
        form_disabled = False

    if is_dg and eval_exists:
        st.info(
            f"✏️ **Mode Modification (DG) :** Évaluation réalisée à l'origine par `{existing_eval[3]}`."
        )

    coef_usine_val = (
        db.get_coef_usine_by_quarter(selected_year, selected_quarter)
        if selected_year and selected_quarter
        else 100.0
    )

    SCORE_LABELS = {
        0: "0 - Insuffisant",
        1: "1 - Passable",
        2: "2 - Moyen",
        3: "3 - Bien",
        4: "4 - Excellent",
    }

    # --- 5. FORMULAIRE D'ÉVALUATION ---
    scores = {}

    with st.form("evaluation_form", clear_on_submit=False):
        st.subheader("⚙️ Données de Base & Paramètres")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.text_input("Coefficient Usine RH (%) :", value=f"{coef_usine_val:.2f} %", disabled=True)
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
                st.caption(f"⚠️ Aucun salaire chiffré enregistré pour le matricule `{clean_target_id}`.")

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

        # --- DÉCOUPAGE ET AFFICHAGE DYNAMIQUE ---
        collectifs = [c for c in criteres if c.get("type_critere") == "COLLECTIF"]
        individuels = [c for c in criteres if c.get("type_critere") == "INDIVIDUEL"]

        # 1. CRITÈRES COLLECTIFS
        if collectifs:
            st.markdown("## 👥 **PERFORMANCE COLLECTIVE**")
            for crit in collectifs:
                code = crit["code_critere"]
                default_val = existing_scores.get(code, None)

                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    scores[code] = st.select_slider(
                        crit.get("titre", crit.get("description", code)),
                        options=[0, 1, 2, 3, 4],
                        value=default_val,
                        disabled=form_disabled,
                        format_func=lambda x: (
                            SCORE_LABELS[x] if x is not None else "-- Sélectionner une note --"
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
                    if crit.get("description"):
                        st.markdown(f"👉 **_{crit['description']}_**")
                    scores[code] = st.select_slider(
                        "",
                        options=[0, 1, 2, 3, 4],
                        value=default_val,
                        disabled=form_disabled,
                        format_func=lambda x: (
                            SCORE_LABELS[x] if x is not None else "-- Sélectionner une note --"
                        ),
                        key=f"note_{code}_{clean_id}",
                    )
                with col2:
                    st.metric("Pondération", f"{int(crit['poids'] * 100)}%")

        commentaire = st.text_area(
            "💬 Commentaire / Remarques sur l'évaluation :",
            value=existing_comment,
            placeholder="Saisissez ici les observations ou justifications...",
            key=f"eval_comment_input_{clean_target_id}",
            disabled=form_disabled,
        )

        submitted = st.form_submit_button(
            "💾 Calculer et Enregistrer",
            type="primary",
            use_container_width=True,
            disabled=form_disabled,
        )

    # --- 6. CALCULS & SAUVEGARDE SQL ---
    if submitted and not form_disabled:
        # 1. Vérification que chaque critère de la grille a reçu une note
        missing_notes = [k for k, v in scores.items() if v is None]

        if missing_notes:
            st.error(f"⚠️ Veuillez renseigner tous les critères ({len(missing_notes)} note(s) manquante(s)).")
        else:
            # --- 2. CALCUL DE LA NOTE GLOBALE NORMALISÉE SUR 4 ---
            somme_poids = sum(float(crit.get("poids", 0.0)) for crit in criteres)

            if somme_poids > 0:
                total_note = sum(scores[crit["code_critere"]] * float(crit["poids"]) for crit in criteres) / somme_poids
            else:
                total_note = 0.0

            # Calculs financiers de la prime
            base_prime = (salary_input / ponderation_base) * coef_usine_pct
            prime_trimestrielle = base_prime * (total_note / 4.0)
            pct_prime = (prime_trimestrielle / base_prime) * 100 if base_prime > 0 else 0.0

            # --- 3. ENREGISTREMENT SQL (ENTÊTE NETTOYÉ + DÉTAILS DYNAMIQUES) ---
            conn = db.get_connection()
            save_success = False

            if conn:
                try:
                    cursor = conn.cursor()
                    # Récupération propre de l'utilisateur évaluateur
                    evaluator = st.session_state.get("username", "System")

                    # A. Sauvegarde dans dbo.evaluations (sans note_critere_1..3)
                    cursor.execute(
                        """
                        MERGE dbo.evaluations AS target
                        USING (SELECT ? AS target_matricule, ? AS year, ? AS quarter) AS source
                        ON (target.target_matricule = source.target_matricule AND target.year = source.year AND target.quarter = source.quarter)
                        WHEN MATCHED THEN
                            UPDATE SET 
                                evaluator_username = ?, 
                                note_totale = ?, 
                                coef_usine_applique = ?, 
                                base_salary = ?, 
                                prime_finale = ?, 
                                commentaire = ?, 
                                updated_at = GETDATE()
                        WHEN NOT MATCHED THEN
                            INSERT (
                                target_matricule, evaluator_username, year, quarter, 
                                note_totale, coef_usine_applique, base_salary, prime_finale, commentaire
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            clean_target_id, selected_year, selected_quarter,
                            evaluator, total_note, coef_usine_val, salary_input, prime_trimestrielle, commentaire,
                            clean_target_id, evaluator, selected_year, selected_quarter, total_note, coef_usine_val,
                            salary_input, prime_trimestrielle, commentaire
                        )
                    )

                    # B. Récupération de l'ID de l'évaluation créée / mise à jour
                    cursor.execute(
                        "SELECT id FROM dbo.evaluations WHERE target_matricule = ? AND year = ? AND quarter = ?",
                        (clean_target_id, selected_year, selected_quarter)
                    )
                    eval_row = cursor.fetchone()

                    if eval_row:
                        eval_id = eval_row[0]

                        # C. SAUVEGARDE DE CHAQUE CRITÈRE AVEC SA DESCRIPTION ET SA NOTE DANS dbo.evaluation_details
                        for crit in criteres:
                            code = crit["code_critere"]
                            titre = crit.get("titre", "")
                            description = crit.get("description", "")
                            note = float(scores[code])
                            poids = float(crit["poids"])

                            cursor.execute(
                                """
                                MERGE dbo.evaluation_details AS target
                                USING (SELECT ? AS evaluation_id, ? AS code_critere) AS source
                                ON (target.evaluation_id = source.evaluation_id AND target.code_critere = source.code_critere)
                                WHEN MATCHED THEN
                                    UPDATE SET 
                                        titre_critere = ?, 
                                        description_critere = ?, 
                                        note = ?, 
                                        poids_applique = ?
                                WHEN NOT MATCHED THEN
                                    INSERT (evaluation_id, code_critere, titre_critere, description_critere, note, poids_applique)
                                    VALUES (?, ?, ?, ?, ?, ?);
                                """,
                                (eval_id, code, titre, description, note, poids, eval_id, code, titre, description,
                                 note, poids)
                            )

                        conn.commit()
                        save_success = True
                        st.success(
                            f"✅ Évaluation enregistrée avec succès ({len(criteres)} critères stockés dans les détails) !")
                    else:
                        st.error("❌ Impossible de récupérer l'identifiant de l'évaluation.")

                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Erreur lors de la sauvegarde SQL : {e}")
                finally:
                    conn.close()

            # --- 4. AFFICHAGE DES RÉSULTATS ---
            st.markdown("---")
            if not has_financial_access:
                st.markdown("### 📊 Résultats de l'Évaluation")
                st.metric("Note Totale", f"{total_note:.2f} / 4.00")
            else:
                st.markdown("### 📊 Synthèse globale et Financière")
                res_c1, res_c2, res_c3, res_c4 = st.columns(4)
                res_c1.metric("Note Totale", f"{total_note:.2f} / 4.00")
                res_c2.metric("Base de Prime", f"{base_prime:,.2f} Ar")
                res_c3.metric("Prime du Trimestre", f"{prime_trimestrielle:,.2f} Ar")
                res_c4.metric("% de Prime", f"{pct_prime:.2f} %")

            if save_success:
                st.rerun()