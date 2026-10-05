import pyodbc
from utils import write_log

CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=primno4;"
    "Database=Robbyson;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

try:
    with pyodbc.connect(CONNECTION_STRING) as conn:

        cursor = conn.cursor()

        cursor.execute("SELECT @@SPID")
        spid = cursor.fetchone()[0]

        write_log(
            f"Executando Robbyson Matriz parte 1 (SPID: {spid})..."
        )

        cursor.execute("EXEC dbo.sp_ins_Robbyson_Matriz_pt1")

        # Consome eventuais result sets/mensagens restantes
        while cursor.nextset():
            pass

        write_log(
            f"Procedure Robbyson Matriz parte 1 finalizada (SPID: {spid})..."
        )

        conn.commit()

except pyodbc.Error as e:
    write_log(f"ERRO PYODBC: {repr(e)}")

except Exception as e:
    write_log(f"ERRO GERAL: {repr(e)}")