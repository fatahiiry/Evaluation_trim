import streamlit as st
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Portail des Applications Métier",
    page_icon="🖥️",
    layout="wide"
)

# Initialisation de l'état de navigation
if "selected_app" not in st.session_state:
    st.session_state.selected_app = None

# -----------------------------------------------------------------------------
# 2. DESIGN SOMBRE PERSONNALISÉ (CSS)
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Fond principal */
    .stApp {
        background-color: #0e1117;
    }
    /* Carte d'application */
    .app-card {
        background-color: #1e2530;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2d3748;
        margin-bottom: 10px;
    }
    .status-badge {
        background-color: #0d382c;
        color: #2ed573;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        float: right;
    }
    .app-icon {
        font-size: 32px;
        margin-bottom: 5px;
    }
    .card-title {
        color: #ffffff;
        font-size: 18px;
        font-weight: bold;
        margin-top: 5px;
    }
    .card-desc {
        color: #a0aec0;
        font-size: 13px;
        margin-top: 8px;
        margin-bottom: 15px;
        height: 40px;
    }
    .tag-dept {
        background-color: #4a1525;
        color: #ff4757;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: bold;
        margin-right: 5px;
    }
    .tag-site {
        background-color: #2d3748;
        color: #cbd5e0;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. BASE DE DONNÉES DES SITES STREAMLIT
# -----------------------------------------------------------------------------
STREAMLIT_SITES = {
    "app_ventes": {
        "title": "Suivi des Commandes & Ventes",
        "icon": "📊",
        "description": "Application d'analyse des ventes mensuelles et suivi commercial.",
        "status": "Opérationnel",
        "department": "COMMERCIAL",
        "site": "Usine A",
        "url": "http://localhost:8501/?embed=true",
        "allowed_roles": ["COMMERCIAL", "ADMIN"]
    },
    "app_coupe": {
        "title": "Gestion des Fiches de Coupe",
        "icon": "✂️",
        "description": "Extraction des données de matelassage et suivi du rendement de coupe.",
        "status": "Opérationnel",
        "department": "PRODUCTION",
        "site": "Atelier Textile",
        "url": "http://localhost:8502/?embed=true",
        "allowed_roles": ["PRODUCTION", "LEAN", "ADMIN"]
    },
    "app_rh": {
        "title": "Évaluation & Heures Supp.",
        "icon": "👥",
        "description": "Suivi de la présence, calcul des heures supplémentaires et primes.",
        "status": "Opérationnel",
        "department": "RH",
        "site": "Siège",
        "url": "http://localhost:8503/?embed=true",
        "allowed_roles": ["RH", "ADMIN"]
    }
}

# -----------------------------------------------------------------------------
# 4. GESTION DU RÔLE UTILISATEUR (OU SESSIONS ODOO)
# -----------------------------------------------------------------------------
st.sidebar.title("🔐 Paramètres Accès")
user_role = st.sidebar.selectbox(
    "Rôle actuel :",
    ["ADMIN", "COMMERCIAL", "PRODUCTION", "RH"],
    index=0
)

# -----------------------------------------------------------------------------
# 5. AFFICHAGE DYNAMIQUE (HUB OU VUE D'UNE APPLICATION)
# -----------------------------------------------------------------------------

# CAS 1 : Une application a été cliquée -> Chargement dans la même page via iframe
if st.session_state.selected_app and st.session_state.selected_app in STREAMLIT_SITES:
    current_app = STREAMLIT_SITES[st.session_state.selected_app]

    # Barre supérieure avec bouton de retour
    col_nav, col_title = st.columns([1, 5])
    with col_nav:
        if st.button("⬅️ Retour au portail", use_container_width=True):
            st.session_state.selected_app = None
            st.rerun()

    with col_title:
        st.subheader(f"{current_app['icon']} {current_app['title']}")

    st.divider()

    # Inclusion du site Streamlit cible
    components.iframe(current_app["url"], height=850, scrolling=True)

# CAS 2 : Vue principale -> Affichage de la grille de cartes
else:
    st.title("🖥️ Portail des Applications Métier")
    st.write("Sélectionnez une interface pour l'ouvrir directement dans ce portail.")
    st.divider()

    # Filtrage des sites autorisés selon le rôle
    visible_apps = {
        key: app for key, app in STREAMLIT_SITES.items()
        if user_role in app["allowed_roles"] or user_role == "ADMIN"
    }

    if not visible_apps:
        st.info("Aucune application disponible pour votre profil utilisateur.")
    else:
        # Disposition sur 2 colonnes
        cols = st.columns(2)

        for idx, (app_key, app) in enumerate(visible_apps.items()):
            with cols[idx % 2]:
                # Rendu visuel de la carte en HTML/CSS
                st.markdown(f"""
                    <div class="app-card">
                        <span class="status-badge">● {app['status']}</span>
                        <div class="app-icon">{app['icon']}</div>
                        <div class="card-title">{app['title']}</div>
                        <div class="card-desc">{app['description']}</div>
                        <div>
                            <span class="tag-dept">{app['department']}</span>
                            <span class="tag-site">{app['site']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # Bouton Streamlit déclenchant le chargement sur la même page
                if st.button("Accéder à l'interface ➔", key=app_key, use_container_width=True):
                    st.session_state.selected_app = app_key
                    st.rerun()

                st.write("")  # Marge verticale entre les cartes