# Runbook: per-agent runtime service rollout & SPIFFE agent binding (ADR-0014 B5 / ADR-0016 S3)

**Goal.** Split the gateway from the agent runtime so that:

1.  `cymbal-pooled-gateway` is the **only** identity holding
    `roles/cloudkms.signerVerifier` on `ws2-context-signing`.
1.  Each catalog agent runs in its own Cloud Run service (`cymbal-agent-shared`
    for `cymbal_shared_diagnostic_agent`, and `cymbal-agent-finvault-alpha` for
    `finvault_regulatory_escalation_agent`) deployed with **Cloud Run Agent
    Identity**
    (`--identity-type=agent-identity --functional-type=agent --identity-certificate`).
1.  Each agent runtime verifies context tokens with public keys only
    (`roles/cloudkms.publicKeyViewer`), holds **zero**
    `roles/cloudkms.signerVerifier` and **zero**
    `roles/iam.serviceAccountTokenCreator` on tenant SAs (`ct-*`), and calls
    `cymbal-credential-broker` using its workload SPIFFE identity
    (`principal://agents.global.org-100000000001.system.id.goog/...`).
1.  Source builds run as the dedicated, least-privilege `cymbal-build-sa`
    instead of the default Compute Engine service account (drift finding S4).

**Staged.** Every stage can be verified and rolled back independently while
keeping gateway traffic working. Run the stages in order; stop at the first
failed verification and roll back that stage only.

> Terraform codifies these resources in
> [../../terraform/modules/agent_runtime/main.tf](../../terraform/modules/agent_runtime/main.tf)
> (`var.enable_agent_runtimes`) and
> [../../terraform/modules/platform_core/build_sa.tf](../../terraform/modules/platform_core/build_sa.tf)
> (`var.enable_build_sa`). Because `--functional-type=agent` and
> `--identity-type=agent-identity` are immutable creation-time flags exposed
> only on the `gcloud beta` track (not yet modeled in `hashicorp/google-beta`
> 6.50), Stage 1 creates the two Cloud Run services via `gcloud beta run deploy`
> and immediately imports them into Terraform state before `terraform apply`
> manages their env vars, scaling, and least-privilege IAM bindings.

---

## Variables

```bash
PROJECT=cymbal-multitenancy-example
PROJECT_NUMBER=123456789012
ORG_ID=100000000001
REGION=us-central1
GATEWAY=cymbal-pooled-gateway
BROKER=cymbal-credential-broker
GATEWAY_SA=cymbal-pooled-runtime-sa@${PROJECT}.iam.gserviceaccount.com
BROKER_SA=cymbal-broker-sa@${PROJECT}.iam.gserviceaccount.com
BUILD_SA=cymbal-build-sa@${PROJECT}.iam.gserviceaccount.com
BROKER_URL=https://${BROKER}-${PROJECT_NUMBER}.${REGION}.run.app
CONTEXT_KEY_VERSION=projects/${PROJECT}/locations/${REGION}/keyRings/cymbal-platform-kr/cryptoKeys/ws2-context-signing/cryptoKeyVersions/1

SHARED_SVC=cymbal-agent-shared
SHARED_AGENT_ID=cymbal_shared_diagnostic_agent
SHARED_URL=https://${SHARED_SVC}-${PROJECT_NUMBER}.${REGION}.run.app
SHARED_PRINCIPAL="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/run/projects/${PROJECT_NUMBER}/locations/${REGION}/services/${SHARED_SVC}"

FINVAULT_SVC=cymbal-agent-finvault-alpha
FINVAULT_AGENT_ID=finvault_regulatory_escalation_agent
FINVAULT_URL=https://${FINVAULT_SVC}-${PROJECT_NUMBER}.${REGION}.run.app
FINVAULT_PRINCIPAL="principal://agents.global.org-${ORG_ID}.system.id.goog/resources/run/projects/${PROJECT_NUMBER}/locations/${REGION}/services/${FINVAULT_SVC}"
```

