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

CREATE OR REPLACE PACKAGE APPS.XX_EBS_WF_AGENT_PKG AS
    /* $Header: XXEBSWFAGENTS.pls 120.2 2026/10/07 00:00:00 apps noship $ */
    FUNCTION resolve_notification_amount(p_nid IN NUMBER) RETURN NUMBER;

    PROCEDURE ensure_active_role(p_role IN VARCHAR2);

    PROCEDURE get_open_worklist(
        p_recipient     IN  VARCHAR2 DEFAULT NULL,
        p_message_type  IN  VARCHAR2 DEFAULT NULL,
        p_status        IN  VARCHAR2 DEFAULT 'OPEN',
        p_limit         IN  NUMBER   DEFAULT 50,
        p_offset        IN  NUMBER   DEFAULT 0,
        x_worklist_json OUT CLOB
    );

    PROCEDURE get_notification_info(
        p_nid       IN  NUMBER,
        x_info_json OUT CLOB
    );

    PROCEDURE get_notification_attrs(
        p_nid        IN  NUMBER,
        x_attrs_json OUT CLOB
    );

    PROCEDURE respond_notification(
        p_user_id      IN NUMBER,
        p_resp_id      IN NUMBER,
        p_resp_appl_id IN NUMBER,
        p_nid          IN NUMBER,
        p_result       IN VARCHAR2,
        p_comment      IN VARCHAR2,
        p_responder    IN VARCHAR2
    );
END XX_EBS_WF_AGENT_PKG;
