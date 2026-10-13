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

CREATE OR REPLACE PACKAGE BODY APPS.XX_EBS_WF_AGENT_PKG AS
    /* $Header: XXEBSWFAGENTB.pls 120.4 2026/10/09 00:00:00 apps noship $ */

    PROCEDURE ensure_active_role(p_role IN VARCHAR2) IS
        PRAGMA AUTONOMOUS_TRANSACTION;
        l_adhoc_count NUMBER := 0;
    BEGIN
        IF p_role IS NOT NULL AND NOT (
            apps.wf_directory.UserActive(p_role)
            OR apps.wf_directory.RoleActive(p_role)
        ) THEN
            SELECT COUNT(*)
              INTO l_adhoc_count
              FROM apps.wf_local_roles
             WHERE name = p_role
               AND orig_system IN ('WF_LOCAL_ROLES', 'WF_LOCAL_USERS');

            IF l_adhoc_count > 0 THEN
                apps.wf_directory.SetAdHocRoleStatus(p_role, 'ACTIVE');
                apps.wf_directory.SetAdHocRoleExpiration(
                    p_role, SYSDATE + 3650
                );
            END IF;
        END IF;
        COMMIT;
    END ensure_active_role;

    FUNCTION resolve_notification_amount(p_nid IN NUMBER) RETURN NUMBER IS
        l_amount NUMBER;
    BEGIN
        SELECT COALESCE(
            (SELECT MAX(
                        TO_NUMBER(
                            REPLACE(wna_po.text_value, ',', '')
                            DEFAULT NULL ON CONVERSION ERROR
                        )
                    )
               FROM apps.wf_notification_attributes wna_po
              WHERE wna_po.notification_id = p_nid
                AND wna_po.name IN (
                    'TOTAL_AMOUNT_DSP', 'PO_AMOUNT_DSP', 'REQ_AMOUNT_DSP'
                )
                AND REGEXP_LIKE(
                    TRIM(wna_po.text_value), '^[0-9,]+(\.[0-9]+)?$'
                )),
            (SELECT MAX(aerh.total)
               FROM apps.wf_notification_attributes wna_exp
               JOIN apps.ap_expense_report_headers_all aerh
                 ON aerh.report_header_id = wna_exp.number_value
                 OR aerh.invoice_num = wna_exp.text_value
              WHERE wna_exp.notification_id = p_nid
                AND wna_exp.name IN (
                    'EXPENSE_REPORT_ID', 'DOCUMENT_NUMBER'
                )),
            (SELECT SUM(pla.unit_price * pla.quantity)
               FROM apps.po_headers_all pha
               JOIN apps.po_lines_all pla
                 ON pla.po_header_id = pha.po_header_id
              WHERE pha.po_header_id = (
                        SELECT MAX(wna_doc.number_value)
                          FROM apps.wf_notification_attributes wna_doc
                         WHERE wna_doc.notification_id = p_nid
                           AND wna_doc.name IN (
                               'DOCUMENT_ID', 'AUTOCREATED_DOC_ID'
                           ))
                 OR pha.segment1 = (
                        SELECT MAX(wna_num.text_value)
                          FROM apps.wf_notification_attributes wna_num
                         WHERE wna_num.notification_id = p_nid
                           AND wna_num.name IN (
                               'DOCUMENT_NUM_REL',
                               'DOCUMENT_NUMBER',
                               'DOC_NUM_CREATED'
                           ))),
            (SELECT SUM(prla.unit_price * prla.quantity)
               FROM apps.po_requisition_headers_all prha
               JOIN apps.po_requisition_lines_all prla
                 ON prla.requisition_header_id = prha.requisition_header_id
              WHERE prha.requisition_header_id = (
                        SELECT MAX(wna_req.number_value)
                          FROM apps.wf_notification_attributes wna_req
                         WHERE wna_req.notification_id = p_nid
                           AND wna_req.name IN (
                               'DOCUMENT_ID', 'REQUISITION_ID'
                           ))
                 OR prha.segment1 = (
                        SELECT MAX(wna_rnum.text_value)
                          FROM apps.wf_notification_attributes wna_rnum
                         WHERE wna_rnum.notification_id = p_nid
                           AND wna_rnum.name IN (
                               'DOCUMENT_NUMBER', 'REQ_NUM'
                           ))),
            (SELECT MAX(okh.estimated_amount)
               FROM apps.wf_notification_attributes wna_okc
               JOIN apps.okc_k_headers_all_b okh
                 ON okh.id = wna_okc.number_value
              WHERE wna_okc.notification_id = p_nid
                AND wna_okc.name = 'CONTRACT_ID'
                AND wna_okc.number_value < 1e15),
            (SELECT MAX(wna_n.number_value)
               FROM apps.wf_notification_attributes wna_n
              WHERE wna_n.notification_id = p_nid
                AND wna_n.name IN (
                    'INSTALL_TOTAL_AMOUNT', 'INSTALL_DIRECT_COST', 'AMOUNT',
                    'TOTAL', 'CONTRACT_AMOUNT', 'EXP_REPORT_TOTAL',
                    'PO_AMOUNT', 'REQ_AMOUNT'
                )
                AND wna_n.number_value IS NOT NULL)
        )
        INTO l_amount
        FROM dual;

        RETURN l_amount;
    END resolve_notification_amount;

    PROCEDURE get_open_worklist(
        p_recipient     IN  VARCHAR2 DEFAULT NULL,
        p_message_type  IN  VARCHAR2 DEFAULT NULL,
        p_status        IN  VARCHAR2 DEFAULT 'OPEN',
        p_limit         IN  NUMBER   DEFAULT 50,
        p_offset        IN  NUMBER   DEFAULT 0,
        x_worklist_json OUT CLOB
    ) IS
        l_status VARCHAR2(30) := NVL(p_status, 'OPEN');
        l_limit  NUMBER := NVL(p_limit, 50);
        l_offset NUMBER := NVL(p_offset, 0);
    BEGIN
        SELECT COALESCE(
            JSON_ARRAYAGG(
                JSON_OBJECT(
                    'notification_id' VALUE sub.notification_id,
                    'message_type'    VALUE sub.message_type,
                    'message_name'    VALUE sub.message_name,
                    'recipient_role'  VALUE sub.recipient_role,
                    'status'          VALUE sub.status,
                    'subject'         VALUE sub.subject,
                    'priority'        VALUE sub.priority,
                    'begin_date'      VALUE sub.begin_date,
                    'due_date'        VALUE sub.due_date,
                    'amount'          VALUE
                        apps.xx_ebs_wf_agent_pkg.resolve_notification_amount(
                            sub.notification_id
                        ),
                    'attributes'      VALUE (
                        SELECT COALESCE(
                                   JSON_OBJECTAGG(
                                       wna.name VALUE COALESCE(
                                           wna.text_value,
                                           TO_CHAR(wna.number_value),
                                           TO_CHAR(
                                               wna.date_value,
                                               'YYYY-MM-DD"T"HH24:MI:SS'
                                           )
                                       )
                                       RETURNING CLOB
                                   ),
                                   TO_CLOB('{}')
                               )
                          FROM apps.wf_notification_attributes wna
                         WHERE wna.notification_id = sub.notification_id
                           AND wna.name IN (
                               'HAS_RECEIPTS', 'RECEIPTS_ATTACHED',
                               'WEEKEND_SPEND', 'WEEKEND_TRANSACTION',
                               'VENDOR_STATUS', 'SUPPLIER_STATUS',
                               'AFTER_THE_FACT', 'RETROACTIVE_PO',
                               'SPLIT_REQUISITION', 'JUSTIFICATION',
                               'EXP_REPORT_TOTAL', 'PO_AMOUNT', 'REQ_AMOUNT',
                               'TOTAL_AMOUNT_DSP', 'PO_AMOUNT_DSP',
                               'REQ_AMOUNT_DSP'
                           )
                    ) FORMAT JSON
                    RETURNING CLOB
                )
                ORDER BY sub.sort_bucket ASC, sub.begin_date_raw DESC
                RETURNING CLOB
            ),
            TO_CLOB('[]')
        )
        INTO x_worklist_json
        FROM (
            SELECT wn.notification_id,
                   wn.message_type,
                   wn.message_name,
                   wn.recipient_role,
                   wn.status,
                   COALESCE(
                       wn.subject,
                       (SELECT MAX(wna_s.text_value)
                          FROM apps.wf_notification_attributes wna_s
                         WHERE wna_s.notification_id = wn.notification_id
                           AND wna_s.name = 'SUBJECT')
                   ) AS subject,
                   wn.priority,
                   TO_CHAR(
                       wn.begin_date, 'YYYY-MM-DD"T"HH24:MI:SS'
                   ) AS begin_date,
                   TO_CHAR(
                       wn.due_date, 'YYYY-MM-DD"T"HH24:MI:SS'
                   ) AS due_date,
                   wn.begin_date AS begin_date_raw,
                   CASE
                       WHEN wn.message_type IN (
                           'APEXP', 'POAPPRV', 'POAPPR', 'REQAPPRV',
                           'REQAPPR', 'OKCAUKAP', 'CREATEPO', 'AMSGAPP'
                       ) THEN 0
                       ELSE 1
                   END AS sort_bucket
              FROM apps.wf_notifications wn
             WHERE wn.status = l_status
               AND (
                   p_recipient IS NULL
                   OR UPPER(wn.recipient_role) = UPPER(p_recipient)
               )
               AND (
                   p_message_type IS NULL
                   OR UPPER(wn.message_type) LIKE
                       RTRIM(UPPER(p_message_type), 'V') || '%'
               )
             ORDER BY sort_bucket ASC, wn.begin_date DESC
             OFFSET l_offset ROWS FETCH NEXT l_limit ROWS ONLY
        ) sub;
    END get_open_worklist;

    PROCEDURE get_notification_info(
        p_nid       IN  NUMBER,
        x_info_json OUT CLOB
    ) IS
        l_exists       NUMBER := 0;
        l_role         VARCHAR2(320);
        l_message_type VARCHAR2(8);
        l_message_name VARCHAR2(30);
        l_priority     NUMBER;
        l_due_date     DATE;
        l_status       VARCHAR2(8);
        l_subject      VARCHAR2(2000);
        l_begin_date   VARCHAR2(40);
        l_due_date_str VARCHAR2(40);
        l_amount       NUMBER;
    BEGIN
        SELECT COUNT(*)
          INTO l_exists
          FROM apps.wf_notifications
         WHERE notification_id = p_nid;

        IF l_exists = 0 THEN
            x_info_json := NULL;
            RETURN;
        END IF;

        apps.wf_notification.GetInfo(
            nid          => p_nid,
            role         => l_role,
            message_type => l_message_type,
            message_name => l_message_name,
            priority     => l_priority,
            due_date     => l_due_date,
            status       => l_status
        );

        IF l_status = 'OPEN' AND l_role IS NOT NULL THEN
            ensure_active_role(l_role);
        END IF;

        SELECT TO_CHAR(wn.begin_date, 'YYYY-MM-DD"T"HH24:MI:SS'),
               TO_CHAR(wn.due_date, 'YYYY-MM-DD"T"HH24:MI:SS'),
               COALESCE(
                   wn.subject,
                   (SELECT MAX(wna_s.text_value)
                      FROM apps.wf_notification_attributes wna_s
                     WHERE wna_s.notification_id = wn.notification_id
                       AND wna_s.name = 'SUBJECT')
               )
          INTO l_begin_date, l_due_date_str, l_subject
          FROM apps.wf_notifications wn
         WHERE wn.notification_id = p_nid;

        l_amount := resolve_notification_amount(p_nid);

        SELECT JSON_OBJECT(
            'notification_id' VALUE p_nid,
            'message_type'    VALUE l_message_type,
            'message_name'    VALUE l_message_name,
            'recipient_role'  VALUE l_role,
            'status'          VALUE l_status,
            'subject'         VALUE l_subject,
            'priority'        VALUE l_priority,
            'begin_date'      VALUE l_begin_date,
            'due_date'        VALUE l_due_date_str,
            'amount'          VALUE l_amount
            RETURNING CLOB
        )
        INTO x_info_json
        FROM dual;
    END get_notification_info;

    PROCEDURE get_notification_attrs(
        p_nid        IN  NUMBER,
        x_attrs_json OUT CLOB
    ) IS
    BEGIN
        SELECT COALESCE(
            JSON_ARRAYAGG(
                JSON_OBJECT(
                    'name'         VALUE wna.name,
                    'text_value'   VALUE wna.text_value,
                    'number_value' VALUE wna.number_value,
                    'date_value'   VALUE TO_CHAR(
                        wna.date_value, 'YYYY-MM-DD"T"HH24:MI:SS'
                    )
                    RETURNING CLOB
                )
                RETURNING CLOB
            ),
            TO_CLOB('[]')
        )
        INTO x_attrs_json
        FROM apps.wf_notification_attributes wna
        WHERE wna.notification_id = p_nid;
    END get_notification_attrs;

    PROCEDURE respond_notification(
        p_user_id      IN NUMBER,
        p_resp_id      IN NUMBER,
        p_resp_appl_id IN NUMBER,
        p_nid          IN NUMBER,
        p_result       IN VARCHAR2,
        p_comment      IN VARCHAR2,
        p_responder    IN VARCHAR2
    ) IS
    BEGIN
        apps.fnd_global.apps_initialize(
            user_id      => p_user_id,
            resp_id      => p_resp_id,
            resp_appl_id => p_resp_appl_id
        );

        FOR r_ntf IN (
            SELECT recipient_role
              FROM apps.wf_notifications
             WHERE notification_id = p_nid
        ) LOOP
            ensure_active_role(r_ntf.recipient_role);
        END LOOP;

        FOR r_attr IN (
            SELECT name
              FROM apps.wf_notification_attributes
             WHERE notification_id = p_nid
               AND name IN ('RESULT', 'WF_NOTE')
        ) LOOP
            IF r_attr.name = 'RESULT' THEN
                apps.wf_notification.setattrtext(
                    nid    => p_nid,
                    aname  => 'RESULT',
                    avalue => p_result
                );
            ELSIF r_attr.name = 'WF_NOTE' THEN
                apps.wf_notification.setattrtext(
                    nid    => p_nid,
                    aname  => 'WF_NOTE',
                    avalue => p_comment
                );
            END IF;
        END LOOP;

        apps.wf_notification.respond(
            nid             => p_nid,
            respond_comment => p_comment,
            responder       => p_responder
        );
    END respond_notification;

END XX_EBS_WF_AGENT_PKG;
