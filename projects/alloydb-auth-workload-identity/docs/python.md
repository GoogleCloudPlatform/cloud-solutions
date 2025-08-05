# Python SQLAlchemy Helper for Authenticating to AlloyDB using Workload Identity Federation for GKE

The application is using the GCP Service Account (through the Workload Identity
Federation for GKE).

## How it works

The SQLAlchemy has an event hook "do_connect" which will be called each time
that a new connection is made. The hook can be installed on "Engine" objects
created by the `create_engile` method of SQLAlchemy.

The Helper installs a hook wich generates `user` and `password` information for
making new PostgreSQL connection from the GKE Metadata server. The `user` comes
from the email attribute of the Service Account and the `password` comes from
the `access_token` of the Service Account.

## Installation

To install the helper, put the following into your `requirements.txt` or
`pyproject.toml` file.

```text
git+https://github.com/GoogleCloudPlatform/cloud-solutions.git#subdirectory=projects/alloydb-auth-workload-identity/src/python
```

## Usage

After creating the engine using `create_engine`, run `setup_gcp_auth_hook` to
register the hook to the engine.

For example:

```python3
import sqlalchemy
import sqlalchemy_gcp_sa_auth

# Your code.

engine = sqlalchemy.create_engine("postgresql+psycopg://<HOST>/<DATABASE>")
sqlalchemy_gcp_sa_auth.setup_gcp_auth_hook(engine)

# Your code.

```
