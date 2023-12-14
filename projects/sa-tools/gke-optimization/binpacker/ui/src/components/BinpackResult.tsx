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
import { Box, Card, CardContent, Divider, Typography } from '@mui/material';
import { FC } from 'react';
import { BinpackingCalculateResponse } from '../../proto/binpacking.pb';
import { byteToGiB, roundMemoryGib } from '../shared/utils/conversion';

type Props = {
  response: BinpackingCalculateResponse | null;
};

const BinpackResult: FC<Props> = ({ response }) => {
  const nodeSpec = (): string => {
    if (response == null || response.recommendation == null)
      return '-------------------';
    const { cpu, memory, numNodes } = response.recommendation;
    return cpu.toString() + ' CPUs ' + memory + ' GB x ' + numNodes;
  };

  const totalCpu = (): string => {
    if (response == null || response.recommendation == null) return '--';
    const { cpu, numNodes } = response.recommendation;
    return (cpu * numNodes).toString();
  };

  const totalMemory = (): string => {
    if (response == null || response.recommendation == null) return '--';
    const { memory, numNodes } = response.recommendation;
    return (memory * numNodes).toString();
  };

  return (
    <>
      <Card>
        <CardContent>
          <Typography
            sx={{ fontWeight: 'bold' }}
            align='center'>
            RECOMMENDATION
          </Typography>
          <Typography
            sx={{ mb: 2, mt: 2 }}
            align='center'>
            Nodes: {nodeSpec()}
          </Typography>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'flex-end',
            }}>
            <Typography variant='h4'>{totalCpu()}</Typography>{' '}
            <Box sx={{ ml: 1 }}>vCPUs</Box>
            <Typography
              variant='h4'
              sx={{ ml: 2 }}>
              {totalMemory()}
            </Typography>
            <Box sx={{ ml: 1 }}>GB</Box>
          </Box>
          <Divider
            variant='middle'
            sx={{ mt: 2, mb: 2 }}
          />

          <Typography
            sx={{ fontWeight: 'bold', mb: 2 }}
            align='center'>
            REQUEST DETAILS
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <Box>
              <Typography sx={{ mb: 2, fontSize: 14, fontWeight: 'bold' }}>
                CPU
              </Typography>
              <Box sx={{ display: 'flex' }}>
                <Box sx={{ textAlign: 'left', mr: 1 }}>
                  <Typography sx={{ fontSize: 12 }}>Total requests:</Typography>
                  <Typography sx={{ fontSize: 12 }}>Max limit:</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.requestDetail?.totalCpuRequest || '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.requestDetail?.maxCpuLimit || '-----'}
                  </Typography>
                </Box>
              </Box>
            </Box>
            <Divider
              orientation='vertical'
              variant='middle'
              flexItem
              sx={{ mx: 2 }}
            />
            <Box>
              <Typography sx={{ mb: 2, fontSize: 14, fontWeight: 'bold' }}>
                Memory (GB)
              </Typography>
              <Box sx={{ display: 'flex' }}>
                <Box sx={{ textAlign: 'left', mr: 1 }}>
                  <Typography sx={{ fontSize: 12 }}>Total requests:</Typography>
                  <Typography sx={{ fontSize: 12 }}>Max limit:</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.requestDetail?.totalMemoryRequest
                      ? roundMemoryGib(
                          byteToGiB(response.requestDetail.totalMemoryRequest)
                        )
                      : '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {/* {response != null && response.requestDetail != null */}
                    {response?.requestDetail?.maxMemoryLimit
                      ? roundMemoryGib(
                          byteToGiB(response.requestDetail.maxMemoryLimit)
                        )
                      : '-----'}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Box>
          <Divider
            variant='middle'
            sx={{ mt: 2, mb: 2 }}
          />
          <Typography
            sx={{ fontWeight: 'bold', mb: 2 }}
            align='center'>
            BREAKDOWN (PER NODE)
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <Box>
              <Typography sx={{ mb: 2, fontSize: 14, fontWeight: 'bold' }}>
                CPU
              </Typography>
              <Box sx={{ display: 'flex' }}>
                <Box sx={{ textAlign: 'left', mr: 1 }}>
                  <Typography sx={{ fontSize: 12 }}>Reserved:</Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    Kube-system resources:
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>Allocatable:</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.cpu?.reserved ||
                      '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.cpu?.systemUsage ||
                      '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.cpu
                      ?.capacityUserWorkloads || '-----'}
                  </Typography>
                </Box>
              </Box>
            </Box>
            <Divider
              orientation='vertical'
              variant='middle'
              flexItem
              sx={{ mx: 2 }}
            />
            <Box>
              <Typography sx={{ mb: 2, fontSize: 14, fontWeight: 'bold' }}>
                Memory (GB)
              </Typography>
              <Box sx={{ display: 'flex' }}>
                <Box sx={{ textAlign: 'left', mr: 1 }}>
                  <Typography sx={{ fontSize: 12 }}>
                    Kernel reservation:
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>Reserved:</Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    Eviction threshold:
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    Kube-system resources:
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>Allocatable:</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.memory?.kernelUsage
                      ? roundMemoryGib(
                          byteToGiB(
                            response?.recommendationBreakdown?.memory
                              ?.kernelUsage
                          )
                        )
                      : '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.memory?.reserved
                      ? roundMemoryGib(
                          byteToGiB(
                            response?.recommendationBreakdown?.memory?.reserved
                          )
                        )
                      : '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.memory
                      ?.evictionThreshold
                      ? roundMemoryGib(
                          byteToGiB(
                            response?.recommendationBreakdown?.memory
                              ?.evictionThreshold
                          )
                        )
                      : '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.memory?.systemUsage
                      ? roundMemoryGib(
                          byteToGiB(
                            response?.recommendationBreakdown?.memory
                              ?.systemUsage
                          )
                        )
                      : '-----'}
                  </Typography>
                  <Typography sx={{ fontSize: 12 }}>
                    {response?.recommendationBreakdown?.memory
                      ?.capacityUserWorkloads
                      ? roundMemoryGib(
                          byteToGiB(
                            response?.recommendationBreakdown?.memory
                              ?.capacityUserWorkloads
                          )
                        )
                      : '-----'}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Box>

          <Typography
            sx={{ mt: 3, fontSize: 14 }}
            align='center'>
            See calculation logic{' '}
            <a
              href='https://cloud.google.com/kubernetes-engine/docs/concepts/plan-node-sizes'
              target='_blank'
              rel='noreferrer'>
              here
            </a>
            .
          </Typography>
        </CardContent>
      </Card>
    </>
  );
};

export default BinpackResult;
