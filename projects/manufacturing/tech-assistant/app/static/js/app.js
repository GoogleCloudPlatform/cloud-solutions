/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * app.js: JS code for the ADK Gemini Live API Toolkit demo app.
 */

/**
 * WebSocket handling
 */

// Connect the server with a WebSocket connection
const userId = 'demo-user';
const sessionId = 'demo-session-' + Math.random().toString(36).substring(7);
let websocket = null;
let isAudio = false;

// Get checkbox elements for RunConfig options
const enableProactivityCheckbox = document.getElementById('enableProactivity');
const enableAffectiveDialogCheckbox = document.getElementById(
    'enableAffectiveDialog');

// Reconnect WebSocket when RunConfig options change
function handleRunConfigChange() {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    addSystemMessage('Reconnecting with updated settings...');
    addConsoleEntry('outgoing', 'Reconnecting due to settings change', {
      proactivity: enableProactivityCheckbox.checked,
      affective_dialog: enableAffectiveDialogCheckbox.checked,
    }, '🔄', 'system');
    websocket.close();
    // connectWebsocket() will be called by onclose handler after delay
  }
}

// Add change listeners to RunConfig checkboxes
enableProactivityCheckbox.addEventListener('change', handleRunConfigChange);
enableAffectiveDialogCheckbox.addEventListener('change', handleRunConfigChange);

// Build WebSocket URL with RunConfig options as query parameters
function getWebSocketUrl() {
  // Use wss:// for HTTPS pages, ws:// for HTTP (localhost development)
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const baseUrl = wsProtocol + '//' + window.location.host + '/ws/' +
      userId + '/' + sessionId;
  const params = new URLSearchParams();

  // Add proactivity option if checked
  if (enableProactivityCheckbox && enableProactivityCheckbox.checked) {
    params.append('proactivity', 'true');
  }

  // Add affective dialog option if checked
  if (enableAffectiveDialogCheckbox && enableAffectiveDialogCheckbox.checked) {
    params.append('affective_dialog', 'true');
  }

  const queryString = params.toString();
  return queryString ? baseUrl + '?' + queryString : baseUrl;
}

// Get DOM elements
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message');
const messagesDiv = document.getElementById('messages');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('status-text');
const consoleContent = document.getElementById('consoleContent');
const clearConsoleBtn = document.getElementById('clearConsole');
const showAudioEventsCheckbox = document.getElementById('showAudioEvents');
let currentMessageId = null;
let currentBubbleElement = null;
let currentInputTranscriptionId = null;
let currentInputTranscriptionElement = null;
let currentOutputTranscriptionId = null;
let currentOutputTranscriptionElement = null;
// Track if input transcription is complete for this turn
let inputTranscriptionFinished = false;
// Track if output transcription delivered the response
let hasOutputTranscriptionInTurn = false;

// Helper function to clean spaces between CJK characters
// Removes spaces between Japanese/Chinese/Korean characters while preserving
// spaces around Latin text
function cleanCJKSpaces(text) {
  // CJK Unicode ranges: Hiragana, Katakana, Kanji, CJK Unified Ideographs,
  // Fullwidth forms
  const cjkPattern = new RegExp(
      '[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uff00-\uffef]');

  // Remove spaces between two CJK characters
  return text.replace(/(\S)\s+(?=\S)/g, (match, char1) => {
    // Get the character after the space(s)
    const nextCharMatch = text.match(new RegExp(char1 + '\\s+(.)', 'g'));
    if (nextCharMatch && nextCharMatch.length > 0) {
      const char2 = nextCharMatch[0].slice(-1);
      // If both characters are CJK, remove the space
      if (cjkPattern.test(char1) && cjkPattern.test(char2)) {
        return char1;
      }
    }
    return match;
  });
}

// Console logging functionality
function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  });
}

