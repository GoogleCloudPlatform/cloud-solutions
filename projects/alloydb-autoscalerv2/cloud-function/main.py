import os
import time
import logging
import requests
from google.cloud import monitoring_v3
from google.auth.transport.requests import Request
from google.auth import default

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def get_env_variable(var_name, default_value=None):
    value = os.getenv(var_name, default_value)
    if value is None:
        logger.error(f"Missing required environment variable: {var_name}")
        raise EnvironmentError(f"Missing required environment variable: {var_name}")
    return value

def load_config():
    min_cpu = int(get_env_variable("MIN_CPU", 2))
    max_cpu = int(get_env_variable("MAX_CPU", 16))
    min_nodes = int(get_env_variable("MIN_NODES", 1))
    max_nodes = int(get_env_variable("MAX_NODES", 5))
    project_id = get_env_variable("GCP_PROJECT")
    region = get_env_variable("ALLOYDB_REGION")
    return min_cpu, max_cpu, min_nodes, max_nodes, project_id, region

def get_authenticated_headers():
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not credentials.valid:
        credentials.refresh(Request())
    return {"Authorization": f"Bearer {credentials.token}"}

def get_alloydb_clusters(headers, project_id, region):
    url = f"https://alloydb.googleapis.com/v1/projects/{project_id}/locations/{region}/clusters"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    clusters = response.json().get("clusters", [])
    return clusters

def get_cluster_instances(cluster_id, headers, project_id, region):
    url = f"https://alloydb.googleapis.com/v1/projects/{project_id}/locations/{region}/clusters/{cluster_id}/instances"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    instances = response.json().get("instances", [])
    return instances

def get_cpu_utilization_per_instance(project_id):
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"
    end_time = time.time()
    start_time = end_time - 300  # last 5 minutes

    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(end_time)},
        "start_time": {"seconds": int(start_time)},
    })

    filter_str = (
        'metric.type = "alloydb.googleapis.com/instance/cpu/average_utilization" '
        'AND resource.type = "alloydb.googleapis.com/Instance"'
    )

    aggregation = monitoring_v3.Aggregation({
        "alignment_period": {"seconds": 300},
        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    })

    results = client.list_time_series(
        request={
            "name": project_name,
            "filter": filter_str,
            "interval": interval,
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            "aggregation": aggregation,
        }
    )

    avg_utilization = {}

    for ts in results:
        instance_id = ts.resource.labels.get("instance_id")
        if not ts.points:
            logger.warning(f"No data points found for instance {instance_id}")
            continue

        latest_point = sorted(ts.points, key=lambda p: p.interval.end_time, reverse=True)[0]
        avg = latest_point.value.double_value
        avg_utilization[instance_id] = avg
        logger.info(f"Instance {instance_id}: 5-min average CPU usage = {avg:.2f}")

    return avg_utilization

