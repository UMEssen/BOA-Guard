from boa_guard.fmx.connect import SQL

def patient_lookup(medico_id: str) -> str:
    query = """\
SELECT p.id FROM patient p 
INNER JOIN patient_identifier pi on p._id = pi._resource
WHERE 
  pi.system = FMX_CODE('https://uk-essen.de/HIS/Cerner/Medico')
  AND pi.use = FMX_CODE('usual')
  AND pi.value = ?;
"""
    df = SQL.execute(query, [medico_id])
    print(df)
    return "TODO"
