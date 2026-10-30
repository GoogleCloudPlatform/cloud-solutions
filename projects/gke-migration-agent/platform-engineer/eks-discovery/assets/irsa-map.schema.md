<!--
 Copyright 2026 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# irsa-map.tsv schema

Tab-separated, no header. One row per IRSA binding across all clusters.

## Columns

| #   | Name            | Description                    |
| --- | --------------- | ------------------------------ |
| 1   | cluster         | Amazon EKS cluster name        |
| 2   | namespace       | Kubernetes namespace           |
| 3   | service_account | Kubernetes ServiceAccount name |
| 4   | role_arn        | IAM role ARN                   |
| 5   | mechanism       | `irsa` or `pod-identity`       |

## Notes

- Multiple rows may share one `role_arn` (N:1 SA-to-role is legal).
- `pod-identity` rows require `describe-pod-identity-association`; the list call
  does not include the role ARN.

## Example

```text
prod-east-1 storefront checkout-sa arn:aws:iam::123456789012:role/checkout irsa
prod-east-1 payments api-sa arn:aws:iam::123456789012:role/payments-api irsa
```
