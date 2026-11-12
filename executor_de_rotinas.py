from querys_sql import (
    UPDATE_ROLE, UPDATE_MOSTRAR_ATRIBUTO, UPDATE_PROJETO_CEGONHA, MOVER_HISTORICO, SISTEMA_MATRIZ, 
    RM_PT1, RM_PT2, ATT_PUBLICO_INSERT_MANUAL, CHECK_RESULTADO, DADOS_HISTORICOS
)
from utils import write_log
import sys
import pyodbc

CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=primno4;"
    "Database=Robbyson;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

QUERYS = {
    "UPDATE_ROLE": UPDATE_ROLE,
    "UPDATE_MOSTRAR_ATRIBUTO": UPDATE_MOSTRAR_ATRIBUTO,
    "UPDATE_PROJETO_CEGONHA": UPDATE_PROJETO_CEGONHA,
    "MOVER_HISTORICO": MOVER_HISTORICO,
    "SISTEMA_MATRIZ": SISTEMA_MATRIZ,
    "RM_PT1": RM_PT1,
    "RM_PT2": RM_PT2,
    "ATT_PUBLICO_INSERT_MANUAL": ATT_PUBLICO_INSERT_MANUAL,
    "CHECK_RESULTADO": CHECK_RESULTADO,
    "DADOS_HISTORICOS": DADOS_HISTORICOS
}

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
    if len(sys.argv) != 2:
        raise ValueError('Informe o(s) nome(s) da(s) query(s) no argumento. Exemplo: python -u executor_de_rotinas.py "UPDATE_ROLE,UPDATE_MOSTRAR_ATRIBUTO"')

    argumentos = sys.argv[1].upper().split(",")

    querys_to_execute = PROCEDURES if "CASCATA" in argumentos else argumentos

    try:
        last_query = None
        with pyodbc.connect(CONNECTION_STRING) as conn:
            with conn.cursor() as cursor:
                
                for query in querys_to_execute:
                    query_clean = query.strip()
                    last_query = query_clean
                    
                    if query_clean not in QUERYS and query_clean not in PROCEDURES:
                        raise ValueError(f"Query inválida: {query_clean}")
                    
                    cursor.execute("SELECT @@SPID")
                    spid = cursor.fetchone()[0]

                    write_log(f"Executando {query_clean} (SPID: {spid})...")
                    cursor.execute(QUERYS.get(query_clean))

                    while cursor.nextset():
                        pass

                    write_log(f"{query_clean} finalizada (SPID: {spid})...")
                
                    conn.commit()

    except pyodbc.Error as e:
        write_log(f"Erro na execução de {last_query} (PYODBC): {str(e)}")
        raise

    except Exception as e:
        write_log(f"Erro estrutural ou na execução de {last_query}: {str(e)}")
        raise

if __name__ == "__main__":
    main()