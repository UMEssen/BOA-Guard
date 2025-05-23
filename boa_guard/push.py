import json
import logging
import os
from pathlib import Path

import requests
import requests.auth

logger = logging.getLogger("boa-guard")


def post_transactions(
    url: str, user: str, pwd: str, json_tx: Path, json_logs: Path
) -> None:
    url, user, pwd = (
        os.environ["FHIR_URL"],
        os.environ["FHIR_USER"],
        os.environ["FHIR_PWD"],
    )
    headers = {"Content-Type": "application/fhir+json"}
    data = json_tx.read_bytes()

    resp = requests.post(
        url,
        data=data,
        headers=headers,
        auth=requests.auth.HTTPBasicAuth(user, pwd),
        timeout=30,
    )

    if resp.ok:
        logger.info(f"Successfully pushed FHIR transactions to '{url}'.")
    else:
        logger.error(f"An error occured while pushing FHIR transactions to '{url}'.")

    with json_logs.open("w", encoding="utf-8") as f:
        json.dump(resp.json(), f, indent=2)
    logger.info(f"FHIR response saved in '{json_logs}'.")
    resp.raise_for_status()


def main(fhir_folder: Path) -> None:
    env_vars = ("FHIR_URL", "FHIR_USER", "FHIR_PWD")
    json_tx = fhir_folder / "transaction_bundles.json"
    json_logs = fhir_folder / "response.json"

    if not json_tx.is_file():
        logger.warning(
            f"FHIR transactions are missing in '{fhir_folder}'. Run "
            "`boa-guard tx -f FHIR_FOLDER` to generate the FHIR bundles."
        )
        return
    if missing := [k for k in env_vars if not os.getenv(k)]:
        logger.error(
            f"Missing env var(s): {', '.join(missing)}. Add them to your `.env`."
        )
        return

    post_transactions(
        os.environ["FHIR_URL"],
        os.environ["FHIR_USER"],
        os.environ["FHIR_PWD"],
        json_tx,
        json_logs,
    )
