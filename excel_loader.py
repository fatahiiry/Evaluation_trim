import os
import pandas as pd
import streamlit as st

# Chemin par défaut du fichier Excel
EXCEL_FILE_PATH = "employes.xlsx"


@st.cache_data(ttl=300)
def load_excel_employees(file_path: str = EXCEL_FILE_PATH) -> pd.DataFrame:
    """Charge et nettoie les données des employés depuis le fichier Excel.

    Utilise st.cache_data pour éviter de relire le fichier à chaque interaction.
    """
    if not os.path.exists(file_path):
        st.warning(
            f"⚠️ Fichier Introuvable : Le fichier '{file_path}' n'existe pas dans le dossier courant."
        )
        # Retourne un DataFrame vide avec la structure minimale attendue
        return pd.DataFrame(columns=["Matricule", "Employé", "Poste", "Département"])

    try:
        # Lecture du fichier Excel
        df = pd.read_excel(file_path)

        # Nettoyage des noms de colonnes (suppression des espaces superflus)
        df.columns = [str(col).strip() for col in df.columns]

        # Vérification des colonnes essentielles
        required_cols = ["Matricule", "Employé", "Poste", "Département"]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.error(
                f"❌ Erreur Structure Excel : Colonne(s) manquante(s) : {', '.join(missing_cols)}"
            )

        # Conversion du matricule en texte propre
        if "Matricule" in df.columns:
            df["Matricule"] = df["Matricule"].astype(str).str.strip()

        # Nettoyage des chaînes de caractères
        for col in ["Employé", "Poste", "Département"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"❌ Erreur lors de la lecture du fichier Excel : {e}")
        return pd.DataFrame(columns=["Matricule", "Employé", "Poste", "Département"])


def get_departments() -> list:
    """Régénère la liste unique des départements disponibles dans le fichier Excel."""
    df = load_excel_employees()
    if "Département" in df.columns and not df.empty:
        depts = sorted(df["Département"].dropna().unique().tolist())
        return [d for d in depts if d and d.upper() != "NAN"]
    return ["DSI", "RH", "Finance", "Production"]