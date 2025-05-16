# BOA-Guard

A simple and easy to use python package which enables the transformation
of BOA results into the corresponding FHIR profiles

---

## Installation

```bash
git clone git@github.com:UMEssen/BOA-Guard.git
cd BOA-Guard
pip install -e .
```

*Requires **Python ≥ 3.10**.*

---

## Quick start

```bash
# generate FHIR bundles from a BOA folder
boa-guard bundles -f FHIR_FOLDER -b BOA_FOLDER

# turn bundles into a single FHIR Transaction
boa-guard tx -f FHIR_FOLDER

# POST the Transaction to a FHIR server
boa-guard push -f FHIR_FOLDER
```

| Command   | Purpose                                        |
| --------- | ---------------------------------------------- |
| `bundles` | Convert BOA JSON output into a FHIR Bundle     |
| `tx`      | Merge FHIR Bundle into a Transaction Bundle    |
| `push`    | Upload (POST) the Transaction to a FHIR server |