function addConsoleEntry(
    type, content, data = null, emoji = null, author = null, isAudio = false) {
  // Skip audio events if checkbox is unchecked
  if (isAudio && !showAudioEventsCheckbox.checked) {
    return;
  }

  const entry = document.createElement('div');
  entry.className = `console-entry ${type}`;

  const header = document.createElement('div');
  header.className = 'console-entry-header';

  const leftSection = document.createElement('div');
  leftSection.className = 'console-entry-left';

  // Add emoji icon if provided
  if (emoji) {
    const emojiIcon = document.createElement('span');
    emojiIcon.className = 'console-entry-emoji';
    emojiIcon.textContent = emoji;
    leftSection.appendChild(emojiIcon);
  }

  // Add expand/collapse icon
  const expandIcon = document.createElement('span');
  expandIcon.className = 'console-expand-icon';
  expandIcon.textContent = data ? '▶' : '';

  const typeLabel = document.createElement('span');
  typeLabel.className = 'console-entry-type';
  typeLabel.textContent = type === 'outgoing' ?
      '↑ Upstream' :
      type === 'incoming' ? '↓ Downstream' : '⚠ Error';

  leftSection.appendChild(expandIcon);
  leftSection.appendChild(typeLabel);

  // Add author badge if provided
  if (author) {
    const authorBadge = document.createElement('span');
    authorBadge.className = 'console-entry-author';
    authorBadge.textContent = author;
    authorBadge.setAttribute('data-author', author);
    leftSection.appendChild(authorBadge);
  }

  const timestamp = document.createElement('span');
  timestamp.className = 'console-entry-timestamp';
  timestamp.textContent = formatTimestamp();

  header.appendChild(leftSection);
  header.appendChild(timestamp);

  const contentDiv = document.createElement('div');
  contentDiv.className = 'console-entry-content';
  contentDiv.textContent = content;

  entry.appendChild(header);
  entry.appendChild(contentDiv);

  // JSON details (hidden by default)
  let jsonDiv = null;
  if (data) {
    jsonDiv = document.createElement('div');
    jsonDiv.className = 'console-entry-json collapsed';
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(data, null, 2);
    jsonDiv.appendChild(pre);
    entry.appendChild(jsonDiv);

    // Make entry clickable if it has data
    entry.classList.add('expandable');

    // Toggle expand/collapse on click
    entry.addEventListener('click', () => {
      const isExpanded = !jsonDiv.classList.contains('collapsed');

      if (isExpanded) {
        // Collapse
        jsonDiv.classList.add('collapsed');
        expandIcon.textContent = '▶';
        entry.classList.remove('expanded');
      } else {
        // Expand
        jsonDiv.classList.remove('collapsed');
        expandIcon.textContent = '▼';
        entry.classList.add('expanded');
      }
    });
  }

  consoleContent.appendChild(entry);
  consoleContent.scrollTop = consoleContent.scrollHeight;
}

function clearConsole() {
  consoleContent.innerHTML = '';
}

// Clear console button handler
clearConsoleBtn.addEventListener('click', clearConsole);

// Update connection status UI
function updateConnectionStatus(connected) {
  if (connected) {
    statusIndicator.classList.remove('disconnected');
    statusText.textContent = 'Connected';
  } else {
    statusIndicator.classList.add('disconnected');
    statusText.textContent = 'Disconnected';
  }
}

