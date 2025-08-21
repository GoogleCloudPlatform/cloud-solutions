// Copyright 2024 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// listen to df-response
window.addEventListener('df-response-received', (event) => {
  event.preventDefault(); // Dialogflow Messenger won't handle the responses.
  // check if flow's responses is available
  const flowPayloads = extractFlowPayloads(event.detail.raw);

  // check if generative responses is available
  const genResponses = extractGenerativeResponses(event.detail.raw);

  if (genResponses) {
    try {
      const dfMessenger = document.querySelector('df-messenger');
      for (const res of genResponses) {
        // eslint-disable-next-line no-prototype-builtins
        if (res.hasOwnProperty('agentUtterance')) {
          dfMessenger.renderCustomText(res.agentUtterance.text, true);
          // eslint-disable-next-line no-prototype-builtins
        } else if (res.hasOwnProperty('toolUse')) {
          const customPayload = extractCustomPayload(res.toolUse);
          if (customPayload) {
            dfMessenger.renderCustomCard(customPayload[0]);
          }
        } else if (
          res && res.flowInvocation &&
            res.flowInvocation.flowState == 'OUTPUT_STATE_OK') {
          for (const flowPayload of flowPayloads) {
            dfMessenger.renderCustomCard(flowPayload.payload.richContent[0]);
          }
        }
      }
    } catch (err) {
      console.log('error in generative response: ', err);
    }
  }

  if (flowPayloads) {
    try {
      const dfMessenger = document.querySelector('df-messenger');
      // eslint-disable-next-line no-unused-vars
      for (const res of flowPayloads) {
        for (const flowPayload of flowPayloads) {
          dfMessenger.renderCustomCard(flowPayload.payload.richContent[0]);
        }
      }
    } catch (err) {
      console.log('error in generative response: ', err);
    }
  }
});

function extractCustomPayload(dfTool) {
  try {
    if (dfTool.outputActionParameters && dfTool.outputActionParameters['200'] &&
        dfTool.outputActionParameters['200'].payload &&
        dfTool.outputActionParameters['200'].payload.richContent) {
      const richContent =
          dfTool.outputActionParameters['200'].payload.richContent;
      console.log(richContent);
      return richContent;
    } else {
      return false;
    }
  } catch (err) {
    console.log('error in tool response: ', err);
  }
}

function extractGenerativeResponses(dfResponse) {
  try {
    const dfActions =
      dfResponse.queryResult.generativeInfo.actionTracingInfo.actions;
    // eslint-disable-next-line max-len,no-prototype-builtins
    const filteredActions = dfActions.filter((action) => !action.hasOwnProperty('userUtterance'));

    if (filteredActions.length > 0) return filteredActions;

    return false;
    // eslint-disable-next-line no-unused-vars
  } catch (err) {
    return false;
  }
}

function extractFlowPayloads(dfResponse) {
  try {
    const flowResponses = dfResponse.queryResult.responseMessages;
    // eslint-disable-next-line max-len,no-prototype-builtins
    const flowPayloads = flowResponses.filter((response) => response.hasOwnProperty('payload'));
    if (flowPayloads.length > 0) return flowPayloads;

    return false;
    // eslint-disable-next-line no-unused-vars
  } catch (err) {
    return false;
  }
}
