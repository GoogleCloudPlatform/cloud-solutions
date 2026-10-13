# Oracle EBS Integrated SOA Gateway (ISG) setup and troubleshooting

This guide walks through enabling, deploying, and troubleshooting the
**Integrated SOA Gateway (ISG)** REST service for **Oracle E-Business Suite
(EBS)** Release 12.2 so that the workflow agent can execute certified responses
through **Path B (`REST`)** at `/webservices/rest/wf/respond`.

## Overview

In Oracle EBS Release 12.2, ISG REST web services run inside the **`oafm`
(Oracle Applications Fusion Middleware)** WebLogic managed server
(`oafm_server1`) on the application tier, exposed on the web entry point port
(typically HTTP port `8000`).

To expose the certified `WF_NOTIFICATION` PL/SQL package (**Workflow
Notification System**) as a REST service:

1.  Configure the `ISGADMIN` service deployment user in `FND_USER` and
    `FND_VAULT`.
1.  Verify that the `oafm_server1` managed server is running on the EBS
    application tier.
1.  Deploy `WF_NOTIFICATION` with service alias `wf` in the **Integration
    Repository** user interface (UI).
1.  Create security grants for the deployed operations.

## Step 1: Configure ISGADMIN in FND_USER and FND_VAULT

Oracle EBS 12.2 requires the internal `ISGADMIN` account (or `ASADMIN` on older
12.2 patch levels) to have a valid password in `FND_USER` and to be registered
in the **EBS FND Vault (`FND_VAULT`)** under the `'ISG'` module before any REST
service can be deployed.

Connect to SQL\*Plus as `APPS` (either on the EBS virtual machine (VM) or
through your port `1521` Identity-Aware Proxy (IAP) tunnel) and run the
following PL/SQL block:

```sql
DECLARE
  v_count NUMBER;
BEGIN
  -- 1. Create or update ISGADMIN in FND_USER with an active password
  SELECT COUNT(*) INTO v_count
  FROM applsys.fnd_user
  WHERE user_name = 'ISGADMIN';

  IF v_count = 0 THEN
    fnd_user_pkg.createuser(
      x_user_name            => 'ISGADMIN',
      x_owner                => 'CUST',
      x_unencrypted_password => 'YOUR_ISGADMIN_PASSWORD',
      x_start_date           => SYSDATE - 1,
      x_password_date        => SYSDATE
    );
  ELSE
    fnd_user_pkg.updateuser(
      x_user_name            => 'ISGADMIN',
      x_owner                => 'CUST',
      x_unencrypted_password => 'YOUR_ISGADMIN_PASSWORD',
      x_start_date           => SYSDATE - 1,
      x_end_date             => fnd_user_pkg.null_date,
      x_password_date        => SYSDATE
    );
  END IF;

  -- 2. Register ISGADMIN (and ASADMIN) in FND_VAULT under the 'ISG' module
  fnd_vault.put('ISG', 'ISGADMIN', 'YOUR_ISGADMIN_PASSWORD');
  fnd_vault.put('ISG', 'ASADMIN', 'YOUR_ISGADMIN_PASSWORD');

  -- 3. Grant the Integration Administrator role to ISGADMIN
  wf_local_synch.PropagateUserRole(
    p_user_name       => 'ISGADMIN',
    p_role_name       => 'UMX|FND_IREP_ADMIN',
    p_start_date      => SYSDATE - 1,
    p_expiration_date => NULL
  );

  COMMIT;
END;
/
```

Verify that the vault entry is populated:

```sql
SELECT fnd_vault.get('ISG', 'ISGADMIN') AS isg_pwd FROM dual;
```

## Step 2: Verify oafm_server1 on the EBS application tier

SSH into your Oracle EBS VM and switch to the `oracle` operating system owner
before sourcing the EBS environment:

```bash
# 1. Switch to the oracle OS owner (required to read FMW_Home node_info.txt)
sudo su - oracle

# 2. Source the EBS Run Edition environment
source /u01/install/APPS/EBSapps.env run

# 3. Check if oafm_server1 is running without needing a password
ps -ef | grep [o]afm_server1

# Or check using admanagedsrvctl.sh
$ADMIN_SCRIPTS_HOME/admanagedsrvctl.sh status oafm_server1
```

If `oafm_server1` is not running, start it:

```bash
$ADMIN_SCRIPTS_HOME/admanagedsrvctl.sh start oafm_server1
```

