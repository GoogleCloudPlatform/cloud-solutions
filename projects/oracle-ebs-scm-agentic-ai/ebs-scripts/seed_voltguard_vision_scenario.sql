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
-- Idempotent seed for the VoltGuard supply chain resiliency scenario on the
-- Oracle E-Business Suite R12.2 Vision database. Run it as APPS, after
-- install_voltguard_agent_user.sql. It reads the Vision setup but never
-- changes it: it creates six US hub organizations in the Vision Operations
-- ledger (USD), modeled on Seattle Manufacturing (M1), adds the scenario items
-- to the item master, and seeds data only in the hubs. Re-running it restores
-- the values below.
--
--   * Miami DC (MIA): 190 VG-GEN-7500 on-hand, 0 reserved (190 ATT), and no
--     VG-SURGE-PRO. Baseline burn of 20.8/day surges 2.4x to 50.0/day (3.8
--     days to stockout).
--   * Atlanta Hub (ATL): 400 VG-GEN-7500 on-hand, 360 reserved for the
--     Southeast Hospital Care Alliance SLA ($250,000 breach penalty), 40 ATT.
--   * Dallas Hub (DAL): 250 VG-GEN-7500 on-hand, 0 reserved (250 ATT), the
--     optimal source for a 150-unit transfer to Miami DC ($1,800 freight,
--     $52,500 protected revenue, +$50,700 net benefit).
--   * Chicago Hub (ORD): 320 VG-GEN-7500 on-hand, 280 reserved for the Midwest
--     Municipal Grid SLA (40 ATT).
--   * Phoenix Hub (PHX): 180 VG-GEN-7500 on-hand, 30 reserved for the
--     Southwest Data Center SLA (150 ATT, with a long-haul option at $3,450
--     freight).
--     The planner's safety stock is 50, but an earlier agent writeback raised
--     it to 80 for a surge that has ended, so the agent offers to return it.
--   * Newark Hub (EWR): 290 VG-GEN-7500 on-hand, 265 reserved for the
--     Northeast Tri-State Transit SLA (25 ATT).
--   * VG-SURGE-PRO at every hub, with on-hand at or below safety stock, so no
--     hub has surplus, and Consolidated Supplies (Plantation, Florida) as the
--     approved supplier in the approved supplier list.
--   * Secondary scenario: PO 40912 from Advantage Corp's US site, in USD,
--     inbound VG-SURGE-PRO for Miami DC with a 3.0-day corridor delay that
--     breaches the 1.5-day plant buffer ($1.2M exposure), and workflow
--     notification 90412 for Maya Lin (MLIN) about the delay.
--   * No open requisitions from confirmed agent writebacks: a re-run removes
--     the requisitions that the agent imported, unless a purchase order or a
--     funds reservation already uses them.
--
-- Every hub has its own location, cost group, the FGI subinventory, and an
-- open period for the current month, every source hub has a direct shipping
-- network to Miami DC, and the items carry the template item's categories, so
-- that confirmed transfers post in Oracle Inventory and requisitions import in
-- Oracle Purchasing.
-- =============================================================================

