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
-- Oracle E-Business Suite supply chain resiliency views (APPS schema).
-- The agent reads these views through the MCP Toolbox `ebs_execute_sql` tool.
-- The views never substitute default values: when Oracle EBS holds no source
-- row, the column is NULL.
-- Quantities aggregate to 0 only when no on-hand, reservation, or safety
-- stock rows exist, which is the Oracle Inventory meaning of "no stock".
-- =============================================================================

-- 1. APPS.VW_SCM_NET_AVAILABILITY
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_NET_AVAILABILITY AS
WITH onhand_summary AS (
    SELECT
        moqd.organization_id,
        moqd.inventory_item_id,
        SUM(moqd.primary_transaction_quantity) AS raw_onhand_qty,
        -- Only stock in reservable subinventories can serve demand.
        SUM(
            CASE
                WHEN msi.reservable_type = 1
                    THEN moqd.primary_transaction_quantity
                ELSE 0
            END
        ) AS reservable_onhand_qty
    FROM
        inv.mtl_onhand_quantities_detail moqd
        INNER JOIN inv.mtl_secondary_inventories msi
            ON msi.organization_id = moqd.organization_id
            AND msi.secondary_inventory_name = moqd.subinventory_code
    GROUP BY
        moqd.organization_id,
        moqd.inventory_item_id
),
reservation_summary AS (
    SELECT
        mr.organization_id,
        mr.inventory_item_id,
        SUM(mr.primary_reservation_quantity) AS sla_reserved_qty
    FROM
        inv.mtl_reservations mr
    GROUP BY
        mr.organization_id,
        mr.inventory_item_id
),
safety_stock_summary AS (
    SELECT
        mss.organization_id,
        mss.inventory_item_id,
        MAX(mss.safety_stock_quantity) KEEP (
            DENSE_RANK LAST ORDER BY mss.effectivity_date
        ) AS safety_stock_qty
    FROM
        inv.mtl_safety_stocks mss
    WHERE
        mss.effectivity_date <= SYSDATE
    GROUP BY
        mss.organization_id,
        mss.inventory_item_id
),
-- The planner's level: the latest effective safety stock whose quantity the
-- agent's Oracle EBS user didn't set (LAST_UPDATED_BY, so a planner's edit of
-- an agent row counts as the planner's). Surge targets start from it, so a
-- confirmed surge level never compounds. update_safety_stock never
-- overwrites a row that a planner set today.
planner_safety_stock AS (
    SELECT
        mss.organization_id,
        mss.inventory_item_id,
        MAX(mss.safety_stock_quantity) KEEP (
            DENSE_RANK LAST ORDER BY mss.effectivity_date
        ) AS baseline_safety_stock_qty
    FROM
        inv.mtl_safety_stocks mss
    WHERE
        mss.effectivity_date <= SYSDATE
        AND mss.last_updated_by NOT IN (
            SELECT fu.user_id
            FROM applsys.fnd_user fu
            WHERE fu.user_name = 'VOLTGUARD_AGENT'
        )
    GROUP BY
        mss.organization_id,
        mss.inventory_item_id
)
SELECT
    mp.organization_id,
    mp.organization_code,
    haou.name AS organization_name,
    msib.inventory_item_id,
    msib.segment1 AS item_code,
    msib.description AS item_description,
    msib.primary_uom_code AS uom_code,
    msib.list_price_per_unit AS unit_list_price_usd,
    NVL(oh.raw_onhand_qty, 0) AS raw_onhand_qty,
    NVL(rs.sla_reserved_qty, 0) AS sla_reserved_qty,
    NVL(ss.safety_stock_qty, 0) AS safety_stock_qty,
    -- NULL when only the agent has set the hub's safety stock for the item.
    NVL2(ss.safety_stock_qty, ps.baseline_safety_stock_qty, 0)
        AS baseline_safety_stock_qty,
    GREATEST(
        NVL(oh.reservable_onhand_qty, 0) - NVL(rs.sla_reserved_qty, 0),
        0
    ) AS available_to_transact_qty,
    SYSTIMESTAMP AS snapshot_timestamp
FROM
    inv.mtl_system_items_b msib
    INNER JOIN inv.mtl_parameters mp
        ON mp.organization_id = msib.organization_id
    LEFT JOIN hr.hr_all_organization_units haou
        ON haou.organization_id = mp.organization_id
    LEFT JOIN onhand_summary oh
        ON oh.organization_id = msib.organization_id
        AND oh.inventory_item_id = msib.inventory_item_id
    LEFT JOIN reservation_summary rs
        ON rs.organization_id = msib.organization_id
        AND rs.inventory_item_id = msib.inventory_item_id
    LEFT JOIN safety_stock_summary ss
        ON ss.organization_id = msib.organization_id
        AND ss.inventory_item_id = msib.inventory_item_id
    LEFT JOIN planner_safety_stock ps
        ON ps.organization_id = msib.organization_id
        AND ps.inventory_item_id = msib.inventory_item_id
WHERE
    msib.inventory_item_status_code = 'Active'
    -- An item master organization defines the item; it counts as a hub only
    -- when it holds stock of the item.
    AND (
        mp.organization_id <> mp.master_organization_id
        OR oh.organization_id IS NOT NULL
    );

-- 2. APPS.VW_SCM_SLA_CONTRACT_LOCKS
-- Customer, tier, and breach penalty come from the sales order when one
-- exists, otherwise from the reservation descriptive flexfield
-- (ATTRIBUTE1 customer, ATTRIBUTE2 penalty in USD, ATTRIBUTE3 tier).
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_SLA_CONTRACT_LOCKS AS
SELECT
    mr.reservation_id,
    mr.organization_id,
    mp.organization_code,
    mr.inventory_item_id,
    msib.segment1 AS item_code,
    msib.description AS item_description,
    mr.demand_source_header_id,
    mr.demand_source_line_id AS order_line_id,
    ooha.header_id AS order_header_id,
    ooha.order_number AS sales_order_number,
    hca.cust_account_id,
    COALESCE(hp.party_name, mr.attribute1, mr.demand_source_name)
        AS customer_party_name,
    COALESCE(ooha.attribute1, mr.attribute3) AS sla_contract_tier,
    TO_NUMBER(
        COALESCE(ooha.attribute2, mr.attribute2)
        DEFAULT NULL ON CONVERSION ERROR
    ) AS breach_penalty_usd,
    mr.primary_reservation_quantity AS reserved_qty,
    mr.requirement_date,
    mr.subinventory_code
FROM
    inv.mtl_reservations mr
    INNER JOIN inv.mtl_parameters mp
        ON mp.organization_id = mr.organization_id
    INNER JOIN inv.mtl_system_items_b msib
        ON msib.organization_id = mr.organization_id
        AND msib.inventory_item_id = mr.inventory_item_id
    -- Only sales order (2) and internal order (8) reservations point at an
    -- order line.
    LEFT JOIN ont.oe_order_lines_all oola
        ON mr.demand_source_type_id IN (2, 8)
        AND oola.line_id = mr.demand_source_line_id
    LEFT JOIN ont.oe_order_headers_all ooha
        ON ooha.header_id = oola.header_id
    LEFT JOIN ar.hz_cust_accounts hca
        ON hca.cust_account_id = ooha.sold_to_org_id
    LEFT JOIN ar.hz_parties hp
        ON hp.party_id = hca.party_id;

-- 3. APPS.VW_SCM_BURN_RATE_AND_MRP
-- Burn counts only sales order (2) and internal order (8) issues from stores
-- (action 1), never transfers, subinventory moves, or adjustments. MRP
-- columns read the uncancelled planned orders of each hub's latest completed
-- plan.
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_BURN_RATE_AND_MRP AS
WITH trailing_7d_issues AS (
    SELECT
        mmt.organization_id,
        mmt.inventory_item_id,
        ROUND(SUM(ABS(mmt.primary_quantity)) / 7.0, 2)
            AS trailing_7d_daily_burn_qty
    FROM
        inv.mtl_material_transactions mmt
    WHERE
        mmt.transaction_date >= SYSDATE - 7
        AND mmt.primary_quantity < 0
        AND mmt.transaction_action_id = 1
        AND mmt.transaction_source_type_id IN (2, 8)
    GROUP BY
        mmt.organization_id,
        mmt.inventory_item_id
),
latest_plan AS (
    SELECT
        mp.organization_id,
        MAX(mp.compile_designator) KEEP (
            DENSE_RANK LAST ORDER BY mp.plan_completion_date
        ) AS compile_designator
    FROM
        mrp.mrp_plans mp
    WHERE
        mp.plan_completion_date IS NOT NULL
    GROUP BY
        mp.organization_id
),
mrp_summary AS (
    SELECT
        mrp.organization_id,
        mrp.inventory_item_id,
        MIN(mrp.new_schedule_date) AS next_mrp_dock_date,
        SUM(mrp.new_order_quantity) AS planned_mrp_order_qty
    FROM
        mrp.mrp_recommendations mrp
        INNER JOIN latest_plan lp
            ON lp.organization_id = mrp.organization_id
            AND lp.compile_designator = mrp.compile_designator
    WHERE
        mrp.order_type = 5
        AND mrp.disposition_status_type = 1
    GROUP BY
        mrp.organization_id,
        mrp.inventory_item_id
)
SELECT
    vna.organization_id,
    vna.organization_code,
    vna.inventory_item_id,
    vna.item_code,
    vna.raw_onhand_qty,
    vna.sla_reserved_qty,
    vna.available_to_transact_qty,
    t7.trailing_7d_daily_burn_qty AS baseline_daily_burn_qty,
    msib.full_lead_time AS static_mrp_lead_time_days,
    mrps.planned_mrp_order_qty,
    mrps.next_mrp_dock_date
FROM
    APPS.VW_SCM_NET_AVAILABILITY vna
    INNER JOIN inv.mtl_system_items_b msib
        ON msib.organization_id = vna.organization_id
        AND msib.inventory_item_id = vna.inventory_item_id
    LEFT JOIN trailing_7d_issues t7
        ON t7.organization_id = vna.organization_id
        AND t7.inventory_item_id = vna.inventory_item_id
    LEFT JOIN mrp_summary mrps
        ON mrps.organization_id = vna.organization_id
        AND mrps.inventory_item_id = vna.inventory_item_id;

-- 4. APPS.VW_SCM_ACTIVE_POS
-- One row per open shipment of an approved standard purchase order. A
-- cancelled, closed, or received shipment is not inbound supply. The unit
-- price is in the purchase order currency. Supply risk attributes come from
-- the purchase order header descriptive flexfield: ATTRIBUTE5 corridor delay
-- days, ATTRIBUTE6 plant buffer days, and ATTRIBUTE7 line-stop exposure in
-- USD.
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_ACTIVE_POS AS
SELECT
    pha.po_header_id,
    pha.segment1 AS po_number,
    pha.authorization_status,
    pla.po_line_id,
    pla.item_id AS inventory_item_id,
    msib.segment1 AS item_code,
    COALESCE(msib.description, pla.item_description) AS item_description,
    plla.ship_to_organization_id AS organization_id,
    mp.organization_code,
    plla.quantity AS ordered_qty,
    plla.quantity - NVL(plla.quantity_received, 0)
        - NVL(plla.quantity_cancelled, 0) AS open_qty,
    pla.unit_price,
    pha.currency_code,
    plla.need_by_date,
    plla.promised_date,
    aps.vendor_id,
    aps.vendor_name AS supplier_name,
    TO_NUMBER(pha.attribute5 DEFAULT NULL ON CONVERSION ERROR)
        AS corridor_delay_days,
    TO_NUMBER(pha.attribute6 DEFAULT NULL ON CONVERSION ERROR)
        AS plant_buffer_days,
    TO_NUMBER(pha.attribute7 DEFAULT NULL ON CONVERSION ERROR)
        AS line_stop_exposure_usd
FROM
    po.po_headers_all pha
    INNER JOIN po.po_lines_all pla
        ON pla.po_header_id = pha.po_header_id
    INNER JOIN po.po_line_locations_all plla
        ON plla.po_line_id = pla.po_line_id
    LEFT JOIN inv.mtl_parameters mp
        ON mp.organization_id = plla.ship_to_organization_id
    LEFT JOIN inv.mtl_system_items_b msib
        ON msib.inventory_item_id = pla.item_id
        AND msib.organization_id = plla.ship_to_organization_id
    LEFT JOIN ap.ap_suppliers aps
        ON aps.vendor_id = pha.vendor_id
WHERE
    pha.type_lookup_code = 'STANDARD'
    AND pha.authorization_status = 'APPROVED'
    AND NVL(pha.cancel_flag, 'N') = 'N'
    AND NVL(pha.closed_code, 'OPEN') = 'OPEN'
    AND NVL(pla.cancel_flag, 'N') = 'N'
    AND NVL(plla.cancel_flag, 'N') = 'N'
    AND NVL(plla.closed_code, 'OPEN')
        NOT IN ('CLOSED', 'CLOSED FOR RECEIVING', 'FINALLY CLOSED')
    AND plla.quantity - NVL(plla.quantity_received, 0)
        - NVL(plla.quantity_cancelled, 0) > 0;

-- 5. APPS.VW_SCM_APPROVED_SUPPLIERS
-- Approved supplier list entries that Oracle Purchasing can order from: an
-- Approved status, an enabled and active supplier, and an active purchasing
-- site. A global entry (USING_ORGANIZATION_ID = -1) applies to every
-- organization that holds the item. The item list price prices purchase
-- requisitions, and the requisition writeback reads this view.
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_APPROVED_SUPPLIERS AS
SELECT
    mp.organization_id,
    mp.organization_code,
    msib.inventory_item_id,
    msib.segment1 AS item_code,
    msib.description AS item_description,
    aps.vendor_id,
    aps.vendor_name AS supplier_name,
    apss.vendor_site_id,
    apss.vendor_site_code AS supplier_site_code,
    apss.city AS supplier_city,
    apss.state AS supplier_state,
    pas.status AS asl_status,
    msib.list_price_per_unit AS list_price_usd
FROM
    po.po_approved_supplier_list asl
    INNER JOIN po.po_asl_statuses pas
        ON pas.status_id = asl.asl_status_id
    INNER JOIN ap.ap_suppliers aps
        ON aps.vendor_id = asl.vendor_id
    INNER JOIN ap.ap_supplier_sites_all apss
        ON apss.vendor_site_id = asl.vendor_site_id
    INNER JOIN inv.mtl_system_items_b msib
        ON msib.inventory_item_id = asl.item_id
        AND (
            asl.using_organization_id = -1
            OR msib.organization_id = asl.using_organization_id
        )
    INNER JOIN inv.mtl_parameters mp
        ON mp.organization_id = msib.organization_id
WHERE
    NVL(asl.disable_flag, 'N') = 'N'
    AND UPPER(pas.status) = 'APPROVED'
    AND aps.enabled_flag = 'Y'
    AND NVL(aps.start_date_active, SYSDATE) <= SYSDATE
    AND NVL(aps.end_date_active, SYSDATE + 1) > SYSDATE
    AND apss.purchasing_site_flag = 'Y'
    AND NVL(apss.inactive_date, SYSDATE + 1) > SYSDATE;

-- 6. APPS.VW_SCM_OPEN_NOTIFICATIONS
-- Open VoltGuard resiliency alerts only (message INVSCM /
-- VOLTGUARD_RESILIENCY_ALERT), never the other Oracle Workflow notifications
-- of the instance. Item, hub, purchase order, and severity come from the
-- notification attributes ITEM_CODE, ORGANIZATION_CODE, PO_NUMBER, and
-- SEVERITY.
CREATE OR REPLACE FORCE VIEW APPS.VW_SCM_OPEN_NOTIFICATIONS AS
SELECT
    wn.notification_id,
    wn.message_type,
    wn.message_name,
    wn.recipient_role,
    wn.status,
    wn.subject,
    wn.begin_date,
    wn.due_date,
    MAX(CASE WHEN wna.name = 'ITEM_CODE' THEN wna.text_value END)
        AS item_code,
    MAX(CASE WHEN wna.name = 'ORGANIZATION_CODE' THEN wna.text_value END)
        AS organization_code,
    MAX(CASE WHEN wna.name = 'PO_NUMBER' THEN wna.text_value END)
        AS related_po_number,
    MAX(CASE WHEN wna.name = 'SEVERITY' THEN wna.text_value END)
        AS alert_severity
FROM
    applsys.wf_notifications wn
    LEFT JOIN applsys.wf_notification_attributes wna
        ON wna.notification_id = wn.notification_id
WHERE
    wn.status = 'OPEN'
    AND wn.message_type = 'INVSCM'
    AND wn.message_name = 'VOLTGUARD_RESILIENCY_ALERT'
GROUP BY
    wn.notification_id,
    wn.message_type,
    wn.message_name,
    wn.recipient_role,
    wn.status,
    wn.subject,
    wn.begin_date,
    wn.due_date;
