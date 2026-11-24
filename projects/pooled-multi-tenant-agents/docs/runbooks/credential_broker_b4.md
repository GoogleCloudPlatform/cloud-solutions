# Runbook: credential broker rollout (ADR-0014 B4)

**Goal.** Move `roles/iam.serviceAccountTokenCreator` on tenant service accounts
(`ct-*`) from the runtime SA (`cymbal-pooled-runtime-sa`) to a new broker SA
(`cymbal-broker-sa`). After this change, the runtime can get a tenant credential
only by asking the broker. It does that with a broker-audience context token
signed by the gateway and a Cloud Run IAM ID token.

**Staged.** Every stage can be verified and rolled back on its own, and requests
keep working throughout. Run the stages in order. Stop at the first failed
verification and roll back that stage only.

> Terraform mirrors these steps in
> `terraform/modules/platform_core/credential_broker.tf` and
> `terraform/modules/tenant` (variables `enable_credential_broker`,
> `credential_broker_url`, `runtime_keeps_token_creator`). The sandbox was
> adopted and applied with Terraform on 2026-11-06, so Terraform now owns these
> grants. The gcloud commands below record how the rollout was done; make new
> changes through Terraform.

## Variables

```bash
PROJECT=cymbal-multitenancy-example
REGION=us-central1
RUNTIME_SA=cymbal-pooled-runtime-sa@${PROJECT}.iam.gserviceaccount.com
BROKER_SA=cymbal-broker-sa@${PROJECT}.iam.gserviceaccount.com
GATEWAY=cymbal-pooled-gateway
BROKER=cymbal-credential-broker
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
# ONE string used for both the runtime's CREDENTIAL_BROKER_URL and the broker's
# BROKER_EXPECTED_AUDIENCE: the runtime requests its ID token for this audience and the broker
# requires exactly it (deterministic Cloud Run URL; no trailing slash).
BROKER_URL=https://${BROKER}-${PROJECT_NUMBER}.${REGION}.run.app
# Tenant service accounts (ct-<sha256(tenant_id)[:24]>), from the platform config:
TENANT_SAS=$(CYMBAL_ENV=sandbox uv run --no-sync python -c "
from agents.platform_config import load_platform_config
from agents.tenant_identity import tenant_service_account_email
c = load_platform_config('sandbox')
print(' '.join(tenant_service_account_email(t.tenant_id, c.gcp.project_id) for t in c.tenants))")
echo "$TENANT_SAS"
```

## Stage 0: deploy the B4 code to the gateway (no behaviour change)

With B4, live mode must choose a credential backend explicitly.
`CYMBAL_DIRECT_IMPERSONATION=1` keeps today's behaviour (the runtime
impersonates `ct-*` itself) until Stage 3. This stage also puts the image that
contains `broker_service/` in place.

```bash
gcloud run deploy $GATEWAY --source=. --region=$REGION --project=$PROJECT --quiet \
  --update-env-vars=CYMBAL_DIRECT_IMPERSONATION=1
IMAGE=$(gcloud run services describe $GATEWAY --region=$REGION --project=$PROJECT \
  --format='value(spec.template.spec.containers[0].image)')
echo "$IMAGE"
```

**Verify:** sign in, Alice → 200, Bob → 200, Test 0 → 401. No
`E_CREDENTIAL_BACKEND_UNCONFIGURED` in the gateway logs. **Rollback:**
`gcloud run services update-traffic $GATEWAY`
(`--to-revisions=<previous>=100 --region=$REGION --project=$PROJECT`)

## Stage 1: create the broker SA and grant it TokenCreator on every `ct-*`

```bash
gcloud iam service-accounts create cymbal-broker-sa --project=$PROJECT \
  --display-name="Cymbal credential broker (ADR-0014 B4)"
for T in $TENANT_SAS; do
  gcloud iam service-accounts add-iam-policy-binding "$T" --project=$PROJECT \
    --member="serviceAccount:$BROKER_SA" --role=roles/iam.serviceAccountTokenCreator
done
# Verify broker tokens with the context-signing public key (public key only):
gcloud kms keys add-iam-policy-binding ws2-context-signing --project=$PROJECT \
  --location=$REGION --keyring=cymbal-platform-kr \
  --member="serviceAccount:$BROKER_SA" --role=roles/cloudkms.publicKeyViewer
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$BROKER_SA" --role=roles/logging.logWriter --condition=None
```

