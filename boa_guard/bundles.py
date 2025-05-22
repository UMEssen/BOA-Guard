import hashlib
import json
import logging
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

import pandas as pd
import pydicom
import pytz

from boa_guard.mapping_dict import mapping_dict
from boa_guard.utils import generate_hash

logger = logging.getLogger("boa-guard")


def main(fhir_folder: Path, boa_folder: Path) -> None:
    json_output = fhir_folder / "fhir-bundles.json"
    result_dict: list[dict[str, Any]] = []
    # Skip the lock/temp Excel files
    for excel_file in boa_folder.rglob("[!~$]*.xlsx"):
        try:
            result_dict.extend(create_bundles(excel_file, excel_file.parent))
        except (FileNotFoundError, NotADirectoryError) as e:
            logger.error(
                "An Error occurred while processing the "
                f"folder '{excel_file.parent}': {type(e).__name__}: {e}"
            )

    fhir_folder.mkdir(exist_ok=True)
    with json_output.open("w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2)
    logger.info(f"Successfully created FHIR bundles in '{fhir_folder}'.")


def create_bundles(excel_path: Path, folder: Path) -> list[dict[str, Any]]:
    json_bca = folder / "bca-measurements.json"
    json_total = folder / "total-measurements.json"
    dicom_path = folder / "dicoms"

    if not json_bca.is_file() or not json_total.is_file():
        raise FileNotFoundError(
            f"'{json_bca.name}' or '{json_total.name}' is missing in '{folder}'. "
            "Without the JSON files the FHIR bundles can't be generated for this Patient."
        )
    elif not dicom_path.is_dir():
        raise NotADirectoryError(
            f"Folder '{dicom_path.name}' is missing in '{folder}'. "
            "Without the DICOM files the FHIR bundles can't be generated for this Patient."
        )

    with json_bca.open(encoding="utf-8") as f:
        bca_dict: dict[str, Any] = json.load(f)["aggregated"]
    with json_total.open(encoding="utf-8") as f:
        total_dict: dict[str, Any] = json.load(f)["segmentations"]["total"]
    dicom_dict = get_dicom_dict(dicom_path)
    info_dict = get_info_dict(excel_path, json_bca, json_total)
    return to_fhir_bundles(bca_dict, total_dict, dicom_dict, info_dict)


def to_fhir_bundles(
    bca_dict: dict[str, Any],
    total_dict: dict[str, Any],
    dicom_dict: dict[str, str],
    info_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    imaging_study = get_imaging_study(dicom_dict)
    observations = [get_bsv_observation(total_dict, dicom_dict)]
    observations.extend(get_bca_observation(bca_dict, dicom_dict, False))
    observations.extend(get_bca_observation(bca_dict, dicom_dict, True))

    image_id = imaging_study["ImagingStudy"]["id"]
    observation_ids = [o["Observation"]["id"] for o in observations]
    result = [imaging_study, *observations]
    result.append(
        get_diagnostic_report(image_id, observation_ids, dicom_dict, info_dict)
    )

    return result


def get_info_dict(excel_path: Path, json_bca: Path, json_total: Path) -> dict[str, Any]:
    df = pd.read_excel(
        excel_path, sheet_name="info", header=None, names=["k", "v"], engine="openpyxl"
    )
    df = df[
        df["k"].isin(
            {
                "BOAVersion",
                "BOAGitHash",
                "PredictedContrastPhase",
                "PredictedContrastInGIT",
            }
        )
    ]
    info_dict: dict[str, Any] = df.set_index("k")["v"].astype(str).to_dict()
    mapping_dict = {"xlsx": "vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    info_dict["reports"] = []
    for name, file in (
        ("BCA Measurements", json_bca),
        ("Total Measurements", json_total),
        ("BOA Excel Report", excel_path),
        ("BOA PDF Report", excel_path.parent / "report.pdf"),
    ):
        if not file.is_file():
            continue
        tmp_dict: dict[str, Any] = {}
        suffix = file.suffix[1:]
        tmp_dict["contentType"] = f"application/{mapping_dict.get(suffix, suffix)}"
        tmp_dict["size"] = file.stat().st_size
        tmp_dict["title"] = name
        # Hash
        tmp_dict["hash"] = hashlib.sha1(file.read_bytes()).hexdigest()
        # Creation
        ts = getattr(file.stat(), "st_birthtime", file.stat().st_ctime)
        tmp_dict["creation"] = datetime.fromtimestamp(
            ts, tz=pytz.timezone("Europe/Berlin")
        ).isoformat(timespec="milliseconds")
        info_dict["reports"].append(tmp_dict)
    return info_dict


def get_dicom_dict(dicom_path: Path) -> dict[str, str]:
    dicoms = [
        pydicom.dcmread(f, stop_before_pixels=True) for f in dicom_path.glob("*.dcm")
    ]
    result: dict[str, Any] = {}
    if not dicoms:
        return result

    keys = [
        "StudyInstanceUID",
        "PatientID",
        "SeriesInstanceUID",
        "SeriesNumber",
        "Modality",
        "SeriesDescription",
        "TimezoneOffsetFromUTC",
        "StudyDate",
        "StudyTime",
        "AcquisitionDate",
        "AcquisitionTime",
    ]
    for key in keys:
        try:
            value = dicoms[0].get(key)
            if value is None:
                result[key] = None
            result[key] = str(value)
        except Exception:
            result[key] = None
    # ImageID
    if (
        result["StudyInstanceUID"] is not None
        and result["SeriesInstanceUID"] is not None
    ):
        combined_string = f"{result['StudyInstanceUID']}_{result['SeriesInstanceUID']}"
        result["ImageID"] = hashlib.sha256(combined_string.encode("utf-8")).hexdigest()
    else:
        result["ImageID"] = "TODO"
    # Started
    result["Started"] = dicom_dt_to_fhir_dt(
        result["StudyDate"], result["StudyTime"], result["TimezoneOffsetFromUTC"]
    )
    # Effective
    result["Effective"] = dicom_dt_to_fhir_dt(
        result["AcquisitionDate"],
        result["AcquisitionTime"],
        result["TimezoneOffsetFromUTC"],
    )
    # NumberOfInstances
    num_slices = 1
    if result["StudyInstanceUID"] is not None:
        series_uid = result["SeriesInstanceUID"]
        num_slices = sum(1 for d in dicoms if d.get("SeriesInstanceUID") == series_uid)
    if num_slices == 1:
        num_slices = int(dicoms[0].get("NumberOfFrames", 1))
    result["NumberOfInstances"] = num_slices
    # AccessionNumber
    result["AccessionNumber"] = dicoms[0].get(
        "AccessionNumber", dicoms[0].get("StudyID")
    )

    return {k if k is not None else "TODO": v for k, v in result.items()}


# BOAImagingStudy
def get_imaging_study(dicom_dict: dict[str, str]) -> dict[str, Any]:
    return {
        "ImagingStudy": {
            "id": generate_hash(32),
            "identifier": [
                {
                    "system": "urn:dicom:uid",
                    "value": f"urn:oid:{dicom_dict['StudyInstanceUID']}",
                },
                {
                    "system": "https://uk-essen.de/PACS/GE/CentricityPACS",
                    "value": f"{dicom_dict['AccessionNumber']}",
                },
            ],
            "status": "available",
            "subject": {"reference": f"Patient/{dicom_dict['PatientID']}"},
            "started": dicom_dict["Started"],
            "numberOfSeries": 1,
            "series": [
                {
                    "uid": dicom_dict["SeriesInstanceUID"],
                    "number": dicom_dict["SeriesNumber"],
                    "modality": dicom_dict["Modality"],
                    "description": dicom_dict["SeriesDescription"],
                    "numberOfInstances": dicom_dict["NumberOfInstances"],
                    # "endpoint": dicom_data["endpoint"],  # TODO
                }
            ],
        }
    }


# BOADiagnosticReport
def get_diagnostic_report(
    image_id: str,
    observation_ids: list[str],
    dicom_dict: dict[str, str],
    info_dict: dict[str, Any],
) -> dict[str, Any]:
    return {
        "DiagnosticReport": {
            "id": generate_hash(32),
            "identifier": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://dicom.nema.org/resources/ontology/DCM",
                                "code": "112002",
                                "display": "SeriesInstanceUID: A unique identifier for a series of DICOM SOP instances",
                            },
                        ]
                    },
                    "system": "urn:dicom:uid",
                    "value": dicom_dict["SeriesInstanceUID"],
                }
            ],
            "status": "preliminary",
            "category": [
                {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/CodeSystem/boa/git-hash",
                            "code": info_dict["BOAGitHash"],
                            "display": "Git Hash",
                        },
                    ]
                },
                {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/CodeSystem/boa/version",
                            "code": info_dict["BOAVersion"],
                            "display": "BOA Version",
                        },
                    ]
                },
                {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/ValueSet/boa/contrast/iv-phase",
                            "code": info_dict["PredictedContrastPhase"],
                            "display": "IV Contrast Phase",
                        },
                    ]
                },
                {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/ValueSet/boa/contrast/git",
                            "code": info_dict["PredictedContrastInGIT"],
                            "display": "GI Tract Contrast",
                        },
                    ]
                },
            ],
            "code": {
                "coding": [
                    {
                        "system": "https://uk-essen.de/fhir/CodeSystem/boa/report",
                        "code": "BOA-Report",
                    }
                ],
            },
            "subject": {
                "reference": f"Patient/{dicom_dict['PatientID']}",
            },
            "effectiveDateTime": dicom_dict["Effective"],
            "result": [{"reference": f"Observation/{id}"} for id in observation_ids],
            "imagingStudy": {
                "reference": f"ImagingStudy/{image_id}",
            },
            "presentedForm": [
                {
                    "contentType": i["contentType"],
                    "url": "TODO",  # TODO
                    "size": i["size"],
                    "hash": i["hash"],
                    "title": i["title"],
                    "creation": i["creation"],
                }
                for i in info_dict["reports"]
            ],
        }
    }


