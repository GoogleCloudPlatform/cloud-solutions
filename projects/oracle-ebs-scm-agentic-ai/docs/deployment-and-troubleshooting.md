# Deployment details and troubleshooting

This page holds the detailed procedures that the [README](../README.md) links
to.

## Publishing the ISG writeback service

The MCP Toolbox sends the writebacks to the `ge_ebs_scm_tools` ISG REST
service. Publish it once per instance, after you install the database objects:

1.  If you haven't enabled ISG REST services yet, follow the
    [Oracle EBS ISG setup and troubleshooting guide][isg-setup-guide].
1.  On the application tier, as the `oracle` user, source `EBSapps.env run`,
    copy `ebs-scripts/ge_ebs_scm_tools_pkg.pls` to the current directory, and
    load the annotated specification into the Integration Repository:

    ```bash
    "${FMW_HOME}/webtier/perl/bin/perl" "${FND_TOP}/bin/irep_parser.pl" -g -v \
        -username=sysadmin \
        inv:patch/115/sql:ge_ebs_scm_tools_pkg.pls:12.0=ge_ebs_scm_tools_pkg.pls
    FNDLOAD apps/APPS_PASSWORD 0 Y UPLOAD \
        "${FND_TOP}/patch/115/import/wfirep.lct" ge_ebs_scm_tools_pkg_pls.ildt
    ```

1.  As `SYSADMIN`, open **Integrated SOA Gateway** > **Integration
    Repository** > `GE_EBS_SCM_TOOLS`. On the **REST Web Service** tab, deploy
    the four methods with the alias `ge_ebs_scm_tools`, and on the **Grants**
    tab, grant them to the user `VOLTGUARD_AGENT`.
1.  Activate the grants: run the **Compile Security** concurrent program with
    **Everything** set to `No`, and then restart the ISG managed server with
    `admanagedsrvctl.sh stop oafm_server1` and
    `admanagedsrvctl.sh start oafm_server1`.
1.  Check the service from the application tier. The response contains a
    `NOT_FOUND` status for the unknown hub `XXX`:

    ```bash
    curl -u VOLTGUARD_AGENT -H "Content-Type: application/json" \
        -X POST http://localhost:8000/webservices/rest/ge_ebs_scm_tools/update_safety_stock/ \
        -d '{"UPDATE_SAFETY_STOCK_Input": {"RESTHeader": {"Responsibility": "INVENTORY_VISION_OPERATIONS", "RespApplication": "INV", "SecurityGroup": "STANDARD", "NLSLanguage": "AMERICAN"}, "InputParameters": {"P_ORGANIZATION_CODE": "XXX", "P_ITEM_CODE": "VG-GEN-7500", "P_SAFETY_STOCK_QTY": 100}}}'
    ```

## Troubleshooting

- **Step 5 of the deployment fails because the `ebs-mcp-toolbox` revision
  isn't ready**: the MCP Toolbox couldn't open one of its sources at startup,
  and its Cloud Run logs name the source. For `ebs-oracle`, check
  `oracle_host`, the firewall rule for `subnet_name`, and the `APPS_AI`
  password, and deploy again.
- **Requisition Import fails with `APP-FND-01564` (`ORACLE error 1017`)**:
  the concurrent managers hold an outdated `APPS` password. Change it only
  with `AFPASSWD` or `FNDCPASS`, and restart the managers with `adcmctl.sh`.
- **ISG returns `ISG_SERVICE_AUTH_FAILURE` (HTTP 403)**: the grants aren't
  active yet. Run **Compile Security** with **Everything** set to `No`, and
  restart `oafm_server1`.
- **ISG returns `ISG_USER_RESP_MISMATCH`**: `VOLTGUARD_AGENT` doesn't hold
  the responsibility in `terraform.tfvars`. Set the responsibility constants
  at the top of `install_voltguard_agent_user.sql` to the keys in
  `terraform.tfvars`, and run the script again.
- **ISG returns HTTP 401**: `ebs_writeback_password` doesn't match the
  `VOLTGUARD_AGENT` password. Run `install_voltguard_agent_user.sql` again,
  and deploy with the same password and a higher
  `ebs_writeback_password_version`.
- **`irep_parser.pl` can't locate `Class/MethodMaker.pm`**: install the pure
  Perl `Class-MethodMaker-1.12` package from the Comprehensive Perl Archive
  Network (CPAN) into `PERL5LIB`.
- **The agent says that the map service is unavailable**: HTTP 403 in the
  agent's logs means that the URL signing secret doesn't match the project.
  Add the current secret to `oracle-ebs-scm-maps-static-signing-secret`, and
  deploy again.
- **The deployment skips the zone exposure and place density tables**: the
  project has no Places Insights subscription. Subscribe to the US listing
  with the linked dataset name `places_insights___us`, and deploy again.
- **Some answers take 30 seconds or more**: on shared capacity, a Gemini call
  sometimes takes 30 seconds, as the `Gemini call:` log lines show. Purchase
  [Vertex AI Provisioned Throughput][provisioned-throughput] to reduce this
  latency.
- **The first answer after an idle period takes longer**: both Cloud Run
  services scale to zero when idle, so an idle deployment adds no Cloud Run
  charges, and the next request starts them again. A conversation that
  waited until the agent instance stopped loses its earlier turns, so plan a
  pending change again before you confirm it. During a demo, set
  `min_instance_count = 1` and deploy again to keep both services running.

[isg-setup-guide]:
    https://github.com/GoogleCloudPlatform/cloud-solutions/blob/main/projects/oracle-ebs-workflow-agentic-ai/docs/isg-setup-and-troubleshooting.md
[provisioned-throughput]:
    https://cloud.google.com/vertex-ai/generative-ai/docs/provisioned-throughput/overview
