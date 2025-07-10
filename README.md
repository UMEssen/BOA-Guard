# BOA-Guard

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)

A simple and easy to use python package which enables the transformation
of BOA results into the corresponding FHIR profiles.

---

## Installation

```bash
git clone https://github.com/UMEssen/BOA-Guard.git
cd BOA-Guard
pip install -e .
```

---

## Configuration

BOA-Guard needs three parameters to authenticate against your FHIR server.
Create a `.env` File with key value pairs like in this [sample](.env_sample):

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
# 1. Generate FHIR bundles from a BOA folder
boa-guard bundles -f FHIR_FOLDER -b BOA_FOLDER

# 2. Turn bundles into a single FHIR Transaction
boa-guard tx -f FHIR_FOLDER

# 3. POST the Transaction to a FHIR server
boa-guard push -f FHIR_FOLDER
```

| Command   | Purpose                                        |
| --------- | ---------------------------------------------- |
| `bundles` | Convert BOA JSON output into a FHIR Bundle     |
| `tx`      | Convert FHIR Bundle into a Transaction Bundle  |
| `push`    | Upload (POST) the Transaction to a FHIR server |

---

## Usage in Python

You can also use BOA-Guard as a Python library:

```py
from boa_guard.bundles import main as bundles
from boa_guard.tx import main as tx
from boa_guard.push import main as push

# 1. Generate FHIR bundles from a BOA folder
bundles("/path/to/fhir_folder", "/path/to/boa_folder")

# 2. Turn bundles into a single FHIR Transaction
tx("/path/to/fhir_folder")

# 3. POST the Transaction to a FHIR server
push("/path/to/fhir_folder")
```