> [!TIP]
>
> **Retrieving the WebLogic Admin password on Vision**: If the WebLogic
> administrator password (`YOUR_WEBLOGIC_PASSWORD`) is unknown on your EBS 12.2
> instance, run the following command as `oracle` (after sourcing
> `EBSapps.env run`) to decrypt it from `boot.properties`:
>
> ```bash
> java -cp $FMW_HOME/wlserver_10.3/server/lib/weblogic.jar weblogic.WLST << 'WLS_EOF'
> import os, java.util.Properties, java.io.FileInputStream
> domain = os.environ['EBS_DOMAIN_HOME']
> service = weblogic.security.internal.SerializedSystemIni.getEncryptionService(domain)
> enc = weblogic.security.internal.encryption.ClearOrEncryptedService(service)
> p = java.util.Properties()
> p.load(java.io.FileInputStream(domain + '/servers/AdminServer/security/boot.properties'))
> print "WLS_USER=" + enc.decrypt(p.getProperty('username'))
> print "WLS_PASS=" + enc.decrypt(p.getProperty('password'))
> exit()
> WLS_EOF
> ```

## Step 3: Deploy WF_NOTIFICATION in the Integration Repository

1.  Log in to Oracle EBS (`http://<ebs-host>:8000/OA_HTML/AppsLogin`) as
    `SYSADMIN`.
1.  Ensure `SYSADMIN` has the **Integrated SOA Gateway** responsibility and the
    **Integration Administrator (`UMX|FND_IREP_ADMIN`)** role assigned under
    **User Management** > **Users**.
1.  Navigate to **Integrated SOA Gateway** > **Integration Repository** and
    click **Search**.
1.  Search for:
    - **Internal Name**: `WF_NOTIFICATION`
    - **Interface Type**: `PL/SQL`
1.  Open **Workflow Notification System (`WF_NOTIFICATION`)** and select the
    **REST Web Service** tab.
1.  Enter **Service Alias**: `wf` (this exposes the service at
    `/webservices/rest/wf/...`).
1.  Select the individual operations required by the workflow agent (do **not**
    click **Select All**, as overloaded PL/SQL procedures can collide):
    - `RESPOND` (Respond to Notification)
    - `SETATTRTEXT` (Set Notification Text Attribute Value)
    - `GETATTRTEXT` (Get Notification Text Attribute Value)
    - `GETINFO` (Get Notification Information)
1.  Click **Deploy** and confirm that the banner displays:
    `Successfully deployed Web Service for interface 'Workflow Notification`
    `System' to Application Server`. _(Note: The second informational line
    stating that ISG is not configured for SOAP Services is expected when using
    REST services and can be ignored.)_
1.  Open the **Grants** tab, select the deployed operations (`RESPOND`,
    `SETATTRTEXT`, `GETATTRTEXT`, `GETINFO`), click **Create Grant**, grant
    access to **All Users** (or your target EBS user such as `OPERATIONS` /
    `SYSADMIN`), and click **Apply**.

## Step 4: Verify the WADL and configure the agent

1.  Verify that the deployed Web Application Description Language (WADL)
    endpoint responds on port `8000`:

    ```bash
    curl -u SYSADMIN:<SYSADMIN_PASSWORD> \
      "http://localhost:8000/webservices/rest/wf/?WADL"
    ```

1.  For local development, open an IAP tunnel to port `8000` on your EBS VM:

    ```bash
    gcloud compute start-iap-tunnel oracle-vision 8000 \
      --project=YOUR_GOOGLE_CLOUD_PROJECT_ID \
      --zone=YOUR_ZONE \
      --local-host-port=localhost:8000
    ```

1.  Set the execution path in `terraform/terraform.tfvars` or runtime
    environment variables:

    ```hcl
    workflow_execution_path = "REST"
    isg_rest_base_url       = "http://localhost:8000"
    ```

## Troubleshooting common ISG issues

### 1. Node info file node_info.txt is not found when sourcing EBSapps.env

- **Symptom**: Running `source /u01/install/APPS/EBSapps.env run` fails with:
  `Node info file .../applications/oacore/APP-INF/node_info.txt is not found.`
- **Cause**: You are logged in as your personal Google Cloud OS Login user,
  which lacks read permissions on `/u01/install/APPS/fs1/FMW_Home` (`750` owned
  by `oracle:oinstall`).
- **Resolution**: Switch to the `oracle` user first (`sudo su - oracle`) and
  then source `/u01/install/APPS/EBSapps.env run`.

### 2. OAException: Password for user:ISGADMIN is not configured

- **Symptom**: Clicking **Deploy** on the **REST Web Service** tab fails with
  `OAException: Password for user:ISGADMIN is not configured.`
- **Cause**: The `ISGADMIN` password has not been stored in `FND_VAULT` under
  the `'ISG'` module, or the `ISGADMIN` user is inactive in `FND_USER`.
