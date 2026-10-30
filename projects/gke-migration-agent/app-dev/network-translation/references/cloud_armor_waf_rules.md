# AWS WAF to Google Cloud Armor rules mapping

This reference documents how to translate AWS WAF protections to Google Cloud
Armor WAF security policies on GKE.

## Concept mapping

| Security Control      | AWS WAF                               | Google Cloud Armor                                    |
| :-------------------- | :------------------------------------ | :---------------------------------------------------- |
| Policy attachment     | WebACL association to ALB             | BackendService attachment via `GCPBackendPolicy`      |
| IP Allow/Denylisting  | IP Set Rule                           | IP match rule (action: `allow` / `deny`)              |
| Geo-Blocking          | Geographic match rule                 | Origin match rule (`origin.region_code`)              |
| Preconfigured WAF     | Managed rule groups (Core, SQLi, LFI) | Preconfigured WAF rules (`evaluatePreconfiguredExpr`) |

## GCPBackendPolicy WAF attachment example

Create Cloud Armor WAF policies in Google Cloud and reference them in GKE
manifests using a `GCPBackendPolicy`.

```yaml
apiVersion: networking.gke.io/v1
kind: GCPBackendPolicy
metadata:
  name: frontend-backend-policy
  namespace: production-app
spec:
  default:
    securityPolicy: shop-armor
  targetRef:
    group: ""
    kind: Service
    name: frontend-service
```

## Preconfigured expression mapping

| AWS Managed Rule Group               | Cloud Armor Equivalent Expression                      |
| :----------------------------------- | :----------------------------------------------------- |
| AWSManagedRulesCommonRuleSet         | `owasp-crs-v030001-id949-lfi` and basic core rule sets |
| AWSManagedRulesSQLiRuleSet           | `owasp-crs-v030001-id942-sqli`                         |
| AWSManagedRulesKnownBadInputsRuleSet | `owasp-crs-v030001-id944-bad-inputs`                   |
