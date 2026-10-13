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

BEGIN
    apps.xx_ebs_wf_agent_pkg.respond_notification(
        p_user_id      => :user_id,
        p_resp_id      => :resp_id,
        p_resp_appl_id => :resp_appl_id,
        p_nid          => :nid,
        p_result       => :result_val,
        p_comment      => :comment_val,
        p_responder    => :responder_val
    );
END;