DECLARE
    -- The seed works as the Vision Operations inventory planner and copies
    -- the setup of the Vision template organization into every hub.
    c_seed_user    CONSTANT VARCHAR2(100) := 'OPERATIONS';
    c_seed_resp    CONSTANT VARCHAR2(30) := 'INVENTORY_VISION_OPERATIONS';
    c_template_org CONSTANT VARCHAR2(3) := 'M1';
    c_miami        CONSTANT VARCHAR2(3) := 'MIA';
    c_po_id        CONSTANT NUMBER := 940912;
    c_po_number    CONSTANT VARCHAR2(20) := '40912';
    c_po_vendor    CONSTANT VARCHAR2(240) := 'Advantage Corp';
    c_po_site      CONSTANT VARCHAR2(15) := 'ADVANTAGE - US';
    c_alert_id     CONSTANT NUMBER := 90412;
    c_asl_vendor   CONSTANT VARCHAR2(240) := 'Consolidated Supplies';
    c_asl_site     CONSTANT VARCHAR2(15) := 'PLANTATION-CTR';
    -- Requisition Import source of the agent's requisition writeback.
    c_req_source   CONSTANT VARCHAR2(25) := 'VOLTGUARD_AI';
    -- Oracle EBS user of the agent's writebacks.
    c_agent_user   CONSTANT VARCHAR2(100) := 'VOLTGUARD_AGENT';
    v_tpl_org_id   NUMBER;
    v_master_id    NUMBER;
    v_tpl_cg_id    NUMBER;
    v_ledger_id    VARCHAR2(150);
    v_ou_id        NUMBER;

    FUNCTION org_id (p_org_code IN VARCHAR2) RETURN NUMBER IS
        v_org_id NUMBER;
    BEGIN
        SELECT organization_id
          INTO v_org_id
          FROM inv.mtl_parameters
         WHERE organization_code = p_org_code;
        RETURN v_org_id;
    END org_id;

    -- Every hub uses the item ID that Miami DC holds for the item number.
    FUNCTION item_id (p_item_code IN VARCHAR2) RETURN NUMBER IS
        v_miami_id NUMBER := org_id(c_miami);
        v_item_id  NUMBER;
    BEGIN
        SELECT inventory_item_id
          INTO v_item_id
          FROM inv.mtl_system_items_b
         WHERE organization_id = v_miami_id
           AND segment1 = p_item_code;
        RETURN v_item_id;
    END item_id;

    -- Finds a supplier site in the operating unit of the template
    -- organization.
    PROCEDURE find_supplier_site (
        p_vendor_name IN VARCHAR2,
        p_site_code   IN VARCHAR2,
        x_vendor_id   OUT NUMBER,
        x_site_id     OUT NUMBER
    ) IS
    BEGIN
        SELECT v.vendor_id, s.vendor_site_id
          INTO x_vendor_id, x_site_id
          FROM ap.ap_suppliers v
          JOIN ap.ap_supplier_sites_all s
            ON s.vendor_id = v.vendor_id
         WHERE v.vendor_name = p_vendor_name
           AND s.vendor_site_code = p_site_code
           AND s.org_id = v_ou_id;
    END find_supplier_site;

    -- Starts the Oracle EBS session as the seed user, on an active assignment
    -- of the seed responsibility.
    PROCEDURE init_seed_context IS
    BEGIN
        FOR r IN (
            SELECT urg.user_id,
                   urg.responsibility_id,
                   urg.responsibility_application_id
              FROM apps.fnd_user_resp_groups urg
              JOIN applsys.fnd_user fu
                ON fu.user_id = urg.user_id
              JOIN applsys.fnd_responsibility fr
                ON fr.responsibility_id = urg.responsibility_id
               AND fr.application_id = urg.responsibility_application_id
             WHERE fu.user_name = c_seed_user
               AND fr.responsibility_key = c_seed_resp
               AND SYSDATE BETWEEN urg.start_date
                               AND NVL(urg.end_date, SYSDATE + 1)
        ) LOOP
            fnd_global.apps_initialize(
                user_id      => r.user_id,
                resp_id      => r.responsibility_id,
                resp_appl_id => r.responsibility_application_id
            );
            mo_global.init('INV');
            RETURN;
        END LOOP;
        raise_application_error(
            -20001,
            c_seed_user || ' has no active ' || c_seed_resp || ' assignment.'
        );
    END init_seed_context;

    -- Creates a hub as a copy of the template organization: same ledger,
    -- legal entity, operating unit, chart of accounts, item master, and
    -- costing, with its own cost group and FGI subinventory.
    PROCEDURE ensure_hub (
        p_org_code IN VARCHAR2,
        p_org_name IN VARCHAR2
    ) IS
        TYPE t_names IS TABLE OF hr.hr_all_organization_units_tl%ROWTYPE;
        TYPE t_infos IS TABLE OF hr.hr_organization_information%ROWTYPE;
        v_count  NUMBER;
        v_org_id NUMBER;
        v_cg_id  NUMBER;
        v_org    hr.hr_all_organization_units%ROWTYPE;
        v_names  t_names;
        v_infos  t_infos;
        v_cg     bom.cst_cost_groups%ROWTYPE;
        v_cg_acc bom.cst_cost_group_accounts%ROWTYPE;
        v_params inv.mtl_parameters%ROWTYPE;
        v_subinv inv.mtl_secondary_inventories%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM inv.mtl_parameters
         WHERE organization_code = p_org_code;
        IF v_count > 0 THEN
            RETURN;
        END IF;
        v_org_id := hr.hr_organization_units_s.NEXTVAL;
        v_cg_id := bom.cst_cost_groups_s.NEXTVAL;

        SELECT *
          INTO v_org
          FROM hr.hr_all_organization_units
         WHERE organization_id = v_tpl_org_id;
        v_org.organization_id := v_org_id;
        v_org.name := p_org_name;
        v_org.created_by := fnd_global.user_id;
        v_org.creation_date := SYSDATE;
        v_org.last_updated_by := fnd_global.user_id;
        v_org.last_update_date := SYSDATE;
        INSERT INTO hr.hr_all_organization_units VALUES v_org;

        SELECT *
          BULK COLLECT INTO v_names
          FROM hr.hr_all_organization_units_tl
         WHERE organization_id = v_tpl_org_id;
        FOR i IN 1 .. v_names.COUNT LOOP
            v_names(i).organization_id := v_org_id;
            v_names(i).name := p_org_name;
            v_names(i).created_by := fnd_global.user_id;
            v_names(i).creation_date := SYSDATE;
            v_names(i).last_updated_by := fnd_global.user_id;
            v_names(i).last_update_date := SYSDATE;
            INSERT INTO hr.hr_all_organization_units_tl VALUES v_names(i);
        END LOOP;

        -- The Inventory classification and the accounting information put the
        -- hub in the ledger and operating unit of the template organization.
        SELECT *
          BULK COLLECT INTO v_infos
          FROM hr.hr_organization_information
         WHERE organization_id = v_tpl_org_id
           AND (
               org_information_context = 'Accounting Information'
               OR (
                   org_information_context = 'CLASS'
                   AND org_information1 = 'INV'
               )
           );
        FOR i IN 1 .. v_infos.COUNT LOOP
            v_infos(i).org_information_id :=
                hr.hr_organization_information_s.NEXTVAL;
            v_infos(i).organization_id := v_org_id;
            v_infos(i).created_by := fnd_global.user_id;
            v_infos(i).creation_date := SYSDATE;
            v_infos(i).last_updated_by := fnd_global.user_id;
            v_infos(i).last_update_date := SYSDATE;
            INSERT INTO hr.hr_organization_information VALUES v_infos(i);
        END LOOP;

        SELECT *
          INTO v_cg
          FROM bom.cst_cost_groups
         WHERE cost_group_id = v_tpl_cg_id;
        v_cg.cost_group_id := v_cg_id;
        v_cg.cost_group := 'CG-' || v_cg_id;
        v_cg.organization_id := v_org_id;
        v_cg.created_by := fnd_global.user_id;
        v_cg.creation_date := SYSDATE;
        v_cg.last_updated_by := fnd_global.user_id;
        v_cg.last_update_date := SYSDATE;
        INSERT INTO bom.cst_cost_groups VALUES v_cg;

        SELECT *
          INTO v_cg_acc
          FROM bom.cst_cost_group_accounts
         WHERE cost_group_id = v_tpl_cg_id
           AND organization_id = v_tpl_org_id;
        v_cg_acc.cost_group_id := v_cg_id;
        v_cg_acc.organization_id := v_org_id;
        v_cg_acc.created_by := fnd_global.user_id;
        v_cg_acc.creation_date := SYSDATE;
        v_cg_acc.last_updated_by := fnd_global.user_id;
        v_cg_acc.last_update_date := SYSDATE;
        INSERT INTO bom.cst_cost_group_accounts VALUES v_cg_acc;

        SELECT *
          INTO v_params
          FROM inv.mtl_parameters
         WHERE organization_id = v_tpl_org_id;
        v_params.organization_id := v_org_id;
        v_params.organization_code := p_org_code;
        v_params.cost_organization_id := v_org_id;
        v_params.default_cost_group_id := v_cg_id;
        v_params.created_by := fnd_global.user_id;
        v_params.creation_date := SYSDATE;
        v_params.last_updated_by := fnd_global.user_id;
        v_params.last_update_date := SYSDATE;
        INSERT INTO inv.mtl_parameters VALUES v_params;

        SELECT *
          INTO v_subinv
          FROM inv.mtl_secondary_inventories
         WHERE organization_id = v_tpl_org_id
           AND secondary_inventory_name = 'FGI';
        v_subinv.organization_id := v_org_id;
        v_subinv.default_cost_group_id := v_cg_id;
        v_subinv.created_by := fnd_global.user_id;
        v_subinv.creation_date := SYSDATE;
        v_subinv.last_updated_by := fnd_global.user_id;
        v_subinv.last_update_date := SYSDATE;
        INSERT INTO inv.mtl_secondary_inventories VALUES v_subinv;
    END ensure_hub;

    -- Oracle Purchasing delivers only to a location of the destination
    -- organization: gives the hub its own copy of the template location.
    -- E-Business Tax derives the tax jurisdiction of a requisition from the
    -- geography references of that location.
    PROCEDURE ensure_hub_location (p_org_code IN VARCHAR2) IS
        TYPE t_names IS TABLE OF hr.hr_locations_all_tl%ROWTYPE;
        v_org_id   NUMBER := org_id(p_org_code);
        v_org_name hr.hr_all_organization_units.name%TYPE;
        v_tpl_id   NUMBER;
        v_loc      hr.hr_locations_all%ROWTYPE;
        v_names    t_names;
        v_count    NUMBER;
        v_status   VARCHAR2(1);
        v_msg_cnt  NUMBER;
        v_msg      VARCHAR2(4000);
    BEGIN
        SELECT hl.*
          INTO v_loc
          FROM hr.hr_all_organization_units haou
          JOIN hr.hr_locations_all hl
            ON hl.location_id = haou.location_id
         WHERE haou.organization_id = v_org_id;
        IF NVL(v_loc.inventory_organization_id, -1) <> v_org_id THEN
            SELECT name
              INTO v_org_name
              FROM hr.hr_all_organization_units
             WHERE organization_id = v_org_id;

            v_tpl_id := v_loc.location_id;
            v_loc.location_id := hr.hr_locations_s.NEXTVAL;
            v_loc.location_code := p_org_code || '- ' || v_org_name;
            v_loc.description := v_org_name;
            v_loc.inventory_organization_id := v_org_id;
            -- The hub needs no map coordinates, and the copied coordinates
            -- would fail the spatial index of the locations table at commit.
            v_loc.geometry := NULL;
            IF v_loc.ship_to_location_id = v_tpl_id THEN
                v_loc.ship_to_location_id := v_loc.location_id;
            END IF;
            v_loc.created_by := fnd_global.user_id;
            v_loc.creation_date := SYSDATE;
            v_loc.last_updated_by := fnd_global.user_id;
            v_loc.last_update_date := SYSDATE;
            INSERT INTO hr.hr_locations_all VALUES v_loc;

            SELECT *
              BULK COLLECT INTO v_names
              FROM hr.hr_locations_all_tl
             WHERE location_id = v_tpl_id;
            FOR i IN 1 .. v_names.COUNT LOOP
                v_names(i).location_id := v_loc.location_id;
                v_names(i).location_code := v_loc.location_code;
                v_names(i).description := v_org_name;
                v_names(i).created_by := fnd_global.user_id;
                v_names(i).creation_date := SYSDATE;
                v_names(i).last_updated_by := fnd_global.user_id;
                v_names(i).last_update_date := SYSDATE;
                INSERT INTO hr.hr_locations_all_tl VALUES v_names(i);
            END LOOP;

            UPDATE hr.hr_all_organization_units
               SET location_id = v_loc.location_id,
                   last_updated_by = fnd_global.user_id,
                   last_update_date = SYSDATE
             WHERE organization_id = v_org_id;
        END IF;

        SELECT COUNT(*)
          INTO v_count
          FROM ar.hz_geo_name_references
         WHERE location_table_name = 'HR_LOCATIONS_ALL'
           AND location_id = v_loc.location_id;
        IF v_count = 0 THEN
            hz_gnr_pub.process_gnr(
                p_location_table_name => 'HR_LOCATIONS_ALL',
                p_location_id         => v_loc.location_id,
                p_call_type           => 'C',
                p_init_msg_list       => fnd_api.g_true,
                x_return_status       => v_status,
                x_msg_count           => v_msg_cnt,
                x_msg_data            => v_msg
            );
            IF v_status <> fnd_api.g_ret_sts_success THEN
                raise_application_error(
                    -20001,
                    'Tax geography for ' || p_org_code || ' failed: '
                    || fnd_msg_pub.get(fnd_msg_pub.g_first, fnd_api.g_false)
                );
            END IF;
        END IF;
    END ensure_hub_location;

    -- Oracle Inventory posts transactions only in an open period: opens the
    -- current month at a hub that has no period for today.
    PROCEDURE ensure_open_period (p_org_code IN VARCHAR2) IS
        v_org_id NUMBER := org_id(p_org_code);
        v_count  NUMBER;
        v_period inv.org_acct_periods%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM inv.org_acct_periods
         WHERE organization_id = v_org_id
           AND TRUNC(SYSDATE) BETWEEN period_start_date
                                  AND schedule_close_date;
        IF v_count = 0 THEN
            SELECT *
              INTO v_period
              FROM inv.org_acct_periods
             WHERE organization_id = v_tpl_org_id
             ORDER BY period_start_date DESC
             FETCH FIRST 1 ROW ONLY;
            v_period.acct_period_id := inv.org_acct_periods_s.NEXTVAL;
            v_period.organization_id := v_org_id;
            v_period.period_year := EXTRACT(YEAR FROM SYSDATE);
            v_period.period_num := EXTRACT(MONTH FROM SYSDATE);
            v_period.period_name :=
                TO_CHAR(SYSDATE, 'Mon-YY', 'NLS_DATE_LANGUAGE=AMERICAN');
            v_period.description := NULL;
            v_period.period_start_date := TRUNC(SYSDATE, 'MM');
            v_period.schedule_close_date := LAST_DAY(TRUNC(SYSDATE));
            v_period.period_close_date := NULL;
            v_period.open_flag := 'Y';
            v_period.summarized_flag := 'N';
            v_period.created_by := fnd_global.user_id;
            v_period.creation_date := SYSDATE;
            v_period.last_updated_by := fnd_global.user_id;
            v_period.last_update_date := SYSDATE;
            INSERT INTO inv.org_acct_periods VALUES v_period;
        END IF;
    END ensure_open_period;

    -- Copies the template item, with its category assignments, from one
    -- organization into another under the scenario item number and ID.
    PROCEDURE copy_item (
        p_from_org  IN NUMBER,
        p_to_org    IN NUMBER,
        p_tpl_item  IN NUMBER,
        p_item_id   IN NUMBER,
        p_item_code IN VARCHAR2,
        p_item_desc IN VARCHAR2
    ) IS
        v_count NUMBER;
        v_item  inv.mtl_system_items_b%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM inv.mtl_system_items_b
         WHERE organization_id = p_to_org
           AND inventory_item_id = p_item_id;
        IF v_count = 0 THEN
            SELECT *
              INTO v_item
              FROM inv.mtl_system_items_b
             WHERE organization_id = p_from_org
               AND inventory_item_id = p_tpl_item;
            v_item.inventory_item_id := p_item_id;
            v_item.organization_id := p_to_org;
            v_item.segment1 := p_item_code;
            v_item.description := p_item_desc;
            v_item.internal_order_flag := 'Y';
            v_item.internal_order_enabled_flag := 'Y';
            v_item.restrict_subinventories_code := 2;
            v_item.restrict_locators_code := 2;
            v_item.full_lead_time := 14;
            v_item.created_by := fnd_global.user_id;
            v_item.creation_date := SYSDATE;
            INSERT INTO inv.mtl_system_items_b VALUES v_item;
        END IF;
        -- Oracle Purchasing needs the item's purchasing category.
        INSERT INTO inv.mtl_item_categories (
            inventory_item_id,
            organization_id,
            category_set_id,
            category_id,
            last_update_date,
            last_updated_by,
            creation_date,
            created_by
        )
        SELECT p_item_id,
               p_to_org,
               mic.category_set_id,
               mic.category_id,
               SYSDATE,
               fnd_global.user_id,
               SYSDATE,
               fnd_global.user_id
          FROM inv.mtl_item_categories mic
         WHERE mic.organization_id = p_from_org
           AND mic.inventory_item_id = p_tpl_item
           AND NOT EXISTS (
               SELECT 1
                 FROM inv.mtl_item_categories cur
                WHERE cur.organization_id = p_to_org
                  AND cur.inventory_item_id = p_item_id
                  AND cur.category_set_id = mic.category_set_id
           );
    END copy_item;

    -- Creates or refreshes a scenario item at a hub, with the planner's
    -- safety stock. Oracle Purchasing validates items in the item master,
    -- so the item master holds every scenario item under the hubs' item ID.
    PROCEDURE ensure_item (
        p_org_code  IN VARCHAR2,
        p_item_code IN VARCHAR2,
        p_item_desc IN VARCHAR2,
        p_price     IN NUMBER,
        p_ss_qty    IN NUMBER
    ) IS
        v_org_id   NUMBER := org_id(p_org_code);
        v_tpl_item NUMBER;
        v_item_id  NUMBER;
    BEGIN
        -- Start from a plain purchased, stocked, and reservable item.
        SELECT inventory_item_id
          INTO v_tpl_item
          FROM inv.mtl_system_items_b
         WHERE organization_id = v_tpl_org_id
           AND inventory_item_status_code = 'Active'
           AND purchasing_enabled_flag = 'Y'
           AND mtl_transactions_enabled_flag = 'Y'
           AND stock_enabled_flag = 'Y'
           AND reservable_type = 1
           AND bom_item_type = 4
           AND lot_control_code = 1
           AND serial_number_control_code = 1
           AND location_control_code = 1
           AND revision_qty_control_code = 1
         ORDER BY inventory_item_id
         FETCH FIRST 1 ROW ONLY;
        SELECT MAX(inventory_item_id)
          INTO v_item_id
          FROM inv.mtl_system_items_b
         WHERE organization_id IN (v_master_id, v_org_id)
           AND segment1 = p_item_code;
        IF v_item_id IS NULL THEN
            v_item_id := inv.mtl_system_items_b_s.NEXTVAL;
        END IF;
        copy_item(
            v_master_id, v_master_id, v_tpl_item, v_item_id, p_item_code,
            p_item_desc
        );
        copy_item(
            v_tpl_org_id, v_org_id, v_tpl_item, v_item_id, p_item_code,
            p_item_desc
        );

        -- The scenario values items by list price, not by standard cost, so
        -- the items are expense items that transact without an item cost.
        UPDATE inv.mtl_system_items_b
           SET description = p_item_desc,
               list_price_per_unit = p_price,
               market_price = p_price,
               costing_enabled_flag = 'N',
               inventory_asset_flag = 'N',
               last_updated_by = fnd_global.user_id,
               last_update_date = SYSDATE
         WHERE inventory_item_id = v_item_id
           AND organization_id IN (v_master_id, v_org_id);

        -- Oracle Inventory reads items through MTL_SYSTEM_ITEMS, which joins
        -- the translation table: every item needs a row per installed language.
        MERGE INTO inv.mtl_system_items_tl tl
        USING (
            SELECT lang.language_code,
                   org.organization_id
              FROM applsys.fnd_languages lang
             CROSS JOIN (
                 SELECT v_master_id AS organization_id FROM dual
                 UNION
                 SELECT v_org_id FROM dual
             ) org
             WHERE lang.installed_flag IN ('B', 'I')
        ) src
        ON (
            tl.inventory_item_id = v_item_id
            AND tl.organization_id = src.organization_id
            AND tl.language = src.language_code
        )
        WHEN MATCHED THEN
            UPDATE SET tl.description = p_item_desc
        WHEN NOT MATCHED THEN
            INSERT (
                inventory_item_id,
                organization_id,
                language,
                source_lang,
                description,
                last_update_date,
                last_updated_by,
                creation_date,
                created_by
            ) VALUES (
                v_item_id,
                src.organization_id,
                src.language_code,
                'US',
                p_item_desc,
                SYSDATE,
                fnd_global.user_id,
                SYSDATE,
                fnd_global.user_id
            );

        -- The planner's safety stock takes effect yesterday, so an agent
        -- writeback today adds its own row instead of overwriting it. Rows
        -- from earlier demos go, so the planner's level is current again.
        DELETE FROM inv.mtl_safety_stocks
         WHERE organization_id = v_org_id
           AND inventory_item_id = v_item_id
           AND effectivity_date >= TRUNC(SYSDATE);
        MERGE INTO inv.mtl_safety_stocks mss
        USING (
            SELECT TRUNC(SYSDATE) - 1 AS effectivity_date
              FROM dual
        ) src
        ON (
            mss.organization_id = v_org_id
            AND mss.inventory_item_id = v_item_id
            AND TRUNC(mss.effectivity_date) = src.effectivity_date
        )
        WHEN MATCHED THEN
            UPDATE SET mss.safety_stock_quantity = p_ss_qty,
                       mss.last_update_date = SYSDATE,
                       mss.last_updated_by = fnd_global.user_id
        WHEN NOT MATCHED THEN
            INSERT (
                organization_id,
                inventory_item_id,
                effectivity_date,
                safety_stock_quantity,
                safety_stock_code,
                last_update_date,
                last_updated_by,
                creation_date,
                created_by
            ) VALUES (
                v_org_id,
                v_item_id,
                src.effectivity_date,
                p_ss_qty,
                1,
                SYSDATE,
                fnd_global.user_id,
                SYSDATE,
                fnd_global.user_id
            );
    END ensure_item;

    -- Records a safety stock that an earlier agent writeback raised for a
    -- surge that has since ended: effective today, under the agent's Oracle
    -- EBS user, above the planner's level that ensure_item set.
    PROCEDURE seed_agent_safety_stock (
        p_org_code  IN VARCHAR2,
        p_item_code IN VARCHAR2,
        p_ss_qty    IN NUMBER
    ) IS
        v_org_id   NUMBER := org_id(p_org_code);
        v_item_id  NUMBER := item_id(p_item_code);
        v_agent_id NUMBER;
    BEGIN
        SELECT MAX(user_id)
          INTO v_agent_id
          FROM applsys.fnd_user
         WHERE user_name = c_agent_user;
        IF v_agent_id IS NULL THEN
            raise_application_error(
                -20001,
                c_agent_user || ' does not exist. Run '
                || 'install_voltguard_agent_user.sql before this seed.'
            );
        END IF;
        INSERT INTO inv.mtl_safety_stocks (
            organization_id,
            inventory_item_id,
            effectivity_date,
            safety_stock_quantity,
            safety_stock_code,
            last_update_date,
            last_updated_by,
            creation_date,
            created_by
        ) VALUES (
            v_org_id,
            v_item_id,
            TRUNC(SYSDATE),
            p_ss_qty,
            1,
            SYSDATE,
            v_agent_id,
            SYSDATE,
            v_agent_id
        );
    END seed_agent_safety_stock;

    -- A Direct Org Transfer needs a direct shipping network from the source
    -- hub to Miami DC. Freight comes from the BigQuery corridors, so the
    -- network adds no Oracle EBS transfer charge (code 1 = None). It copies
    -- the accounts of a direct Vision network into the template organization
    -- that needs no internal order.
    PROCEDURE ensure_direct_network (p_from_code IN VARCHAR2) IS
        v_from_id NUMBER := org_id(p_from_code);
        v_to_id   NUMBER := org_id(c_miami);
        v_count   NUMBER;
        v_network inv.mtl_interorg_parameters%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM inv.mtl_interorg_parameters
         WHERE from_organization_id = v_from_id
           AND to_organization_id = v_to_id;
        IF v_count = 0 THEN
            SELECT mip.*
              INTO v_network
              FROM inv.mtl_interorg_parameters mip
              JOIN hr.hr_organization_information oi
                ON oi.organization_id = mip.from_organization_id
               AND oi.org_information_context = 'Accounting Information'
               AND oi.org_information1 = v_ledger_id
             WHERE mip.to_organization_id = v_tpl_org_id
               AND mip.intransit_type = 1
               AND mip.internal_order_required_flag = 2
             ORDER BY mip.from_organization_id
             FETCH FIRST 1 ROW ONLY;
            v_network.from_organization_id := v_from_id;
            v_network.to_organization_id := v_to_id;
            v_network.matl_interorg_transfer_code := 1;
            v_network.interorg_trnsfr_charge_percent := NULL;
            v_network.created_by := fnd_global.user_id;
            v_network.creation_date := SYSDATE;
            v_network.last_updated_by := fnd_global.user_id;
            v_network.last_update_date := SYSDATE;
            INSERT INTO inv.mtl_interorg_parameters VALUES v_network;
        END IF;
    END ensure_direct_network;

    -- Resets a hub balance directly: re-seeding after a confirmed writeback
    -- must not add material transactions to the issue history.
    PROCEDURE seed_hub_onhand (
        p_org_code  IN VARCHAR2,
        p_item_code IN VARCHAR2,
        p_target_oh IN NUMBER
    ) IS
        v_org_id  NUMBER := org_id(p_org_code);
        v_item_id NUMBER := item_id(p_item_code);
        v_onhand  inv.mtl_onhand_quantities_detail%ROWTYPE;
    BEGIN
        DELETE FROM inv.mtl_onhand_quantities_detail
         WHERE organization_id = v_org_id
           AND inventory_item_id = v_item_id;
        IF p_target_oh > 0 THEN
            SELECT *
              INTO v_onhand
              FROM inv.mtl_onhand_quantities_detail
             WHERE organization_id = v_tpl_org_id
               AND ROWNUM = 1;
            SELECT mp.default_cost_group_id,
                   mp.default_status_id,
                   msib.primary_uom_code
              INTO v_onhand.cost_group_id,
                   v_onhand.status_id,
                   v_onhand.transaction_uom_code
              FROM inv.mtl_parameters mp
              JOIN inv.mtl_system_items_b msib
                ON msib.organization_id = mp.organization_id
             WHERE mp.organization_id = v_org_id
               AND msib.inventory_item_id = v_item_id;
            v_onhand.onhand_quantities_id :=
                inv.mtl_material_transactions_s.NEXTVAL;
            v_onhand.organization_id := v_org_id;
            v_onhand.owning_organization_id := v_org_id;
            v_onhand.planning_organization_id := v_org_id;
            v_onhand.inventory_item_id := v_item_id;
            v_onhand.subinventory_code := 'FGI';
            v_onhand.revision := NULL;
            v_onhand.locator_id := NULL;
            v_onhand.lot_number := NULL;
            v_onhand.lpn_id := NULL;
            v_onhand.project_id := NULL;
            v_onhand.task_id := NULL;
            v_onhand.is_consigned := 2;
            v_onhand.create_transaction_id := NULL;
            v_onhand.update_transaction_id := NULL;
            v_onhand.secondary_uom_code := NULL;
            v_onhand.secondary_transaction_quantity := NULL;
            v_onhand.transaction_quantity := p_target_oh;
            v_onhand.primary_transaction_quantity := p_target_oh;
            v_onhand.date_received := SYSDATE;
            v_onhand.orig_date_received := SYSDATE;
            v_onhand.created_by := fnd_global.user_id;
            v_onhand.creation_date := SYSDATE;
            v_onhand.last_updated_by := fnd_global.user_id;
            v_onhand.last_update_date := SYSDATE;
            INSERT INTO inv.mtl_onhand_quantities_detail VALUES v_onhand;
        END IF;
    END seed_hub_onhand;

    -- Reserves SLA stock through the Oracle Inventory reservation API, with an
    -- Inventory demand source named after the SLA contract, and records the
    -- contract's customer, breach penalty, and tier in the flexfield.
    PROCEDURE seed_hub_reservation (
        p_org_code       IN VARCHAR2,
        p_reserved_qty   IN NUMBER,
        p_customer_name  IN VARCHAR2,
        p_breach_penalty IN NUMBER,
        p_sla_tier       IN VARCHAR2
    ) IS
        v_org_id      NUMBER := org_id(p_org_code);
        v_item_id     NUMBER := item_id('VG-GEN-7500');
        v_rsv         inv_reservation_global.mtl_reservation_rec_type;
        v_serials_in  inv_reservation_global.serial_number_tbl_type;
        v_serials_out inv_reservation_global.serial_number_tbl_type;
        v_status      VARCHAR2(1);
        v_msg_count   NUMBER;
        v_msg_data    VARCHAR2(2000);
        v_reserved    NUMBER;
        v_rsv_id      NUMBER;
    BEGIN
        DELETE FROM inv.mtl_reservations
         WHERE organization_id = v_org_id
           AND inventory_item_id = v_item_id;
        -- The record type defaults to FND_API missing values, which the API
        -- rejects: start from NULL fields.
        v_rsv := NULL;
        SELECT primary_uom_code
          INTO v_rsv.primary_uom_code
          FROM inv.mtl_system_items_b
         WHERE organization_id = v_org_id
           AND inventory_item_id = v_item_id;
        v_rsv.organization_id := v_org_id;
        v_rsv.inventory_item_id := v_item_id;
        v_rsv.requirement_date := SYSDATE + 1;
        v_rsv.demand_source_type_id := inv_reservation_global.g_source_type_inv;
        v_rsv.demand_source_name := SUBSTR(p_customer_name, 1, 30);
        v_rsv.reservation_uom_code := v_rsv.primary_uom_code;
        v_rsv.reservation_quantity := p_reserved_qty;
        v_rsv.primary_reservation_quantity := p_reserved_qty;
        v_rsv.supply_source_type_id := inv_reservation_global.g_source_type_inv;
        v_rsv.subinventory_code := 'FGI';
        v_rsv.ship_ready_flag := 2;
        inv_reservation_pub.create_reservation(
            p_api_version_number       => 1.0,
            p_init_msg_lst             => fnd_api.g_true,
            x_return_status            => v_status,
            x_msg_count                => v_msg_count,
            x_msg_data                 => v_msg_data,
            p_rsv_rec                  => v_rsv,
            p_serial_number            => v_serials_in,
            x_serial_number            => v_serials_out,
            p_partial_reservation_flag => fnd_api.g_false,
            p_force_reservation_flag   => fnd_api.g_false,
            p_validation_flag          => fnd_api.g_true,
            x_quantity_reserved        => v_reserved,
            x_reservation_id           => v_rsv_id
        );
        IF v_status <> fnd_api.g_ret_sts_success THEN
            raise_application_error(
                -20002,
                'Reservation at ' || p_org_code || ' failed: '
                || fnd_msg_pub.get(fnd_msg_pub.g_first, fnd_api.g_false)
            );
        END IF;
        UPDATE inv.mtl_reservations
           SET attribute1 = p_customer_name,
               attribute2 = TO_CHAR(p_breach_penalty),
               attribute3 = p_sla_tier
         WHERE reservation_id = v_rsv_id;
    END seed_hub_reservation;

    -- Removes the requisitions that confirmed writebacks imported from the
    -- agent's source, with their supply and approval history, so they don't
    -- remain open supply. Requisitions that a purchase order or a funds
    -- reservation already uses stay.
    PROCEDURE remove_agent_requisitions IS
        v_headers sys.odcinumberlist;
    BEGIN
        SELECT prh.requisition_header_id
          BULK COLLECT INTO v_headers
          FROM po.po_requisition_headers_all prh
         WHERE prh.interface_source_code = c_req_source
           AND prh.org_id = v_ou_id
           AND NOT EXISTS (
                   SELECT 1
                     FROM po.po_requisition_lines_all prl
                     LEFT JOIN po.po_req_distributions_all prd
                       ON prd.requisition_line_id = prl.requisition_line_id
                    WHERE prl.requisition_header_id = prh.requisition_header_id
                      AND (prl.line_location_id IS NOT NULL
                           OR NVL(prd.encumbered_flag, 'N') = 'Y')
               );
        DELETE FROM inv.mtl_supply
         WHERE supply_type_code = 'REQ'
           AND req_header_id IN (SELECT COLUMN_VALUE FROM TABLE(v_headers));
        DELETE FROM po.po_action_history
         WHERE object_type_code = 'REQUISITION'
           AND object_id IN (SELECT COLUMN_VALUE FROM TABLE(v_headers));
        DELETE FROM po.po_req_distributions_all
         WHERE requisition_line_id IN (
                   SELECT requisition_line_id
                     FROM po.po_requisition_lines_all
                    WHERE requisition_header_id IN (
                              SELECT COLUMN_VALUE FROM TABLE(v_headers)
                          )
               );
        DELETE FROM po.po_requisition_lines_all
         WHERE requisition_header_id IN (SELECT COLUMN_VALUE FROM TABLE(v_headers));
        DELETE FROM po.po_requisition_headers_all
         WHERE requisition_header_id IN (SELECT COLUMN_VALUE FROM TABLE(v_headers));
        DELETE FROM po.po_requisitions_interface_all
         WHERE interface_source_code = c_req_source;
    END remove_agent_requisitions;