**Verify:**

```bash
for T in $TENANT_SAS; do gcloud iam service-accounts get-iam-policy "$T" --project=$PROJECT \
  --format=json | grep -c "$BROKER_SA"; done          # 1 per tenant SA
RUN_LIVE_GCP_TESTS=1 uv run --no-sync pytest -q \
  tests/breach_suite/test_live_credential_broker.py -k "broker_sa_can_mint or cross_tenants"
```

**Rollback:**

```bash
for T in $TENANT_SAS; do
  gcloud iam service-accounts remove-iam-policy-binding "$T" --project=$PROJECT \
    --member="serviceAccount:$BROKER_SA" --role=roles/iam.serviceAccountTokenCreator
done
gcloud kms keys remove-iam-policy-binding ws2-context-signing --project=$PROJECT \
  --location=$REGION --keyring=cymbal-platform-kr \
  --member="serviceAccount:$BROKER_SA" --role=roles/cloudkms.publicKeyViewer
gcloud projects remove-iam-policy-binding $PROJECT \
  --member="serviceAccount:$BROKER_SA" --role=roles/logging.logWriter --condition=None
gcloud iam service-accounts delete $BROKER_SA --project=$PROJECT --quiet
```

## Stage 2: deploy the broker service (IAM-only; the runtime SA is the only invoker)

```bash
gcloud run deploy $BROKER --image="$IMAGE" --region=$REGION --project=$PROJECT \
  --service-account=$BROKER_SA --no-allow-unauthenticated --ingress=all \
  --max-instances=1 --cpu-boost \
  --command=uvicorn --args=broker_service.main:create_app,--factory,--host,0.0.0.0,--port,8080 \
  --set-env-vars=BROKER_ALLOWED_CALLERS=$RUNTIME_SA,BROKER_EXPECTED_AUDIENCE=$BROKER_URL,CYMBAL_ENV=sandbox,GOOGLE_CLOUD_PROJECT=$PROJECT
gcloud run services add-iam-policy-binding $BROKER --region=$REGION --project=$PROJECT \
  --member="serviceAccount:$RUNTIME_SA" --role=roles/run.invoker
```

**Verify:**

```bash
gcloud run services get-iam-policy $BROKER --region=$REGION --project=$PROJECT
#   -> exactly one run.invoker member: serviceAccount:$RUNTIME_SA (no allUsers / allAuthenticatedUsers)
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BROKER_URL/internal/v1/tenant-credential"  # 403
RUN_LIVE_GCP_TESTS=1 CREDENTIAL_BROKER_URL=$BROKER_URL uv run --no-sync pytest -q \
  tests/breach_suite/test_live_credential_broker.py -k broker_service
gcloud logging read "resource.labels.service_name=\"$BROKER\" severity>=ERROR" \
  --project=$PROJECT --limit=20 --freshness=10m                       # nothing unexpected
```

**Rollback:**
`gcloud run services delete $BROKER --region=$REGION --project=$PROJECT --quiet`

The broker refuses to start unless it runs on Cloud Run (`K_SERVICE`),
`BROKER_ALLOWED_CALLERS` is set and `BROKER_EXPECTED_AUDIENCE` is an https URL,
so a revision with missing settings never becomes ready.

## Stage 3: point the runtime at the broker

```bash
gcloud run services update $GATEWAY --region=$REGION --project=$PROJECT \
  --update-env-vars=CREDENTIAL_BROKER_URL=$BROKER_URL \
  --remove-env-vars=CYMBAL_DIRECT_IMPERSONATION
```

**Verify** (the runtime still holds TokenCreator, so a failure here is a pure
broker problem):

- Sign in; run Alice and Bob with live cloud on (live tenant checks: KMS, Secret
  Manager, GCS). Both should return 200, Test 0 should return 401, and
  cross-tenant checks should still return 403.
- Broker audit lines show the mints:

    ```bash
    gcloud logging read "resource.labels.service_name=\"$BROKER\" textPayload:\"tenant_credential_mint\"" \
      --project=$PROJECT --limit=10 --freshness=10m
    ```

- No `E_BROKER_*` or 5xx in gateway logs:

    ```bash
    gcloud logging read "resource.labels.service_name=\"$GATEWAY\" (textPayload:\"E_BROKER\" OR httpRequest.status>=500)" \
      --project=$PROJECT --limit=20 --freshness=10m
    ```

