from pathlib import Path
from datetime import datetime

def write_log(message):

    arquivo_log = (
        Path(r"C:\Users\e.gustavo.santos.GRUPO_A&C\Documents\Projetos\11 - cascata_procedures")
        / "logs"
        / f"log_etl_{datetime.now():%Y-%m-%d}.txt"
    )

    arquivo_log.parent.mkdir(exist_ok=True)

    with open(arquivo_log, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {str(message)}\n")