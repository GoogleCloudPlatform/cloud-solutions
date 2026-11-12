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
-- APPS.GE_EBS_SCM_TOOLS specification: the VoltGuard writebacks that Oracle
-- Integrated SOA Gateway (ISG) publishes as the ge_ebs_scm_tools REST service.
--
-- The irep annotations below let irep_parser.pl load the package into the
-- Integration Repository. ISG authenticates the caller, checks its grants, and
-- starts the Oracle EBS session from the RESTHeader responsibility before it
-- calls a function. Every function returns a JSON document with STATUS
-- (SUCCESS or ERROR), CODE, MESSAGE, and result fields.
-- =============================================================================

CREATE OR REPLACE PACKAGE GE_EBS_SCM_TOOLS AUTHID CURRENT_USER AS
/* $Header: ge_ebs_scm_tools_pkg.pls 120.2 2026/11/09 12:00:00 voltguard ship $ */
/*#
 * VoltGuard supply chain writebacks for the Gemini Enterprise agent. Each
 * function validates its input, calls an Oracle public API, writes to the MCP
 * audit log, and returns a JSON status.
 * @rep:scope public
 * @rep:product INV
 * @rep:lifecycle active
 * @rep:displayname VoltGuard Supply Chain Writebacks
 * @rep:compatibility S
 * @rep:category BUSINESS_ENTITY INV_REPLENISHMENT
 */

    /*#
     * Transfers stock between two hubs with INV_TXN_MANAGER_PUB after
     * checking the source hub's available-to-transact quantity.
     * @param p_source_org_code Organization code of the source hub
     * @param p_dest_org_code Organization code of the destination hub
     * @param p_item_code Item number
     * @param p_transfer_qty Whole number of units to transfer
     * @return JSON status of the transfer
     * @rep:scope public
     * @rep:lifecycle active
     * @rep:displayname Stage Inter-Organization Transfer
     */
    FUNCTION stage_interorg_transfer (
        p_source_org_code IN VARCHAR2,
        p_dest_org_code   IN VARCHAR2,
        p_item_code       IN VARCHAR2,
        p_transfer_qty    IN NUMBER
    ) RETURN VARCHAR2;

    /*#
     * Stages a requisition for an approved supplier of the item at the item
     * list price in PO_REQUISITIONS_INTERFACE_ALL and submits the
     * Requisition Import concurrent request.
     * @param p_destination_org_code Organization code of the receiving hub
     * @param p_item_code Item number
     * @param p_quantity Whole number of units to requisition
     * @param p_unit_price Item list price in USD
     * @param p_suggested_vendor_name Approved supplier name
     * @return JSON status of the requisition
     * @rep:scope public
     * @rep:lifecycle active
     * @rep:displayname Stage Purchase Requisition
     */
    FUNCTION stage_purchase_requisition (
        p_destination_org_code  IN VARCHAR2,
        p_item_code             IN VARCHAR2,
        p_quantity              IN NUMBER,
        p_unit_price            IN NUMBER,
        p_suggested_vendor_name IN VARCHAR2
    ) RETURN VARCHAR2;

    /*#
     * Records a new safety stock quantity effective today with
     * INV_SAFETY_STOCKS_PUB.
     * @param p_organization_code Organization code of the hub
     * @param p_item_code Item number
     * @param p_safety_stock_qty New safety stock quantity in whole units
     * @return JSON status of the safety stock update
     * @rep:scope public
     * @rep:lifecycle active
     * @rep:displayname Update Safety Stock
     */
    FUNCTION update_safety_stock (
        p_organization_code IN VARCHAR2,
        p_item_code         IN VARCHAR2,
        p_safety_stock_qty  IN NUMBER
    ) RETURN VARCHAR2;

    /*#
     * Closes an open VoltGuard resiliency alert in Oracle Workflow and
     * records the closure code and the resolution note on it.
     * @param p_notification_id Oracle Workflow notification ID of the alert
     * @param p_action Closure code, MITIGATED or ACKNOWLEDGED
     * @param p_resolution_note Note that summarizes the outcome
     * @return JSON status of the notification close
     * @rep:scope public
     * @rep:lifecycle active
     * @rep:displayname Close Workflow Notification
     */
    FUNCTION close_workflow_notification (
        p_notification_id IN NUMBER,
        p_action          IN VARCHAR2,
        p_resolution_note IN VARCHAR2
    ) RETURN VARCHAR2;

END GE_EBS_SCM_TOOLS;
/
