-- Copyright 2025 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

CREATE EXTENSION IF NOT EXISTS dblink;

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Run immediately at the start of the minute
SELECT cron.schedule('sweep_00', '* * * * *', 'CALL exchange.execute_taker_sweep()');

-- Run at 10 seconds past
SELECT cron.schedule('sweep_10', '* * * * *', 'SELECT pg_sleep(10); CALL exchange.execute_taker_sweep()');

-- Run at 20 seconds past
SELECT cron.schedule('sweep_20', '* * * * *', 'SELECT pg_sleep(20); CALL exchange.execute_taker_sweep()');

-- Run at 30 seconds past
SELECT cron.schedule('sweep_30', '* * * * *', 'SELECT pg_sleep(30); CALL exchange.execute_taker_sweep()');

-- Run at 40 seconds past
SELECT cron.schedule('sweep_40', '* * * * *', 'SELECT pg_sleep(40); CALL exchange.execute_taker_sweep()');

-- Run at 50 seconds past
SELECT cron.schedule('sweep_50', '* * * * *', 'SELECT pg_sleep(50); CALL exchange.execute_taker_sweep()');

SELECT cron.schedule('maintain_snapshots', '0 * * * *', $$
    DELETE FROM exchange.order_book_snapshot
    WHERE created < now() - INTERVAL '72 hours';
$$);
