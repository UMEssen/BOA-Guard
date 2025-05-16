import json
import logging
import os
from pathlib import Path
from typing import Any

import requests
import requests.auth

logger = logging.getLogger("boa-guard")


# Experimental
def _log_failure(resp: requests.Response) -> None:
    """Log only the pieces that help to debug an HTTP error."""
    logger.error(
        f"{resp.request.method} {resp.url} -> {resp.status_code} {resp.reason}"
    )

    # surface correlation IDs, validators often include one of these
    for h in ("X-Request-Id", "Correlation-Id", "ETag", "Last-Modified"):
        if h in resp.headers:
            logger.error("%s: %s", h, resp.headers[h])

    # FHIR servers usually return OperationOutcome on problems
    try:
        payload: Any = resp.json()
    except ValueError:
        payload = resp.text

    if isinstance(payload, dict) and payload.get("resourceType") == "OperationOutcome":
        for issue in payload.get("issue", []):
            logger.error(
                "OperationOutcome %s: %s",
                issue.get("severity", "<unknown>"),
                issue.get("diagnostics")
                or issue.get("details", {}).get("text", "<no details>"),
            )
    else:
        logger.error("Body: %s", str(payload))


def post_transactions(json_tx: Path) -> None:
    with json_tx.open(encoding="utf-8") as f:
        tx_dict = json.load(f)

    headers = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }

    resp = requests.post(
        os.environ["FHIR_URL"],
        data=tx_dict,
        headers=headers,
        auth=requests.auth.HTTPBasicAuth(
            os.environ["FHIR_USER"], os.environ["FHIR_PWD"]
        ),
    )

    if resp.ok:
        logger.info(
            f"Successfully pushed FHIR transactions to '{os.environ['FHIR_URL']}'"
        )
    else:
        _log_failure(resp)
    resp.raise_for_status()


def main(fhir_folder: Path) -> None:
    json_tx = fhir_folder / "transaction_bundles.json"

    if not json_tx.is_file():
        logger.warning(
            f"FHIR transactions are missing in '{fhir_folder}'. Execute "
            "`boa-guard tx -f FHIR_FOLDER` to generate the FHIR bundles."
        )
        return
    if not all(i in os.environ for i in ["FHIR_URL", "FHIR_USER", "FHIR_PWD"]):
        logger.error(
            "Not all environment variables are set. Add 'FHIR_URL', "
            "'FHIR_USER' and 'FHIR_PWD' to the '.env' file."
        )
        return
    post_transactions(json_tx)
