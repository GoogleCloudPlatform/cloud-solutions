# Bucket Selection Plan: aws-s3-poc-selection-us-east

## Bucket Analysis Summary

| Bucket Name            | Region           | Total Size | Object Sizes       | File Types                              | Permissions Complexity              | Notes                                                                               |
| ---------------------- | ---------------- | ---------- | ------------------ | --------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------- |
| engineering-bucket     | `us-east-1`      | 880.0 GiB  | Mix of GiB and MiB | Diverse (code, docs, vm images, logs)   | Medium (Role-based)                 | Excellent candidate. In the target region with diverse data and permissions.        |
| finance-bucket         | `eu-central-1`   | 650.0 GiB  | GiB range          | Financial documents (.xlsx, .pdf, .csv) | Medium                              | Not in the target region.                                                           |
| human-resources-bucket | `ap-southeast-2` | 550.0 GiB  | GiB range          | HR documents (.csv, .zip, .pdf)         | High (Deny policies)                | Not in the target region. Good candidate for testing complex `Deny` policies later. |
| legal-bucket           | `sa-east-1`      | 720.0 GiB  | GiB range          | Legal documents (.pdf, .zip, .docx)     | High (Deny policies)                | Not in the target region. Good candidate for testing complex `Deny` policies later. |
| marketing-bucket       | `us-west-2`      | 750.0 GiB  | Mix of GiB and MiB | Marketing materials (.jpg, .pdf, .mp4)  | High (Public, Deny, Specific Roles) | Good candidate for testing complex permissions, but not in the target region.       |

## Recommendations for POC Migration

For the initial Proof of Concept (POC) migration to the US EAST region, the
**engineering-bucket** is the definitive choice.

### Primary Selection: `engineering-bucket`

**Reasoning:**

1.  **Region Alignment:** Located in `us-east-1`, it matches the target US EAST
    region preference. This ensures the POC focuses on migration mechanics
    rather than network latency issues.
1.  **Data Diversity:** It provides the most representative "real-world"
    dataset:
    - **Object Size:** Ranges from small source code files (MiB) to massive
      Virtual Machine images (~45 GiB). This tests throughput for large objects
      and overhead for small objects.
    - **File Types:** Includes binaries, text, logs, and compressed archives.
1.  **Permissions:** It uses a standard Role-Based Access Control (RBAC) model
    which is the most common pattern to validate against GCP IAM.

### Secondary Consideration: `marketing-bucket`

While not in the US East region (`us-west-2`), the **marketing-bucket** is
notable for its **Complex Permissions** (Public Read, Deny logic). If the POC
scope expands to include complex policy translation or cross-region transfers,
this should be the next candidate.

### Conclusion

Proceed with **engineering-bucket** for the immediate US EAST POC.
