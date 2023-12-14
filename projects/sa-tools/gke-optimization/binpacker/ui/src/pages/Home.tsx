/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { Container, Grid, SelectChangeEvent } from '@mui/material';
import { ChangeEvent, FC, useState } from 'react';
import ResponsiveAppBar from '../components/ResponsiveAppBar';
import Disclaimer from '../components/Disclaimer';
import BinpackResult from '../components/BinpackResult';
import WorkloadTable from '../components/WorkloadTable';
import PodTable from '../components/PodTable';
import ProjectIdField from '../components/ProjectIdField';
import MinNumNodesField from '../components/MinNumNodesField';
import ToggleViewLink from '../components/ToggleViewLink';
import { metricFetchAll } from '../services/MetricApi';
import DiscoverButton from '../components/DiscoverButton';
import ClusterSelector from '../components/ClusterSelector';
import NodePoolSelector, {
  UNSCHEDULED_LABEL,
  UNSCHEDULED_NODEPOOL,
} from '../components/NodePoolSelector';
import GetRecommendationButton from '../components/GetRecommendationButton';
import TestRecommendationButton from '../components/TestRecommendationButton';
import { binpackingCalculate } from '../services/BinpackingApi';
import {
  BinpackingCalculateRequest,
  BinpackingCalculateResponse,
} from '../../proto/binpacking.pb';
import {
  Cluster,
  MetricFetchAllResponse,
  Nodepool,
  Pod,
} from '../../proto/metric.pb';
import { notifyError, notifySuccess } from '../components/CustomToast';
import axios from 'axios';
import { PodExtended, Workload } from '../shared/types/types';
import { capitalizeWorkloadType } from '../shared/utils/string';
import { byteToMiB } from '../shared/utils/conversion';
import { Workload as RequestWorkload } from '../../proto/binpacking.pb';

const DEFAULT_MIN_NODES = 1;
const LOADING_MESSAGE = 'Fetching clusters, node pools and pods';

