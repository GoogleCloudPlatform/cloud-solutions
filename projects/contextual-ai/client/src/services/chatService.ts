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

import {Conversation, ConversationEntry, ChatMessage} from '@/types/chat';
import {WidgetAnalysisRequest} from '../types/chat';
import ApiService from './api';

type ConversationListener = (conversations: Conversation[]) => void;

export class ChatService {
  private static conversations: Conversation[] = [];
  private static listeners: ConversationListener[] = [];
  private static conversationCounter = 1;

  // Subscribe to conversation updates
  static subscribe(listener: ConversationListener) {
    this.listeners.push(listener);
    // Immediately notify with current conversations
    listener(this.conversations);

    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  // Notify all listeners of conversation updates
  private static notifyListeners() {
    this.listeners.forEach(listener => listener([...this.conversations]));
  }

  // Add a new conversation from widget analysis
  static async addWidgetAnalysisConversation(
    widgetTitle: string,
    widgetAnalysisRequest: WidgetAnalysisRequest
  ): Promise<string> {
    try {
      // Send widget analysis request to backend API
      const response = await ApiService.analyzeWidget(widgetAnalysisRequest);

      if (response.status === 'success') {
        // Refresh conversations from backend
        await this.refreshConversations();
        return response.data.conversationId;
      } else {
        console.error('Failed to analyze widget:', response.message);
        return '';
      }
    } catch (error) {
      console.error('Error analyzing widget:', error);
      return '';
    }
  }

  // Refresh conversations from backend
  static async refreshConversations(): Promise<void> {
    try {
      const response = await ApiService.getConversations(50, 0, 24); // Last 24 hours

      if (response.status === 'success') {
        this.conversations = response.data.conversations || [];
        this.notifyListeners();
      } else {
        console.error('Failed to refresh conversations:', response.message);
      }
    } catch (error) {
      console.error('Error refreshing conversations:', error);
    }
  }

  // Add a regular chat message to the most recent conversation or create new one
  static async addChatMessage(message: string): Promise<string> {
    try {
      // Send message to backend API
      const response = await ApiService.sendChatMessage(message);

      if (response.status === 'success') {
        // Refresh conversations from backend
        await this.refreshConversations();
        return response.data.conversationId;
      } else {
        console.error('Failed to send chat message:', response.message);
        return '';
      }
    } catch (error) {
      console.error('Error sending chat message:', error);
      return '';
    }
  }

  // Add an AI response to an existing conversation
  static addAIResponse(
    conversationId: string,
    response: string,
    metadata?: ConversationEntry['metadata']
  ): void {
    const conversation = this.conversations.find(
      conv => conv.id === conversationId
    );
    if (!conversation) return;

    const timestamp = new Date().toISOString();
    const assistantEntry: ConversationEntry = {
      id: `${conversationId}-assistant-${Date.now()}`,
      timestamp,
      type: 'assistant',
      content: response,
      metadata,
    };

    conversation.entries.push(assistantEntry);
    conversation.updatedAt = timestamp;

    this.notifyListeners();
  }

  // Get all conversations
  static getAllConversations(): Conversation[] {
    return [...this.conversations];
  }

  // Get conversation by ID
  static getConversation(id: string): Conversation | null {
    return this.conversations.find(conv => conv.id === id) || null;
  }

  // Convert conversations to chat messages format (for existing chat UI)
  static getLatestChatMessages(limit: number = 20): ChatMessage[] {
    const messages: ChatMessage[] = [];

    // Get latest conversations and their entries
    const latestConversations = this.conversations.slice(
      0,
      Math.ceil(limit / 2)
    );

    for (const conversation of latestConversations) {
      for (const entry of conversation.entries) {
        messages.push({
          id: entry.id,
          content: entry.content,
          sender: entry.type,
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

  // Mark conversation as resolved
  static resolveConversation(id: string): void {
    const conversation = this.conversations.find(conv => conv.id === id);
    if (conversation) {
      conversation.status = 'resolved';
      conversation.updatedAt = new Date().toISOString();
      this.notifyListeners();
    }
  }

  // Clear all conversations (for testing)
  static clearAll(): void {
    this.conversations = [];
    this.notifyListeners();
  }

  // Initialize by loading conversations from backend
  static async initialize(): Promise<void> {
    if (this.conversations.length > 0) return; // Already initialized

    // Load real conversations from backend
    await this.refreshConversations();
  }
}

export default ChatService;
