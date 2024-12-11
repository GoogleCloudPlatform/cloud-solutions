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

"""Provides a base test framework for testing DAG tasks."""

import datetime
import pendulum

import airflow
from airflow import models
from airflow import settings
from airflow.decorators import task
from airflow.decorators import task_group
from airflow.operators import python as airflow_operators
from airflow.utils import state
from airflow.utils import types as dag_types

from absl.testing import parameterized
from typing import Any, Mapping, Optional


class DagTestCase(parameterized.TestCase):
    """Base Test class for DAG task / operator testing."""

    def setUp(self):
        """Sets up DAG tests."""
        super().setUp()
        self.start_date = pendulum.datetime(2024, 1, 1)
        self.dag = airflow.DAG(
            'test_dag',
            schedule='@once',
            start_date=self.start_date,
        )
        self.session = settings.Session()
        # Clear up before running, in case a previous run failed.
        self._clear_test_dag()

    def tearDown(self):
        """Cleans up DAG tests."""
        super().tearDown()
        self._clear_test_dag()

    def asssertDagStructure(
        self, dag: models.DAG, dag_structure: dict[str, list[str]]
    ):
        """Asserts that the DAG structure follows the expectations.

        Asserts:
            The task exists.
            The task has expected downstream dependencies.

        Args:
            dag: DAG under test.
            dag_structure: expected structure of the tasks where:
                - the key represent the task_id.
                - the value is a list of expected downstream tasks.
        """
        for task_id, task_dependencies in dag_structure.items():
            self.assertTrue(
                dag.has_task(task_id),
                f'Expected task {task_id} to exist, but it was not found.',
            )

            dag_task = dag.get_task(task_id)
            unique_expected_tasks = list(set(task_dependencies))
            self.assertCountEqual(
                dag_task.downstream_task_ids,
                unique_expected_tasks,
                f'Expected downstream tasks of {task_id} '
                f'to be: {unique_expected_tasks}, '
                f'but found: {dag_task.downstream_task_ids}.',
            )

    def assertDagTaskRunSuccessfully(self, dagrun, task_id: str):
        """Asserts that given task id has run successfully.

        Args:
            dagrun: DAG run in which to check.
            task_id: task id of the task whose instance will be checked.
        """
        task_instance = dagrun.fetch_task_instance(
            dag_id=dagrun.dag_id, dag_run_id=dagrun.run_id, task_id=task_id
        )
        self.assertIsNotNone(
            task_instance,
            msg=(
                f'Expected task `{task_id}` to have run successfully, '
                'but the task instance was not found.'
            ),
        )
        self.assertEqual(
            task_instance.state,
            state.TaskInstanceState.SUCCESS,
            msg=(
                f'Expected task `{task_id}` to have run successfully, '
                'but the task state was {task_instance.state} instead.'
            ),
        )

    def create_xcom_push_task(
        self, xcom_task_id: str, xcom_map: Mapping[str, Any]
    ):
        """Creates a task to set up / push XCom variables.

        Args:
            xcom_task_id: id of the task to push Xcom.
            xcom_map: mapping of XCom keys to their values.

        Returns:
            Task that executes the Xcom.
        """

        @task(task_id=xcom_task_id)
        def xcom_push():
            context = airflow_operators.get_current_context()
            return_value = None
            for xcom_key, xcom_value in xcom_map.items():
                # To push `return_value`, the value must be returned instead.
                if xcom_key == 'return_value':
                    return_value = xcom_value
                    continue
                context['ti'].xcom_push(
                    key=xcom_key,
                    value=xcom_value,
                )
            if return_value is not None:
                return return_value

        return xcom_push()

    def create_xcom_push_task_group(
        self,
        xcom_data: Mapping[str, Mapping[str, Any]],
        xcom_group_id: Optional[str] = 'xcom_group',
    ):
        """Creates a task group with tasks to set up / push Xcom variables.

        These variables are normally called from a different task in a previous
        step. This is the equivalent of mocking Xcom.

        Args:
            xcom_data: map of variables where the key is the task name
                and the value is another map of the XCom key and its value.
            xcom_group_id: group id for the task group. This will not be used
                as part of the task_id name, but may be helpful when more than
                one task group is run, if ever.

        Returns:
            Task group with all the tasks.
        """

        @task_group(group_id=xcom_group_id, prefix_group_id=False)
        def xcom_push_group():
            previous_task = None
            for xcom_task_id, xcom_map in xcom_data.items():
                next_task = self.create_xcom_push_task(
                    xcom_task_id=xcom_task_id,
                    xcom_map=xcom_map,
                )
                if previous_task:
                    previous_task.set_downstream(next_task)
                previous_task = next_task

        return xcom_push_group()

    def run_test_dag(self, run_all_tasks=True):
        """Runs the test DAG (self.dag).

        Args:
            run_all_tasks: whether to run all tasks. Normally, this is desirable
                but there might be cases where more control is needed.

        Returns:
            DagRun for the test DAG.
        """
        dagrun = self.dag.create_dagrun(
            state=state.DagRunState.RUNNING,
            execution_date=self.start_date,
            start_date=self.start_date,
            data_interval=(
                self.start_date,
                self.start_date + datetime.timedelta(days=1),
            ),
            run_type=dag_types.DagRunType.MANUAL,
        )

        self.tasks_run_set = set()
        for ti in dagrun.get_task_instances():
            ti.task = self.dag.get_task(task_id=ti.task_id)
            if run_all_tasks:
                self._run_task_id(dagrun, ti.task_id)

        return dagrun

    def _run_task_id(self, dagrun, task_id):
        """Runs a given task id.

        Args:
            dagrun: DAG run in which to execute task.
            task_id: task id for which to run the given task instance.
        """
        if task_id in self.tasks_run_set:
            return  # Already run before.

        task_instance = dagrun.fetch_task_instance(
            dag_id=dagrun.dag_id, dag_run_id=dagrun.run_id, task_id=task_id
        )
        if not task_instance.task:
            task_instance.task = self.dag.get_task(
                task_id=task_instance.task_id
            )

        # Ensures that all upstream tasks have run first.
        for upstream_task_id in task_instance.task.upstream_task_ids:
            self._run_task_id(dagrun, upstream_task_id)

        task_instance.run(ignore_ti_state=True)
        self.tasks_run_set.add(task_instance.task_id)

    def _clear_test_dag(self):
        """Deletes all dag runs for the test DAG."""
        (
            self.session.query(models.DagRun)
            .filter(models.DagRun.dag_id == self.dag.dag_id)
            .delete()
        )
        self.session.commit()
