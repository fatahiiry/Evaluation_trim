import datetime
import jwt
import streamlit as st
import extra_streamlit_components as stx
import auth

SECRET_KEY = "KJo5btNCnUeb-TJCeT8de7xeOBx4JrQ72qOfXolUc4I"
COOKIE_NAME = "evaluation_auth"
DUREE_HEURES = 8


def get_cookie_manager():
    # Pas de @st.cache_resource ici : le composant doit être recréé à chaque run
    return stx.CookieManager(key="cookie_manager")


def creer_jeton(username, role):
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=DUREE_HEURES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def lire_jeton(jeton):
    try:
        return jwt.decode(jeton, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


def sauvegarder_session(cookie_manager, username, role):
    expire = datetime.datetime.now() + datetime.timedelta(hours=DUREE_HEURES)
    cookie_manager.set(COOKIE_NAME, creer_jeton(username, role), expires_at=expire)

def restaurer_session(cookie_manager):
    if st.session_state.get("authenticated"):
        return
    if st.session_state.get("logged_out"):
        return
    jeton = cookie_manager.get(COOKIE_NAME)
    if jeton:
        data = lire_jeton(jeton)
        if data:
            st.session_state["authenticated"] = True
            st.session_state["username"] = data["username"]
            st.session_state["role"] = data["role"]
            info = auth.get_user_details(data["username"])
            st.session_state["nom_complet"] = info["nom_complet"]
            st.session_state["matricule"] = data["username"]
            st.session_state["department"] = info["department"]

def supprimer_session(cookie_manager):
    try:
        cookie_manager.set(
            COOKIE_NAME,
            "",
            expires_at=datetime.datetime.now() - datetime.timedelta(days=1),
            key="logout_cookie",
        )
    except Exception:
        pass