# BOABodyCompositionAnalysisObservation
def get_bca_observation(
    bca_dict: dict[str, Any],
    dicom_dict: dict[str, Any],
    without_extremeties: bool,
) -> list[dict[str, Any]]:
    code = "volume-filtered" if without_extremeties else "volume-unfiltered"
    measurements = (
        "measurements_no_extremities" if without_extremeties else "measurements"
    )
    bca_coding_dict = mapping_dict["bca"]
    tissue_coding_dict = mapping_dict["tissues"]

    return [
        {
            "Observation": {
                "id": generate_hash(32),
                "status": {
                    "value": "preliminary",
                },
                "code": {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/CodeSystem/boa/measurements",
                            "code": code,
                        },
                    ]
                },
                "subject": {"reference": f"Patient/{dicom_dict['PatientID']}"},
                "effectiveDateTime": dicom_dict["Effective"],
                "bodySite": {
                    "coding": [
                        {
                            "system": "https://uk-essen.de/fhir/ValueSet/boa/body-site",
                            "code": bv,
                            "display": bk,
                        },
                    ]
                },
                "derivedFrom": dicom_dict["ImageID"],
                "component": [
                    {
                        "code": {
                            "coding": [
                                {
                                    "system": "https://uk-essen.de/fhir/CodeSystem/boa/slice-range",
                                    "code": "axial-slice-range",
                                    "display": f"{bca_dict[bk]['min_slice_idx']} - {bca_dict[bk]['max_slice_idx']}",
                                },
                            ]
                        },
                        "valueRange": {
                            "low": {
                                "value": bca_dict[bk]["min_slice_idx"],
                            },
                            "high": {
                                "value": bca_dict[bk]["max_slice_idx"],
                            },
                        },
                    },
                    *[
                        {
                            "code": {
                                "coding": [
                                    {
                                        "system": "https://uk-essen.de/fhir/ValueSet/boa/tissues",
                                        "code": tv,
                                        "display": tk,
                                    },
                                ]
                            },
                            "valueQuantity": {
                                "value": f"{bca_dict[bk][measurements][tk]['sum']:.2f}",
                                "unit": "ml",
                            },
                        }
                        for tk, tv in tissue_coding_dict.items()
                    ],
                ],
            }
        }
        for bk, bv in bca_coding_dict.items()
        if bk in bca_dict
    ]