BEGIN
    init_seed_context;
    SELECT mp.organization_id,
           mp.master_organization_id,
           mp.default_cost_group_id,
           oi.org_information1,
           TO_NUMBER(oi.org_information3)
      INTO v_tpl_org_id, v_master_id, v_tpl_cg_id, v_ledger_id, v_ou_id
      FROM inv.mtl_parameters mp
      JOIN hr.hr_organization_information oi
        ON oi.organization_id = mp.organization_id
       AND oi.org_information_context = 'Accounting Information'
     WHERE mp.organization_code = c_template_org;

    -- 1. Hubs, items, open periods, and shipping networks to Miami DC
    ensure_hub(c_miami, 'Miami DC');
    ensure_hub('ATL', 'Atlanta Hub');
    ensure_hub('DAL', 'Dallas Hub');
    ensure_hub('ORD', 'Chicago Hub');
    ensure_hub('PHX', 'Phoenix Hub');
    ensure_hub('EWR', 'Newark Hub');
    ensure_hub_location(c_miami);
    ensure_hub_location('ATL');
    ensure_hub_location('DAL');
    ensure_hub_location('ORD');
    ensure_hub_location('PHX');
    ensure_hub_location('EWR');
    ensure_open_period(c_miami);
    ensure_open_period('ATL');
    ensure_open_period('DAL');
    ensure_open_period('ORD');
    ensure_open_period('PHX');
    ensure_open_period('EWR');
    ensure_item(c_miami, 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 100);
    ensure_item(c_miami, 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 50);
    ensure_item('ATL', 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 80);
    ensure_item('DAL', 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 75);
    ensure_item('ORD', 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 80);
    ensure_item('PHX', 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 50);
    ensure_item('EWR', 'VG-GEN-7500', 'Portable Backup Generator 7500W', 350, 70);
    ensure_item('ATL', 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 40);
    ensure_item('DAL', 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 30);
    ensure_item('ORD', 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 40);
    ensure_item('PHX', 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 25);
    ensure_item('EWR', 'VG-SURGE-PRO', 'Whole-Home Surge Protector and Assembly Module', 145, 35);
    seed_agent_safety_stock('PHX', 'VG-GEN-7500', 80);
    ensure_direct_network('ATL');
    ensure_direct_network('DAL');
    ensure_direct_network('ORD');
    ensure_direct_network('PHX');
    ensure_direct_network('EWR');

    -- 2. On-hand balances and SLA reservations. Every hub holds VG-SURGE-PRO
    --    at its safety stock, so no hub has surplus to transfer, and no
    --    requisition from an earlier confirmed writeback stays open.
    seed_hub_onhand(c_miami, 'VG-GEN-7500', 190);
    seed_hub_onhand(c_miami, 'VG-SURGE-PRO', 0);
    seed_hub_onhand('ATL', 'VG-GEN-7500', 400);
    seed_hub_onhand('DAL', 'VG-GEN-7500', 250);
    seed_hub_onhand('ORD', 'VG-GEN-7500', 320);
    seed_hub_onhand('PHX', 'VG-GEN-7500', 180);
    seed_hub_onhand('EWR', 'VG-GEN-7500', 290);
    seed_hub_onhand('ATL', 'VG-SURGE-PRO', 40);
    seed_hub_onhand('DAL', 'VG-SURGE-PRO', 30);
    seed_hub_onhand('ORD', 'VG-SURGE-PRO', 40);
    seed_hub_onhand('PHX', 'VG-SURGE-PRO', 25);
    seed_hub_onhand('EWR', 'VG-SURGE-PRO', 35);
    seed_hub_reservation('ATL', 360, 'Southeast Hospital Care Alliance SLA', 250000, 'TIER_1_CRITICAL_INFRASTRUCTURE');
    seed_hub_reservation('ORD', 280, 'Midwest Municipal Grid SLA', 195000, 'TIER_1_CRITICAL_INFRASTRUCTURE');
    seed_hub_reservation('PHX', 30, 'Southwest Data Center SLA', 90000, 'TIER_1_CRITICAL_INFRASTRUCTURE');
    seed_hub_reservation('EWR', 265, 'Northeast Tri-State Transit SLA', 210000, 'TIER_1_CRITICAL_INFRASTRUCTURE');
    remove_agent_requisitions;

    -- 3. Secondary scenario, PO 40912 for Miami DC from Advantage Corp's US
    --    site: need-by tomorrow, promised in 4 days, with the corridor delay,
    --    plant buffer, and line-stop exposure in the header flexfield. A
    --    standard Vision Operations PO is the template. The PO uses the
    --    ledger currency, so it has no exchange rate.
    DECLARE
        v_count    NUMBER;
        v_tpl_id   NUMBER;
        v_miami_id NUMBER := org_id(c_miami);
        v_item_id  NUMBER := item_id('VG-SURGE-PRO');
        v_vendor   NUMBER;
        v_site     NUMBER;
        v_header   po.po_headers_all%ROWTYPE;
        v_line     po.po_lines_all%ROWTYPE;
        v_shipment po.po_line_locations_all%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM po.po_headers_all
         WHERE po_header_id = c_po_id;
        IF v_count = 0 THEN
            SELECT MIN(pha.po_header_id)
              INTO v_tpl_id
              FROM po.po_headers_all pha
             WHERE pha.org_id = v_ou_id
               AND pha.type_lookup_code = 'STANDARD'
               AND EXISTS (
                   SELECT 1
                     FROM po.po_line_locations_all pll
                    WHERE pll.po_header_id = pha.po_header_id
               );
            SELECT *
              INTO v_header
              FROM po.po_headers_all
             WHERE po_header_id = v_tpl_id;
            SELECT *
              INTO v_line
              FROM po.po_lines_all
             WHERE po_header_id = v_tpl_id
             ORDER BY line_num
             FETCH FIRST 1 ROW ONLY;
            SELECT *
              INTO v_shipment
              FROM po.po_line_locations_all
             WHERE po_line_id = v_line.po_line_id
             ORDER BY shipment_num
             FETCH FIRST 1 ROW ONLY;
            v_header.po_header_id := c_po_id;
            v_header.segment1 := c_po_number;
            v_header.created_by := fnd_global.user_id;
            v_header.creation_date := SYSDATE;
            INSERT INTO po.po_headers_all VALUES v_header;
            v_line.po_line_id := c_po_id;
            v_line.po_header_id := c_po_id;
            v_line.line_num := 1;
            v_line.created_by := fnd_global.user_id;
            v_line.creation_date := SYSDATE;
            INSERT INTO po.po_lines_all VALUES v_line;
            v_shipment.line_location_id := c_po_id;
            v_shipment.po_header_id := c_po_id;
            v_shipment.po_line_id := c_po_id;
            v_shipment.shipment_num := 1;
            v_shipment.created_by := fnd_global.user_id;
            v_shipment.creation_date := SYSDATE;
            INSERT INTO po.po_line_locations_all VALUES v_shipment;
        END IF;
        find_supplier_site(c_po_vendor, c_po_site, v_vendor, v_site);
        UPDATE po.po_headers_all
           SET authorization_status = 'APPROVED',
               closed_code = 'OPEN',
               vendor_id = v_vendor,
               vendor_site_id = v_site,
               vendor_contact_id = NULL,
               currency_code = (
                   SELECT gl.currency_code
                     FROM gl.gl_ledgers gl
                    WHERE gl.ledger_id = TO_NUMBER(v_ledger_id)
               ),
               rate_type = NULL,
               rate_date = NULL,
               rate = NULL,
               attribute3 = NULL,
               attribute4 = NULL,
               attribute5 = '3.0',
               attribute6 = '1.5',
               attribute7 = '1200000',
               last_updated_by = fnd_global.user_id,
               last_update_date = SYSDATE
         WHERE po_header_id = c_po_id
           AND segment1 = c_po_number;
        IF SQL%ROWCOUNT = 0 THEN
            raise_application_error(
                -20003,
                'PO header ' || c_po_id || ' already belongs to another PO.'
            );
        END IF;
        UPDATE po.po_lines_all
           SET item_id = v_item_id,
               item_description = 'Whole-Home Surge Protector and Assembly Module',
               unit_price = 145,
               quantity = 300,
               closed_code = 'OPEN',
               last_updated_by = fnd_global.user_id,
               last_update_date = SYSDATE
         WHERE po_line_id = c_po_id;
        UPDATE po.po_line_locations_all pll
           SET pll.quantity = 300,
               pll.quantity_received = 0,
               pll.quantity_billed = 0,
               pll.quantity_cancelled = 0,
               pll.closed_code = 'OPEN',
               pll.ship_to_organization_id = v_miami_id,
               pll.ship_to_location_id = (
                   SELECT haou.location_id
                     FROM hr.hr_all_organization_units haou
                    WHERE haou.organization_id = v_miami_id
               ),
               pll.need_by_date = TRUNC(SYSDATE) + 1,
               pll.promised_date = TRUNC(SYSDATE) + 4,
               pll.last_updated_by = fnd_global.user_id,
               pll.last_update_date = SYSDATE
         WHERE pll.line_location_id = c_po_id;
    END;

    -- 4. Approved supplier list: Consolidated Supplies (Plantation, Florida)
    --    supplies VG-SURGE-PRO to every hub. A global, approved Vision entry
    --    for a direct item and its attributes are the template.
    DECLARE
        v_item_id NUMBER := item_id('VG-SURGE-PRO');
        v_vendor  NUMBER;
        v_site    NUMBER;
        v_asl_id  NUMBER;
        v_asl     po.po_approved_supplier_list%ROWTYPE;
        v_attr    po.po_asl_attributes%ROWTYPE;
    BEGIN
        find_supplier_site(c_asl_vendor, c_asl_site, v_vendor, v_site);
        SELECT MAX(asl_id)
          INTO v_asl_id
          FROM po.po_approved_supplier_list
         WHERE using_organization_id = -1
           AND item_id = v_item_id
           AND vendor_id = v_vendor
           AND vendor_site_id = v_site;
        IF v_asl_id IS NULL THEN
            SELECT asl.*
              INTO v_asl
              FROM po.po_approved_supplier_list asl
             WHERE asl.using_organization_id = -1
               AND asl.item_id IS NOT NULL
               AND asl.asl_status_id = 2
               AND asl.vendor_business_type = 'DIRECT'
               AND NVL(asl.disable_flag, 'N') = 'N'
               AND EXISTS (
                   SELECT 1
                     FROM po.po_asl_attributes paa
                    WHERE paa.asl_id = asl.asl_id
                      AND paa.using_organization_id = -1
               )
             ORDER BY asl.asl_id
             FETCH FIRST 1 ROW ONLY;
            SELECT *
              INTO v_attr
              FROM po.po_asl_attributes
             WHERE asl_id = v_asl.asl_id
               AND using_organization_id = -1;
            SELECT po.po_approved_supplier_list_s.NEXTVAL
              INTO v_asl_id
              FROM dual;
            v_asl.asl_id := v_asl_id;
            v_asl.owning_organization_id := org_id(c_miami);
            v_asl.vendor_id := v_vendor;
            v_asl.vendor_site_id := v_site;
            v_asl.item_id := v_item_id;
            v_asl.category_id := NULL;
            v_asl.manufacturer_id := NULL;
            v_asl.manufacturer_asl_id := NULL;
            v_asl.primary_vendor_item := NULL;
            v_asl.comments := NULL;
            v_asl.created_by := fnd_global.user_id;
            v_asl.creation_date := SYSDATE;
            v_asl.last_updated_by := fnd_global.user_id;
            v_asl.last_update_date := SYSDATE;
            INSERT INTO po.po_approved_supplier_list VALUES v_asl;
            v_attr.asl_id := v_asl_id;
            v_attr.vendor_id := v_vendor;
            v_attr.vendor_site_id := v_site;
            v_attr.item_id := v_item_id;
            v_attr.category_id := NULL;
            v_attr.created_by := fnd_global.user_id;
            v_attr.creation_date := SYSDATE;
            v_attr.last_updated_by := fnd_global.user_id;
            v_attr.last_update_date := SYSDATE;
            INSERT INTO po.po_asl_attributes VALUES v_attr;
        END IF;
        UPDATE po.po_approved_supplier_list
           SET asl_status_id = 2,
               disable_flag = NULL,
               last_updated_by = fnd_global.user_id,
               last_update_date = SYSDATE
         WHERE asl_id = v_asl_id;
    END;

    -- 5. Secondary scenario, notification 90412 for Maya Lin (MLIN) about the
    --    PO 40912 delay, with the attributes that
    --    APPS.VW_SCM_OPEN_NOTIFICATIONS reads
    DECLARE
        v_count NUMBER;
        v_alert applsys.wf_notifications%ROWTYPE;
    BEGIN
        SELECT COUNT(*)
          INTO v_count
          FROM applsys.wf_notifications
         WHERE notification_id = c_alert_id;
        IF v_count = 0 THEN
            SELECT *
              INTO v_alert
              FROM applsys.wf_notifications
             WHERE ROWNUM = 1;
            v_alert.notification_id := c_alert_id;
            v_alert.group_id := c_alert_id;
            v_alert.message_type := 'INVSCM';
            v_alert.message_name := 'VOLTGUARD_RESILIENCY_ALERT';
            v_alert.access_key := 'VG' || c_alert_id;
            v_alert.callback := NULL;
            v_alert.context := NULL;
            v_alert.user_key := NULL;
            v_alert.mail_status := 'SENT';
            v_alert.priority := 1;
            v_alert.begin_date := SYSDATE;
            v_alert.due_date := SYSDATE + 1;
            INSERT INTO applsys.wf_notifications VALUES v_alert;
        END IF;
        UPDATE applsys.wf_notifications
           SET status = 'OPEN',
               recipient_role = 'MLIN',
               original_recipient = 'MLIN',
               end_date = NULL,
               responder = NULL,
               subject = 'PO #40912 delayed: Miami DC (MIA) VG-SURGE-PRO '
                   || 'inbound misses the 1.5-day plant buffer'
         WHERE notification_id = c_alert_id
           AND message_name = 'VOLTGUARD_RESILIENCY_ALERT';
        IF SQL%ROWCOUNT = 0 THEN
            raise_application_error(
                -20004,
                'Notification ' || c_alert_id || ' already belongs to another '
                || 'Oracle Workflow message.'
            );
        END IF;
        -- A confirmed close records its outcome on the alert. Reopening the
        -- alert removes that record.
        DELETE FROM applsys.wf_notification_attributes
         WHERE notification_id = c_alert_id
           AND name IN ('RESOLUTION_ACTION', 'RESOLUTION_NOTE');
        MERGE INTO applsys.wf_notification_attributes wna
        USING (
            SELECT 'ITEM_CODE' AS name, 'VG-SURGE-PRO' AS text_value FROM dual
            UNION ALL
            SELECT 'ORGANIZATION_CODE', c_miami FROM dual
            UNION ALL
            SELECT 'PO_NUMBER', c_po_number FROM dual
            UNION ALL
            SELECT 'SEVERITY', 'HIGH' FROM dual
        ) src
        ON (
            wna.notification_id = c_alert_id
            AND wna.name = src.name
        )
        WHEN MATCHED THEN
            UPDATE SET wna.text_value = src.text_value
        WHEN NOT MATCHED THEN
            INSERT (notification_id, name, text_value)
            VALUES (c_alert_id, src.name, src.text_value);
    END;

    COMMIT;
END;
/
