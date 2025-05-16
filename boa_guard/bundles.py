import hashlib
import json
import logging
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

import pydicom
import pytz
from pytz import BaseTzInfo

logger = logging.getLogger("boa-guard")


def main(fhir_folder: Path, boa_folder: Path) -> None:
    json_output = fhir_folder / "fhir-bundles.json"
    result_dict: list[dict[str, Any]] = []
    for folder in boa_folder.rglob("*.xlsx"):
        try:
            result_dict.extend(create_bundles(folder.parent, fhir_folder))
        except (FileNotFoundError, NotADirectoryError) as e:
            logger.warning(f"{type(e).__name__}: {e}")

    fhir_folder.mkdir(exist_ok=True)
    with json_output.open("w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2)
    logger.info(f"Successfully created FHIR bundles in '{fhir_folder}'")


def create_bundles(folder: Path, output_dir: Path) -> list[dict[str, Any]]:
    json_bca = folder / "bca-measurements.json"
    json_total = folder / "total-measurements.json"
    dicom_path = folder / "dicoms"
    bca_dict: dict[str, Any] = {}
    total_dict: dict[str, Any] = {}
    dicom_dict: dict[str, Any] = {}

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
        bca_dict = json.load(f)
    bca_dict = bca_dict["aggregated"]

    with json_total.open(encoding="utf-8") as f:
        total_dict = json.load(f)
        total_dict = total_dict["segmentations"]["total"]

    dicom_dict = get_dicom_tags(dicom_path)

    return to_fhir_bundles(bca_dict, total_dict, dicom_dict)


def to_fhir_bundles(
    bca_dict: dict[str, Any], total_dict: dict[str, Any], dicom_dict: dict[str, str]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    result.append(get_imaging_study(dicom_dict))
    result.extend(get_bca_observation(bca_dict, dicom_dict, False))
    result.extend(get_bca_observation(bca_dict, dicom_dict, True))
    result.append(get_bsv_observation(total_dict, dicom_dict))

    return result


def get_dicom_tags(dicom_path: Path) -> dict[str, Any]:
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

    return {k if k is not None else "TODO": v for k, v in result.items()}


# BOAImagingStudy
def get_imaging_study(dicom_dict: dict[str, str]) -> dict[str, Any]:
    result_dict = {
        "ImagingStudy": {
            "identifier": {
                "system": "urn:dicom:uid",
                "value": f"urn:oid:{dicom_dict['StudyInstanceUID']}",
            },
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
    return result_dict


# BOABodyCompositionAnalysisObservation
def get_bca_observation(
    bca_dict: dict[str, Any], dicom_dict: dict[str, Any], without_extremeties: bool
) -> list[dict[str, Any]]:
    code = "volume-filtered" if without_extremeties else "volume-unfiltered"
    measurements = (
        "measurements_no_extremities" if without_extremeties else "measurements"
    )

    bca_coding_dict = {
        "abdominal_cavity": {
            "name": "Abdominal Cavity",
            "body_site": "361473009",
        },
        "thoracic_cavity": {
            "name": "Thoracic Cavity",
            "body_site": "43799004",
        },
        "mediastinum": {
            "name": "Mediastinum",
            "body_site": "72410000",
        },
        "pericardium": {
            "name": "Pericardium",
            "body_site": "76848001",
        },
    }

    tissue_coding_dict = {
        "bone": "3138006",
        "muscle": "91727004",
        "tat": "tat",
        "imat": "imat",
        "sat": "sat",
        "vat": "RID50365",
        "pat": "pat",
        "eat": "eat",
    }

    return [
        {
            "Observation": {
                "status.value": "preliminary",
                "code.coding": {
                    "system": "https://uk-essen.de/fhir/CodeSystem/boa/measurements",
                    "code": code,
                },
                "subject": dicom_dict["PatientID"],
                "effectiveDateTime": dicom_dict["Effective"],
                "bodySite.coding": {
                    "system": "https://uk-essen.de/fhir/ValueSet/boa/body-site",
                    "code": bv["body_site"],
                },
                "derivedFrom": dicom_dict["ImageID"],
                "component": [
                    {
                        "sliceRange": {
                            "code.coding": {
                                "system": "https://uk-essen.de/fhir/CodeSystem/boa/slice-range",
                                "code": "axial-slice-range",
                                "display": f"{bca_dict[bk]['min_slice_idx']} - {bca_dict[bk]['max_slice_idx']}",
                            },
                            "value": {
                                "low.value": bca_dict[bk]["min_slice_idx"],
                                "high.value": bca_dict[bk]["max_slice_idx"],
                            },
                        }
                    },
                    *[
                        {
                            tk: {
                                "code.coding": {
                                    "system": "https://uk-essen.de/fhir/ValueSet/boa/tissues",
                                    "code": tv,
                                },
                                "value": {
                                    "value": f"{bca_dict[bk][measurements][tk]['sum']:.2f}",
                                    "unit": "ml",
                                },
                            }
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
    total_dict: dict[str, Any], dicom_dict: dict[str, Any]
) -> dict[str, Any]:
    # TODO put in json file
    total_coding_dict = {
        "spleen": "78961009",
        "right-kidney": "9846003",
        "left-kidney": "18639004",
        "gallbladder": "28231008",
        "liver": "10200004",
        "stomach": "69695003",
        "aorta": "15825003",
        "inferior-vena-cava": "64131007",
        "portal-vein-and-splenic-vein": "110765007",
        "pancreas": "15776009",
        "right-adrenal-gland": "29392005",
        "left-adrenal-gland": "12003004",
        "lung-left-upper-lobe": "44714003",
        "lung-left-lower-lobe": "41224006",
        "lung-right-upper-lobe": "42400003",
        "lung-right-middle-lobe": "72481006",
        "lung-right-lower-lobe": "266005",
        "vertebra-L5": "49668003",
        "vertebra-L4": "11994002",
        "vertebra-L3": "36470004",
        "vertebra-L2": "14293000",
        "vertebra-L1": "66794005",
        "vertebra-T12": "23215003",
        "vertebra-T11": "12989004",
        "vertebra-T10": "7610001",
        "vertebra-T9": "82687006",
        "vertebra-T8": "11068009",
        "vertebra-T7": "62487009",
        "vertebra-T6": "45296009",
        "vertebra-T5": "56401006",
        "vertebra-T4": "73071006",
        "vertebra-T3": "1626008",
        "vertebra-T2": "53733008",
        "vertebra-T1": "64864005",
        "vertebra-C7": "87391001",
        "vertebra-C6": "36054005",
        "vertebra-C5": "36978003",
        "vertebra-C4": "5329002",
        "vertebra-C3": "113205007",
        "vertebra-C2": "39976000",
        "vertebra-C1": "14806007",
        "esophagus": "32849002",
        "trachea": "44567001",
        "myocardium": "74281007",
        "heart-left-atrium": "82471001",
        "heart-left-ventricle": "87878005",
        "heart-right-atrium": "73829009",
        "heart-right-ventricle": "53085002",
        "pulmonary-artery": "81040000",
        "brain": "12738006",
        "iliac-artery-left": "721077009",
        "iliac-artery-right": "721035009",
        "iliac-vena-left": "764118005",
        "iliac-vena-right": "764119002",
        "small-bowel": "30315005",
        "duodenum": "38848004",
        "colon": "71854001",
        "rib-left-1": "rib-left-1",
        "rib-left-2": "rib-left-2",
        "rib-left-3": "rib-left-3",
        "rib-left-4": "rib-left-4",
        "rib-left-5": "rib-left-5",
        "rib-left-6": "rib-left-6",
        "rib-left-7": "rib-left-7",
        "rib-left-8": "rib-left-8",
        "rib-left-9": "rib-left-9",
        "rib-left-10": "rib-left-10",
        "rib-left-11": "rib-left-11",
        "rib-left-12": "rib-left-12",
        "rib-right-1": "rib-right-1",
        "rib-right-2": "rib-right-2",
        "rib-right-3": "rib-right-3",
        "rib-right-4": "rib-right-4",
        "rib-right-5": "rib-right-5",
        "rib-right-6": "rib-right-6",
        "rib-right-7": "rib-right-7",
        "rib-right-8": "rib-right-8",
        "rib-right-9": "rib-right-9",
        "rib-right-10": "rib-right-10",
        "rib-right-11": "rib-right-11",
        "rib-right-12": "rib-right-12",
        "humerus-left": "719460003",
        "humerus-right": "719461004",
        "scapula-left": "719627005",
        "scapula-right": "719628000",
        "clavicula-left": "720617006",
        "clavicula-right": "720616002",
        "femur-left": "722738000",
        "femur-right": "722739008",
        "hip-left": "RID29356",
        "hip-right": "RID29355",
        "sacrum": "699698002",
        "face": "89545001",
        "gluteus-maximus-left": "gluteus-maximus-left",
        "gluteus-maximus-right": "gluteus-maximus-right",
        "gluteus-medius-left": "1236872009",
        "gluteus-medius-right": "1236873004",
        "gluteus-minimus-left": "gluteus-minimus-left",
        "gluteus-minimus-right": "gluteus-minimus-right",
        "autochthon-left": "autochthon-left",
        "autochthon-right": "autochthon-right",
        "iliopsoas-left": "RID30908",
        "iliopsoas-right": "RID30907",
        "urinary-bladder": "89837001",
    }
    total_dict = name_mapping(list(total_coding_dict.keys()), total_dict)

    return {
        "Observation": {
            "status.value": "preliminary",
            "subject": dicom_dict["PatientID"],
            "effective": dicom_dict["Effective"],
            "derivedFrom": dicom_dict["ImageID"],
            "component": [
                {
                    k: {
                        "code.coding": {
                            "system": "https://uk-essen.de/fhir/ValueSet/boa/body-structure",
                            "code": total_coding_dict[k],
                        },
                        "value": {
                            "value": f"{v['volume_ml']:.2f}" if v["present"] else 0.0,
                            "unit": "ml",
                        },
                    }
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

    if isinstance(tz, BaseTzInfo):
        # `pytz` zone: use its safer `localize`
        localized_dt = tz.localize(naive_dt)
    else:
        # generic `tzinfo`: just attach it
        localized_dt = naive_dt.replace(tzinfo=tz)

    return localized_dt.isoformat()
