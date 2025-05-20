# BOA-Guard

A simple and easy to use python package which enables the transformation
of BOA results into the corresponding FHIR profiles.

---

## Installation

```bash
git clone git@github.com:UMEssen/BOA-Guard.git
cd BOA-Guard
pip install -e .
```

*Requires **Python ≥ 3.10***

---

## Configuration

BOA-Guard needs three parameters to authenticate against your FHIR server.
Create a `.env` with key value pairs like in this [sample](.env_sample):

```txt
FHIR_URL=http://localhost:3000/fhir
FHIR_USER=TODO
FHIR_PWD=TODO
```

Alternatively, you can export the variables directly in your shell:

```bash
export FHIR_URL=http://localhost:3000/fhir
export FHIR_USER=TODO
export FHIR_PWD=TODO
```

---

## Quick start

```bash
# Generate FHIR bundles from a BOA folder
boa-guard bundles -f FHIR_FOLDER -b BOA_FOLDER

# Turn bundles into a single FHIR Transaction
boa-guard tx -f FHIR_FOLDER

# POST the Transaction to a FHIR server
boa-guard push -f FHIR_FOLDER
```

| Command   | Purpose                                        |
| --------- | ---------------------------------------------- |
| `bundles` | Convert BOA JSON output into a FHIR Bundle     |
| `tx`      | Convert FHIR Bundle into a Transaction Bundle  |
| `push`    | Upload (POST) the Transaction to a FHIR server |