---

## Stage 0: provision `cymbal-build-sa` and build the B5 container image

1.  Enable `enable_build_sa = true` in `terraform/sandbox.tfvars` and apply the
    dedicated build SA (`cymbal-build-sa`) and its four minimal bindings
    (`roles/logging.logWriter` on project, `roles/artifactregistry.writer` on
    `cloud-run-source-deploy`, `roles/storage.objectViewer` +
    `roles/storage.objectCreator` on `run-sources-${PROJECT}-${REGION}`):

    ```bash
    CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
      terraform -chdir=terraform apply -var-file=sandbox.tfvars -var="enable_build_sa=true"
    ```

1.  Deploy the gateway image (which now includes `runtime_service/`) using
    `--build-service-account`, with `AGENT_RUNTIME_URLS` still unset so the
    gateway continues executing turns in-process:

    ```bash
    gcloud run deploy "$GATEWAY" --source=. --region="$REGION" --project="$PROJECT" --quiet \
      --build-service-account="projects/${PROJECT}/serviceAccounts/${BUILD_SA}"
    IMAGE=$(gcloud run services describe "$GATEWAY" --region="$REGION" --project="$PROJECT" \
      --format='value(spec.template.spec.containers[0].image)')
    echo "IMAGE=$IMAGE"
    ```

**Verify:**

- Gateway `/api/v1/health` returns `200`.
- Build logs show `serviceAccountEmail: cymbal-build-sa@...`.

**Rollback:**

```bash
gcloud run services update-traffic "$GATEWAY" --to-revisions=<previous>=100 \
  --region="$REGION" --project="$PROJECT"
```

---

## Stage 1: bootstrap `cymbal-agent-shared` & `cymbal-agent-finvault-alpha` with Agent Identity and import into Terraform

1.  Create both Cloud Run services on the `gcloud beta` track with
    `--identity-type=agent-identity --functional-type=agent --identity-certificate`
    and `--no-allow-unauthenticated`:

    ```bash
    gcloud beta run deploy "$SHARED_SVC" \
      --image="$IMAGE" --region="$REGION" --project="$PROJECT" --quiet \
      --identity-type=agent-identity --functional-type=agent --identity-certificate \
      --no-allow-unauthenticated --ingress=all --max-instances=1 --cpu-boost \
      --command=uvicorn \
      --args=runtime_service.main:create_app,--factory,--host,0.0.0.0,--port,8080 \
      --set-env-vars="CYMBAL_ENV=sandbox,CYMBAL_LIVE_GCP=0,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_REGION=${REGION},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=true,RUNTIME_AGENT_ID=${SHARED_AGENT_ID},RUNTIME_ALLOWED_CALLERS=${GATEWAY_SA},RUNTIME_EXPECTED_AUDIENCE=${SHARED_URL},CREDENTIAL_BROKER_URL=${BROKER_URL},CONTEXT_SIGNING_KMS_KEY=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_KMS_KEY_VERSION=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_REQUIRE_KMS=1,CONTEXT_TOKEN_REQUIRE_AGENT_ID=0"

    gcloud beta run deploy "$FINVAULT_SVC" \
      --image="$IMAGE" --region="$REGION" --project="$PROJECT" --quiet \
      --identity-type=agent-identity --functional-type=agent --identity-certificate \
      --no-allow-unauthenticated --ingress=all --max-instances=1 --cpu-boost \
      --command=uvicorn \
      --args=runtime_service.main:create_app,--factory,--host,0.0.0.0,--port,8080 \
      --set-env-vars="CYMBAL_ENV=sandbox,CYMBAL_LIVE_GCP=0,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_REGION=${REGION},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=true,RUNTIME_AGENT_ID=${FINVAULT_AGENT_ID},RUNTIME_ALLOWED_CALLERS=${GATEWAY_SA},RUNTIME_EXPECTED_AUDIENCE=${FINVAULT_URL},CREDENTIAL_BROKER_URL=${BROKER_URL},CONTEXT_SIGNING_KMS_KEY=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_KMS_KEY_VERSION=${CONTEXT_KEY_VERSION},CONTEXT_TOKEN_REQUIRE_KMS=1,CONTEXT_TOKEN_REQUIRE_AGENT_ID=0"
    ```

