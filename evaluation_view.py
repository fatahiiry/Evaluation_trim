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
    base_salary=0.0,
    is_admin=False,
    is_dg=False,
    selected_year=None,
    selected_quarter=None,
):
    apply_slider_styles()

    st.markdown(f"## 📋 Grille d'Évaluation : **{target_name}**")

    # --- 1. VÉRIFICATION DE L'EXISTENCE D'UNE ÉVALUATION EN BDD ---
    existing_eval = None
    conn = db.get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT note_totale, prime_finale, evaluator_username 
                FROM dbo.evaluations 
                WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
                (target_id, selected_year, selected_quarter),
            )
            existing_eval = cursor.fetchone()
        except Exception:
            pass
        finally:
            conn.close()

    eval_exists = existing_eval is not None

    # --- 2. RESTRICTION DG : MODIFICATION UNIQUEMENT SI DÉJÀ ENREGISTRÉ ---
    if is_dg and not eval_exists:
        st.warning(
            "🔒 **Accès restreint (Direction Générale) :** Cet employé n'a pas encore été évalué par son manager pour ce trimestre. Vous pourrez modifier la note uniquement lorsqu'une évaluation aura été soumise."
        )
        form_disabled = True
    else:
        form_disabled = False

    if is_dg and eval_exists:
        st.info(
            f"✏️ **Mode Édition DG :** Évaluation existante enregistrée par `{existing_eval[2]}` (Note actuelle : {existing_eval[0]:.2f}/4). Vous pouvez ajuster les notes ci-dessous."
        )

    # Récupération automatique du Coef Usine fixé par les RH
    if selected_year and selected_quarter:
        coef_usine_val = db.get_coef_usine_by_quarter(
            selected_year, selected_quarter
        )
    else:
        coef_usine_val = 4.0

    clean_id = str(target_id or target_name).replace(" ", "_")

    SCORE_LABELS = {
        0: "0 - Insuffisant",
        1: "1 - Passable",
        2: "2 - Moyen",
        3: "3 - Bien",
        4: "4 - Excellent",
    }

    scores = {}

    with st.form("evaluation_form"):
        # --- PARAMÈTRES USINE & SALAIRE ---
        st.subheader("⚙️ Données de Base & Paramètres")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.text_input(
                "Coefficient Usine RH (%) :",
                value=f"{coef_usine_val:.2f} %",
                disabled=True,
                help="Ce coefficient est défini par les RH pour le trimestre en cours.",
            )
            coef_usine_pct = coef_usine_val / 100.0

        with col_s2:
            ponderation_base = st.number_input(
                "Pondération (0 à 4) :",
                min_value=0.1,
                max_value=4.0,
                value=4.0,
                step=0.5,
                disabled=form_disabled,
            )

        with col_s3:
            if is_admin or is_dg:
                salary_input = st.number_input(
                    "Salaire de base (Ar) :",
                    min_value=0.0,
                    value=float(base_salary),
                    step=50000.0,
                    disabled=form_disabled,
                )
            else:
                st.text_input(
                    "Salaire de base :",
                    value="•••••••• Ar (Confidentiel)",
                    disabled=True,
                )
                salary_input = float(base_salary)

        st.divider()

        # --- CRITÈRE COLLECTIF (10%) ---
        st.markdown("## 👥 **CRITÈRE COLLECTIF (10%)**")
        st.info(
            "📌 **Résultat de la performance de la direction/département/service (Moyenne indicateurs qualité IQ).**"
        )

        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            st.markdown("### **Performance de la direction/département/service**")
            scores["Performance Collective"] = st.select_slider(
                "",
                options=[0, 1, 2, 3, 4],
                value=None,
                disabled=form_disabled,
                format_func=lambda x: (
                    SCORE_LABELS[x]
                    if x is not None
                    else "-- Sélectionner une note --"
                ),
                key=f"note_collective_{clean_id}",
            )
        with col_c2:
            st.metric("Pondération", "10%")

        st.divider()

        # --- CRITÈRES INDIVIDUELS (90%) ---
        st.markdown("## 👤 **CRITÈRES INDIVIDUELS**")

        criteria = [
            (
                "Corporate",
                "Respect des valeurs et engagement envers l'entreprise",
                0.10,
            ),
            ("Ne compte pas ses heures", "Disponibilité et implication", 0.05),
            (
                "Motivé",
                "Dynamisme, attitude proactive et engagement dans les missions",
                0.15,
            ),
            (
                "Respecte les process",
                "Suivi rigoureux des procédures et règles internes",
                0.15,
            ),
            (
                "Encadre bien et forme bien",
                "Leadership, encadrement et accompagnement des équipes",
                0.10,
            ),
            (
                "Propose des améliorations",
                "Suggestions d'optimisation et mise en place d'initiatives",
                0.15,
            ),
            (
                "Communication",
                "Qualité des échanges avec les collègues et supérieurs",
                0.10,
            ),
            (
                "Autonomie",
                "Capacité à gérer ses tâches sans supervision constante",
                0.10,
            ),
        ]

        for title, desc, weight in criteria:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### 🎯 **{title}**")
                st.markdown(f"👉 **_{desc}_**")
                scores[title] = st.select_slider(
                    "",
                    options=[0, 1, 2, 3, 4],
                    value=None,
                    disabled=form_disabled,
                    format_func=lambda x: (
                        SCORE_LABELS[x]
                        if x is not None
                        else "-- Sélectionner une note --"
                    ),
                    key=f"note_{title}_{clean_id}",
                )
            with col2:
                st.metric("Pondération", f"{int(weight * 100)}%")
            st.write("")

        submitted = st.form_submit_button(
            "💾 Calculer et Enregistrer",
            type="primary",
            use_container_width=True,
            disabled=form_disabled,
        )

    # --- CALCULS & SAUVEGARDE SQL ---
    if submitted and not form_disabled:
        missing_notes = [k for k, v in scores.items() if v is None]

        if missing_notes:
            st.error(
                f"⚠️ Veuillez renseigner tous les critères avant de valider ({len(missing_notes)} note(s) manquante(s))."
            )
        else:
            total_note = (scores["Performance Collective"] * 0.10) + sum(
                scores[title] * weight for title, _, weight in criteria
            )
            base_prime = (salary_input / ponderation_base) * coef_usine_pct
            prime_trimestrielle = base_prime * (total_note / 4.0)
            pct_prime = (
                (prime_trimestrielle / salary_input * 100)
                if salary_input > 0
                else 0.0
            )

            conn = db.get_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    evaluator = st.session_state.get("username", "System")

                    cursor.execute(
                        """
                        MERGE dbo.evaluations AS target
                        USING (SELECT ? AS target_matricule, ? AS year, ? AS quarter) AS source
                        ON (target.target_matricule = source.target_matricule AND target.year = source.year AND target.quarter = source.quarter)
                        WHEN MATCHED THEN
                            UPDATE SET evaluator_username = ?, note_totale = ?, coef_usine_applique = ?, base_salary = ?, prime_finale = ?, updated_at = GETDATE()
                        WHEN NOT MATCHED THEN
                            INSERT (target_matricule, evaluator_username, year, quarter, note_totale, coef_usine_applique, base_salary, prime_finale)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                        (
                            target_id,
                            selected_year,
                            selected_quarter,
                            evaluator,
                            total_note,
                            coef_usine_val,
                            salary_input,
                            prime_trimestrielle,
                            target_id,
                            evaluator,
                            selected_year,
                            selected_quarter,
                            total_note,
                            coef_usine_val,
                            salary_input,
                            prime_trimestrielle,
                        ),
                    )
                    conn.commit()
                    st.success(
                        "✅ Évaluation enregistrée en base de données avec succès !"
                    )
                except Exception as e:
                    st.error(f"Erreur lors de la sauvegarde SQL : {e}")
                finally:
                    conn.close()

            st.markdown("### 📊 Résultats du Calcul de la Prime")
            res_c1, res_c2, res_c3, res_c4 = st.columns(4)

            res_c1.metric("Note Totale", f"{total_note:.2f} / 4")
            res_c2.metric("Base de Prime", f"{base_prime:,.2f} Ar")
            res_c3.metric(
                "Prime du Trimestre", f"{prime_trimestrielle:,.2f} Ar"
            )
            res_c4.metric("% de Prime", f"{pct_prime:.2f} %")