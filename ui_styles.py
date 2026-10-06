import streamlit as st
import auth


def apply_custom_styles():
    """Injecte le CSS personnalisé pour la mise en page globale et la sidebar."""
    st.markdown(
        """
    <style>
        /* Réduction de l'espace haut quand l'utilisateur est connecté */
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

        /* SIDEBAR CONTAINER */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }

        /* BORDURES FORCÉES SUR LES CHAMPS (INPUTS, SELECTBOX, NUMBER INPUT) DE LA SIDEBAR */
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] div[role="combobox"] {
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
            background-color: #ffffff !important;
        }

        /* Ciblage des conteneurs BaseWeb dans la Sidebar (notamment dans les expanders) */
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
            background-color: #ffffff !important;
        }

        /* Effet au survol des champs */
        [data-testid="stSidebar"] input:hover,
        [data-testid="stSidebar"] div[role="combobox"]:hover,
        [data-testid="stSidebar"] [data-baseweb="input"]:hover,
        [data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
            border-color: #94a3b8 !important;
        }

        /* Focus / Clic actif sur les champs */
        [data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
        [data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


def inject_modern_css():
    """Injecte les styles modernes pour le contenu principal (Main Container)."""
    st.markdown(
        """
    <style>
        /* Bandeau d'en-tête principal */
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

        /* Modernisation des cartes métriques */
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
    """Boîte de dialogue pour le changement de mot de passe utilisateur."""
    old_p = st.text_input("🔑 Ancien mot de passe", type="password")
    new_p = st.text_input("🆕 Nouveau mot de passe", type="password")
    confirm_p = st.text_input(
        "🔄 Confirmer le nouveau mot de passe", type="password"
    )

    st.caption(
        "📌 *Exigences : 8 caractères minimum, au moins 1 majuscule, 1 minuscule et 1 chiffre.*"
    )

    if st.button("Valider la modification", use_container_width=True, type="primary"):
        if not old_p or not new_p or not confirm_p:
            st.error("Veuillez remplir tous les champs.")
        elif new_p != confirm_p:
            st.error("Les nouveaux mots de passe ne correspondent pas.")
        else:
            current_user = st.session_state.get("username")
            if not current_user:
                st.error("Utilisateur non identifié. Veuillez vous re-connecter.")
            elif auth.verify_password(current_user, old_p):
                success, msg = auth.update_password(current_user, new_p)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("L'ancien mot de passe est incorrect.")