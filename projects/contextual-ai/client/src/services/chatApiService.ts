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

import {
  ChatMessage,
  ChatMessageRequest,
  ChatResponse,
  Conversation,
  ConversationListResponse,
} from '../types/chat';

class ChatApiService {
  private static readonly API_BASE_URL =
    process.env.REACT_APP_API_URL || 'http://localhost:8080';

  // Get all conversations from backend
  static async getConversations(
    limit: number = 50,
    offset: number = 0,
    hours?: number
  ): Promise<ConversationListResponse> {
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
      });

      if (hours) {
        params.append('hours', hours.toString());
      }

      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/conversations?${params}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to fetch conversations: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching conversations:', error);
      throw error;
    }
  }

  // Get specific conversation by ID
  static async getConversation(conversationId: string): Promise<Conversation> {
    try {
      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/conversations/${conversationId}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to fetch conversation: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching conversation:', error);
      throw error;
    }
  }

  // Send chat message
  static async sendMessage(message: ChatMessageRequest): Promise<ChatResponse> {
    try {
      const response = await fetch(`${this.API_BASE_URL}/api/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(message),
      });

      if (!response.ok) {
        throw new Error(
          `Failed to send message: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  // Resolve conversation
  static async resolveConversation(conversationId: string): Promise<void> {
    try {
      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/conversations/${conversationId}/resolve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to resolve conversation: ${response.status} ${response.statusText}`
        );
      }
    } catch (error) {
      console.error('Error resolving conversation:', error);
      throw error;
    }
  }

  // Clear all conversations (for testing)
  static async clearAllConversations(): Promise<void> {
    try {
      const response = await fetch(
        `${this.API_BASE_URL}/api/chat/conversations`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to clear conversations: ${response.status} ${response.statusText}`
        );
      }
    } catch (error) {
      console.error('Error clearing conversations:', error);
      throw error;
    }
  }

  // Health check
  static async healthCheck(): Promise<unknown> {
    try {
      const response = await fetch(`${this.API_BASE_URL}/api/chat/health`, {
        method: 'GET',
      });

      if (!response.ok) {
        throw new Error(
          `Health check failed: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  }

  // Convert backend conversations to frontend chat message format
  static convertToChatMessages(
    conversations: Conversation[],
    limit: number = 20
  ): ChatMessage[] {
    const messages: ChatMessage[] = [];

    // Get latest conversations and their entries
    const latestConversations = conversations.slice(0, Math.ceil(limit / 2));

    for (const conversation of latestConversations) {
      for (const entry of conversation.entries) {
        // Ensure sender type is strictly 'user' or 'assistant'
        const sender: 'user' | 'assistant' =
          entry.type === 'user' ? 'user' : 'assistant';

        messages.push({
          id: entry.id,
          content: entry.content,
          sender,
          timestamp: entry.timestamp,
          metadata: entry.metadata,
        });

        if (messages.length >= limit) break;
      }
      if (messages.length >= limit) break;
    }

    return messages.sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }

  // Poll for conversation updates
  static startPolling(
    callback: (conversations: Conversation[]) => void,
    intervalMs: number = 3000
  ): () => void {
    let isPolling = true;

    const poll = async () => {
      if (!isPolling) return;

      try {
        const response = await this.getConversations(50, 0, 24); // Last 24 hours
        callback(response.conversations);
      } catch (error) {
        console.error('Polling error:', error);
      }

      if (isPolling) {
        setTimeout(poll, intervalMs);
      }
    };

    // Start polling
    poll();

    // Return stop function
    return () => {
      isPolling = false;
    };
  }
}

export default ChatApiService;
