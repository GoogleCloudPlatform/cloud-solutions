#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Sets up the Database Archival and Pruning DAG.

This is separated from dag_archive_and_prune for two reasons:

1.  Airflow requires the dag definition to be done on the file at global level.
    This is achieved here.

2.  We do not want to do this on dag_archive_and_prune, because then the DAG
    will be created/run when importing the module, which would difficult
    testing whenever mocking or faking is needed. Airflow does not detect the
    DAG if it is inside `if __name__ == "__main__"`.
"""

import airflow
from airflow.utils.dates import days_ago
from database_archival.dag import config
from database_archival.dag import dag_archive_and_prune

dag = airflow.DAG(
    dag_id=config.DAG_NAME,
    schedule=config.DAG_SCHEDULE_INTERVAL,
    start_date=days_ago(1),
)
dag_archive_and_prune.set_up_archive_and_prune_dag(dag)
