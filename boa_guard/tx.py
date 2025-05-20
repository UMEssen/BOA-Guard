import json
import logging
from pathlib import Path
from typing import Any

from boa_guard.utils import generate_hash

logger = logging.getLogger("boa-guard")


def main(fhir_folder: Path) -> None:
    json_bundle = fhir_folder / "fhir-bundles.json"
    json_output = fhir_folder / "transaction_bundles.json"

    if not json_bundle.is_file():
        logger.warning(
            f"FHIR bundles are missing in '{fhir_folder}'. Run "
            "`boa-guard bundles -f FHIR_FOLDER -b BOA_FOLDER` to "
            "generate the FHIR bundles."
        )
        return

    with json_bundle.open(encoding="utf-8") as f:
        bundle_dict: list[dict[str, Any]] = json.load(f)
    transaction_dict = create_transactions(bundle_dict)

    with json_output.open("w", encoding="utf-8") as f:
        json.dump(transaction_dict, f, indent=2)
    logger.info(f"Successfully created FHIR transactions in '{fhir_folder}'.")


def create_transactions(bundle_dict: list[dict[str, Any]]) -> dict[str, Any]:
    transaction_entries = []
    for resource in bundle_dict:
        resource_type, resource_entry = next(iter(resource.items()))
        resource_entry["resourceType"] = resource_type
        transaction_entry = {
            # "fullUrl": entry.get("fullUrl", f"urn:uuid:{resource_id}"),
            "resource": resource_entry,
            "request": {
                "method": "POST",  # "PUT" or "POST" if you're creating new resources
                "url": f"{resource_type}/{generate_hash(32)}",
            },
        }
        transaction_entries.append(transaction_entry)

    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": transaction_entries,
    }