# BOABodyStructureVolumeObservation
def get_bsv_observation(
    total_dict: dict[str, Any],
    dicom_dict: dict[str, Any],
) -> dict[str, Any]:
    total_coding_dict = mapping_dict["total"]
    total_dict = name_mapping(list(total_coding_dict.keys()), total_dict)

    return {
        "Observation": {
            "id": generate_hash(32),
            "status": "preliminary",
            "subject": {"reference": f"Patient/{dicom_dict['PatientID']}"},
            "effectiveDateTime": dicom_dict["Effective"],
            "derivedFrom": dicom_dict["ImageID"],
            "component": [
                {
                    "code": {
                        "coding": [
                            {
                                "system": "https://uk-essen.de/fhir/ValueSet/boa/body-structure",
                                "code": total_coding_dict[k],
                                "display": k,
                            },
                        ]
                    },
                    "value": {
                        "value": f"{v['volume_ml']:.2f}" if v["present"] else 0.0,
                        "unit": "ml",
                    },
                }
                for k, v in total_dict.items()
            ],
        }
    }


def name_mapping(keys: list[str], total_dict: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    split_mapping = {
        "vertebra": "vertebrae",
    }
    total_mapping = {
        "heart_myocardium": "myocardium",
    }
    total_dict = {total_mapping.get(k, k): v for k, v in total_dict.items()}

    for k in keys:
        tag = total_mapping.get(k, k)
        split_name = [
            split_mapping.get(n, n)
            for n in tag.split("-")
            if n not in {"left", "right"}
        ]
        key = None
        prefix = None

        if "left" in tag:
            prefix = "left"
        elif "right" in tag:
            prefix = "right"

        if prefix:
            for i in range(len(split_name)):
                tmp_key = "_".join([*split_name[:i], prefix, *split_name[i:]])
                if tmp_key in total_dict:
                    key = tmp_key
                    break
            if not key:
                key = "_".join([*split_name, prefix])
        else:
            key = "_".join(split_name)
        if key not in total_dict:
            continue
        result[tag] = total_dict[key]
    return result


def dicom_offset_to_tzinfo(offset_str: str | None) -> tzinfo:
    if offset_str and len(offset_str) == 5 and offset_str[0] in {"+", "-"}:
        try:
            sign = 1 if offset_str[0] == "+" else -1
            hours = int(offset_str[1:3])
            minutes = int(offset_str[3:5])
            total_minutes = sign * (hours * 60 + minutes)
            return pytz.FixedOffset(total_minutes)
        except ValueError:
            pass
    # Default to Berlin timezone
    return pytz.timezone("Europe/Berlin")


def dicom_dt_to_fhir_dt(
    dicom_date: str | None,
    dicom_time: str | None = None,
    timezone_offset_str: str | None = None,
) -> str:
    if not dicom_date:
        return "TODO"

    year = int(dicom_date[0:4])
    month = int(dicom_date[4:6])
    day = int(dicom_date[6:8])

    if dicom_time:
        time_part, *frac = dicom_time.split(".")
        hour = int(time_part[0:2]) if len(time_part) >= 2 else 0
        minute = int(time_part[2:4]) if len(time_part) >= 4 else 0
        second = int(time_part[4:6]) if len(time_part) >= 6 else 0
        # Adjust the fraction to microseconds (up to 6 digits)
        microsecond = int(float(f"0.{frac[0]}") * 1e6) if frac else 0
    else:
        hour = minute = second = microsecond = 0

    naive_dt = datetime(year, month, day, hour, minute, second, microsecond)
    tz = dicom_offset_to_tzinfo(timezone_offset_str)

    if isinstance(tz, pytz.BaseTzInfo):
        # `pytz` zone: use its safer `localize`
        localized_dt = tz.localize(naive_dt)
    else:
        # generic `tzinfo`: just attach it
        localized_dt = naive_dt.replace(tzinfo=tz)

    return localized_dt.isoformat()
