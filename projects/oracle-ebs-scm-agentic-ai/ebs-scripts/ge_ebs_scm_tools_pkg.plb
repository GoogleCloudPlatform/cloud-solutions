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
-- APPS.GE_EBS_SCM_TOOLS body: the VoltGuard writebacks behind the
-- ge_ebs_scm_tools Integrated SOA Gateway (ISG) REST service. Install the
-- specification (ge_ebs_scm_tools_pkg.pls) first.
--
-- ISG starts the Oracle EBS session for the authenticated user and the
-- RESTHeader responsibility. Every function checks that session, validates
-- its input, calls an Oracle public API or open interface, writes an audit
-- row through the framework procedure APPS.MCP_TOOLBOX_LOG, and returns a
-- JSON document with STATUS (SUCCESS or ERROR), CODE, MESSAGE, and result
-- fields.
--
-- Error codes: INVALID_INPUT, NOT_FOUND, BUSINESS_RULE, EBS_API_ERROR,
-- SETUP_ERROR.
--
-- Prerequisite: install the framework database objects first
-- (EBSScripts/install_all_mcp_db.sql in the framework repository).
-- =============================================================================

CREATE OR REPLACE PACKAGE BODY APPS.GE_EBS_SCM_TOOLS AS

    c_mcp_client         CONSTANT VARCHAR2(30) := 'voltguard-scm-agent';
    c_max_note_chars     CONSTANT PLS_INTEGER := 2000;
    -- The only Oracle Workflow message that the agent can close.
    c_alert_message_type CONSTANT VARCHAR2(8) := 'INVSCM';
    c_alert_message_name CONSTANT VARCHAR2(30) := 'VOLTGUARD_RESILIENCY_ALERT';

    e_not_found EXCEPTION;

    FUNCTION result_json (
        p_status  IN VARCHAR2,
        p_code    IN VARCHAR2,
        p_message IN VARCHAR2,
        p_fields  IN JSON_OBJECT_T DEFAULT NULL
    ) RETURN VARCHAR2 IS
        l_result JSON_OBJECT_T;
    BEGIN
        IF p_fields IS NULL THEN
            l_result := JSON_OBJECT_T();
        ELSE
            l_result := p_fields;
        END IF;
        l_result.put('STATUS', p_status);
        l_result.put('CODE', p_code);
        l_result.put('MESSAGE', p_message);
        RETURN l_result.to_string;
    END result_json;

    -- Writes the audit row in its own transaction and never raises, so an
    -- audit failure can't turn a committed Oracle EBS change into an error
    -- result that invites a duplicate retry, and error rows survive the
    -- caller's ROLLBACK.
    PROCEDURE audit (
        p_program_unit IN VARCHAR2,
        p_level        IN VARCHAR2,
        p_message      IN VARCHAR2
    ) IS
        PRAGMA AUTONOMOUS_TRANSACTION;
    BEGIN
        APPS.MCP_TOOLBOX_LOG(
            p_log_message  => SUBSTR(p_message, 1, 4000),
            p_log_level    => p_level,
            p_username     => fnd_global.user_name,
            p_program_unit => 'GE_EBS_SCM_TOOLS.' || p_program_unit,
            p_mcp_client   => c_mcp_client
        );
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
    END audit;

    -- Completes the Oracle EBS session that ISG started from the RESTHeader.
    -- Returns FALSE when the call has no user or responsibility context.
    FUNCTION session_ready RETURN BOOLEAN IS
    BEGIN
        IF fnd_global.user_id = -1 OR fnd_global.resp_id = -1 THEN
            RETURN FALSE;
        END IF;
        mo_global.init(fnd_global.application_short_name);
        RETURN TRUE;
    END session_ready;

    -- Result for a call without an Oracle EBS session.
    FUNCTION session_error (p_program_unit IN VARCHAR2) RETURN VARCHAR2 IS
    BEGIN
        audit(
            p_program_unit, 'ERROR',
            'The call has no Oracle EBS user and responsibility context.'
        );
        RETURN result_json(
            'ERROR', 'SETUP_ERROR',
            'Oracle EBS did not start a session for the agent. The MCP '
            || 'audit log records the details.'
        );
    END session_error;

    FUNCTION org_id (p_org_code IN VARCHAR2) RETURN NUMBER IS
        l_org_id NUMBER;
    BEGIN
        SELECT organization_id
          INTO l_org_id
          FROM inv.mtl_parameters
         WHERE organization_code = UPPER(TRIM(p_org_code));
        RETURN l_org_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE e_not_found;
    END org_id;

    PROCEDURE item_in_org (
        p_org_id    IN  NUMBER,
        p_item_code IN  VARCHAR2,
        x_item_id   OUT NUMBER,
        x_uom_code  OUT VARCHAR2
    ) IS
    BEGIN
        SELECT inventory_item_id, primary_uom_code
          INTO x_item_id, x_uom_code
          FROM inv.mtl_system_items_b
         WHERE organization_id = p_org_id
           AND segment1 = UPPER(TRIM(p_item_code));
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE e_not_found;
    END item_in_org;

    PROCEDURE availability (
        p_org_id           IN  NUMBER,
        p_item_id          IN  NUMBER,
        x_att_qty          OUT NUMBER,
        x_safety_stock_qty OUT NUMBER
    ) IS
    BEGIN
        SELECT available_to_transact_qty, safety_stock_qty
          INTO x_att_qty, x_safety_stock_qty
          FROM APPS.VW_SCM_NET_AVAILABILITY
         WHERE organization_id = p_org_id
           AND inventory_item_id = p_item_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE e_not_found;
    END availability;

    -- Picks the active reservable subinventory with the most stock available
    -- to transact, by the Oracle Inventory quantity tree, which accounts for
    -- reservations that name a subinventory. The transfer carries no
    -- revision, lot, or serial detail.
    PROCEDURE source_subinventory (
        p_org_id       IN  NUMBER,
        p_item_id      IN  NUMBER,
        x_subinventory OUT VARCHAR2,
        x_att_qty      OUT NUMBER
    ) IS
        l_status    VARCHAR2(1);
        l_msg_count NUMBER;
        l_msg_data  VARCHAR2(4000);
        l_qoh       NUMBER;
        l_rqoh      NUMBER;
        l_qr        NUMBER;
        l_qs        NUMBER;
        l_att       NUMBER;
        l_atr       NUMBER;
    BEGIN
        x_att_qty := 0;
        FOR l_sub IN (
            SELECT DISTINCT moqd.subinventory_code
              FROM inv.mtl_onhand_quantities_detail moqd
              JOIN inv.mtl_secondary_inventories msi
                ON msi.organization_id = moqd.organization_id
               AND msi.secondary_inventory_name = moqd.subinventory_code
             WHERE moqd.organization_id = p_org_id
               AND moqd.inventory_item_id = p_item_id
               AND msi.reservable_type = 1
               AND NVL(msi.disable_date, SYSDATE + 1) > SYSDATE
             ORDER BY moqd.subinventory_code
        ) LOOP
            inv_quantity_tree_pub.query_quantities(
                p_api_version_number  => 1.0,
                p_init_msg_lst        => fnd_api.g_true,
                x_return_status       => l_status,
                x_msg_count           => l_msg_count,
                x_msg_data            => l_msg_data,
                p_organization_id     => p_org_id,
                p_inventory_item_id   => p_item_id,
                p_tree_mode           => inv_quantity_tree_pub.g_transaction_mode,
                p_is_revision_control => FALSE,
                p_is_lot_control      => FALSE,
                p_is_serial_control   => FALSE,
                p_revision            => NULL,
                p_lot_number          => NULL,
                p_subinventory_code   => l_sub.subinventory_code,
                p_locator_id          => NULL,
                x_qoh                 => l_qoh,
                x_rqoh                => l_rqoh,
                x_qr                  => l_qr,
                x_qs                  => l_qs,
                x_att                 => l_att,
                x_atr                 => l_atr
            );
            IF l_status <> fnd_api.g_ret_sts_success THEN
                raise_application_error(
                    -20001,
                    'Quantity tree: ' || NVL(
                        fnd_msg_pub.get(fnd_msg_pub.g_last, fnd_api.g_false),
                        l_msg_data
                    )
                );
            END IF;
            IF l_att > x_att_qty THEN
                x_subinventory := l_sub.subinventory_code;
                x_att_qty := l_att;
            END IF;
        END LOOP;
    END source_subinventory;

    -- Picks the active subinventory that receives a transfer: the item's
    -- default receiving subinventory, else the one that holds the most stock
    -- of the item, else the first reservable one, so a hub with no stock of
    -- the item can still receive it.
    FUNCTION receiving_subinventory (
        p_org_id  IN NUMBER,
        p_item_id IN NUMBER
    ) RETURN VARCHAR2 IS
        l_subinventory VARCHAR2(10);
    BEGIN
        SELECT candidate.subinventory_code
          INTO l_subinventory
          FROM (
              SELECT msd.subinventory_code, 1 AS preference, 0 AS onhand_qty
                FROM inv.mtl_item_sub_defaults msd
               WHERE msd.organization_id = p_org_id
                 AND msd.inventory_item_id = p_item_id
                 AND msd.default_type = 2
              UNION ALL
              SELECT moqd.subinventory_code, 2,
                     SUM(moqd.primary_transaction_quantity)
                FROM inv.mtl_onhand_quantities_detail moqd
               WHERE moqd.organization_id = p_org_id
                 AND moqd.inventory_item_id = p_item_id
               GROUP BY moqd.subinventory_code
              UNION ALL
              SELECT msi.secondary_inventory_name, 3, 0
                FROM inv.mtl_secondary_inventories msi
               WHERE msi.organization_id = p_org_id
                 AND msi.reservable_type = 1
          ) candidate
          JOIN inv.mtl_secondary_inventories active
            ON active.organization_id = p_org_id
           AND active.secondary_inventory_name = candidate.subinventory_code
           AND NVL(active.disable_date, SYSDATE + 1) > SYSDATE
         ORDER BY candidate.preference, candidate.onhand_qty DESC,
                  candidate.subinventory_code
         FETCH FIRST 1 ROW ONLY;
        RETURN l_subinventory;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RETURN NULL;
    END receiving_subinventory;

    FUNCTION stage_interorg_transfer (
        p_source_org_code IN VARCHAR2,
        p_dest_org_code   IN VARCHAR2,
        p_item_code       IN VARCHAR2,
        p_transfer_qty    IN NUMBER
    ) RETURN VARCHAR2 IS
        c_unit          CONSTANT VARCHAR2(30) := 'stage_interorg_transfer';
        l_source_org_id NUMBER;
        l_dest_org_id   NUMBER;
        l_item_id       NUMBER;
        l_dest_item_id  NUMBER;
        l_uom_code      VARCHAR2(3);
        l_dest_uom_code VARCHAR2(3);
        l_source_subinv VARCHAR2(10);
        l_dest_subinv   VARCHAR2(10);
        l_txn_type_id   NUMBER;
        l_networks      NUMBER;
        l_lock          INTEGER;
        l_att           NUMBER;
        l_subinv_att    NUMBER;
        l_safety_stock  NUMBER;
        l_header_id     NUMBER;
        l_rc            NUMBER;
        l_status        VARCHAR2(1);
        l_msg_count     NUMBER;
        l_msg_data      VARCHAR2(4000);
        l_trans_count   NUMBER;
        l_error         VARCHAR2(4000);
        l_audit         VARCHAR2(32767);
        l_result        VARCHAR2(32767);
        l_fields        JSON_OBJECT_T := JSON_OBJECT_T();
    BEGIN
        IF p_transfer_qty IS NULL
           OR p_transfer_qty <= 0
           OR p_transfer_qty <> TRUNC(p_transfer_qty) THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'Transfer quantity must be a positive whole number.'
            );
        END IF;
        IF UPPER(TRIM(p_source_org_code)) = UPPER(TRIM(p_dest_org_code)) THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'The source and destination hubs must be different.'
            );
        END IF;

        IF NOT session_ready THEN
            RETURN session_error(c_unit);
        END IF;
        l_source_org_id := org_id(p_source_org_code);
        l_dest_org_id := org_id(p_dest_org_code);
        item_in_org(l_source_org_id, p_item_code, l_item_id, l_uom_code);
        item_in_org(l_dest_org_id, p_item_code, l_dest_item_id, l_dest_uom_code);

        l_fields.put('SOURCE_ORG_CODE', UPPER(TRIM(p_source_org_code)));
        l_fields.put('DEST_ORG_CODE', UPPER(TRIM(p_dest_org_code)));
        l_fields.put('ITEM_CODE', UPPER(TRIM(p_item_code)));
        l_fields.put('TRANSFER_QTY', p_transfer_qty);

        SELECT COUNT(*)
          INTO l_networks
          FROM inv.mtl_interorg_parameters
         WHERE from_organization_id = l_source_org_id
           AND to_organization_id = l_dest_org_id
           AND intransit_type = 1;
        IF l_networks = 0 THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Oracle Inventory has no direct shipping network from '
                || UPPER(TRIM(p_source_org_code)) || ' to '
                || UPPER(TRIM(p_dest_org_code)) || '.',
                l_fields
            );
        END IF;

        -- Holds transfers of the item out of the source hub until COMMIT or
        -- ROLLBACK, so two calls can't pass the same availability check.
        l_lock := DBMS_LOCK.REQUEST(
            id                => DBMS_UTILITY.GET_HASH_VALUE(
                c_unit || ':' || l_source_org_id || ':' || l_item_id,
                0, 1073741824
            ),
            lockmode          => DBMS_LOCK.X_MODE,
            timeout           => 10,
            release_on_commit => TRUE
        );
        IF l_lock NOT IN (0, 4) THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Another transfer of ' || UPPER(TRIM(p_item_code)) || ' from '
                || UPPER(TRIM(p_source_org_code)) || ' is in progress. Try '
                || 'again in a minute.',
                l_fields
            );
        END IF;

        availability(l_source_org_id, l_item_id, l_att, l_safety_stock);
        l_fields.put('SOURCE_ATT_QTY', l_att);
        IF l_att < p_transfer_qty THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Only ' || l_att || ' units are available to transact at '
                || UPPER(TRIM(p_source_org_code)) || ' after SLA reservations, '
                || 'so a transfer of ' || p_transfer_qty
                || ' units would breach those reservations.',
                l_fields
            );
        END IF;

        source_subinventory(
            l_source_org_id, l_item_id, l_source_subinv, l_subinv_att
        );
        IF l_subinv_att < p_transfer_qty THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'No subinventory at ' || UPPER(TRIM(p_source_org_code))
                || ' has ' || p_transfer_qty || ' units available to '
                || 'transact. The most in one subinventory is '
                || l_subinv_att || '.',
                l_fields
            );
        END IF;
        l_dest_subinv := receiving_subinventory(l_dest_org_id, l_dest_item_id);
        IF l_dest_subinv IS NULL THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Oracle Inventory has no active subinventory at '
                || UPPER(TRIM(p_dest_org_code)) || ' that can receive '
                || 'the item.',
                l_fields
            );
        END IF;

        SELECT transaction_type_id
          INTO l_txn_type_id
          FROM inv.mtl_transaction_types
         WHERE transaction_type_name = 'Direct Org Transfer';

        SELECT inv.mtl_material_transactions_s.NEXTVAL
          INTO l_header_id
          FROM dual;

        INSERT INTO inv.mtl_transactions_interface (
            transaction_header_id,
            transaction_interface_id,
            source_code,
            source_line_id,
            source_header_id,
            process_flag,
            transaction_mode,
            organization_id,
            inventory_item_id,
            subinventory_code,
            transaction_quantity,
            transaction_uom,
            transaction_date,
            transaction_type_id,
            transfer_organization,
            transfer_subinventory,
            last_update_date,
            last_updated_by,
            creation_date,
            created_by
        ) VALUES (
            l_header_id,
            l_header_id,
            'VOLTGUARD_AI',
            l_header_id,
            l_header_id,
            1,
            3,
            l_source_org_id,
            l_item_id,
            l_source_subinv,
            -1 * p_transfer_qty,
            l_uom_code,
            SYSDATE,
            l_txn_type_id,
            l_dest_org_id,
            l_dest_subinv,
            SYSDATE,
            fnd_global.user_id,
            SYSDATE,
            fnd_global.user_id
        );

        l_rc := inv_txn_manager_pub.process_transactions(
            p_api_version      => 1.0,
            p_init_msg_list    => fnd_api.g_true,
            p_commit           => fnd_api.g_false,
            p_validation_level => fnd_api.g_valid_level_full,
            x_return_status    => l_status,
            x_msg_count        => l_msg_count,
            x_msg_data         => l_msg_data,
            x_trans_count      => l_trans_count,
            p_table            => 1,
            p_header_id        => l_header_id
        );

        IF l_rc <> 0 OR l_status <> fnd_api.g_ret_sts_success THEN
            SELECT MAX(NVL(error_explanation, error_code))
              INTO l_error
              FROM inv.mtl_transactions_interface
             WHERE transaction_header_id = l_header_id;
            ROLLBACK;
            audit(c_unit, 'ERROR', NVL(l_error, l_msg_data));
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle Inventory rejected the transfer. The details are '
                || 'recorded in the MCP audit log.',
                l_fields
            );
        END IF;

        l_fields.put('TRANSACTION_HEADER_ID', l_header_id);
        l_fields.put('SOURCE_SUBINVENTORY', l_source_subinv);
        l_fields.put('DEST_SUBINVENTORY', l_dest_subinv);
        l_audit := l_fields.to_string;
        l_result := result_json(
            'SUCCESS', 'PROCESSED',
            'Oracle Inventory processed the inter-organization transfer.',
            l_fields
        );
        COMMIT;
        audit(c_unit, 'INFO', l_audit);
        RETURN l_result;
    EXCEPTION
        WHEN e_not_found THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'NOT_FOUND',
                'Oracle EBS has no item ' || UPPER(TRIM(p_item_code))
                || ' at hub ' || UPPER(TRIM(p_source_org_code)) || ' or '
                || UPPER(TRIM(p_dest_org_code)) || '.'
            );
        WHEN OTHERS THEN
            l_error := SQLERRM;
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle EBS could not complete the transfer. The details are '
                || 'recorded in the MCP audit log.'
            );
    END stage_interorg_transfer;

    FUNCTION stage_purchase_requisition (
        p_destination_org_code  IN VARCHAR2,
        p_item_code             IN VARCHAR2,
        p_quantity              IN NUMBER,
        p_unit_price            IN NUMBER,
        p_suggested_vendor_name IN VARCHAR2
    ) RETURN VARCHAR2 IS
        c_unit         CONSTANT VARCHAR2(30) := 'stage_purchase_requisition';
        l_dest_org_id  NUMBER;
        l_item_id      NUMBER;
        l_uom_code     VARCHAR2(3);
        l_vendor_id    NUMBER;
        l_vendor_name  APPS.VW_SCM_APPROVED_SUPPLIERS.supplier_name%TYPE;
        l_site_id      NUMBER;
        l_list_price   NUMBER;
        l_pending      NUMBER;
        l_preparer_id  NUMBER;
        l_location_id  NUMBER;
        l_ou_id        NUMBER;
        l_request_id   NUMBER;
        l_error        VARCHAR2(4000);
        l_audit        VARCHAR2(32767);
        l_result       VARCHAR2(32767);
        l_fields       JSON_OBJECT_T := JSON_OBJECT_T();
    BEGIN
        IF p_quantity IS NULL
           OR p_quantity <= 0
           OR p_quantity <> TRUNC(p_quantity) THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'Requisition quantity must be a positive whole number.'
            );
        END IF;
        IF p_unit_price IS NULL OR p_unit_price <= 0 THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'The unit price must be positive.'
            );
        END IF;
        IF TRIM(p_suggested_vendor_name) IS NULL THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'The requisition needs a suggested supplier.'
            );
        END IF;

        IF NOT session_ready THEN
            RETURN session_error(c_unit);
        END IF;
        l_dest_org_id := org_id(p_destination_org_code);
        item_in_org(l_dest_org_id, p_item_code, l_item_id, l_uom_code);

        -- The supplier must be an approved purchasing source of the item for
        -- the hub, and the price must be the item list price.
        BEGIN
            SELECT vendor_id, supplier_name, vendor_site_id, list_price_usd
              INTO l_vendor_id, l_vendor_name, l_site_id, l_list_price
              FROM APPS.VW_SCM_APPROVED_SUPPLIERS
             WHERE organization_id = l_dest_org_id
               AND inventory_item_id = l_item_id
               AND UPPER(supplier_name) = UPPER(TRIM(p_suggested_vendor_name))
             ORDER BY supplier_site_code
             FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RETURN result_json(
                    'ERROR', 'BUSINESS_RULE',
                    TRIM(p_suggested_vendor_name) || ' is not an approved '
                    || 'supplier of ' || UPPER(TRIM(p_item_code)) || ' for '
                    || UPPER(TRIM(p_destination_org_code)) || '.'
                );
        END;
        IF l_list_price IS NULL THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Oracle EBS has no list price for ' || UPPER(TRIM(p_item_code))
                || ' at ' || UPPER(TRIM(p_destination_org_code)) || '.'
            );
        END IF;
        IF p_unit_price <> l_list_price THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'The unit price must be the item list price of '
                || l_list_price || ' USD.'
            );
        END IF;

        -- Requisition Import runs as a concurrent request, so a staged row
        -- that it hasn't imported yet blocks a duplicate requisition.
        SELECT COUNT(*)
          INTO l_pending
          FROM po.po_requisitions_interface_all
         WHERE interface_source_code = 'VOLTGUARD_AI'
           AND destination_organization_id = l_dest_org_id
           AND item_id = l_item_id
           AND NVL(process_flag, 'PENDING') <> 'ERROR';
        IF l_pending > 0 THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'A requisition for ' || UPPER(TRIM(p_item_code)) || ' at '
                || UPPER(TRIM(p_destination_org_code)) || ' is still waiting '
                || 'for Requisition Import. Check the open requisitions in a '
                || 'minute before you stage another.'
            );
        END IF;

        SELECT MAX(fu.employee_id)
          INTO l_preparer_id
          FROM applsys.fnd_user fu
         WHERE fu.user_id = fnd_global.user_id;
        SELECT MAX(haou.location_id)
          INTO l_location_id
          FROM hr.hr_all_organization_units haou
         WHERE haou.organization_id = l_dest_org_id;
        SELECT MAX(ood.operating_unit)
          INTO l_ou_id
          FROM apps.org_organization_definitions ood
         WHERE ood.organization_id = l_dest_org_id;

        IF l_preparer_id IS NULL OR l_location_id IS NULL OR l_ou_id IS NULL
        THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Oracle EBS setup is incomplete for a requisition at '
                || UPPER(TRIM(p_destination_org_code)) || ': the EBS user '
                || 'needs an employee record and the hub needs a location '
                || 'and an operating unit.'
            );
        END IF;

        -- The demo stages the requisition as APPROVED, so a buyer sees it at
        -- once. In production, stage it as INCOMPLETE: Requisition Import
        -- then starts the Oracle Purchasing approval workflow (argument6).
        INSERT INTO po.po_requisitions_interface_all (
            interface_source_code,
            destination_type_code,
            authorization_status,
            preparer_id,
            item_id,
            quantity,
            unit_price,
            uom_code,
            destination_organization_id,
            deliver_to_location_id,
            deliver_to_requestor_id,
            need_by_date,
            suggested_vendor_id,
            suggested_vendor_site_id,
            suggested_vendor_name,
            org_id,
            creation_date,
            created_by
        ) VALUES (
            'VOLTGUARD_AI',
            'INVENTORY',
            'APPROVED',
            l_preparer_id,
            l_item_id,
            p_quantity,
            l_list_price,
            l_uom_code,
            l_dest_org_id,
            l_location_id,
            l_preparer_id,
            SYSDATE + 2,
            l_vendor_id,
            l_site_id,
            l_vendor_name,
            l_ou_id,
            SYSDATE,
            fnd_global.user_id
        );

        fnd_request.set_org_id(l_ou_id);
        l_request_id := fnd_request.submit_request(
            application => 'PO',
            program     => 'REQIMPORT',
            description => 'VoltGuard AI requisition import',
            start_time  => NULL,
            sub_request => FALSE,
            argument1   => 'VOLTGUARD_AI',
            argument2   => NULL,
            argument3   => 'ALL',
            argument4   => NULL,
            argument5   => 'N',
            argument6   => 'Y'
        );

        IF NVL(l_request_id, 0) <= 0 THEN
            l_error := fnd_message.get;
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle Purchasing did not accept the Requisition Import '
                || 'request. The MCP audit log records the details.'
            );
        END IF;

        l_fields.put('DESTINATION_ORG_CODE', UPPER(TRIM(p_destination_org_code)));
        l_fields.put('ITEM_CODE', UPPER(TRIM(p_item_code)));
        l_fields.put('QUANTITY', p_quantity);
        l_fields.put('UNIT_PRICE_USD', l_list_price);
        l_fields.put('SUGGESTED_VENDOR_NAME', l_vendor_name);
        l_fields.put('CONCURRENT_REQUEST_ID', l_request_id);
        l_audit := l_fields.to_string;
        l_result := result_json(
            'SUCCESS', 'SUBMITTED',
            'VoltGuard staged the requisition and submitted Requisition '
            || 'Import. Oracle Purchasing creates the requisition when the '
            || 'concurrent request completes.',
            l_fields
        );
        COMMIT;
        audit(c_unit, 'INFO', l_audit);
        RETURN l_result;
    EXCEPTION
        WHEN e_not_found THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'NOT_FOUND',
                'Oracle EBS has no item ' || UPPER(TRIM(p_item_code))
                || ' at hub ' || UPPER(TRIM(p_destination_org_code)) || '.'
            );
        WHEN OTHERS THEN
            l_error := SQLERRM;
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle EBS could not stage the requisition. The details are '
                || 'recorded in the MCP audit log.'
            );
    END stage_purchase_requisition;

    FUNCTION update_safety_stock (
        p_organization_code IN VARCHAR2,
        p_item_code         IN VARCHAR2,
        p_safety_stock_qty  IN NUMBER
    ) RETURN VARCHAR2 IS
        c_unit       CONSTANT VARCHAR2(30) := 'update_safety_stock';
        l_org_id     NUMBER;
        l_item_id    NUMBER;
        l_uom_code   VARCHAR2(3);
        l_att        NUMBER;
        l_previous   NUMBER;
        l_today      DATE;
        l_today_user NUMBER;
        l_original   inv_safety_stocks_pub.safety_stock_rec_type;
        l_new        inv_safety_stocks_pub.safety_stock_rec_type;
        l_status     VARCHAR2(1);
        l_msg_count  NUMBER;
        l_msg_data   VARCHAR2(4000);
        l_error      VARCHAR2(4000);
        l_audit      VARCHAR2(32767);
        l_result     VARCHAR2(32767);
        l_fields     JSON_OBJECT_T := JSON_OBJECT_T();
    BEGIN
        IF p_safety_stock_qty IS NULL
           OR p_safety_stock_qty < 0
           OR p_safety_stock_qty <> TRUNC(p_safety_stock_qty) THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'Safety stock must be zero or a positive whole number.'
            );
        END IF;

        IF NOT session_ready THEN
            RETURN session_error(c_unit);
        END IF;
        l_org_id := org_id(p_organization_code);
        item_in_org(l_org_id, p_item_code, l_item_id, l_uom_code);
        availability(l_org_id, l_item_id, l_att, l_previous);

        -- Oracle Inventory keeps one safety stock row per effectivity date:
        -- update today's row when it exists, otherwise create one. A row
        -- that a planner set today stays untouched, so the planner's level
        -- remains in Oracle Inventory and in the baseline.
        SELECT MAX(mss.effectivity_date),
               MAX(mss.last_updated_by) KEEP (
                   DENSE_RANK LAST ORDER BY mss.effectivity_date
               )
          INTO l_today, l_today_user
          FROM inv.mtl_safety_stocks mss
         WHERE mss.organization_id = l_org_id
           AND mss.inventory_item_id = l_item_id
           AND TRUNC(mss.effectivity_date) = TRUNC(SYSDATE);
        IF l_today_user <> fnd_global.user_id THEN
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'A planner set today''s safety stock for '
                || UPPER(TRIM(p_item_code)) || ' at '
                || UPPER(TRIM(p_organization_code)) || ', so the agent '
                || 'doesn''t overwrite it. Change it in Oracle Inventory '
                || 'instead.'
            );
        END IF;

        l_new.organization_id := l_org_id;
        l_new.inventory_item_id := l_item_id;
        l_new.effectivity_date := NVL(l_today, TRUNC(SYSDATE));
        l_new.safety_stock_code := 1;
        l_new.safety_stock_quantity := p_safety_stock_qty;
        fnd_msg_pub.initialize;
        IF l_today IS NULL THEN
            inv_safety_stocks_pub.create_safety_stock(
                x_return_status    => l_status,
                x_msg_count        => l_msg_count,
                x_msg_data         => l_msg_data,
                p_safety_stock_rec => l_new
            );
        ELSE
            l_original.organization_id := l_org_id;
            l_original.inventory_item_id := l_item_id;
            l_original.effectivity_date := l_today;
            inv_safety_stocks_pub.update_safety_stock(
                x_return_status             => l_status,
                x_msg_count                 => l_msg_count,
                x_msg_data                  => l_msg_data,
                p_original_safety_stock_rec => l_original,
                p_to_safety_stock_rec       => l_new
            );
        END IF;

        IF l_status <> fnd_api.g_ret_sts_success THEN
            l_error := NVL(
                fnd_msg_pub.get(fnd_msg_pub.g_last, fnd_api.g_false),
                l_msg_data
            );
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle Inventory rejected the safety stock update. The MCP '
                || 'audit log records the details.'
            );
        END IF;

        l_fields.put('ORGANIZATION_CODE', UPPER(TRIM(p_organization_code)));
        l_fields.put('ITEM_CODE', UPPER(TRIM(p_item_code)));
        l_fields.put('PREVIOUS_SAFETY_STOCK_QTY', l_previous);
        l_fields.put('SAFETY_STOCK_QTY', p_safety_stock_qty);
        l_fields.put('EFFECTIVITY_DATE', TO_CHAR(TRUNC(SYSDATE), 'YYYY-MM-DD'));
        l_audit := l_fields.to_string;
        l_result := result_json(
            'SUCCESS', 'UPDATED',
            'Oracle Inventory recorded the new safety stock.',
            l_fields
        );
        COMMIT;
        audit(c_unit, 'INFO', l_audit);
        RETURN l_result;
    EXCEPTION
        WHEN e_not_found THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'NOT_FOUND',
                'Oracle EBS has no item ' || UPPER(TRIM(p_item_code))
                || ' at hub ' || UPPER(TRIM(p_organization_code)) || '.'
            );
        WHEN OTHERS THEN
            l_error := SQLERRM;
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle EBS could not update the safety stock. The MCP audit '
                || 'log records the details.'
            );
    END update_safety_stock;

    -- Records a resolution detail on a notification as a runtime text
    -- attribute, which Oracle Workflow keeps with the closed notification.
    PROCEDURE add_text_attribute (
        p_notification_id IN NUMBER,
        p_name            IN VARCHAR2,
        p_value           IN VARCHAR2
    ) IS
    BEGIN
        wf_notification.addattr(nid => p_notification_id, aname => p_name);
        wf_notification.setattrtext(
            nid    => p_notification_id,
            aname  => p_name,
            avalue => p_value
        );
    END add_text_attribute;

    FUNCTION close_workflow_notification (
        p_notification_id IN NUMBER,
        p_action          IN VARCHAR2,
        p_resolution_note IN VARCHAR2
    ) RETURN VARCHAR2 IS
        c_unit   CONSTANT VARCHAR2(30) := 'close_workflow_notification';
        l_action CONSTANT VARCHAR2(32767) := UPPER(TRIM(p_action));
        l_status VARCHAR2(8);
        l_error  VARCHAR2(4000);
        l_audit  VARCHAR2(32767);
        l_result VARCHAR2(32767);
        l_fields JSON_OBJECT_T := JSON_OBJECT_T();
    BEGIN
        IF p_notification_id IS NULL OR TRIM(p_resolution_note) IS NULL THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'Provide a notification ID and a resolution note.'
            );
        END IF;
        IF l_action IS NULL OR l_action NOT IN ('MITIGATED', 'ACKNOWLEDGED')
        THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'The action must be MITIGATED or ACKNOWLEDGED.'
            );
        END IF;
        IF LENGTH(p_resolution_note) > c_max_note_chars THEN
            RETURN result_json(
                'ERROR', 'INVALID_INPUT',
                'Keep the resolution note within ' || c_max_note_chars
                || ' characters.'
            );
        END IF;

        IF NOT session_ready THEN
            RETURN session_error(c_unit);
        END IF;
        -- Only VoltGuard resiliency alerts, which are FYI notifications.
        BEGIN
            SELECT status
              INTO l_status
              FROM applsys.wf_notifications
             WHERE notification_id = p_notification_id
               AND message_type = c_alert_message_type
               AND message_name = c_alert_message_name;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE e_not_found;
        END;

        IF l_status <> 'OPEN' THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'BUSINESS_RULE',
                'Workflow notification ' || p_notification_id
                || ' is already ' || l_status || '.'
            );
        END IF;

        add_text_attribute(p_notification_id, 'RESOLUTION_ACTION', l_action);
        add_text_attribute(
            p_notification_id, 'RESOLUTION_NOTE', p_resolution_note
        );
        wf_notification.close(
            nid       => p_notification_id,
            responder => fnd_global.user_name
        );

        l_fields.put('NOTIFICATION_ID', p_notification_id);
        l_fields.put('ACTION', l_action);
        l_fields.put('RESPONDER', fnd_global.user_name);
        l_fields.put('RESOLUTION_NOTE', p_resolution_note);
        l_audit := l_fields.to_string;
        l_result := result_json(
            'SUCCESS', 'CLOSED',
            'Oracle Workflow closed the notification.',
            l_fields
        );
        COMMIT;
        audit(c_unit, 'INFO', l_audit);
        RETURN l_result;
    EXCEPTION
        WHEN e_not_found THEN
            ROLLBACK;
            RETURN result_json(
                'ERROR', 'NOT_FOUND',
                'Oracle Workflow has no VoltGuard resiliency alert '
                || p_notification_id || '.'
            );
        WHEN OTHERS THEN
            l_error := SQLERRM;
            ROLLBACK;
            audit(c_unit, 'ERROR', l_error);
            RETURN result_json(
                'ERROR', 'EBS_API_ERROR',
                'Oracle Workflow could not close the notification. The MCP '
                || 'audit log records the details.'
            );
    END close_workflow_notification;

END GE_EBS_SCM_TOOLS;
/