1.  Import both Cloud Run services into Terraform state and apply
    `enable_agent_runtimes = true` so Terraform creates the least-privilege IAM
    bindings (`gateway_invokes_agent_runtime`, `agent_context_key_viewer`,
    `agent_invokes_broker`):

    ```bash
    CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
      terraform -chdir=terraform import -var-file=sandbox.tfvars -var="enable_agent_runtimes=true" \
      'module.agent_runtime["shared"].google_cloud_run_v2_service.agent_runtime' \
      "projects/${PROJECT}/locations/${REGION}/services/${SHARED_SVC}"

    CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
      terraform -chdir=terraform import -var-file=sandbox.tfvars -var="enable_agent_runtimes=true" \
      'module.agent_runtime["finvault-alpha"].google_cloud_run_v2_service.agent_runtime' \
      "projects/${PROJECT}/locations/${REGION}/services/${FINVAULT_SVC}"

    # Set enable_agent_runtimes = true and enable_build_sa = true in terraform/sandbox.tfvars, then apply:
    CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
      terraform -chdir=terraform apply -var-file=sandbox.tfvars \
      -var="enable_agent_runtimes=true" -var="enable_build_sa=true"
    ```

**Verify:**

```bash
# Unauthenticated requests to both agent runtime services must return 403 at Cloud Run IAM:
curl -s -o /dev/null -w '%{http_code}\n' "${SHARED_URL}/healthz"       # 403
curl -s -o /dev/null -w '%{http_code}\n' "${FINVAULT_URL}/healthz"     # 403

# Each agent runtime has exactly one run.invoker member: serviceAccount:${GATEWAY_SA}
gcloud run services get-iam-policy "$SHARED_SVC" --region="$REGION" --project="$PROJECT"
gcloud run services get-iam-policy "$FINVAULT_SVC" --region="$REGION" --project="$PROJECT"
```

**Rollback:**

```bash
CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
  terraform -chdir=terraform apply -var-file=sandbox.tfvars \
  -var="enable_agent_runtimes=false" -var="deletion_protection=false"
```

---

## Stage 2: add the agent principals to `BROKER_ALLOWED_CALLERS` (keeping runtime SA fallback)

Update `additional_broker_allowed_callers` in `terraform/sandbox.tfvars` (with
`broker_keep_runtime_caller = true` so the gateway's in-process fallback
continues to work):

```hcl
additional_broker_allowed_callers = [
  "principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-shared",
  "principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-finvault-alpha",
]
broker_keep_runtime_caller = true
```

Apply via Terraform:

```bash
CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
  terraform -chdir=terraform apply -var-file=sandbox.tfvars
```

**Verify:**

- Broker `/healthz` is healthy and live broker suite
  (`tests/breach_suite/test_live_credential_broker.py`) passes.

**Rollback:**

- Set `additional_broker_allowed_callers = []` in `terraform/sandbox.tfvars` and
  re-apply.

---

## Stage 3: route gateway turns to the dedicated agent runtime services (`AGENT_RUNTIME_URLS`)

Configure `AGENT_RUNTIME_URLS` on `cymbal-pooled-gateway` so Hop 3–5 executes
remotely on `cymbal-agent-shared` and `cymbal-agent-finvault-alpha`:

```bash
AGENT_URLS_JSON=$(printf '{"%s":"%s","%s":"%s"}' \
  "$SHARED_AGENT_ID" "$SHARED_URL" \
  "$FINVAULT_AGENT_ID" "$FINVAULT_URL")

gcloud run services update "$GATEWAY" --region="$REGION" --project="$PROJECT" \
  --update-env-vars="^@^AGENT_RUNTIME_URLS=${AGENT_URLS_JSON}"
```