def scale_primary_instance(instance, cpu_utilization, headers, min_cpu, max_cpu):
    current_cpu = int(instance["machineConfig"]["cpuCount"])
    instance_name = instance["name"]
    instance_id = instance_name.split("/")[-1]
    new_cpu = current_cpu

    logger.info(f"[{instance_id}][PRIMARY] Current CPU: {current_cpu}, Utilization: {cpu_utilization:.2f}")

    if cpu_utilization > 0.8 and current_cpu < max_cpu:
        new_cpu = min(current_cpu * 2, max_cpu)
    elif cpu_utilization < 0.2 and current_cpu > min_cpu:
        new_cpu = max(current_cpu // 2, min_cpu)

    if new_cpu != current_cpu:
        machine_type = f"n2-highmem-{new_cpu}"
        patch_body = {
            "machineConfig": {
                "cpuCount": new_cpu,
                "machineType": machine_type
            }
        }
        patch_url = f"https://alloydb.googleapis.com/v1/{instance_name}?updateMask=machineConfig.cpuCount,machineConfig.machineType"

        try:
            response = requests.patch(patch_url, headers=headers, json=patch_body)
            response.raise_for_status()
            logger.info(f"[{instance_id}][PRIMARY] Scaling operation initiated: {current_cpu} -> {new_cpu}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.warning(f"[{instance_id}][PRIMARY] Instance is busy (409 Conflict), scaling skipped")
            else:
                logger.error(f"[{instance_id}][PRIMARY] Scaling failed: {e}")
                raise
    else:
        logger.info(f"[{instance_id}][PRIMARY] No scaling needed.")

def scale_read_pool_instance(instance, cpu_utilization, headers, min_nodes, max_nodes):
    current_nodes = int(instance["readPoolConfig"]["nodeCount"])
    instance_name = instance["name"]
    instance_id = instance_name.split("/")[-1]
    new_nodes = current_nodes

    logger.info(f"[{instance_id}][READ_POOL] Current Nodes: {current_nodes}, Utilization: {cpu_utilization:.2f}")

    if cpu_utilization > 0.8 and current_nodes < max_nodes:
        new_nodes = current_nodes + 1
    elif cpu_utilization < 0.2 and current_nodes > min_nodes:
        new_nodes = current_nodes - 1

    if new_nodes != current_nodes:
        patch_body = {
            "readPoolConfig": {
                "nodeCount": new_nodes
            }
        }
        patch_url = f"https://alloydb.googleapis.com/v1/{instance_name}?updateMask=readPoolConfig.nodeCount"

        try:
            response = requests.patch(patch_url, headers=headers, json=patch_body)
            response.raise_for_status()
            logger.info(f"[{instance_id}][READ_POOL] Scaling operation initiated: {current_nodes} -> {new_nodes}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                logger.warning(f"[{instance_id}][READ_POOL] Instance is busy (409 Conflict), scaling skipped")
            else:
                logger.error(f"[{instance_id}][READ_POOL] Scaling failed: {e}")
                raise
    else:
        logger.info(f"[{instance_id}][READ_POOL] No scaling needed.")

def is_instance_ready_for_scaling(instance_name, headers):
    response = requests.get(f"https://alloydb.googleapis.com/v1/{instance_name}", headers=headers)
    response.raise_for_status()
    instance_data = response.json()

    state = instance_data.get("state", "UNKNOWN")
    logger.info(f"Instance {instance_name.split('/')[-1]} state: {state}")

    return state == "READY"

def scale_alloydb(request=None):
    logger.info("Function scale_alloydb invoked")

    try:
        min_cpu, max_cpu, min_nodes, max_nodes, project_id, region = load_config()
        headers = get_authenticated_headers()
        logger.info("Authenticated headers obtained")

        cpu_per_instance = get_cpu_utilization_per_instance(project_id)
        logger.info(f"CPU utilization per instance: {cpu_per_instance}")

        clusters = get_alloydb_clusters(headers, project_id, region)
        logger.info(f"Fetched {len(clusters)} clusters")

        for cluster in clusters:
            cluster_id = cluster["name"].split("/")[-1]
            logger.info(f"Processing cluster: {cluster_id}")

            instances = get_cluster_instances(cluster_id, headers, project_id, region)
            logger.info(f"Cluster {cluster_id} has {len(instances)} instances")

            for instance in instances:
                instance_name = instance["name"]
                instance_id = instance_name.split("/")[-1]
                cpu_util = cpu_per_instance.get(instance_id, 0.0)
                logger.info(f"Instance {instance_id}: type={instance.get('instanceType')}, CPU utilization={cpu_util:.2f}")

                # Check if instance is ready for scaling
                if not is_instance_ready_for_scaling(instance_name, headers):
                    logger.warning(f"Instance {instance_id} not ready for scaling, skipping")
                    continue

                instance_type = instance.get("instanceType")
                if instance_type == "PRIMARY":
                    scale_primary_instance(instance, cpu_util, headers, min_cpu, max_cpu)
                elif instance_type == "READ_POOL":
                    scale_read_pool_instance(instance, cpu_util, headers, min_nodes, max_nodes)
                else:
                    logger.warning(f"Unknown instance type: {instance_type}")

        logger.info("Autoscaling function completed successfully")
        return "OK"

    except Exception as e:
        logger.exception(f"Error during AlloyDB scaling: {e}")
        raise
