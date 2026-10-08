import pandas as pd
import streamlit as st
import database as db

ROLES_RESPONSABLE = ["Manager", "Évaluateur", "Administrateur"]
ROLES_DIRECTION = ["DG", "Administrateur"]

EMPTY_VALID = {
    "resp": False, "resp_par": None, "resp_le": None,
    "dir": False, "dir_par": None, "dir_le": None,
    "dir_comment": None,
}


def fmt_date(dt):
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "-"

def get_validation_status(year, quarter):
    result = {}
    conn = db.get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT target_matricule,
                       valide_responsable_le, valide_responsable_par,
                       valide_direction_le, valide_direction_par,
                       commentaire_direction
                FROM dbo.evaluations WHERE year = ? AND quarter = ?
                """,
                (year, quarter),
            )
            for m, r_le, r_par, d_le, d_par, d_com in cur.fetchall():
                result[str(m).strip()] = {
                    "resp": r_le is not None, "resp_par": r_par, "resp_le": r_le,
                    "dir": d_le is not None, "dir_par": d_par, "dir_le": d_le,
                    "dir_comment": d_com,
                }
        except Exception as e:
            st.error(f"Erreur statut de validation : {e}")
        finally:
            conn.close()
    return result

def validate_bulk(matricules, year, quarter, niveau, username, commentaire=None):
    """Valide plusieurs évaluations. Retourne le nombre réellement validé."""
    conn = db.get_connection()
    if not conn:
        return 0
    count = 0
    try:
        cur = conn.cursor()
        for m in matricules:
            if niveau == "responsable":
                cur.execute(
                    """
                    UPDATE dbo.evaluations
                    SET valide_responsable_le = GETDATE(), valide_responsable_par = ?
                    WHERE target_matricule = ? AND year = ? AND quarter = ?
                      AND valide_responsable_le IS NULL
                    """,
                    (username, m, year, quarter),
                )
            else:
                # La direction ne valide que ce que le responsable a déjà validé
                cur.execute(
                    """
                    UPDATE dbo.evaluations
                    SET valide_direction_le = GETDATE(),
                        valide_direction_par = ?,
                        commentaire_direction = COALESCE(NULLIF(?, ''), commentaire_direction)
                    WHERE target_matricule = ? AND year = ? AND quarter = ?
                      AND valide_responsable_le IS NOT NULL
                      AND valide_direction_le IS NULL
                    """,
                    (username, (commentaire or "").strip(), m, year, quarter),
                )
            count += cur.rowcount
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        st.error(f"Erreur de validation : {e}")
        return 0
    finally:
        conn.close()

def cancel_validation(matricule, year, quarter, niveau):
    conn = db.get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        if niveau == "responsable":
            # Annuler le responsable annule aussi la direction
            cur.execute(
                """
                UPDATE dbo.evaluations
                SET valide_responsable_le = NULL, valide_responsable_par = NULL,
                    valide_direction_le = NULL, valide_direction_par = NULL
                WHERE target_matricule = ? AND year = ? AND quarter = ?
                """,
                (matricule, year, quarter),
            )
        else:
            cur.execute(
                """
                UPDATE dbo.evaluations
                SET valide_direction_le = NULL, valide_direction_par = NULL
                WHERE target_matricule = ? AND year = ? AND quarter = ?
                """,
                (matricule, year, quarter),
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur d'annulation : {e}")
        return False
    finally:
        conn.close()

def save_direction_comment(matricule, year, quarter, texte):
    conn = db.get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE dbo.evaluations SET commentaire_direction = ?
            WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
            ((texte or "").strip() or None, matricule, year, quarter),
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur d'enregistrement du commentaire : {e}")
        return False
    finally:
        conn.close()

def set_validation(matricule, year, quarter, niveau, username, valeur=True):
    """niveau = 'responsable' ou 'direction'"""
    if niveau not in ("responsable", "direction"):
        return False
    col = f"valide_{niveau}"
    conn = db.get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE dbo.evaluations
            SET {col} = ?, {col}_par = ?, {col}_le = GETDATE()
            WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
            (1 if valeur else 0, username if valeur else None, matricule, year, quarter),
        )
        # Annuler la validation du responsable annule aussi celle de la direction
        if niveau == "responsable" and not valeur:
            cur.execute(
                """
                UPDATE dbo.evaluations
                SET valide_direction = 0, valide_direction_par = NULL, valide_direction_le = NULL
                WHERE target_matricule = ? AND year = ? AND quarter = ?
                """,
                (matricule, year, quarter),
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur de validation : {e}")
        return False
    finally:
        conn.close()

# 1. POP-UP DES DÉTAILS DE L'ÉVALUATION
@st.dialog("📋 Détails de l'évaluation", width="large")
def show_evaluation_details(matricule, nom_complet, year, quarter, user_role="Manager"):
    st.markdown(f"**Collaborateur :** {nom_complet} (`{matricule}`)")
    st.markdown(f"**Période :** Trimestre {quarter} - Année {year}")
    st.markdown("---")

    conn = db.get_connection()
    if not conn:
        st.error("Connexion à la base impossible.")
        return

    eval_data = None
    details = []
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, note_totale, prime_finale, base_salary, coef_usine_applique,
                   commentaire, evaluator_username
            FROM dbo.evaluations
            WHERE target_matricule = ? AND year = ? AND quarter = ?
            """,
            (matricule, year, quarter),
        )
        eval_data = cursor.fetchone()

        if eval_data:
            cursor.execute(
                """
                SELECT code_critere, titre_critere, description_critere, note, poids_applique
                FROM dbo.evaluation_details
                WHERE evaluation_id = ?
                ORDER BY id ASC
                """,
                (eval_data[0],),
            )
            details = cursor.fetchall()
    except Exception as e:
        st.error(f"Erreur lors du chargement des détails : {e}")
        return
    finally:
        conn.close()

    if not eval_data:
        st.warning(
            "Aucune évaluation enregistrée pour ce collaborateur sur cette période."
        )
        return

    (
        eval_id,
        note_totale,
        prime_finale,
        base_salary,
        coef_usine,
        commentaire,
        evaluator,
    ) = eval_data

    # --- Synthèse ---
    if user_role in ["RH", "DG", "Administrateur"]:
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Note Totale",
            f"{note_totale:.2f} / 4.00" if note_totale is not None else "-",
        )
        c2.metric(
            "Prime finale",
            f"{prime_finale:,.2f} Ar" if prime_finale is not None else "-",
        )
        c3.metric("Évaluateur", evaluator or "Non renseigné")
    else:
        c1, c2 = st.columns(2)
        c1.metric(
            "Note Totale",
            f"{note_totale:.2f} / 4.00" if note_totale is not None else "-",
        )
        c2.metric("Évaluateur", evaluator or "Non renseigné")

    # --- Critères ---
    st.markdown("---")
    st.subheader("📌 Critères évalués")

    if details:
        table_critere_data = []
        for code, titre, desc, note, poids in details:
            if poids is not None:
                poids_display = (
                    f"{poids * 100:.0f}%" if poids <= 1 else f"{poids:.0f}%"
                )
            else:
                poids_display = "-"

            table_critere_data.append(
                {
                    "Code / Critère": titre or code or "-",
                    "Description": desc or "-",
                    "Poids": poids_display,
                    "Note / 4": note,
                }
            )

        df_criteres = pd.DataFrame(table_critere_data)

        def highlight_critere_note(val):
            if isinstance(val, (int, float)) and val < 2.0:
                return "background-color: #ffcccc; color: #900c3f; font-weight: bold;"
            return ""

        styled_criteres = df_criteres.style.map(
            highlight_critere_note, subset=["Note / 4"]
        ).format({"Note / 4": "{:.2f}"})

        st.dataframe(styled_criteres, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun détail de critère enregistré pour cette évaluation.")

    # --- Commentaire global ---
    st.markdown("---")
    st.subheader("💬 Commentaire global")
    if commentaire and str(commentaire).strip():
        st.info(commentaire)
    else:
        st.caption("*Aucun commentaire rédigé pour cette évaluation.*")

    # --- Validation ---
    st.markdown("---")
    st.subheader("✅ Validation")

    current_user = st.session_state.get("username", "")
    v = get_validation_status(year, quarter).get(
        str(matricule).strip(), EMPTY_VALID
    )

    def _refresh():
        st.session_state["df_version"] = st.session_state.get("df_version", 0) + 1
        st.rerun()

    col_r, col_d = st.columns(2)

    with col_r:
        st.markdown(
            f"**Responsable :** {'✅ Validé' if v['resp'] else '⏳ En attente'}"
        )
        if v["resp"]:
            st.caption(f"par {v['resp_par'] or '-'} le {fmt_date(v['resp_le'])}")
        if user_role in ROLES_RESPONSABLE:
            if not v["resp"]:
                if st.button(
                    "Valider (Responsable)", type="primary", key="btn_val_resp"
                ):
                    validate_bulk(
                        [matricule], year, quarter, "responsable", current_user
                    )
                    _refresh()
            elif not v["dir"]:
                if st.button("Annuler ma validation", key="btn_cancel_resp"):
                    cancel_validation(matricule, year, quarter, "responsable")
                    _refresh()

    with col_d:
        st.markdown(
            f"**Direction :** {'✅ Validé' if v['dir'] else '⏳ En attente'}"
        )
        if v["dir"]:
            st.caption(f"par {v['dir_par'] or '-'} le {fmt_date(v['dir_le'])}")

    # --- Commentaire de la direction ---
    st.markdown("##### 🏛️ Commentaire de la direction")
    if user_role in ROLES_DIRECTION:
        com = st.text_area(
            "Commentaire de la direction",
            value=v["dir_comment"] or "",
            key=f"com_dir_{matricule}",
            label_visibility="collapsed",
            placeholder="Observation de la direction générale…",
        )
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("💾 Enregistrer le commentaire", key="btn_save_com"):
                if save_direction_comment(matricule, year, quarter, com):
                    st.success("Commentaire enregistré.")
        with col_b2:
            if not v["dir"]:
                if v["resp"]:
                    if st.button(
                        "Valider (Direction)", type="primary", key="btn_val_dir"
                    ):
                        validate_bulk(
                            [matricule], year, quarter,
                            "direction", current_user, com,
                        )
                        _refresh()
                else:
                    st.caption("Validation possible après le responsable.")
            else:
                if st.button("Annuler la validation", key="btn_cancel_dir"):
                    cancel_validation(matricule, year, quarter, "direction")
                    _refresh()
    else:
        if v["dir_comment"]:
            st.info(v["dir_comment"])
        else:
            st.caption("*Aucun commentaire de la direction.*")

# 2. PAGE DASHBOARD & SUIVI GLOBAL
def render_dashboard_page(user_role="Manager", username=""):
    # 1. Extraction et nettoyage strict du username
    if isinstance(username, (tuple, list)):
        clean_username = str(username[0]).strip() if len(username) > 0 else ""
    else:
        clean_username = str(username or "").strip()

    # 2. Récupération dynamique de la période active
    config = db.get_active_quarter_config()
    current_year = config["year"]
    current_quarter = config["quarter"]

    st.markdown(
        f"## 📊 Tableau de Bord & Suivi Global (T{current_quarter} {current_year})"
    )

    # 3. Chargement des évaluations enregistrées
    data_eval = db.get_dashboard_data_by_role(
        user_role=user_role,
        username=clean_username,
        year=current_year,
        quarter=current_quarter,
    )
    df_eval = pd.DataFrame(data_eval) if data_eval else pd.DataFrame()

    # 4. Chargement de l'effectif TOTAL selon le rôle
    df_all_emp = pd.DataFrame()
    conn = db.get_connection()

    if conn:
        try:
            cursor = conn.cursor()
            if user_role in ["RH", "DG", "Administrateur"]:
                query = "SELECT matricule, nom_complet, department FROM dbo.employees"
                cursor.execute(query)
            else:
                query = "SELECT matricule, nom_complet, department FROM dbo.employees WHERE evaluator_username = ?"
                cursor.execute(query, clean_username)

            rows = cursor.fetchall()
            if rows:
                cols = [column[0] for column in cursor.description]
                df_all_emp = pd.DataFrame.from_records(rows, columns=cols)
        except Exception as e:
            st.error(f"Erreur lors du chargement des collaborateurs : {e}")
        finally:
            conn.close()

    # Fallback si df_all_emp est vide
    if df_all_emp.empty and not df_eval.empty:
        df_all_emp = df_eval.copy()

    if df_all_emp.empty:
        st.warning(
            "⚠️ Aucun collaborateur trouvé pour votre profil ou votre périmètre."
        )
        return

    # Normalisation
    if "department" in df_all_emp.columns:
        df_all_emp["department"] = (
            df_all_emp["department"].fillna("Non défini").astype(str).str.strip()
        )
    df_all_emp["matricule"] = df_all_emp["matricule"].astype(str).str.strip()

    # Identification des matricules évalués
    evaluated_mats = set()
    if not df_eval.empty and "matricule" in df_eval.columns:
        done_mask = df_eval["statut"].isin(["✅ Fait", "Terminé", "Fait"])
        evaluated_mats = set(
            df_eval[done_mask]["matricule"].astype(str).str.strip().tolist()
        )

    # Statuts de validation (responsable / direction)
    valid_map = get_validation_status(current_year, current_quarter)
    mats_in_scope = set(df_all_emp["matricule"].tolist())
    nb_valid_resp = sum(1 for m in mats_in_scope if valid_map.get(m, EMPTY_VALID)["resp"])
    nb_valid_dir = sum(1 for m in mats_in_scope if valid_map.get(m, EMPTY_VALID)["dir"])

    # 5. Calcul des KPIs
    total_collab = len(df_all_emp)

    faits_count = len(mats_in_scope.intersection(evaluated_mats))
    non_faits_count = max(0, total_collab - faits_count)
    taux_avancement = (
        (faits_count / total_collab * 100) if total_collab > 0 else 0.0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Total à évaluer", total_collab)
    col2.metric("✅ Évaluations faites", faits_count)
    col3.metric("⏳ En attente", non_faits_count)
    col4.metric("📈 Taux de réalisation", f"{taux_avancement:.1f} %")

    col5, col6, _, _ = st.columns(4)
    col5.metric("🧑‍💼 Validées par le responsable", nb_valid_resp)
    col6.metric("🏛️ Validées par la direction", nb_valid_dir)

    st.divider()

    # 6. Synthèse par Département (RH / DG / Admin)
    if user_role in ["RH", "DG", "Administrateur"]:
        st.subheader("🏢 Statistiques du suivi par Département")
        dept_summary = []
        departments = sorted(df_all_emp["department"].dropna().unique())

        for dept in departments:
            emp_in_dept = df_all_emp[df_all_emp["department"] == dept]
            total_dept = len(emp_in_dept)
            mats_in_dept = set(emp_in_dept["matricule"].tolist())
            faites_dept = len(mats_in_dept.intersection(evaluated_mats))
            attente_dept = max(0, total_dept - faites_dept)
            pct_dept = (
                (faites_dept / total_dept * 100) if total_dept > 0 else 0.0
            )
            valid_resp_dept = sum(
                1 for m in mats_in_dept if valid_map.get(m, EMPTY_VALID)["resp"]
            )
            valid_dir_dept = sum(
                1 for m in mats_in_dept if valid_map.get(m, EMPTY_VALID)["dir"]
            )

            statut_dept = (
                "🟢 Terminé"
                if pct_dept == 100
                else ("🔵 En cours" if pct_dept > 0 else "🔴 Non démarré")
            )

            dept_summary.append(
                {
                    "Département": dept,
                    "Total à évaluer": total_dept,
                    "Évaluations faites": faites_dept,
                    "En attente": attente_dept,
                    "Validé responsable": valid_resp_dept,
                    "Validé direction": valid_dir_dept,
                    "% Réalisation": f"{pct_dept:.1f}%",
                    "Statut": statut_dept,
                }
            )

        st.dataframe(
            pd.DataFrame(dept_summary), use_container_width=True, hide_index=True
        )
        st.divider()

    # 7. Tableau détaillé avec sélection de ligne et Pop-up
    st.subheader(
        "📋 Liste des Évaluations"
        if user_role in ["RH", "DG", "Administrateur"]
        else "📋 Suivi de mes Collaborateurs"
    )

    if not df_eval.empty:
        st.caption(
            "💡 *Cochez une ou plusieurs lignes pour valider en groupe. "
            "Avec une seule ligne, vous pouvez ouvrir la fiche détaillée.*"
        )

        mats_str = df_eval["matricule"].astype(str).str.strip()
        df_eval["date_resp"] = mats_str.map(
            lambda m: fmt_date(valid_map[m]["resp_le"])
            if valid_map.get(m, EMPTY_VALID)["resp"] else "⏳ En attente"
        )
        df_eval["date_dir"] = mats_str.map(
            lambda m: fmt_date(valid_map[m]["dir_le"])
            if valid_map.get(m, EMPTY_VALID)["dir"] else "⏳ En attente"
        )

        base_cols = ["matricule", "nom_complet", "department", "statut",
                     "date_resp", "date_dir", "note_totale"]
        if user_role in ["RH", "DG", "Administrateur"]:
            base_cols.append("prime_finale")

        available_cols = [c for c in base_cols if c in df_eval.columns]
        df_filtered = df_eval[available_cols].copy().rename(columns={
            "date_resp": "Date validation responsable",
            "date_dir": "Date validation direction",
        })

        def highlight_low_scores(row):
            note = row.get("note_totale")
            if pd.notnull(note) and note < 2.0:
                return ["background-color: #ffcccc; color: #900c3f; font-weight: bold;"] * len(row)
            return [""] * len(row)

        styled_df = df_filtered.style.apply(highlight_low_scores, axis=1)
        column_formats = {}
        if "note_totale" in df_filtered.columns:
            column_formats["note_totale"] = "{:.2f}"
        if "prime_finale" in df_filtered.columns:
            column_formats["prime_finale"] = "{:,.2f} Ar"
        if column_formats:
            styled_df = styled_df.format(column_formats)

        event = st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key=f"df_eval_{st.session_state.get('df_version', 0)}",
        )

        selected_rows = event.selection.rows
        if selected_rows:
            selected = df_eval.iloc[selected_rows]
            sel_mats = selected["matricule"].astype(str).str.strip().tolist()
            current_user = st.session_state.get("username", "")

            st.markdown(f"**{len(sel_mats)} évaluation(s) sélectionnée(s)**")

            if len(sel_mats) == 1:
                if st.button("🔍 Voir la fiche détaillée", key="btn_open_detail"):
                    show_evaluation_details(
                        matricule=sel_mats[0],
                        nom_complet=selected.iloc[0].get("nom_complet", ""),
                        year=current_year,
                        quarter=current_quarter,
                        user_role=user_role,
                    )

            if user_role in ROLES_RESPONSABLE:
                a_valider = [m for m in sel_mats if not valid_map.get(m, EMPTY_VALID)["resp"]]
                if st.button(
                    f"✅ Valider la sélection (Responsable) — {len(a_valider)}",
                    key="bulk_resp",
                    disabled=not a_valider,
                ):
                    n = validate_bulk(a_valider, current_year, current_quarter,
                                      "responsable", current_user)
                    st.toast(f"{n} évaluation(s) validée(s).", icon="✅")
                    st.session_state["df_version"] = st.session_state.get("df_version", 0) + 1
                    st.rerun()

            if user_role in ROLES_DIRECTION:
                a_valider_dir = [
                    m for m in sel_mats
                    if valid_map.get(m, EMPTY_VALID)["resp"]
                    and not valid_map.get(m, EMPTY_VALID)["dir"]
                ]
                ignores = len(sel_mats) - len(a_valider_dir)
                com_bulk = st.text_area(
                    "Commentaire de la direction (appliqué à toute la sélection, optionnel)",
                    key="bulk_dir_comment",
                )
                if ignores:
                    st.caption(f"{ignores} ligne(s) ignorée(s) : déjà validées par la direction ou pas encore par le responsable.")
                if st.button(
                    f"🏛️ Valider la sélection (Direction) — {len(a_valider_dir)}",
                    key="bulk_dir",
                    type="primary",
                    disabled=not a_valider_dir,
                ):
                    n = validate_bulk(a_valider_dir, current_year, current_quarter,
                                      "direction", current_user, com_bulk)
                    st.toast(f"{n} évaluation(s) validée(s) par la direction.", icon="✅")
                    st.session_state["df_version"] = st.session_state.get("df_version", 0) + 1
                    st.rerun()
    else:
        st.info("Aucune évaluation enregistrée pour cette période.")