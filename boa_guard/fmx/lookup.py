import logging

from boa_guard.fmx.connect import SQL

logger = logging.getLogger("boa-guard")


def patient_lookup(medico_id: str) -> str:
    query = """\
SELECT p.id
FROM patient p
INNER JOIN patient_identifier pi on p._id = pi._resource
WHERE
  pi.system = FMX_CODE('https://uk-essen.de/HIS/Cerner/Medico')
  AND pi.use = FMX_CODE('usual')
  AND pi.value = %s;"""
    df = SQL.execute(query, (medico_id,))
    if df.empty:
        logger.warning(
            f"Lookup for patient `{medico_id}` returned "
            "no results. Continuing with `medico_id`."
        )
        return medico_id
    return str(df.at[0, "id"])