// Create a message bubble element
function createMessageBubble(text, isUser, isPartial = false) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isUser ? 'user' : 'agent'}`;

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'bubble';

  const textP = document.createElement('p');
  textP.className = 'bubble-text';
  textP.textContent = text;

  // Add typing indicator for partial messages
  if (isPartial && !isUser) {
    const typingSpan = document.createElement('span');
    typingSpan.className = 'typing-indicator';
    textP.appendChild(typingSpan);
  }

  bubbleDiv.appendChild(textP);
  messageDiv.appendChild(bubbleDiv);

  return messageDiv;
}

// (createImageBubble removed - unused)

// Update existing message bubble text
function updateMessageBubble(element, text, isPartial = false) {
  const textElement = element.querySelector('.bubble-text');

  // Remove existing typing indicator
  const existingIndicator = textElement.querySelector('.typing-indicator');
  if (existingIndicator) {
    existingIndicator.remove();
  }

  textElement.textContent = text;

  // Add typing indicator for partial messages
  if (isPartial) {
    const typingSpan = document.createElement('span');
    typingSpan.className = 'typing-indicator';
    textElement.appendChild(typingSpan);
  }
}

// Add a system message
function addSystemMessage(text) {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'system-message';
  messageDiv.textContent = text;
  messagesDiv.appendChild(messageDiv);
  scrollToBottom();
}

// Scroll to bottom of messages
function scrollToBottom() {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Sanitize event data for console display (replace large audio data with
// summary)
function sanitizeEventForDisplay(event) {
  // Deep clone the event object
  const sanitized = JSON.parse(JSON.stringify(event));

  // Check for audio data in content.parts
  if (sanitized.content && sanitized.content.parts) {
    sanitized.content.parts = sanitized.content.parts.map((part) => {
      if (part.inlineData && part.inlineData.data) {
        // Calculate byte size (base64 string length / 4 * 3, roughly)
        const byteSize = Math.floor(part.inlineData.data.length * 0.75);
        return {
          ...part,
          inlineData: {
            ...part.inlineData,
            data: `(${byteSize.toLocaleString()} bytes)`,
          },
        };
      }
      return part;
    });
  }

  return sanitized;
}

// WebSocket handlers
function connectWebsocket() {
  // Connect websocket
  const wsUrl = getWebSocketUrl();
  websocket = new WebSocket(wsUrl);

  // Handle connection open
  websocket.onopen = function() {
    console.log('WebSocket connection opened.');
    updateConnectionStatus(true);
    addSystemMessage('Connected to ADK streaming server');

    // Log to console
    addConsoleEntry('incoming', 'WebSocket Connected', {
      userId: userId,
      sessionId: sessionId,
      url: wsUrl,
    }, '🔌', 'system');

    // Update UI for active session
    const btn = document.getElementById('session-control-button');
    const tBtn = document.getElementById('text-mode-button');
    const aBtn = document.getElementById('audio-mode-button');
    const vBtn = document.getElementById('video-mode-button');

    if (btn) btn.textContent = 'Stop Session';
    if (tBtn) tBtn.disabled = false;
    if (aBtn) aBtn.disabled = false;
    if (vBtn) vBtn.disabled = false;
    const imgBtn = document.getElementById('imageButton');
    if (imgBtn) imgBtn.disabled = false;
  };

  // Handle incoming messages
  websocket.onmessage = function(event) {
    // Parse the incoming ADK Event
    const adkEvent = JSON.parse(event.data);
    console.log('[AGENT TO CLIENT] ', adkEvent);

    // Log to console panel
    let eventSummary = 'Event';
    let eventEmoji = '📨'; // Default emoji
    const author = adkEvent.author || 'system';

    if (adkEvent.turnComplete) {
      eventSummary = 'Turn Complete';
      eventEmoji = '✅';
    } else if (adkEvent.interrupted) {
      eventSummary = 'Interrupted';
      eventEmoji = '⏸️';
    } else if (adkEvent.inputTranscription) {
      // Show transcription text in summary
      const transcriptionText = adkEvent.inputTranscription.text || '';
      const truncated = transcriptionText.length > 60 ?
        transcriptionText.substring(0, 60) + '...' :
        transcriptionText;
      eventSummary = `Input Transcription: "${truncated}"`;
      eventEmoji = '📝';
    } else if (adkEvent.outputTranscription) {
      // Show transcription text in summary
      const transcriptionText = adkEvent.outputTranscription.text || '';
      const truncated = transcriptionText.length > 60 ?
        transcriptionText.substring(0, 60) + '...' :
        transcriptionText;
      eventSummary = `Output Transcription: "${truncated}"`;
      eventEmoji = '📝';
    } else if (adkEvent.usageMetadata) {
      // Show token usage information
      const usage = adkEvent.usageMetadata;
      const promptTokens = usage.promptTokenCount || 0;
      const responseTokens = usage.candidatesTokenCount || 0;
      const totalTokens = usage.totalTokenCount || 0;
      eventSummary = `Token Usage: ${totalTokens.toLocaleString()} total (` +
          `${promptTokens.toLocaleString()} prompt + ` +
          `${responseTokens.toLocaleString()} response)`;
      eventEmoji = '📊';
    } else if (adkEvent.content && adkEvent.content.parts) {
      const hasText = adkEvent.content.parts.some((p) => p.text);
      const hasAudio = adkEvent.content.parts.some((p) => p.inlineData);
      const hasExecutableCode = adkEvent.content.parts.some(
          (p) => p.executableCode);
      const hasCodeExecutionResult = adkEvent.content.parts.some(
          (p) => p.codeExecutionResult);

      if (hasExecutableCode) {
        // Show executable code
        const codePart = adkEvent.content.parts.find((p) => p.executableCode);
        if (codePart && codePart.executableCode) {
          const code = codePart.executableCode.code || '';
          const language = codePart.executableCode.language || 'unknown';
          const truncated = code.length > 60 ?
            code.substring(0, 60).replace(/\n/g, ' ') + '...' :
            code.replace(/\n/g, ' ');
          eventSummary = `Executable Code (${language}): ${truncated}`;
          eventEmoji = '💻';
        }
      }

      if (hasCodeExecutionResult) {
        // Show code execution result
        const resultPart = adkEvent.content.parts.find(
            (p) => p.codeExecutionResult);
        if (resultPart && resultPart.codeExecutionResult) {
          const outcome = resultPart.codeExecutionResult.outcome || 'UNKNOWN';
          const output = resultPart.codeExecutionResult.output || '';
          const truncatedOutput = output.length > 60 ?
            output.substring(0, 60).replace(/\n/g, ' ') + '...' :
            output.replace(/\n/g, ' ');
          eventSummary =
              `Code Execution Result (${outcome}): ${truncatedOutput}`;
          eventEmoji = outcome === 'OUTCOME_OK' ? '✅' : '❌';
        }
      }

      if (hasText) {
        // Show text preview in summary
        const textPart = adkEvent.content.parts.find((p) => p.text);
        if (textPart && textPart.text) {
          const text = textPart.text;
          const truncated = text.length > 80 ?
            text.substring(0, 80) + '...' :
            text;
          eventSummary = `Text: "${truncated}"`;
          eventEmoji = '💭';
        } else {
          eventSummary = 'Text Response';
          eventEmoji = '💭';
        }
      }

      if (hasAudio) {
        // Extract audio info for summary
        const audioPart = adkEvent.content.parts.find((p) => p.inlineData);
        if (audioPart && audioPart.inlineData) {
          const mimeType = audioPart.inlineData.mimeType || 'unknown';
          const dataLength = audioPart.inlineData.data ?
              audioPart.inlineData.data.length : 0;
          // Base64 string length / 4 * 3 gives approximate bytes
          const byteSize = Math.floor(dataLength * 0.75);
          eventSummary = `Audio Response: ${mimeType} (` +
              `${byteSize.toLocaleString()} bytes)`;
          eventEmoji = '🔊';
        } else {
          eventSummary = 'Audio Response';
          eventEmoji = '🔊';
        }

        // Log audio event with isAudio flag (filtered by checkbox)
        const sanitizedEvent = sanitizeEventForDisplay(adkEvent);
        addConsoleEntry(
            'incoming', eventSummary, sanitizedEvent, eventEmoji, author, true);
      }
    }

    // Create a sanitized version for console display (replace large audio
    // data with summary)
    // Skip if already logged as audio event above
    const isAudioOnlyEvent = adkEvent.content && adkEvent.content.parts &&
      adkEvent.content.parts.some((p) => p.inlineData) &&
      !adkEvent.content.parts.some((p) => p.text);
    if (!isAudioOnlyEvent) {
      const sanitizedEvent = sanitizeEventForDisplay(adkEvent);
      addConsoleEntry(
          'incoming', eventSummary, sanitizedEvent, eventEmoji, author);
    }

    // Handle turn complete event
    if (adkEvent.turnComplete === true) {
      // Remove typing indicator from current message
      if (currentBubbleElement) {
        const textElement = currentBubbleElement.querySelector('.bubble-text');
        const typingIndicator = textElement.querySelector('.typing-indicator');
        if (typingIndicator) {
          typingIndicator.remove();
        }
      }
      // Remove typing indicator from current output transcription
      if (currentOutputTranscriptionElement) {
        const textElement =
            currentOutputTranscriptionElement.querySelector('.bubble-text');
        const typingIndicator = textElement.querySelector('.typing-indicator');
        if (typingIndicator) {
          typingIndicator.remove();
        }
      }
      currentMessageId = null;
      currentBubbleElement = null;
      currentOutputTranscriptionId = null;
      currentOutputTranscriptionElement = null;
      inputTranscriptionFinished = false; // Reset for next turn
      hasOutputTranscriptionInTurn = false; // Reset for next turn
      return;
    }

    // Handle interrupted event
    if (adkEvent.interrupted === true) {
      // Stop audio playback if it's playing
      if (audioPlayerNode) {
        audioPlayerNode.port.postMessage({command: 'endOfAudio'});
      }

      // Keep the partial message but mark it as interrupted
      if (currentBubbleElement) {
        const textElement = currentBubbleElement.querySelector('.bubble-text');

        // Remove typing indicator
        const typingIndicator = textElement.querySelector('.typing-indicator');
        if (typingIndicator) {
          typingIndicator.remove();
        }

        // Add interrupted marker
        currentBubbleElement.classList.add('interrupted');
      }

      // Keep the partial output transcription but mark it as interrupted
      if (currentOutputTranscriptionElement) {
        const textElement =
            currentOutputTranscriptionElement.querySelector('.bubble-text');

        // Remove typing indicator
        const typingIndicator = textElement.querySelector('.typing-indicator');
        if (typingIndicator) {
          typingIndicator.remove();
        }

        // Add interrupted marker
        currentOutputTranscriptionElement.classList.add('interrupted');
      }

      // Reset state so new content creates a new bubble
      currentMessageId = null;
      currentBubbleElement = null;
      currentOutputTranscriptionId = null;
      currentOutputTranscriptionElement = null;
      inputTranscriptionFinished = false; // Reset for next turn
      hasOutputTranscriptionInTurn = false; // Reset for next turn
      return;
    }

    // Handle input transcription (user's spoken words)
    if (adkEvent.inputTranscription && adkEvent.inputTranscription.text) {
      const transcriptionText = adkEvent.inputTranscription.text;
      const isFinished = adkEvent.inputTranscription.finished;

      if (transcriptionText) {
        // Ignore late-arriving transcriptions after we've finished for this
        // turn
        if (inputTranscriptionFinished) {
          return;
        }

        if (currentInputTranscriptionId == null) {
          // Create new transcription bubble
          currentInputTranscriptionId = Math.random().toString(36).substring(7);
          // Clean spaces between CJK characters
          const cleanedText = cleanCJKSpaces(transcriptionText);
          currentInputTranscriptionElement = createMessageBubble(
              cleanedText, true, !isFinished);
          currentInputTranscriptionElement.id = currentInputTranscriptionId;

          // Add a special class to indicate it's a transcription
          currentInputTranscriptionElement.classList.add('transcription');

          messagesDiv.appendChild(currentInputTranscriptionElement);
        } else {
          // Update existing transcription bubble only if model hasn't started
          // responding
          // This prevents late partial transcriptions from overwriting
          // complete ones
          if (currentOutputTranscriptionId == null &&
              currentMessageId == null) {
            if (isFinished) {
              // Final transcription contains the complete text, replace
              // entirely
              const cleanedText = cleanCJKSpaces(transcriptionText);
              updateMessageBubble(
                  currentInputTranscriptionElement, cleanedText, false);
            } else {
              // Partial transcription - append to existing text
              const existingText = currentInputTranscriptionElement
                  .querySelector('.bubble-text').textContent;
              // Remove typing indicator if present
              const cleanText = existingText.replace(/\.\.\.$/, '');
              // Clean spaces between CJK characters before updating
              const accumulatedText = cleanCJKSpaces(
                  cleanText + transcriptionText);
              updateMessageBubble(
                  currentInputTranscriptionElement, accumulatedText, true);
            }
          }
        }

        // If transcription is finished, reset the state and mark as complete
        if (isFinished) {
          currentInputTranscriptionId = null;
          currentInputTranscriptionElement = null;
          // Prevent duplicate bubbles from late events
          inputTranscriptionFinished = true;
        }

        scrollToBottom();
      }
    }

    // Handle output transcription (model's spoken words)
    if (adkEvent.outputTranscription && adkEvent.outputTranscription.text) {
      const transcriptionText = adkEvent.outputTranscription.text;
      const isFinished = adkEvent.outputTranscription.finished;
      hasOutputTranscriptionInTurn = true;

      if (transcriptionText) {
        // Finalize any active input transcription when server starts responding
        if (currentInputTranscriptionId != null &&
            currentOutputTranscriptionId == null) {
          // This is the first output transcription - finalize input
          // transcription
          const textElement = currentInputTranscriptionElement
              .querySelector('.bubble-text');
          const typingIndicator = textElement
              .querySelector('.typing-indicator');
          if (typingIndicator) {
            typingIndicator.remove();
          }
          // Reset input transcription state so next user input creates new
          // balloon
          currentInputTranscriptionId = null;
          currentInputTranscriptionElement = null;
          // Prevent duplicate bubbles from late events
          inputTranscriptionFinished = true;
        }

        if (currentOutputTranscriptionId == null) {
          // Create new transcription bubble for agent
          currentOutputTranscriptionId =
              Math.random().toString(36).substring(7);
          currentOutputTranscriptionElement = createMessageBubble(
              transcriptionText, false, !isFinished);
          currentOutputTranscriptionElement.id = currentOutputTranscriptionId;

          // Add a special class to indicate it's a transcription
          currentOutputTranscriptionElement.classList.add('transcription');

          messagesDiv.appendChild(currentOutputTranscriptionElement);
        } else {
          // Update existing transcription bubble
          if (isFinished) {
            // Final transcription contains the complete text, replace entirely
            updateMessageBubble(
                currentOutputTranscriptionElement, transcriptionText, false);
          } else {
            // Partial transcription - append to existing text
            const existingText = currentOutputTranscriptionElement
                .querySelector('.bubble-text').textContent;
            // Remove typing indicator if present
            const cleanText = existingText.replace(/\.\.\.$/, '');
            updateMessageBubble(
                currentOutputTranscriptionElement,
                cleanText + transcriptionText, true);
          }
        }

        // If transcription is finished, reset the state
        if (isFinished) {
          currentOutputTranscriptionId = null;
          currentOutputTranscriptionElement = null;
        }

        scrollToBottom();
      }
    }

    // Handle content events (text or audio)
    if (adkEvent.content && adkEvent.content.parts) {
      const parts = adkEvent.content.parts;

      // Finalize any active input transcription when server starts
      // responding with content
      if (currentInputTranscriptionId != null && currentMessageId == null &&
          currentOutputTranscriptionId == null) {
        // This is the first content event - finalize input transcription
        const textElement = currentInputTranscriptionElement
            .querySelector('.bubble-text');
        const typingIndicator = textElement
            .querySelector('.typing-indicator');
        if (typingIndicator) {
          typingIndicator.remove();
        }
        // Reset input transcription state so next user input creates new
        // balloon
        currentInputTranscriptionId = null;
        currentInputTranscriptionElement = null;
        // Prevent duplicate bubbles from late events
        inputTranscriptionFinished = true;
      }

      for (const part of parts) {
        // Handle inline data (audio)
        if (part.inlineData) {
          const mimeType = part.inlineData.mimeType;
          const data = part.inlineData.data;

          if (mimeType && mimeType.startsWith('audio/pcm') && audioPlayerNode) {
            audioPlayerNode.port.postMessage(base64ToArray(data));
          }
        }

        // Handle text
        if (part.text) {
          // Skip thinking/reasoning text from chat bubbles (shown in event
          // console)
          if (part.thought) {
            continue;
          }

          // Skip final aggregated content when output transcription already
          // delivered the response (prevents duplicate thinking text replay)
          if (!adkEvent.partial && hasOutputTranscriptionInTurn) {
            continue;
          }

          // Add a new message bubble for a new turn
          if (currentMessageId == null) {
            currentMessageId = Math.random().toString(36).substring(7);
            currentBubbleElement = createMessageBubble(part.text, false, true);
            currentBubbleElement.id = currentMessageId;
            messagesDiv.appendChild(currentBubbleElement);
          } else {
            // Update the existing message bubble with accumulated text
            const existingText = currentBubbleElement
                .querySelector('.bubble-text').textContent;
            // Remove the "..." if present
            const cleanText = existingText.replace(/\.\.\.$/, '');
            updateMessageBubble(
                currentBubbleElement, cleanText + part.text, true);
          }

          // Scroll down to the bottom of the messagesDiv
          scrollToBottom();
        }
      }
    }
  };

  // Handle connection close
  websocket.onclose = function() {
    console.log('WebSocket connection closed.');
    updateConnectionStatus(false);
    addSystemMessage('Session closed.');

    // Log to console
    addConsoleEntry('error', 'WebSocket Disconnected', {
      status: 'Connection closed',
    }, '🔌', 'system');

    // Reset UI state
    const btn = document.getElementById('session-control-button');
    if (btn) btn.textContent = 'Start Session';

    const tBtn = document.getElementById('text-mode-button');
    const aBtn = document.getElementById('audio-mode-button');
    const vBtn = document.getElementById('video-mode-button');
    if (tBtn) tBtn.disabled = true;
    if (aBtn) aBtn.disabled = true;
    if (vBtn) vBtn.disabled = true;
  };

  websocket.onerror = function(e) {
    console.log('WebSocket error: ', e);
    updateConnectionStatus(false);

    // Log to console
    addConsoleEntry('error', 'WebSocket Error', {
      error: e.type,
      message: 'Connection error occurred',
    }, '⚠️', 'system');
  };
}

// Add submit handler to the form
function addSubmitHandler() {
  messageForm.onsubmit = function(e) {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message) {
      // Add user message bubble
      const userBubble = createMessageBubble(message, true, false);
      messagesDiv.appendChild(userBubble);
      scrollToBottom();

      // Clear input
      messageInput.value = '';

      // Send message to server
      sendMessage(message);
      console.log('[CLIENT TO AGENT] ' + message);
    }
    return false;
  };
}

// Send a message to the server as JSON
function sendMessage(message) {
  if (websocket && websocket.readyState == WebSocket.OPEN) {
    const jsonMessage = JSON.stringify({
      type: 'text',
      text: message,
    });
    websocket.send(jsonMessage);

    // Log to console panel
    addConsoleEntry('outgoing', 'User Message: ' + message, null, '💬', 'user');
  }
}

// Decode Base64 data to Array
// Handles both standard base64 and base64url encoding
function base64ToArray(base64) {
  // Convert base64url to standard base64
  // Replace URL-safe characters: - with +, _ with /
  let standardBase64 = base64.replace(/-/g, '+').replace(/_/g, '/');

  // Add padding if needed
  while (standardBase64.length % 4) {
    standardBase64 += '=';
  }

  const binaryString = window.atob(standardBase64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Live Video/Audio handling
 */

const videoModeButton = document.getElementById('video-mode-button');
const cameraPreview = document.getElementById('cameraPreview');
const videoContainer = document.getElementById('videoContainer');
const switchCameraButton = document.getElementById('switchCameraButton');

let cameraStream = null;
let videoInterval = null;
let isLive = false;
let currentFacingMode = 'user';

// Check camera count and show/hide switch button
async function checkCameraCount() {
  const display = document.getElementById('cameraCountDisplay');
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    console.log('enumerateDevices not supported.');
    if (display) display.textContent = 'Cameras: Not supported';
    return;
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(
        (device) => device.kind === 'videoinput');
    console.log('Video devices found:', videoDevices.length);

    if (display) display.textContent = `Cameras: ${videoDevices.length}`;

    if (videoDevices.length > 1 && switchCameraButton) {
      switchCameraButton.style.display = 'inline-block';
    }
  } catch (error) {
    console.error('Error checking camera count:', error);
    if (display) display.textContent = 'Cameras: Error';
  }
}

// Start live session (Video + Audio)
async function startLiveSession() {
  if (isLive) {
    stopLiveSession();
    return;
  }

  try {
    // Disable other buttons
    const tBtn = document.getElementById('text-mode-button');
    const aBtn = document.getElementById('audio-mode-button');
    if (tBtn) tBtn.disabled = true;
    if (aBtn) aBtn.disabled = true;

    // 1. Start Audio (if not already started)
    if (!isAudio) {
      startAudio();
      isAudio = true;
    }

    // 2. Start Video
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: {ideal: 768},
        height: {ideal: 768},
        facingMode: {ideal: currentFacingMode},
      },
    });

    cameraPreview.srcObject = cameraStream;
    videoContainer.style.display = 'block';

    if (videoModeButton) {
      videoModeButton.textContent = 'Stop Video';
      // Change to red when running
      videoModeButton.style.backgroundColor = '#ea4335';
    }
    isLive = true;

    // Check camera count after permission is granted
    await checkCameraCount();

    addSystemMessage('Live session started - streaming video and audio');
    addConsoleEntry('outgoing', 'Live Session Started', {
      video: true,
      audio: true,
    }, '🎥', 'system');

    // 3. Start Video Streaming (Send frames periodically)
    const canvas = document.createElement('canvas');
    videoInterval = setInterval(() => {
      if (websocket && websocket.readyState === WebSocket.OPEN && isLive) {
        canvas.width = cameraPreview.videoWidth;
        canvas.height = cameraPreview.videoHeight;
        const context = canvas.getContext('2d');
        context.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);

        canvas.toBlob((blob) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64data = reader.result.split(',')[1];
            sendImage(base64data);
          };
          reader.readAsDataURL(blob);
        }, 'image/jpeg', 0.5); // Lower quality for faster streaming
      }
    }, 500); // Send every 500ms (2 fps)
  } catch (error) {
    console.error('Error starting live session:', error);
    addSystemMessage(`Failed to start live session: ${error.message}`);
    addConsoleEntry('error', 'Live session failed', {
      error: error.message,
    }, '⚠️', 'system');
    stopLiveSession();
  }
}

// Stop live session
function stopLiveSession() {
  if (videoInterval) {
    clearInterval(videoInterval);
    videoInterval = null;
  }

  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }

  cameraPreview.srcObject = null;
  videoContainer.style.display = 'none';

  if (videoModeButton) {
    videoModeButton.textContent = 'Video';
    videoModeButton.style.backgroundColor = '#f4b400';
  }
  isLive = false;

  // Enable other buttons
  const tBtn = document.getElementById('text-mode-button');
  const aBtn = document.getElementById('audio-mode-button');
  if (tBtn) tBtn.disabled = false;
  if (aBtn) aBtn.disabled = false;

  addSystemMessage('Live session stopped');
  addConsoleEntry('outgoing', 'Live Session Stopped', null, '⏹️', 'system');
}

// Send image to server
function sendImage(base64Image) {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    const jsonMessage = JSON.stringify({
      type: 'image',
      data: base64Image,
      mimeType: 'image/jpeg',
    });
    websocket.send(jsonMessage);
    console.log('[CLIENT TO AGENT] Sent image');
  }
}

// Event listeners
if (videoModeButton) {
  videoModeButton.addEventListener('click', startLiveSession);
}
if (switchCameraButton) {
  switchCameraButton.addEventListener('click', () => {
    currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
    addSystemMessage(`Switched to ${currentFacingMode} camera.`);
    if (isLive) {
      stopLiveSession();
      startLiveSession();
    }
  });
}

const contextButton = document.getElementById('context-button');
const contextModal = document.getElementById('contextModal');
const closeModal = document.getElementById('closeModal');
const contextForm = document.getElementById('contextForm');

if (contextButton && contextModal) {
  contextButton.addEventListener('click', async () => {
    try {
      const response = await fetch('/get-context');
      const result = await response.json();

      if (result.status === 'success') {
        document.getElementById('contextPrompt').value = result.prompt || '';
        document.getElementById('contextGcsPath').value = result.gcs_path || '';

        const filesList = document.getElementById('existingFilesList');
        if (filesList) {
          filesList.innerHTML = '';
          if (result.files && result.files.length > 0) {
            result.files.forEach((filename) => {
              const li = document.createElement('li');
              li.textContent = filename;
              filesList.appendChild(li);
            });
          } else {
            const li = document.createElement('li');
            li.textContent = 'No files found';
            li.style.color = '#999';
            filesList.appendChild(li);
          }
        }
      }
    } catch (error) {
      console.error('Error fetching context:', error);
    }
    contextModal.style.display = 'flex';
  });
}

if (closeModal && contextModal) {
  closeModal.addEventListener('click', () => {
    contextModal.style.display = 'none';
  });
}

window.addEventListener('click', (event) => {
  if (event.target === contextModal) {
    contextModal.style.display = 'none';
  }
});

if (contextForm) {
  contextForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(contextForm);

    try {
      const response = await fetch('/upload-context', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      if (result.status === 'success') {
        addSystemMessage('Context saved successfully.');
        contextModal.style.display = 'none';
      } else {
        addSystemMessage(`Failed to save context: ${result.message}`);
      }
    } catch (error) {
      console.error('Error uploading context:', error);
      addSystemMessage('Error uploading context.');
    }
  });
}


/**
 * Audio handling
 */

let audioPlayerNode;
let audioPlayerContext;
// let audioRecorderNode; (unused)
let audioRecorderContext;
let micStream;

// Import the audio worklets
import {startAudioPlayerWorklet} from './audio-player.js';
import {startAudioRecorderWorklet} from './audio-recorder.js';

// Start audio
function startAudio() {
  // Start audio output
  startAudioPlayerWorklet().then(([node, ctx]) => {
    audioPlayerNode = node;
    audioPlayerContext = ctx;
  });
  // Start audio input
  startAudioRecorderWorklet(audioRecorderHandler).then(
      ([node, ctx, stream]) => {
        // audioRecorderNode = node; (unused)
        audioRecorderContext = ctx;
        micStream = stream;
      },
  );
}

// Start the audio only when the user clicked the button
console.log('app.js loading...');
checkCameraCount(); // Check camera count on load
const textModeButton = document.getElementById('text-mode-button');
const audioModeButton = document.getElementById('audio-mode-button');
const sessionControlButton = document.getElementById('session-control-button');
console.log('sessionControlButton on load:', sessionControlButton);


// Disable mode buttons on load until session is started
if (textModeButton) textModeButton.disabled = true;
if (audioModeButton) audioModeButton.disabled = true;
if (videoModeButton) videoModeButton.disabled = true;

if (sessionControlButton) {
  sessionControlButton.addEventListener('click', toggleSession);
}


if (audioModeButton) {
  audioModeButton.addEventListener('click', () => {
    if (!isAudio) {
      startAudio();
      isAudio = true;
      addSystemMessage('Audio mode enabled.');
      // Disable other buttons
      const tBtn = document.getElementById('text-mode-button');
      const vBtn = document.getElementById('video-mode-button');
      if (tBtn) tBtn.disabled = true;
      if (vBtn) vBtn.disabled = true;
      audioModeButton.disabled = true;
    }
  });
}

function stopAudio() {
  if (isAudio) {
    if (audioRecorderContext) audioRecorderContext.close();
    if (audioPlayerContext) audioPlayerContext.close();
    if (micStream) micStream.getTracks().forEach((track) => track.stop());
    isAudio = false;
    addSystemMessage('Audio mode disabled.');
    if (audioModeButton) audioModeButton.disabled = false;
    const tBtn = document.getElementById('text-mode-button');
    const vBtn = document.getElementById('video-mode-button');
    if (tBtn) tBtn.disabled = false;
    if (vBtn) vBtn.disabled = false;
  }
}

function toggleSession() {
  const btn = document.getElementById('session-control-button');
  const tBtn = document.getElementById('text-mode-button');
  const aBtn = document.getElementById('audio-mode-button');
  const vBtn = document.getElementById('video-mode-button');

  if (websocket && websocket.readyState === WebSocket.OPEN) {
    // Stop session
    if (isLive) stopLiveSession();
    stopAudio();

    addSystemMessage('Stopping session...');
    websocket.onclose = null;
    websocket.close();
    websocket = null;

    updateConnectionStatus(false);
    if (btn) btn.textContent = 'Start Session';

    // Disable other buttons
    if (tBtn) tBtn.disabled = true;
    if (aBtn) aBtn.disabled = true;
    if (vBtn) vBtn.disabled = true;
    const imgBtn = document.getElementById('imageButton');
    if (imgBtn) imgBtn.disabled = true;
  } else {
    // Start session
    addSystemMessage('Starting session...');
    connectWebsocket();
    if (btn) btn.textContent = 'Connecting...';
  }
}
addSubmitHandler();

// Audio recorder handler
function audioRecorderHandler(pcmData) {
  if (websocket && websocket.readyState === WebSocket.OPEN && isAudio) {
    // Send audio as binary WebSocket frame (more efficient than base64 JSON)
    websocket.send(pcmData);
    console.log(
        '[CLIENT TO AGENT] Sent audio chunk: %s bytes', pcmData.byteLength);

    // Log to console panel (optional, can be noisy with frequent audio chunks)
    // addConsoleEntry('outgoing', `Audio chunk: ${pcmData.byteLength} bytes`);
  }
}

