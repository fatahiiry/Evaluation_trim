# rh_salary_view.py
import importlib
import database as db
import pandas as pd
import streamlit as st

# Force le rechargement du module database en cas de modification
importlib.reload(db)


def normalize_matricule(val, width=4) -> str:
    """
    Nettoie et formate un matricule pour garantir un format fixe sur 'width' chiffres (ex: '52' -> '0052').
    Gère également les conversions automatiques d'Excel (ex: 52.0 -> '0052').
    """
    if pd.isna(val) or val is None:
        return ""

    val_str = str(val).strip()
    if not val_str or val_str.lower() == "nan":
        return ""

    # Supprime la partie décimale ajoutée par Excel (ex: '52.0' -> '52')
    clean_val = val_str.split(".")[0].strip()

    # Si c'est un nombre, on complète avec des zéros à gauche
    if clean_val.isdigit():
        return clean_val.zfill(width)

    # Si le matricule contient des lettres (ex: 'E052'), on le conserve tel quel
    return clean_val


def clean_salary_value(val) -> float:
    """Nettoie et convertit une valeur de salaire Excel en float valide."""
    if pd.isna(val) or val is None:
        return 0.0

    val_str = str(val).strip()
    val_str = val_str.replace(",", ".").replace(" ", "")
    val_str = (
        val_str.upper()
        .replace("AR", "")
        .replace("ARIARY", "")
        .replace("EUR", "")
        .replace("USD", "")
    )

    try:
        return float(val_str)
    except ValueError:
        return 0.0


def render_rh_salary_management():
    st.title("🔒 Administration des Salaires (Accès RH)")

    tab_import, tab_edit = st.tabs(
        ["📥 Import/Mise à jour Excel", "✏️ Modification Individuelle"]
    )

    with tab_import:
        st.caption(
            "Le fichier Excel doit contenir les colonnes 'Matricule' et 'Salaire'. L'import mettra à jour les salaires existants sans supprimer les autres. Les matricules seront automatiquement normalisés sur 4 chiffres."
        )
        file = st.file_uploader(
            "Importer un fichier Excel",
            type=["xlsx", "xls"],
            key="rh_excel_upload",
        )

        if file and st.button("💾 Chiffrer et Sauvegarder en BDD", type="primary"):
            try:
                # Lecture en forçant le type chaîne (str) pour éviter la perte des zéros par pandas
                df = pd.read_excel(file, dtype=str)

                # Nettoyage des noms de colonnes (minuscules sans espaces)
                df.columns = [str(c).strip().lower() for c in df.columns]

                col_mat = next((c for c in df.columns if "mat" in c), None)
                col_sal = next((c for c in df.columns if "sal" in c), None)

                if col_mat and col_sal:
                    success_count = 0
                    error_count = 0
                    error_details = []

                    progress_bar = st.progress(0)
                    total_rows = len(df)

                    for index, row in df.iterrows():
                        # 🔹 Normalisation du matricule sur 4 chiffres (ex: 52 -> '0052')
                        mat = normalize_matricule(row[col_mat], width=4)
                        sal = clean_salary_value(row[col_sal])

                        if mat:
                            try:
                                db.save_employee_salary(mat, sal)
                                success_count += 1
                            except Exception as err:
                                error_count += 1
                                error_details.append(
                                    f"Ligne {index + 2} (Matricule {mat}) : {err}"
                                )
                        else:
                            error_count += 1
                            error_details.append(
                                f"Ligne {index + 2} : Matricule invalide ou vide."
                            )

                        # Mise à jour de la barre de progression
                        progress_bar.progress((index + 1) / total_rows)

                    # --- MESSAGES ET BILAN FINAUX ---
                    if success_count > 0 and error_count == 0:
                        st.success(
                            f"🎉 Import terminé avec succès ! **{success_count}** salaire(s) chiffré(s) et enregistré(s) en BDD."
                        )
                    elif success_count > 0 and error_count > 0:
                        st.warning(
                            f"⚠️ Import terminé partiellement : **{success_count}** réussi(s), **{error_count}** échec(s)."
                        )
                        with st.expander("Voir le détail des erreurs"):
                            for err_msg in error_details:
                                st.write(f"- {err_msg}")
                    else:
                        st.error(
                            "❌ L'import a totalement échoué. Aucun salaire n'a été enregistré."
                        )
                        with st.expander("Voir le détail des erreurs"):
                            for err_msg in error_details:
                                st.write(f"- {err_msg}")

                else:
                    st.error(
                        "❌ Erreur de format : Colonnes 'Matricule' et 'Salaire' introuvables dans le fichier Excel."
                    )
            except Exception as e:
                st.error(f"❌ Erreur lors de la lecture du fichier : {e}")

    with tab_edit:
        mat_input = st.text_input("Saisir le Matricule de l'employé :")
        if mat_input:
            # 🔹 Normalisation du matricule saisi manuellement
            mat_search = normalize_matricule(mat_input, width=4)
            try:
                current_sal = db.get_employee_salary(mat_search)
                st.info(
                    f"Matricule : **{mat_search}** | Salaire actuel déchiffré : **{current_sal:,.2f} Ar**"
                )

                new_sal = st.number_input(
                    "Nouveau Salaire de Base (Ar) :",
                    value=current_sal,
                    step=50000.0,
                )
                if st.button("💾 Enregistrer la modification"):
                    db.save_employee_salary(mat_search, new_sal)
                    st.success(
                        f"✅ Nouveau salaire pour le matricule **{mat_search}** enregistré avec succès !"
                    )
            except Exception as e:
                st.error(f"Erreur lors de la récupération du salaire : {e}")