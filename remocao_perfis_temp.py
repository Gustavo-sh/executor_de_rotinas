import pyodbc
from utils import write_log

CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=primno4;"
    "Database=RobbysonMatriz;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

try:
    with pyodbc.connect(CONNECTION_STRING, autocommit = True) as conn:

        cursor = conn.cursor()

        write_log("Removendo os perfis temporarios e atributos alocados manualmente...")

        cursor.execute("update robbysonmatriz.dbo.acessos_sistema_matriz set role = original_role")

        cursor.execute("update robbysonmatriz.dbo.perfis_temporarios_sistema_matriz set mostrar_atributo = 0 where mostrar_atributo = 1")

        cursor.execute("update robbysonmatriz.dbo.sistema_matriz set meta_final = 87.7 where periodo = dateadd(d, 1, eomonth(getdate(), -1)) and atributo like '%projeto_cegonha%' and id_indicador = 901")

        write_log("Processo finalizado com sucesso...")

except pyodbc.Error as e:
    write_log(f"ERRO PYODBC: {repr(e)}")

except Exception as e:
    write_log(f"ERRO GERAL: {repr(e)}")