-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     https://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- =============================================================================
-- Creates APPS_AI, the read-only database user that the MCP Toolbox connects
-- as. APPS_AI can only SELECT the Oracle EBS objects in the agent's semantic
-- maps. A logon trigger sets CURRENT_SCHEMA to APPS, so the agent's SQL keeps
-- its unqualified APPS names. Writebacks go through the ge_ebs_scm_tools
-- Integrated SOA Gateway (ISG) REST service instead.
--
-- Run as EBS_SYSTEM (or another DBA) after install_scm_inventory_views.sql.
-- The script is idempotent: a second run resets the password and the grants.
-- =============================================================================

SET VERIFY OFF
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
ACCEPT apps_ai_password CHAR PROMPT 'Password for APPS_AI: ' HIDE

-- Copy the password into a bind variable and turn substitution off, so no
-- statement below contains its text. The password can't contain ~'.
VARIABLE apps_ai_password VARCHAR2(128)
EXECUTE :apps_ai_password := q'~&apps_ai_password~'
UNDEFINE apps_ai_password
SET DEFINE OFF

DECLARE
    e_invalid_password EXCEPTION;
    PRAGMA EXCEPTION_INIT(e_invalid_password, -44003);
    l_exists   NUMBER;
    l_password VARCHAR2(130);
BEGIN
    -- ENQUOTE_NAME quotes the password and rejects double quotation marks,
    -- which an Oracle password can't contain.
    l_password := sys.dbms_assert.enquote_name(:apps_ai_password, FALSE);
    SELECT COUNT(*) INTO l_exists FROM dba_users WHERE username = 'APPS_AI';
    IF l_exists = 0 THEN
        EXECUTE IMMEDIATE 'CREATE USER apps_ai IDENTIFIED BY ' || l_password;
    ELSE
        EXECUTE IMMEDIATE
            'ALTER USER apps_ai IDENTIFIED BY ' || l_password
            || ' ACCOUNT UNLOCK';
    END IF;
EXCEPTION
    WHEN e_invalid_password THEN
        raise_application_error(
            -20001,
            'The APPS_AI password can''t contain a double quotation mark.'
        );
END;
/

GRANT CREATE SESSION TO apps_ai;

CREATE OR REPLACE TRIGGER apps_ai.apps_ai_logon
AFTER LOGON ON apps_ai.SCHEMA
BEGIN
    EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = APPS';
END;
/

-- Keep this list equal to the Oracle EBS objects in the semantic maps
-- (tests/test_contracts.py checks it).
BEGIN
    FOR r IN (
        SELECT column_value AS object_name
          FROM TABLE(sys.odcivarchar2list(
              'AP_SUPPLIERS',
              'AP_SUPPLIER_SITES_ALL',
              'HZ_CUST_ACCOUNTS',
              'HZ_CUST_ACCT_SITES_ALL',
              'HZ_CUST_SITE_USES_ALL',
              'HZ_LOCATIONS',
              'HZ_PARTIES',
              'HZ_PARTY_SITES',
              'MTL_ITEM_LOCATIONS',
              'MTL_MATERIAL_TRANSACTIONS',
              'MTL_ONHAND_QUANTITIES_DETAIL',
              'MTL_PARAMETERS',
              'MTL_RESERVATIONS',
              'MTL_SECONDARY_INVENTORIES',
              'MTL_SYSTEM_ITEMS_B',
              'MTL_TRANSACTION_TYPES',
              'OE_ORDER_HEADERS_ALL',
              'OE_ORDER_LINES_ALL',
              'OE_PRICE_ADJUSTMENTS',
              'OE_TRANSACTION_TYPES_ALL',
              'PO_DISTRIBUTIONS_ALL',
              'PO_HEADERS_ALL',
              'PO_LINES_ALL',
              'PO_LINE_LOCATIONS_ALL',
              'PO_REQUISITION_HEADERS_ALL',
              'PO_REQUISITION_LINES_ALL',
              'RCV_SHIPMENT_HEADERS',
              'RCV_TRANSACTIONS',
              'VW_SCM_ACTIVE_POS',
              'VW_SCM_APPROVED_SUPPLIERS',
              'VW_SCM_BURN_RATE_AND_MRP',
              'VW_SCM_NET_AVAILABILITY',
              'VW_SCM_OPEN_NOTIFICATIONS',
              'VW_SCM_SLA_CONTRACT_LOCKS',
              'WSH_DELIVERY_ASSIGNMENTS',
              'WSH_DELIVERY_DETAILS',
              'WSH_NEW_DELIVERIES'
          ))
    ) LOOP
        EXECUTE IMMEDIATE
            'GRANT SELECT ON APPS.' || r.object_name || ' TO apps_ai';
    END LOOP;
END;
/

PROMPT APPS_AI is ready: SELECT on the semantic map objects only.
