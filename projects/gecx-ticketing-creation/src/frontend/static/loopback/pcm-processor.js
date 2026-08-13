// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/* global sampleRate */

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channelData = input[0]; // Mono channel
    const currentSampleRate = sampleRate; // Global sampleRate inside Worklet

    // Downsample from currentSampleRate to 16kHz
    const downsampled = this.downsample(
        channelData,
        currentSampleRate,
        this.targetSampleRate,
    );
    const int16Buffer = this.floatTo16BitPCM(downsampled);

    this.port.postMessage(int16Buffer);
    return true;
  }

  downsample(samples, fromRate, toRate) {
    if (fromRate === toRate) return samples;
    if (fromRate < toRate) {
      // Upsampling not expected, return as is
      return samples;
    }
    const sampleRateRatio = fromRate / toRate;
    const newLength = Math.round(samples.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetResultFraction = 0.0;

    while (offsetResult < result.length) {
      const nextOffsetResultFraction = offsetResultFraction + sampleRateRatio;
      const index = Math.floor(offsetResultFraction);
      const nextIndex = Math.floor(nextOffsetResultFraction);

      let sum = 0;
      let count = 0;
      for (let i = index; i < nextIndex && i < samples.length; i++) {
        sum += samples[i];
        count++;
      }
      if (count > 0) {
        result[offsetResult] = sum / count;
      } else {
        result[offsetResult] = 0;
      }
      offsetResult++;
      offsetResultFraction = nextOffsetResultFraction;
    }
    return result;
  }

  floatTo16BitPCM(input) {
    const buffer = new ArrayBuffer(input.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      // true for little endian
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