**Verify:**

- Run the live gateway and broker suites; confirm turns appear in Cloud Logging
  for `cymbal-agent-shared` and `cymbal-agent-finvault-alpha`.
- Confirm RetailStream (`bob@retailstream.com`) attempting
  `finvault_regulatory_escalation_agent` is still refused at gateway admission
  (and would also be refused by `cymbal-agent-finvault-alpha` with `403`).

**Rollback:**

```bash
gcloud run services update "$GATEWAY" --region="$REGION" --project="$PROJECT" \
  --remove-env-vars=AGENT_RUNTIME_URLS
```

---

## Stage 4: flip ADR-0016 agent-binding flags in strict safe order

Flip the three enforcement flags **one at a time** so in-flight tokens always
carry `agent_id` before downstream verifiers require it:

1.  **Step 4a — Gateway binds `agent_id` into signed context & broker tokens
    (`CONTEXT_TOKEN_BIND_AGENT_ID=1`):**

    ```bash
    gcloud run services update "$GATEWAY" --region="$REGION" --project="$PROJECT" \
      --update-env-vars=CONTEXT_TOKEN_BIND_AGENT_ID=1
    ```

    _Verify:_ Alice and Bob turns succeed; decoded context tokens contain
    `agent_id`. _Rollback:_ `--update-env-vars=CONTEXT_TOKEN_BIND_AGENT_ID=0`

1.  **Step 4b — Broker enforces caller SPIFFE principal == token's `agent_id`
    (`BROKER_REQUIRE_AGENT_BINDING=1`):** Ensure `agent_identity.bindings` in
    `config/environments/sandbox.yaml` maps `cymbal_shared_diagnostic_agent` to
    `$SHARED_PRINCIPAL` and `finvault_regulatory_escalation_agent` to
    `$FINVAULT_PRINCIPAL`, deploy the updated config image, and enable
    `BROKER_REQUIRE_AGENT_BINDING=1`:

    ```bash
    gcloud run services update "$BROKER" --region="$REGION" --project="$PROJECT" \
      --update-env-vars=BROKER_REQUIRE_AGENT_BINDING=1
    ```

    _Verify:_ Live broker and blast-radius suites pass. _Rollback:_
    `--update-env-vars=BROKER_REQUIRE_AGENT_BINDING=0`

1.  **Step 4c — All verifiers require `agent_id`
    (`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`):** Update
    `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` on both agent runtime services via
    `gcloud beta run services update` (because `hashicorp/google-beta` 6.50
    omits `spec.functional_type` on `UpdateService`), and set
    `require_agent_binding = true` in `terraform/sandbox.tfvars` so the gateway
    and broker also enforce `CONTEXT_TOKEN_REQUIRE_AGENT_ID=1`:

    ```bash
    gcloud beta run services update "$SHARED_SVC" --region="$REGION" --project="$PROJECT" \
      --update-env-vars=CONTEXT_TOKEN_REQUIRE_AGENT_ID=1
    gcloud beta run services update "$FINVAULT_SVC" --region="$REGION" --project="$PROJECT" \
      --update-env-vars=CONTEXT_TOKEN_REQUIRE_AGENT_ID=1
    CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
      terraform -chdir=terraform apply -var-file=sandbox.tfvars -var="require_agent_binding=true"
    gcloud run services update "$BROKER" --region="$REGION" --project="$PROJECT" \
      --update-env-vars=CONTEXT_TOKEN_REQUIRE_AGENT_ID=1
    ```

    _Verify:_ Any context token or broker token missing `agent_id` is rejected
    with `401 E_CONTEXT_TOKEN_AGENT_ID_MISSING`. _Rollback:_ Set
    `CONTEXT_TOKEN_REQUIRE_AGENT_ID=0` on `$SHARED_SVC`, `$FINVAULT_SVC`, and
    `$BROKER`, set `require_agent_binding = false` in
    `terraform/sandbox.tfvars`, and re-apply.

