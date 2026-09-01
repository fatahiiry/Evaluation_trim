from datetime import datetime


def get_current_quarter_info():
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return quarter, now.year


def get_quarter_label(quarter: int, year: int) -> str:
    labels = {
        1: f"T1 {year} (Jan - Mar)",
        2: f"T2 {year} (Avr - Jun)",
        3: f"T3 {year} (Jul - Sep)",
        4: f"T4 {year} (Oct - Déc)",
    }
    return labels.get(quarter, f"T{quarter} {year}")