**Rollback:**

```bash
gcloud run services update $GATEWAY --region=$REGION --project=$PROJECT \
  --remove-env-vars=CREDENTIAL_BROKER_URL --update-env-vars=CYMBAL_DIRECT_IMPERSONATION=1
```

## Stage 4: remove the runtime SA's TokenCreator on every `ct-*`

Do this only after Stage 3 has been verified.

**Pre-check: list every member that can mint for each tenant SA.** After this
stage the only allowed holders of `roles/iam.serviceAccountTokenCreator` on a
`ct-*` are `$BROKER_SA` and named, time-boxed operators. Remove anything else;
the 2026-11-04 rollout found the unused legacy `cymbal-ingress-pep-sa` here.

```bash
for T in $TENANT_SAS; do
  echo "== $T"
  gcloud iam service-accounts get-iam-policy "$T" --project=$PROJECT --format=json \
    | python3 -c "import json,sys; p=json.load(sys.stdin); [print(m) for b in p.get('bindings',[]) if b['role']=='roles/iam.serviceAccountTokenCreator' for m in b['members']]"
done
# For each unexpected member M (e.g. serviceAccount:cymbal-ingress-pep-sa@...):
#   gcloud iam service-accounts remove-iam-policy-binding "$T" --project=$PROJECT \
#     --member="$M" --role=roles/iam.serviceAccountTokenCreator
```

```bash
for T in $TENANT_SAS; do
  gcloud iam service-accounts remove-iam-policy-binding "$T" --project=$PROJECT \
    --member="serviceAccount:$RUNTIME_SA" --role=roles/iam.serviceAccountTokenCreator
done
```

IAM changes can take a few minutes to propagate. Tokens the runtime minted
earlier expire within 5 minutes.

**Verify:** repeat the Stage 3 checks after about 10 minutes, then run Stage 5.
**Rollback** (restores the runtime's grant; to also mint directly again, run the
Stage 3 rollback):

```bash
for T in $TENANT_SAS; do
  gcloud iam service-accounts add-iam-policy-binding "$T" --project=$PROJECT \
    --member="serviceAccount:$RUNTIME_SA" --role=roles/iam.serviceAccountTokenCreator
done
```

## Stage 5: live 403 test

**Operator access (time-boxed).** The live tests impersonate the runtime and
broker SAs, so the operator running them needs
`roles/iam.serviceAccountTokenCreator` on `$RUNTIME_SA` and `$BROKER_SA`. Grant
it with an IAM condition that expires (the 2026-11-04 run used 24 hours) and
never as a standing grant:

```bash
EXPIRY=$(date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ)
for SA in $RUNTIME_SA $BROKER_SA; do
  gcloud iam service-accounts add-iam-policy-binding "$SA" --project=$PROJECT \
    --member="user:<operator-email>" --role=roles/iam.serviceAccountTokenCreator \
    --condition="expression=request.time < timestamp('$EXPIRY'),title=b4-live-tests-expiry"
done
```

```bash
RUN_LIVE_GCP_TESTS=1 B4_STAGE4_DONE=1 CREDENTIAL_BROKER_URL=$BROKER_URL \
  uv run --no-sync pytest -v tests/breach_suite/test_live_credential_broker.py
RUN_LIVE_GCP_TESTS=1 uv run --no-sync pytest -v tests/breach_suite/test_live_tenant_blast_radius.py
```

Expected results:

- the runtime SA's direct `generateAccessToken` on each `ct-*` returns **403**;
- the broker SA's returns **200**;
- broker-minted tenant tokens still get **403** on the other tenant's key, in
  both directions;
- the broker service refuses unauthenticated callers and non-runtime callers;
- a runtime call without a broker token gets **401** `E_BROKER_TOKEN_MISSING`.

The operator running these tests needs TokenCreator on
`cymbal-pooled-runtime-sa` and `cymbal-broker-sa` (for impersonation). That is
the operator's own grant, not the runtime's.

## Full rollback (reverse order)

Run the rollbacks in this order:

1.  Stage 4: re-add the runtime's TokenCreator.
1.  Stage 3: remove `CREDENTIAL_BROKER_URL` and set
    `CYMBAL_DIRECT_IMPERSONATION=1`.
1.  Stage 2: delete the broker service.
1.  Stage 1: remove the broker's grants and delete its SA.

