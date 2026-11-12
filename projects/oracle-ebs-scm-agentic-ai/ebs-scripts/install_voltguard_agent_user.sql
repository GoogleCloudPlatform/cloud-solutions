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
-- Creates VOLTGUARD_AGENT, the Oracle EBS user that calls the
-- ge_ebs_scm_tools Integrated SOA Gateway (ISG) REST service. The user gets
-- the inventory and purchasing responsibilities of the writebacks and the
-- employee of an existing user, so requisitions keep the same preparer and
-- approvals. Oracle EBS records every writeback under VOLTGUARD_AGENT.
--
-- Run as APPS. The defaults below are the Oracle EBS Vision values: change
-- them to match terraform.tfvars. The script is idempotent: a second run
-- resets the password and keeps the responsibilities.
-- =============================================================================

SET VERIFY OFF
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
ACCEPT agent_password CHAR PROMPT 'Password for VOLTGUARD_AGENT: ' HIDE

-- Copy the password into a bind variable and turn substitution off, so no
-- statement below contains its text. The password can't contain ~'.
VARIABLE agent_password VARCHAR2(128)
EXECUTE :agent_password := q'~&agent_password~'
UNDEFINE agent_password
SET DEFINE OFF

DECLARE
    c_user                      CONSTANT VARCHAR2(30) := 'VOLTGUARD_AGENT';
    c_employee_user             CONSTANT VARCHAR2(100) := 'OPERATIONS';
    c_inventory_responsibility  CONSTANT VARCHAR2(30) :=
        'INVENTORY_VISION_OPERATIONS';
    c_purchasing_responsibility CONSTANT VARCHAR2(30) :=
        'PURCHASING_OPERATIONS';
    l_employee_id NUMBER;
BEGIN
    SELECT employee_id
      INTO l_employee_id
      FROM applsys.fnd_user
     WHERE user_name = c_employee_user;

    -- Create the user without the employee first: Oracle Workflow registers
    -- the user's role, which the responsibility assignments need, only for
    -- users that don't have an employee yet.
    IF fnd_user_pkg.testusername(c_user) = fnd_user_pkg.user_ok_create THEN
        fnd_user_pkg.createuser(
            x_user_name              => c_user,
            x_owner                  => NULL,
            x_unencrypted_password   => :agent_password,
            x_description            => 'VoltGuard supply chain agent (ISG)',
            x_password_date          => SYSDATE,
            x_password_lifespan_days => NULL
        );
    ELSE
        fnd_user_pkg.updateuser(
            x_user_name            => c_user,
            x_owner                => NULL,
            x_unencrypted_password => :agent_password,
            x_password_date        => SYSDATE
        );
    END IF;

    FOR r IN (
        SELECT fa.application_short_name, fr.responsibility_key
          FROM applsys.fnd_responsibility fr
          JOIN applsys.fnd_application fa
            ON fa.application_id = fr.application_id
         WHERE fr.responsibility_key IN (
                   c_inventory_responsibility, c_purchasing_responsibility
               )
    ) LOOP
        fnd_user_pkg.addresp(
            username       => c_user,
            resp_app       => r.application_short_name,
            resp_key       => r.responsibility_key,
            security_group => 'STANDARD',
            description    => 'VoltGuard writebacks',
            start_date     => TRUNC(SYSDATE),
            end_date       => NULL
        );
    END LOOP;

    -- Requisition Import uses this employee as the preparer.
    fnd_user_pkg.updateuser(
        x_user_name   => c_user,
        x_owner       => NULL,
        x_employee_id => l_employee_id
    );
    COMMIT;
END;
/

PROMPT VOLTGUARD_AGENT is ready. Grant it the ge_ebs_scm_tools ISG methods.
