import streamlit as st
import auth


def render_login_page():
    st.markdown(
        """
    <style>
    /* Masquer le header Streamlit */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    .main .block-container {
        padding-top: 2rem !important;
        max-width: 100% !important;
    }

    /* Style ciblant le conteneur Streamlit avec bordure */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        max-width: 520px !important;
        margin: 0 auto !important;
        padding: 0px !important; /* Mis à 0 pour que le bandeau colle aux bords */
        background: #FFFFFF !important;
        border: 2px solid #2E86C1 !important;
        border-radius: 16px !important;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.12) !important;
        overflow: hidden !important; /* Garde les coins arrondis propres */
    }

    /* BANDEAU DE TITRE DE CONNEXION (Fond bleu + texte blanc agrandi) */
    .login-header-banner {
        background-color: #2E86C1 !important;
        color: #FFFFFF !important;
        text-align: center !important;
        padding: 18px 20px !important;
        font-weight: 800 !important;
        font-size: 30px !important;
        letter-spacing: 0.5px;
        margin-bottom: 20px !important;
    }

    /* Conteneur interne pour ajouter du rembourrage sous le bandeau */
    .login-body {
        padding: 0px 25px 25px 25px;
    }

    /* Personnalisation des champs texte */
    div.stTextInput { 
        margin-bottom: 12px !important; 
    }
    div.stTextInput > div > div > input {
        height: 50px !important;
        font-size: 16px !important;
        border: 1.5px solid #D5D8DC !important;
        border-radius: 8px !important;
    }
    div.stTextInput > div > div > input:focus {
        border-color: #2E86C1 !important;
        box-shadow: 0 0 0 3px rgba(46, 134, 193, 0.2) !important;
    }

    /* Styles des boutons */
    div.stButton > button {
        height: 48px;
        font-size: 15px;
        border-radius: 8px;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s ease;
    }

    div.stButton > button[kind="secondary"] {
        border: 1.5px solid #D5D8DC;
        background-color: #FFFFFF;
        color: #2C3E50;
    }

    div.stButton > button[kind="primary"] {
        background-color: #2E86C1 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(46, 134, 193, 0.3) !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background-color: #1B4F72 !important;
        transform: translateY(-1px);
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Centrage sur la page
    _, col_center, _ = st.columns([1, 1.5, 1])

    with col_center:
        with st.container(border=True):
            # Bandeau bleu avec texte blanc agrandi
            st.markdown(
                "<div class='login-header-banner'>🔐 Connexion EVALUATION</div>",
                unsafe_allow_html=True,
            )

            # Champs de saisie et boutons dans le corps de la carte
            username = st.text_input(
                "👤 Identifiant / Matricule",
                placeholder="Entrez votre identifiant",
                key="login_username",
            )
            password = st.text_input(
                "🔑 Mot de passe",
                type="password",
                placeholder="Entrez votre mot de passe",
                key="login_password",
            )

            st.write("")  # Espace

            col_btn1, col_btn2 = st.columns([1, 1])

            with col_btn1:
                if st.button(
                        "Se connecter", type="primary", use_container_width=True
                ):
                    if username and password:
                        role = auth.check_user_db(
                            username.strip(), password.strip()
                        )
                        if role:
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = username.strip()
                            st.session_state["role"] = role
                            st.rerun()
                        else:
                            st.error("Identifiant ou mot de passe incorrect.")
                    else:
                        st.warning("Veuillez remplir tous les champs.")

            with col_btn2:
                if st.button("Mot de passe oublié ?", use_container_width=True):
                    st.info("Veuillez contacter votre administrateur RH.")