The runtime then mints by direct impersonation again, exactly as before B4.

## Sandbox rollout record (2026-11-04)

| Stage | Result                                                                                                                                                                                                                                                                                                                          |
| :---- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0     | Gateway revision 00028 with the B4 code and `CYMBAL_DIRECT_IMPERSONATION=1` (no behaviour change intended).                                                                                                                                                                                                                     |
| 1     | `cymbal-broker-sa` created; TokenCreator on both `ct-*`; `publicKeyViewer` on `ws2-context-signing`; log writer.                                                                                                                                                                                                                |
| 2     | Broker `cymbal-credential-broker-00001-bkr` (us-central1), `--no-allow-unauthenticated`, run.invoker = runtime SA only, max 1 instance.                                                                                                                                                                                         |
| 3     | Gateway revision 00029 with `CREDENTIAL_BROKER_URL` (direct impersonation removed). Note: the hosted gateway runs without `CYMBAL_LIVE_GCP` (simulation mode), so it does not mint tenant credentials at request time and does not call the broker; the broker path is proven by the hermetic suite and the Stage 5 live tests. |
| 4     | Runtime SA's TokenCreator removed on both `ct-*`. The pre-check also found TokenCreator on both `ct-*` held by the unused legacy `cymbal-ingress-pep-sa`; removed the same day.                                                                                                                                                 |
| 5     | Live tests 13/13 passed (run by the operator against IAM and the broker service directly): 8 broker (`test_live_credential_broker.py`) + 5 blast radius (`test_live_tenant_blast_radius.py`). Operator access was a 24-hour conditional grant.                                                                                  |

Follow-up: `cymbal-ingress-pep-sa` still holds unused project roles
(`aiplatform.user`, `bigquery.admin`, `datastore.user`, `dlp.admin`, `dlp.user`,
`modelarmor.admin`, `serviceusage.serviceUsageConsumer`) while nothing runs as
it. Retire it: remove those bindings, then disable the account (and delete it
after a quiet period):

```bash
LEGACY=cymbal-ingress-pep-sa@${PROJECT}.iam.gserviceaccount.com
for R in roles/aiplatform.user roles/bigquery.admin roles/datastore.user roles/dlp.admin \
         roles/dlp.user roles/modelarmor.admin roles/serviceusage.serviceUsageConsumer; do
  gcloud projects remove-iam-policy-binding $PROJECT --member="serviceAccount:$LEGACY" \
    --role="$R" --condition=None
done
gcloud iam service-accounts disable $LEGACY --project=$PROJECT
# Later, once nothing has broken: gcloud iam service-accounts delete $LEGACY --project=$PROJECT
```

## Ongoing operations

- **Recurring check (e.g. daily, and after every IAM change):** the broker must
  have no public invokers:

    ```bash
    gcloud run services get-iam-policy $BROKER --region=$REGION --project=$PROJECT \
      --format=json | grep -E '"allUsers"|"allAuthenticatedUsers"' && echo "ALERT: public broker"
    ```

    Also consider the org policy `iam.allowedPolicyMemberDomains` (Domain
    Restricted Sharing). It makes `allUsers` / `allAuthenticatedUsers` bindings
    impossible project- or org-wide.

- **Onboarding and offboarding:** the broker reads the tenant list from the
  platform config baked into its image (`config/`). Offboarding a tenant
  therefore means a config change **and** a broker redeploy. The gateway's
  in-process offboarding does not reach the broker, and until the redeploy the
  broker still mints for that tenant if it receives a valid broker token. The
  gateway stops issuing broker tokens for offboarded tenants immediately.

## Known limits

- The broker's replay store is in process, so it runs with `max-instances=1`. A
  shared store comes with scale-out.
- The broker reads the caller identity from the Cloud Run-verified ID token.
  Cloud Run IAM (no `allUsers`, invoker = runtime SA only) is what stops other
  callers; the in-app check is defence in depth.
- Until B5 splits the gateway from the runtime, the runtime process can still
  get KMS signatures (it runs as the gateway identity). A fully compromised
  runtime could therefore still sign context tokens and get broker tokens for
  any onboarded tenant (ADR-0014 D4). B4 takes TokenCreator off the runtime SA,
  makes every mint go through one audited, allowlisted service, and sets up B5.
  The blast-radius reduction lands with B5.
