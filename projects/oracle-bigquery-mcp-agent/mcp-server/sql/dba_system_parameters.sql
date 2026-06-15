# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

SELECT i.instance_name, i.status, d.database_role, i.host_name,
       (SELECT banner FROM v$version WHERE ROWNUM = 1) AS banner,
       TO_CHAR(i.startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
FROM v$instance i
CROSS JOIN v$database d
