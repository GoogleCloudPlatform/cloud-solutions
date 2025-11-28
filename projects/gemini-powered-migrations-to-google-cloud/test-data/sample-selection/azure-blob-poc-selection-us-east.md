# Container Selection Plan: azure-blob-poc-selection-us-east

## Container Analysis Summary

| Container Name  | Region          | Total Size | Blob Sizes           | Blob Count | File Types                          | Permissions Complexity | Notes                                                            |
| --------------- | --------------- | ---------- | -------------------- | ---------- | ----------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| finance         | `eastus2`       | ~41.2 GB   | ✅ Mix (KB to 100MB) | 4,285      | ✅ Backups (.bak), SQL, XML, Docs   | High (Net Rules)       | ✅ Strongest candidate. Good size mix and region alignment.      |
| engineering     | `eastus`        | ~1.02 GB   | Mostly Small (KB/MB) | 4,525      | Dev artifacts (.whl, .parquet, .js) | High (Net Rules)       | ✅ Good secondary. Excellent for small-file performance testing. |
| human-resources | `centralus`     | N/A        | Mix                  | 4,150      | Docs                                | High                   | ❌ Wrong Region.                                                 |
| legal           | `centralus`     | N/A        | Mix                  | 3,980      | Legal Docs                          | High                   | ❌ Wrong Region.                                                 |
| marketing       | `canadaeast`    | N/A        | Mix                  | 3,860      | Marketing Assets                    | High                   | ❌ Wrong Region.                                                 |
| product         | `canadacentral` | N/A        | Mix                  | 3,894      | Product Specs                       | High                   | ❌ Wrong Region.                                                 |
| sales           | `canadacentral` | N/A        | Mix                  | 4,247      | Sales Data                          | High                   | ❌ Wrong Region.                                                 |

## Recommendations for proof of concept migration

For the Proof of Concept (POC) migration to the US EAST region, the **finance**
container is the optimal selection.

### Primary Selection: `finance`

**Reasoning:**

1.  **Region Alignment:** Located in `eastus2`, which is a primary US East
    region, minimizing latency and egress costs during the POC.
1.  **Data Representative:**
    - **Size & Scale:** With a total size of ~41.2 GB, it provides a substantial
      dataset to validate throughput.
    - **Object Mix:** It contains a realistic mix of "larger" files (Database
      backups ~100MB) and smaller documents (PDFs, XMLs). This variation is
      critical for testing multi-part upload settings and throughput scaling.
1.  **Complexity:** The container enforces strict Network Rules
    (`defaultAction: Deny`), providing a necessary test case for mapping Azure
    VNet/IP restrictions to Google Cloud VPC Service Controls or IAM conditions.

### Secondary Selection: `engineering`

**Reasoning:** The **engineering** container (`eastus`) is a strong alternative
or add-on. While smaller (~1GB), it contains a high density of small files
(code, logs), which is excellent for stress-testing "metadata-heavy" operations
and evaluating object creation latency (Requests Per Second) rather than just
bandwidth.

### Conclusion

Start the POC with **finance** to validate throughput and large-file handling,
optionally adding **engineering** to test small-file performance.
