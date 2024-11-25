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

/* eslint-disable */

// listen to df-response
window.addEventListener('df-response-received', (event) => {
  event.preventDefault(); // Dialogflow Messenger won't handle the responses.

  // check if flow's responses is available
  let flowPayloads = extractFlowPayloads(event.detail.raw);

  // check if generative responses is available
  let genResponses = extractGenerativeResponses(event.detail.raw);

  if(genResponses){
    try {
      const dfMessenger = document.querySelector('df-messenger');
      for(const res of genResponses) {
        if(res.hasOwnProperty("agentUtterance")){
          dfMessenger.renderCustomText(res.agentUtterance.text, true);
        } else if(res.hasOwnProperty("toolUse")) {
          let customPayload = extractCustomPayload(res.toolUse);
          if(customPayload) {
            dfMessenger.renderCustomCard(customPayload[0]);
          }
        } else if(res && res.flowInvocation && res.flowInvocation.flowState == "OUTPUT_STATE_OK") {
          for (const flowPayload of flowPayloads) {
              dfMessenger.renderCustomCard(flowPayload.payload.richContent[0]);
          }
        }
      }
    } catch(err) {
      console.log("error in generative response: ", err);
    }
  }
});

function extractCustomPayload(dfTool) {
  try {
      if (dfTool.outputActionParameters && dfTool.outputActionParameters["200"] && dfTool.outputActionParameters["200"].payload && dfTool.outputActionParameters["200"].payload.richContent) {
          return dfTool.outputActionParameters["200"].payload.richContent
      }
      else {
          return false
      }
  } catch (err) {
      console.log("error in tool response: ", err);
  }
}

function extractGenerativeResponses(dfResponse) {
  try {
      let dfActions = dfResponse.queryResult.generativeInfo.actionTracingInfo.actions;
      let filteredActions = dfActions.filter(action => !action.hasOwnProperty("userUtterance"));

      if(filteredActions.length > 0) return filteredActions;

      return false;
  } catch (err) {
      return false;
  }
}

function extractFlowPayloads(dfResponse) {
  try {
      let flowResponses = dfResponse.queryResult.responseMessages;
      let flowPayloads = flowResponses.filter(response => response.hasOwnProperty("payload"));

      if(flowPayloads.length > 0) return flowPayloads;

      return false;
  } catch (err) {
      return false;
  }
}
