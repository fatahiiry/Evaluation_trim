import streamlit as st


def apply_slider_styles():
    """Injecte du CSS pour agrandir visuellement les barres de notation et les curseurs."""
    st.markdown(
        """
        <style>
        /* Agrandissement de la barre du slider */
        div[data-baseweb="slider"] > div {
            height: 12px !important;
            padding-top: 15px !important;
            padding-bottom: 15px !important;
        }
        /* Agrandissement du bouton / curseur */
        div[data-baseweb="slider"] div[role="slider"] {
            height: 24px !important;
            width: 24px !important;
            top: -6px !important;
        }
        /* Couleur bleue pro */
        div[data-baseweb="slider"] div[role="slider"] {
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
    target_name="Employé", base_salary=0.0, is_admin=False
):
    apply_slider_styles()

    st.markdown(f"## 📋 Grille d'Évaluation : **{target_name}**")

    # Échelle de notation (0 à 4)
    SCORE_LABELS = {
        0: "0 - Insuffisant",
        1: "1 - Passable",
        2: "2 - Moyen",
        3: "3 - Bien",
        4: "4 - Excellent",
    }

    scores = {}

    with st.form("evaluation_form"):
        # --- 1. PARAMÈTRES USINE & SALAIRE ---
        st.subheader("⚙️ Données de Base")
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            coef_usine_pct = (
                st.number_input(
                    "Coefficient Usine (Efficience & Qualité en %)",
                    min_value=0.0,
                    max_value=100.0,
                    value=4.0,
                    step=0.5,
                )
                / 100.0
            )

        with col_s2:
            if is_admin:
                # Affichage et saisie déverrouillée pour l'Admin uniquement
                salary_input = st.number_input(
                    "Salaire de base (Ar / Ariary)",
                    min_value=0.0,
                    value=float(base_salary),
                    step=50000.0,
                )
            else:
                # Masquage strict et champ désactivé pour les Managers
                st.text_input(
                    "Salaire de base :",
                    value="•••••••• Ar (Confidentiel)",
                    disabled=True,
                )
                salary_input = float(base_salary)

        st.divider()

        # --- 2. CRITÈRE COLLECTIF (10%) ---
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
                format_func=lambda x: (
                    SCORE_LABELS[x]
                    if x is not None
                    else "-- Sélectionner une note --"
                ),
                key="note_collective",
            )
        with col_c2:
            st.metric("Pondération", "10%")

        st.divider()

        # --- 3. CRITÈRES INDIVIDUELS ---
        st.markdown("## 👤 **CRITÈRES INDIVIDUELS**")

        criteria = [
            ("Corporate", "Respect des valeurs et engagement envers l'entreprise", 0.10),
            ("Ne compte pas ses heures", "Disponibilité et implication", 0.05),
            ("Motivé", "Dynamisme, attitude proactive et engagement dans les missions", 0.15),
            ("Respecte les process", "Suivi rigoureux des procédures et règles internes", 0.15),
            ("Encadre bien et forme bien", "Leadership, encadrement et accompagnement des équipes", 0.10),
            ("Propose des améliorations", "Suggestions d'optimisation et mise en place d'initiatives", 0.15),
            ("Autonomie", "Capacité à gérer ses tâches sans supervision constante", 0.10),
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
                    format_func=lambda x: (
                        SCORE_LABELS[x]
                        if x is not None
                        else "-- Sélectionner une note --"
                    ),
                    key=f"note_{title}",
                )
            with col2:
                st.metric("Pondération", f"{int(weight * 100)}%")
            st.write("")

        submitted = st.form_submit_button(
            "💾 Calculer et Enregistrer", type="primary", use_container_width=True
        )

    # --- CALCULS & RÉSULTATS AUTOMATIQUES ---
    if submitted:
        missing_notes = [k for k, v in scores.items() if v is None]

        if missing_notes:
            st.error(
                f"⚠️ Veuillez renseigner tous les critères avant de valider ({len(missing_notes)} note(s) manquante(s))."
            )
        else:
            # Note totale pondérée (sur 4)
            total_note = (scores["Performance Collective"] * 0.10) + sum(
                scores[title] * weight for title, _, weight in criteria
            )

            # Base de prime = (Salaire / 4) * Coef Usine
            base_prime = (salary_input / 4.0) * coef_usine_pct

            # Prime Trimestre = Base de prime * (Note Totale / 4)
            prime_trimestrielle = base_prime * (total_note / 4.0)

            # Pourcentage de prime
            pct_prime = (
                (prime_trimestrielle / salary_input * 100)
                if salary_input > 0
                else 0.0
            )

            st.success("✅ Évaluation enregistrée avec succès !")

            st.markdown("### 📊 Résultats du Calcul de la Prime")
            res_c1, res_c2, res_c3, res_c4 = st.columns(4)

            res_c1.metric("Note Totale (sur 4)", f"{total_note:.2f} / 4")
            res_c2.metric("Base de Prime", f"{base_prime:,.2f} Ar")
            res_c3.metric("Prime du Trimestre", f"{prime_trimestrielle:,.2f} Ar")
            res_c4.metric("% de Prime", f"{pct_prime:.2f} %")