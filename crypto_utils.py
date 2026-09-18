import os
from cryptography.fernet import Fernet
import streamlit as st


def get_cipher():
    key = st.secrets.get("SALARY_SECRET_KEY") or os.getenv("SALARY_SECRET_KEY")
    if not key:
        raise ValueError(
            "La clé SALARY_SECRET_KEY est manquante dans .streamlit/secrets.toml !"
        )
    return Fernet(key.encode())


def encrypt_salary(amount: float) -> str:
    """Chiffre un float vers une chaîne AES-256."""
    if amount is None or amount < 0:
        amount = 0.0
    cipher = get_cipher()
    return cipher.encrypt(str(amount).encode()).decode()


def decrypt_salary(encrypted_str: str) -> float:
    """Déchiffre la chaîne AES-256 en float."""
    if not encrypted_str:
        return 0.0
    try:
        cipher = get_cipher()
        return float(cipher.decrypt(encrypted_str.encode()).decode())
    except Exception:
        return 0.0