const Home: FC = () => {
  const [projectId, setProjectId] = useState<string>('');
  const [showWorkloadTable, setShowWorkloadTable] = useState<boolean>(true);
  const [minNodes, setMinNodes] = useState<number>(DEFAULT_MIN_NODES);
  const [loading, setLoading] = useState<boolean>(false);
  const [recommendation, setRecommendation] =
    useState<BinpackingCalculateResponse | null>(null);
  const [cluster, setCluster] = useState<Cluster | null>(null);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [nodePools, setNodePools] = useState<Nodepool[]>([]);
  const [clusterNodePools, setClusterNodePools] = useState<Nodepool[]>([]);
  const [selectedNodePools, setSelectedNodePools] = useState<Nodepool[]>([]);
  const [pods, setPods] = useState<Pod[]>([]);
  const [selectedWorkloads, setSelectedWorkloads] = useState<Workload[]>([]);
  const [selectedPods, setSelectedPods] = useState<PodExtended[]>([]);
  const [checkedIndexes, setCheckedIndexes] = useState<number[]>([]);

  const toggleView = () => {
    setShowWorkloadTable((value) => !value);
    setCheckedIndexes([]);
  };

  const onChangeProjectId = (e: ChangeEvent<HTMLInputElement>) => {
    setProjectId(e.target.value);
  };

  const onClickDiscover = async () => {
    setLoading(true);
    let metricFetchAllResponse: MetricFetchAllResponse | null = null;
    try {
      metricFetchAllResponse = await metricFetchAll({
        projectId: projectId,
      });
      notifySuccess(
        `Successfully discovered ${metricFetchAllResponse?.clusters.length} clusters, ${metricFetchAllResponse?.nodepools.length} node pools and ${metricFetchAllResponse?.pods.length} pods`
      );
    } catch (e) {
      let message = 'Failed to discover clusters, node pools and pods';
      let details;
      if (axios.isAxiosError(e)) {
        if (e.response) {
          details = e.response.data.details;
        } else if (e.request) {
          details = 'network error: failed to connect backend api';
        } else {
          details = e.message;
        }
      } else {
        details = 'unexpected error occured';
      }
      notifyError({
        message: message,
        details: details,
      });
    }
    setClusterNodePools([]);
    setSelectedNodePools([]);
    setSelectedWorkloads([]);
    setSelectedPods([]);
    setRecommendation(null);
    if (
      metricFetchAllResponse == null ||
      metricFetchAllResponse.clusters.length == 0
    ) {
      setLoading(false);
      return;
    }
    setClusters(metricFetchAllResponse.clusters);
    setNodePools(metricFetchAllResponse.nodepools);
    setPods(metricFetchAllResponse.pods);
    setLoading(false);
  };

  const onClickGetBinpackingRecommendation = async () => {
    setLoading(true);
    const binpackingRequest = buildBinpackingRequest();
    console.log(binpackingRequest);
    try {
      const binpackingCalculateResponse = await binpackingCalculate(
        binpackingRequest
      );
      setRecommendation(binpackingCalculateResponse);
    } catch (e) {
      let message = 'Failed to calculate recommendations';
      let details;
      if (axios.isAxiosError(e)) {
        if (e.response) {
          details = e.response.data.details;
        } else if (e.request) {
          details = 'network error: failed to connect backend api';
        } else {
          details = e.message;
        }
      } else {
        details = 'unexpected error occured';
      }
      notifyError({
        message: message,
        details: details,
      });
    }
    setLoading(false);
  };

  const buildBinpackingRequest = (): BinpackingCalculateRequest => {
    if (showWorkloadTable) {
      const requestWorkloads = checkedIndexes.flatMap((index) => {
        let ds: RequestWorkload[] = [];
        const existingWorkload = selectedWorkloads.at(index) as Workload;
        for (let i = 0; i < existingWorkload.replicas; i++) {
          ds.push({
            cpuRequest: existingWorkload.cpuRequest,
            cpuLimit: existingWorkload.cpuLimit,
            memoryRequest: existingWorkload.memoryRequest,
            memoryLimit: existingWorkload.memoryLimit,
          });
        }
        return ds;
      });
      return {
        workloads: requestWorkloads,
        minNumNodes: minNodes,
      };
    }

    const requestWorkloads: RequestWorkload[] = checkedIndexes.map((index) => {
      const existingPod = selectedPods.at(index) as PodExtended;
      return {
        cpuRequest: existingPod.cpuRequest,
        cpuLimit: existingPod.cpuLimit,
        memoryRequest: existingPod.memoryRequest,
        memoryLimit: existingPod.memoryLimit,
      };
    });
    return {
      workloads: requestWorkloads,
      minNumNodes: minNodes,
    };
  };

  const onChangeCluster = (event: SelectChangeEvent<Cluster>) => {
    const selectedCluster = event.target.value as Cluster;
    setCluster(selectedCluster);
    const filteredNodePools = nodePools.filter(
      (item) =>
        item.cluster === selectedCluster.name &&
        item.clusterLocation === selectedCluster.location
    );
    const filteredNodePoolsWithUnscheduled = [
      ...filteredNodePools,
      UNSCHEDULED_NODEPOOL,
    ];
    setClusterNodePools(filteredNodePoolsWithUnscheduled);
    setSelectedNodePools(filteredNodePoolsWithUnscheduled);

    const selectedNodePoolNames = filteredNodePoolsWithUnscheduled.map(
      (item) => {
        if (item.name === UNSCHEDULED_LABEL) return '';
        return item.name;
      }
    );

    setSelectedWorkloads(
      buildWorkloads(selectedNodePoolNames, selectedCluster)
    );
    setSelectedPods(buildPods(selectedNodePoolNames, selectedCluster));
  };

  const onChangeSelectedNodePools = (event: SelectChangeEvent<Nodepool[]>) => {
    const updatedNodePools = event.target.value as Nodepool[];
    setSelectedNodePools(updatedNodePools);

    const selectedNodePoolNames = updatedNodePools.map((item) => {
      if (item.name === UNSCHEDULED_LABEL) return '';
      return item.name;
    });

    setSelectedWorkloads(buildWorkloads(selectedNodePoolNames));
    setSelectedPods(buildPods(selectedNodePoolNames));
    setCheckedIndexes([]);
  };

  const onChangeMinNodes = (e: ChangeEvent<HTMLInputElement>) => {
    setMinNodes(parseInt(e.target.value));
  };

  const buildWorkloads = (
    selectedNodePoolNames: string[],
    selectedCluster?: Cluster
  ): Workload[] => {
    if (selectedCluster == null && cluster == null) return [];

    const existedCluster = (
      selectedCluster != null ? selectedCluster : cluster
    ) as Cluster;

    const filteredPods = pods.filter((pod) => {
      return (
        pod.cluster === existedCluster.name &&
        pod.clusterLocation === existedCluster.location &&
        selectedNodePoolNames.includes(pod.nodepool)
      );
    });

    const groupedWorkloads = filteredPods.reduce(
      (result: Workload[], current: Pod) => {
        const element = result.find(
          (p) =>
            p.namespace === current.namespace &&
            p.type === capitalizeWorkloadType(current.parentType.toString()) &&
            p.name === current.parent
        );
        if (element) {
          element.replicas++;
        } else {
          result.push({
            name: current.parent,
            type: capitalizeWorkloadType(current.parentType.toString()),
            namespace: current.namespace,
            replicas: 1,
            cpuRequest: current.cpuRequest,
            cpuLimit: current.cpuLimit,
            memoryRequest: current.memoryRequest,
            memoryLimit: current.memoryLimit,
            memoryRequestInMiB: byteToMiB(current.memoryRequest),
            memoryLimitInMiB: byteToMiB(current.memoryLimit),
          });
        }
        return result;
      },
      []
    );
    return groupedWorkloads;
  };

  const buildPods = (
    selectedNodePoolNames: string[],
    selectedCluster?: Cluster
  ): PodExtended[] => {
    if (selectedCluster == null && cluster == null) return [];

    const existedCluster = (
      selectedCluster != null ? selectedCluster : cluster
    ) as Cluster;

    const filteredPods = pods.filter((pod) => {
      return (
        pod.cluster === existedCluster.name &&
        pod.clusterLocation === existedCluster.location &&
        selectedNodePoolNames.includes(pod.nodepool)
      );
    });

    return filteredPods.map((pod) => ({
      ...pod,
      memoryRequestInMiB: byteToMiB(pod.memoryRequest),
      memoryLimitInMiB: byteToMiB(pod.memoryLimit),
    }));
  };

  return (
    <>
      <ResponsiveAppBar />
      <Container
        component='main'
        maxWidth='xl'
        sx={{ mt: 12 }}>
        <Grid
          container
          spacing={2}>
          <Grid
            item
            xs={12}
            sx={{ mb: 2 }}>
            <Disclaimer />
          </Grid>
          <Grid
            item
            xs={8}
            container
            spacing={1}
            alignContent='flex-start'>
            <Grid
              item
              sx={{ backgroundColor: 'white' }}
              xs={9}>
              <ProjectIdField
                projectId={projectId}
                onChange={onChangeProjectId}
                editable={!loading}
              />
            </Grid>
            <Grid
              item
              xs={3}>
              <DiscoverButton
                clickable={!loading && projectId.length > 0}
                onClick={onClickDiscover}
              />
            </Grid>
            <Grid
              item
              xs={6}>
              <ClusterSelector
                cluster={cluster}
                clusters={clusters}
                selectable={!loading && clusters != null && clusters.length > 0}
                onChange={onChangeCluster}
              />
            </Grid>
            <Grid
              item
              xs={6}>
              <NodePoolSelector
                nodePools={clusterNodePools}
                selectedNodePools={selectedNodePools}
                selectable={
                  !loading &&
                  clusterNodePools != null &&
                  clusterNodePools.length > 0
                }
                onChange={onChangeSelectedNodePools}
              />
            </Grid>
            <Grid
              item
              xs={12}
              sx={{ mt: 2, mb: 2 }}>
              {showWorkloadTable ? (
                <WorkloadTable
                  workloads={selectedWorkloads}
                  setCheckedIndexes={setCheckedIndexes}
                  checkedIndexes={checkedIndexes}
                  loading={loading}
                  loadingMessage={LOADING_MESSAGE}
                />
              ) : (
                <PodTable
                  pods={selectedPods}
                  setCheckedIndexes={setCheckedIndexes}
                  checkedIndexes={checkedIndexes}
                  loading={loading}
                  loadingMessage={LOADING_MESSAGE}
                />
              )}
            </Grid>
            <Grid
              item
              xs={4}>
              <ToggleViewLink
                showWorkloadsView={showWorkloadTable}
                onClick={toggleView}
                clickable={!loading}
              />
            </Grid>
            <Grid
              item
              xs={4}>
              <MinNumNodesField
                minNodes={minNodes}
                onChange={onChangeMinNodes}
              />
            </Grid>
            <Grid
              item
              xs={4}>
              <GetRecommendationButton
                clickable={!loading && checkedIndexes.length > 0}
                onClick={onClickGetBinpackingRecommendation}
              />
            </Grid>
          </Grid>
          <Grid
            item
            container
            xs={4}
            spacing={2}
            justifyContent='center'
            alignItems='flex-start'>
            <Grid
              item
              xs={12}>
              <BinpackResult response={recommendation} />
              <TestRecommendationButton />
            </Grid>
          </Grid>
        </Grid>
      </Container>
    </>
  );
};

export default Home;