- **Resolution**: Execute the PL/SQL block in
  [Step 1](#step-1-configure-isgadmin-in-fnd_user-and-fnd_vault) as `APPS` to
  update `ISGADMIN` and call `fnd_vault.put('ISG', 'ISGADMIN', '<PASSWORD>')`.

### 3. Generic "You have encountered an unexpected error" banner in OAF

- **Symptom**: Clicking **Deploy** displays the generic **Oracle Application
  Framework (OAF)** error page without showing the underlying Java exception.
- **Resolution**: Enable the `FND: Diagnostics` profile option in SQL\*Plus as
  `APPS`:

    ```sql
    DECLARE
      v_saved BOOLEAN;
    BEGIN
      v_saved := fnd_profile.save('FND_DIAGNOSTICS', 'Y', 'SITE');
      COMMIT;
    END;
    /
    ```

    Log out and log back in to the EBS UI, reproduce the error, and click the
    **Click here for exception details** link to inspect the full stack trace.

### 4. JBO-26048: Constraint FND_SOA_SERVICE_OPERATIONS_PK violated on Insert

- **Symptom**: Deploying `WF_NOTIFICATION` after a previous failed attempt
  throws `JBO-26048: Constraint "FND_SOA_SERVICE_OPERATIONS_PK" violated`
  `during post operation: "Insert"`.
- **Cause**: A prior failed deployment inserted partial operation rows into
  `APPLSYS.FND_SOA_SERVICE_OPERATIONS` while leaving the service status as
  undeployed (or the browser tab cached uncommitted OAF entity state).
- **Resolution**:
    1.  Delete the orphaned rows in SQL\*Plus as `APPS`:

        ```sql
        DELETE FROM applsys.fnd_soa_service_operations
        WHERE class_id IN (
          SELECT class_id
          FROM applsys.fnd_irep_classes
          WHERE irep_name = 'WF_NOTIFICATION'
        );

        COMMIT;
        ```

    1.  Do **not** click **Deploy** on the stale browser page. Navigate back to
        **Integration Repository** > **Search**, open a fresh page for
        `WF_NOTIFICATION`, enter alias `wf`, check only `RESPOND`,
        `SETATTRTEXT`, `GETATTRTEXT`, and `GETINFO`, and click **Deploy**.

### 5. ISG_SERVICE_AUTH_FAILURE due to ORA-01017 in oafm_server1 (Oracle 19c)

- **Symptom**: Calling a deployed ISG REST endpoint returns HTTP 500 with
  `ISG_SERVICE_AUTH_FAILURE`, and `oafm_server1.out` shows
  `ORA-01017: invalid username/password; logon denied` inside
  `AppsConnectionManager.makeGuestConnection`.
- **Cause**: `FND_ORACLE_USERID` stores the `APPS` password in uppercase,
  whereas Oracle 19c (`sec_case_sensitive_logon = TRUE`) only has `11G 12C`
  password verifiers if `SQLNET.ALLOWED_LOGON_VERSION_SERVER=8` is not set.
- **Resolution**:
    1.  Add `SQLNET.ALLOWED_LOGON_VERSION_SERVER=8` to
        `$ORACLE_HOME/network/admin/EBSDB_apps/sqlnet_ifile.ora`.
    1.  In SQL\*Plus (`as sysdba`), ensure `sec_case_sensitive_logon = TRUE`
        (required by `python-oracledb` thin mode) and set the `APPS` database
        password in uppercase so it matches `FND_ORACLE_USERID`:

        ```sql
        ALTER SYSTEM SET sec_case_sensitive_logon = TRUE SCOPE=BOTH;
        ALTER SESSION SET CONTAINER = EBSDB;
        ALTER USER APPS IDENTIFIED BY "<UPPERCASE_APPS_PASSWORD>";
        ```

    1.  Verify with `java oracle.apps.fnd.security.AdminAppServer`
        `apps/<APPS_PASSWORD> TEST DBC=$FND_SECURE/EBSDB.dbc`.

### 6. ISG_SERVICE_AUTH_FAILURE due to uncompiled security grants

- **Symptom**: After creating `Create Grant` entries in the Integration
  Repository while Concurrent Managers are stopped, ISG REST calls still fail
  with `Not authorized to access the utility function`.
- **Cause**: New menus created for ISG grants remain marked as uncompiled
  (`function_id = -99999`, `grant_flag = 'U'`) in
  `APPLSYS.FND_COMPILED_MENU_FUNCTIONS` until `FND_FUNCTION.COMPILE` runs.
- **Resolution**: Compile the function security menus manually in SQL\*Plus as
  `APPS` and bounce `oafm_server1`:

    ```sql
    DECLARE
      v_errbuf  VARCHAR2(2000);
      v_retcode VARCHAR2(2000);
    BEGIN
      fnd_function.compile(v_errbuf, v_retcode, 'N');
      COMMIT;
    END;
    /
    ```
