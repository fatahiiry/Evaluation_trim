import streamlit as st
from database import get_coef_usine_by_quarter, save_coef_usine_by_quarter
from quarter_utils import get_current_quarter_info, get_quarter_label


def render_rh_config_view(db_conn=None):
    st.title("⚙️ Paramétrage RH - Coefficient Usine")

    current_q, current_y = get_current_quarter_info()

    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input(
            "Année :", min_value=2024, max_value=2030, value=current_y
        )
    with col2:
        quarter = st.selectbox(
            "Trimestre :",
            [1, 2, 3, 4],
            index=current_q - 1,
            format_func=lambda q: get_quarter_label(q, year),
        )

    # Récupération de la valeur (si db_conn est None, get_coef_usine_by_quarter s'ouvre lui-même)
    current_val = get_coef_usine_by_quarter(year, quarter)
    if current_val is None:
        current_val = 4.0

    with st.form("form_rh_coef"):
        new_coef = st.number_input(
            "Coefficient Usine (%) :",
            min_value=0.0,
            max_value=100.0,
            value=float(current_val),
            step=0.5,
        )
        if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
            user = st.session_state.get("username", "RH")
            save_coef_usine_by_quarter(
                year=year, quarter=quarter, coef_usine=new_coef, username=user
            )
            st.success(
                f"✅ Coefficient Usine de {new_coef}% enregistré pour {get_quarter_label(quarter, year)} !"
            )