---

## Stage 5: negative live Layer-3 verification tests

Run the live adversarial checks confirming all three authorization layers
(`Tenant ∩ User ∩ Agent`):

1.  **Cross-agent token substitution:** `cymbal-agent-finvault-alpha`'s SPIFFE
    identity calling the broker with a broker token bound to
    `cymbal_shared_diagnostic_agent` (or vice versa) returns **403
    `E_AGENT_PRINCIPAL_MISMATCH`**.
1.  **Gateway direct broker call:** `cymbal-pooled-runtime-sa` calling
    `cymbal-credential-broker` directly under `BROKER_REQUIRE_AGENT_BINDING=1`
    returns **403**.
1.  **Direct agent runtime invocation:** any caller other than
    `cymbal-pooled-runtime-sa` calling `cymbal-agent-shared` or
    `cymbal-agent-finvault-alpha` returns **403**.
1.  **KMS signing audit:** only `cymbal-pooled-runtime-sa` holds
    `roles/cloudkms.signerVerifier` on `ws2-context-signing`; both agent
    principals get **403** on `asymmetricSign`.

---

## Stage 6: remove the pooled runtime SA fallback from the broker

Once Stages 3–5 are green, codify the full B5/ADR-0016 target state in
`terraform/sandbox.tfvars` so `terraform apply` preserves `AGENT_RUNTIME_URLS`,
`CONTEXT_TOKEN_BIND_AGENT_ID=1`, `BROKER_REQUIRE_AGENT_BINDING=1`, and
`CONTEXT_TOKEN_REQUIRE_AGENT_ID=1` while removing `cymbal-pooled-runtime-sa`
from the broker's `BROKER_ALLOWED_CALLERS` and `roles/run.invoker`:

```hcl
# Final B5 / ADR-0016 Layer 3 + drift S4 settings in terraform/sandbox.tfvars:
enable_agent_runtimes      = true
enable_build_sa            = true
bind_agent_id              = true
require_agent_binding      = true
broker_keep_runtime_caller = false
additional_broker_allowed_callers = [
  "principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-shared",
  "principal://agents.global.org-100000000001.system.id.goog/resources/run/projects/123456789012/locations/us-central1/services/cymbal-agent-finvault-alpha",
]
agent_runtime_urls_json = "{\"cymbal_shared_diagnostic_agent\":\"https://cymbal-agent-shared-123456789012.us-central1.run.app\",\"finvault_regulatory_escalation_agent\":\"https://cymbal-agent-finvault-alpha-123456789012.us-central1.run.app\"}"
```

Apply and verify convergence:

```bash
CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
  terraform -chdir=terraform apply -var-file=sandbox.tfvars
CLOUDSDK_METRICS_ENVIRONMENT=datacloud.ai-agent \
  terraform -chdir=terraform plan -var-file=sandbox.tfvars
# Expected: No changes. Your infrastructure matches the configuration.
```

**Rollback:** set `broker_keep_runtime_caller = true` and re-apply.

---

## Ongoing operations: zero public Cloud Run invokers check

Run after every IAM or Terraform change (and on a daily schedule) to verify that
**none** of the four Cloud Run services (`cymbal-pooled-gateway`,
`cymbal-credential-broker`, `cymbal-agent-shared`,
`cymbal-agent-finvault-alpha`) grants `roles/run.invoker` to `allUsers` or
`allAuthenticatedUsers`:

```bash
for SVC in "$GATEWAY" "$BROKER" "$SHARED_SVC" "$FINVAULT_SVC"; do
  echo "== Checking $SVC"
  gcloud run services get-iam-policy "$SVC" --region="$REGION" --project="$PROJECT" \
    --format=json | grep -E '"allUsers"|"allAuthenticatedUsers"' \
    && { echo "ALERT: public invoker on $SVC"; exit 1; }
done
echo "OK: zero public Cloud Run invokers across gateway, broker, and agent runtimes."
```
