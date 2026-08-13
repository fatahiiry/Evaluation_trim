import streamlit as st


def apply_custom_styles():
    """Injecte le CSS personnalisé sans altérer la page de connexion."""
    st.markdown(
        """
    <style>
        /* Réduction de l'espace haut UNIQUEMENT lorsque l'utilisateur est connecté */
        div[data-testid="stSidebarNav"] + section .block-container,
        .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }

        /* Masque le fond du header natif Streamlit */
        header[data-testid="stHeader"] {
            background-color: rgba(0, 0, 0, 0) !important;
        }

        /* Arrière-plan global */
        .main {
            background-color: #f8f9fa;
        }

        /* BANDEAU D'EN-TÊTE PRINCIPAL (MAIN HEADER) */
        .main-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 20px 24px;
            border-radius: 12px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        }
        .main-header h1 {
            color: white !important;
            margin: 0;
            font-size: 1.8rem;
            font-weight: 600;
        }
        .main-header p {
            margin-top: 5px;
            opacity: 0.9;
            font-size: 0.95rem;
            margin-bottom: 0;
        }

        /* MÉTRIQUES ET CARTES D'INFORMATION */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #1e3c72 !important;
        }
        [data-testid="stMetric"] {
            background-color: white;
            padding: 15px 20px;
            border-radius: 10px;
            border-left: 5px solid #2a5298;
            box-shadow: 0 2px 5px rgba(0,0,0,0.04);
        }

        /* ONGLETS DE NAVIGATION (ST.TABS) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: white;
            border-radius: 8px;
            padding: 10px 20px;
            border: 1px solid #e2e8f0;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1e3c72 !important;
            color: white !important;
            border-color: #1e3c72 !important;
        }

        /* SIDEBAR */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )
def inject_modern_css():
    st.markdown(
        """
    <style>
        /* Fond global de l'application */
        .main {
            background-color: #f8f9fa;
        }

        /* En-tête principal en bandeau gradient */
        .main-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 24px;
            border-radius: 12px;
            color: white;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        }
        .main-header h1 {
            color: white !important;
            margin: 0;
            font-size: 1.8rem;
            font-weight: 600;
        }
        .main-header p {
            margin-top: 5px;
            opacity: 0.9;
            font-size: 0.95rem;
            margin-bottom: 0;
        }

        /* Modernisation des métriques (Carte de l'effectif) */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #1e3c72 !important;
        }
        [data-testid="stMetric"] {
            background-color: white;
            padding: 15px 20px;
            border-radius: 10px;
            border-left: 5px solid #2a5298;
            box-shadow: 0 2px 5px rgba(0,0,0,0.04);
        }

        /* Style moderne pour les onglets st.tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: white;
            border-radius: 8px;
            padding: 10px 20px;
            border: 1px solid #e2e8f0;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1e3c72 !important;
            color: white !important;
            border-color: #1e3c72 !important;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

@st.dialog("🔑 Modifier mon mot de passe")
def reset_password_dialog():
    """Boîte de dialogue pour le changement de mot de passe."""
    import auth  # Import local pour éviter les imports circulaires

    old_p = st.text_input("🆕 Ancien mot de passe", type="password")
    new_p = st.text_input("🔄 Nouveau mot de passe", type="password")
    confirm_p = st.text_input(
        "🔄 Confirmer le nouveau mot de passe", type="password"
    )

    if st.button("Valider la modification", use_container_width=True):
        if not old_p or not new_p or not confirm_p:
            st.error("Veuillez remplir tous les champs.")
        elif new_p != confirm_p:
            st.error("Les nouveaux mots de passe ne correspondent pas.")
        else:
            current_user = st.session_state.get("username")
            if auth.verify_password(current_user, old_p):
                if auth.update_password(current_user, new_p):
                    st.success("Mot de passe modifié avec succès !")
                    st.rerun()
                else:
                    st.error("Erreur lors de la mise à jour en BDD.")
            else:
                st.error("L'ancien mot de passe est incorrect.")