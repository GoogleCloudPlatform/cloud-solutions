# Environment sandbox pre-flight validation

Before executing any Python scripts or processing cluster manifests, you
**must** sequentially verify and initialize the local environment:

## Pre-requisite step 1: Virtual environment and pip enforcement

1.  Verify that `python3` (>=3.10) is available on the host workstation.
1.  Initialize or activate the localized `venv` specified in the frontmatter
    (`.agent/skills/ingress2gateway/scripts/.venv`).
1.  **Mandatory Pip Enforcement Logic:**
    - You **must** explicitly call the bootstrapping command:
      `python3 -m ensurepip --default-pip` directly against the environment to
      guarantee a pip binary exists. Do not assume or guess its status.
    - If `ensurepip` fails or is stripped from the underlying host's OS
      distribution, you are forbidden from sliding into a pip-less lifecycle.
      You must immediately halt and ask the user explicitly:
      `"Python pip is missing and ensurepip failed. Is it okay to download`
      `and run the official installation script (get-pip.py) from`
      `bootstrap.pypa.io? (yes/no)"`. Abort if the user declines; execute
      securely using curl/python if approved.
1.  Install dependencies using the virtual environment's pip binary with
    `pip install --require-hashes -r requirements.txt` to ensure reproducible,
    tamper-proof builds. **All Python execution must happen exclusively using
    this virtual environment binary invocation.**

## Pre-requisite step 2: Host tools, exception handling and interactive installation

1.  Check for the local presence of `gcloud` and `kubectl`.
1.  **Interactive Fallback Protocol:** If either tool is missing, **stop
    execution** and explicitly ask the user for permission to install them:
    - _Prompt Text:_ `"The required binaries (gcloud/kubectl) are missing. Is it
      okay to install the Google Cloud SDK and the gcloud kubectl component
      configured for GKE 1.30+ on your host workstation? (yes/no)"\*
1.  **Conditional Installation:**
    - If the user says **no**, abort execution immediately with a prerequisite
      failure message.
    - If the user says **yes**, programmatically download and configure the
      Google Cloud SDK. Use `gcloud components install kubectl` to install a
      version compatible with **GKE version 1.30 and above** (Kubernetes client
      version $\ge$ 1.30).
1.  Execute `gcloud auth list --filter=status:ACTIVE --format="value(account)"`
    to confirm active authentication status without printing secret bearer
    tokens to standard output or agent logs.

## Pre-requisite step 3: External binary access validation

1.  Make a lightweight HTTPS HEAD or GET request to
    `https://api.github.com/repos/kubernetes-sigs/ingress2gateway/releases`
    inside the Python venv.
1.  **Do not download or extract any binary assets. Do not generate any python
    script to download the binary.** Verify only that a `200 OK` status response
    is returned, proving that the runtime host has the required unrestricted
    outbound HTTPS access (port 443) to query and download release assets when
    needed.

## Pre-requisite step 4: Stop execution here

1.  **Mandatory Hold:** Do not proceed to any task execution, manifest
    discovery, or processing after completing the pre-requisite check steps
    above.
1.  Present a status summary of the verified environment to the console and
    explicitly **ask the user for approval to proceed to the next phase: Phase
    2: Context & Identity Resolution**.
