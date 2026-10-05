import pyodbc
from utils import write_log

CONNECTION_STRING = "Driver={ODBC Driver 18 for SQL Server};Server=primno4;Database=Robbyson;Trusted_Connection=yes;TrustServerCertificate=yes;"

PROCEDURES = [
    "sp_ins_coins",
    "sp_ins_igd_novo",
    "Sp_Ins_MapaDeCalor",
    "SP_Ins_Telaunica_mpc_supervisor_feedbacks_cr",
    "SP_Ins_Telaunica_mpc_supervisor_feedbacks",
    "SP_Ins_Telaunica_mpc_supervisor",
    "SP_Ins_MPC_compilado",
    "sp_peop",
    "sp_score_coordenador",
    "sp_ins_quiz",
    "sp_ins_quiz_rep"
]

def main():
    try:
        with pyodbc.connect(CONNECTION_STRING) as conn:
            cursor = conn.cursor()

            for procedure in PROCEDURES:
                cursor.execute("SELECT @@SPID")
                spid = cursor.fetchone()[0]
                write_log(f"Executando {procedure} (SPID: {spid})...")
                cursor.execute(f"EXEC {procedure}")
                write_log(f"Procedure {procedure} finalizada...")
                while cursor.nextset():
                    pass

            conn.commit()
    except Exception as e:
        write_log(str(e))

if __name__ == "__main__":
    main()