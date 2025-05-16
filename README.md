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
They are read from environment variables, so the easiest way is to place a
.env file next to where you run the commands like [this](.env_sample).

```txt
FHIR_URL=https://fhir.example.org/fhir
FHIR_USER=Username
FHIR_PWD=SecretPassword
```

An alternative way is to export the environment variables so no .env file is needed.

```bash
export FHIR_URL="https://fhir.example.org/fhir"
export FHIR_USER="myUsername"
export FHIR_PWD="superSecretPassword"
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
