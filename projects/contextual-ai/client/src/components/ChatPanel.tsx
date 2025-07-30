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

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Send, Bot, Paperclip, MoreVertical, ChevronLeft, ChevronRight, Zap, Trash2 } from 'lucide-react';
import ChatService from '@/services/chatService';
import ChatApiService from '@/services/chatApiService';
import FollowUpAnalysisService from '@/services/followUpAnalysis';
import { ChatMessage } from '@/types/chat';

interface ChatPanelProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  externalThinking?: boolean;
}

// Initialize data on component load
ChatService.initialize();

export function ChatPanel({ isCollapsed, onToggleCollapse, externalThinking = false }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [useBackendApi] = useState(true);
  const [showDropdown, setShowDropdown] = useState(false);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const messagesContainerRef = React.useRef<HTMLDivElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const prevMessageCountRef = React.useRef(0);

  // Subscribe to chat service updates and backend API polling
  useEffect(() => {
    if (useBackendApi) {
      // Use backend API with polling
      const updateMessagesFromBackend = (conversations: any[]) => {
        const latestMessages = ChatApiService.convertToChatMessages(conversations, 20);
        setMessages(latestMessages);
      };

      // Start polling for updates
      const stopPolling = ChatApiService.startPolling(updateMessagesFromBackend, 2000);

      return stopPolling;
    } else {
      // Use local chat service
      const updateMessages = () => {
        const latestMessages = ChatService.getLatestChatMessages(20);
        setMessages(latestMessages);
      };

      // Subscribe to conversation updates
      const unsubscribe = ChatService.subscribe(() => {
        updateMessages();
      });

      // Initial load
      updateMessages();

      return unsubscribe;
    }
  }, [useBackendApi]);

  // Check if user is at bottom of scroll
  const checkIfAtBottom = () => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      const threshold = 50; // 50px threshold for "at bottom"
      setIsAtBottom(scrollTop + clientHeight >= scrollHeight - threshold);
    }
  };

  // Combine internal and external thinking states
  const isCurrentlyThinking = isThinking || externalThinking;

  // Auto-scroll to bottom when new messages arrive or when thinking starts/stops
  useEffect(() => {
    const hasNewMessages = messages.length > prevMessageCountRef.current;
    prevMessageCountRef.current = messages.length;

    // Scroll to bottom if:
    // 1. New messages were added, OR
    // 2. User is already at the bottom and something changed, OR
    // 3. Thinking state changed (loading indicators)
    if (hasNewMessages || isAtBottom || isCurrentlyThinking) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      setIsAtBottom(true);
    }
  }, [messages, isCurrentlyThinking, isAtBottom]);

  // Handle dropdown outside clicks
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  const handleClearMessages = async () => {
    try {
      if (useBackendApi) {
        // Clear messages via backend API
        await ChatApiService.clearAllConversations();
      } else {
        // Clear local chat service
        ChatService.clearAll();
      }
      setMessages([]);
      setShowDropdown(false);
    } catch (error) {
      console.error('Failed to clear messages:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage = inputValue;
    setInputValue('');

    if (useBackendApi) {
      // Use backend API with streaming
      setIsThinking(true);

      try {
        // Add user message to local state immediately
        const userMsgId = `user-${Date.now()}`;
        const userMsg: ChatMessage = {
          id: userMsgId,
          content: userMessage,
          sender: 'user',
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMsg]);

        // Add placeholder for AI response
        const aiMsgId = `ai-${Date.now()}`;
        const aiMsg: ChatMessage = {
          id: aiMsgId,
          content: '',
          sender: 'assistant',
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, aiMsg]);

        let streamedContent = '';

        await ChatApiService.sendMessageStream(
          { content: userMessage },
          // onChunk
          (chunk: string) => {
            streamedContent += chunk;
            setMessages(prev => prev.map(msg =>
              msg.id === aiMsgId ? { ...msg, content: streamedContent } : msg
            ));
          },
          // onComplete
          () => {
            setIsThinking(false);
            console.log('Streaming completed');
          },
          // onError
          (error: string) => {
            console.error('Streaming error:', error);
            setMessages(prev => prev.map(msg =>
              msg.id === aiMsgId ? {
                ...msg,
                content: "I apologize, " +
                  "but I'm having trouble processing your request right now." +
                  " Please try again later."
              } : msg
            ));
            setIsThinking(false);
          }
        );
      } catch (error) {
        console.error('Failed to send message via API:', error);

        // Fallback to local service
        const conversationId = await ChatService.addChatMessage(userMessage);
        const fallbackResponse = "I apologize, " +
          "but I'm having trouble connecting to the AI service right now. " +
          "Please try again later.";
        if (conversationId) {
          ChatService.addAIResponse(conversationId, fallbackResponse);
        }
        setIsThinking(false);
      }
    } else {
      // Use local chat service
      const conversationId = await ChatService.addChatMessage(userMessage);

      // Show thinking indicator and generate AI response
      setIsThinking(true);

      setTimeout(async () => {
        try {
          const aiResponse = await FollowUpAnalysisService.generateFollowUpResponse(
            userMessage,
            conversationId
          );

          // Add AI response to the conversation
          if (conversationId) {
            ChatService.addAIResponse(conversationId, aiResponse);
          }
        } catch (error) {
          console.error('Failed to generate AI response:', error);

          // Fallback response
          const fallbackResponse = "I apologize, but I'm having" +
            " trouble processing your " +
            "request right now. Please try asking again or click on" +
            " a chart for analysis.";
          if (conversationId) {
            ChatService.addAIResponse(conversationId, fallbackResponse);
          }
        } finally {
          setIsThinking(false);
        }
      }, 1500); // Simulate thinking time
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (isCollapsed) {
    return (
      <div className="w-16 bg-background border-l border-border flex flex-col h-full">
        {/* Collapsed Header - Fixed under top nav */}
        <div className="p-2 border-b border-border">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="w-full h-12"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* Collapsed Chat Icon - Scrollable area */}
        <div className="flex-1 flex flex-col items-center justify-center space-y-4 p-2 overflow-hidden">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
        </div>

        {/* Message Count - Fixed at bottom */}
        <div className="p-2 border-t border-border">
          <div className="text-center">
            <Badge variant="secondary" className="w-8 h-8 rounded-full p-0 flex items-center justify-center text-xs">
              {messages.length}
            </Badge>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-background border-l border-border flex flex-col h-full">
      {/* Header - At top of chat panel */}
      <div className="p-4 border-b border-border bg-background">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Bot className="h-4 w-4 text-primary-foreground" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">AI Assistant</h3>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-xs text-muted-foreground">Online</span>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-1">
            <Button variant="ghost" size="icon" onClick={onToggleCollapse}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <div className="relative" ref={dropdownRef}>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowDropdown(!showDropdown)}
              >
                <MoreVertical className="h-4 w-4" />
              </Button>

              {showDropdown && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-background border border-border rounded-md shadow-lg z-50">
                  <div className="py-1">
                    <button
                      onClick={handleClearMessages}
                      className="flex items-center w-full px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Clear Messages
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages - Scrollable area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        onScroll={checkIfAtBottom}
      >
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex items-start space-x-3 ${
              message.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
            }`}
          >
            <Avatar className="h-7 w-7 flex-shrink-0">
              {message.sender === 'user' ? (
                <>
                  <AvatarImage src="https://github.com/shadcn.png" alt="User" />
                  <AvatarFallback>CG</AvatarFallback>
                </>
              ) : (
                <>
                  <AvatarFallback className="bg-primary text-primary-foreground">
                    {message.metadata?.widgetId ? (
                      <Zap className="h-3 w-3" />
                    ) : (
                      <Bot className="h-3 w-3" />
                    )}
                  </AvatarFallback>
                </>
              )}
            </Avatar>

            <div className={`flex-1 max-w-[85%] ${message.sender === 'user' ? 'text-right' : ''}`}>
              <div
                className={`rounded-lg p-3 text-sm ${
                  message.sender === 'user'
                    ? 'bg-primary text-primary-foreground ml-auto'
                    : message.metadata?.widgetId
                    ? 'bg-blue-50 border border-blue-200 text-foreground'
                    : 'bg-muted text-foreground'
                }`}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>

                {/* Show mock AI indicator */}
                {message.metadata?.isMockAI && (
                  <div className="mt-2 text-xs text-orange-600 bg-orange-50 border border-orange-200 rounded px-2 py-1">
                    ⚠️ Mock AI Response - Add Gemini API key for real AI analysis
                  </div>
                )}

                {/* Show action suggestions for widget analyses */}
                {message.metadata?.actionSuggestions && message.metadata.actionSuggestions.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-border">
                    <div className="text-xs text-muted-foreground mb-2">Recommended Actions:</div>
                    <div className="space-y-1">
                      {message.metadata.actionSuggestions.map((action, index) => (
                        <div key={index} className="text-xs bg-background rounded px-2 py-1 border">
                          • {action}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                <span>{new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                {message.metadata?.widgetId && (
                  <Badge variant="secondary" className="text-xs">
                    Widget Analysis
                  </Badge>
                )}
                {message.metadata?.isMockAI && (
                  <Badge variant="outline" className="text-xs text-orange-600 border-orange-300">
                    Mock AI
                  </Badge>
                )}
                {message.metadata?.aiProvider === 'gemini' && (
                  <Badge variant="outline" className="text-xs text-green-600 border-green-300">
                    Gemini AI
                  </Badge>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {isCurrentlyThinking && (
          <div className="flex items-start space-x-3">
            <Avatar className="h-7 w-7 flex-shrink-0">
              <AvatarFallback className="bg-primary text-primary-foreground">
                <Bot className="h-3 w-3" />
              </AvatarFallback>
            </Avatar>

            <div className="flex-1 max-w-[85%]">
              <div className="rounded-lg p-3 text-sm bg-muted text-foreground">
                <div className="flex items-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                  </div>
                  <span className="text-muted-foreground">Analyzing...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input - Fixed at bottom */}
      <div className="p-4 border-t border-border bg-background">
        <div className="flex items-center space-x-2">
          <Button variant="ghost" size="icon" className="shrink-0">
            <Paperclip className="h-4 w-4" />
          </Button>
          <div className="flex-1 relative">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              className="pr-10 text-sm"
            />
            <Button
              size="icon"
              className="absolute right-1 top-1/2 transform -translate-y-1/2 h-7 w-7"
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isCurrentlyThinking}
            >
              <Send className="h-3 w-3" />
            </Button>
          </div>
        </div>
        <div className="text-xs text-muted-foreground mt-2 text-center">
          {isCurrentlyThinking ?
            'Analyzing widget data...' :
            'Click charts for analysis • Ask follow-up questions'
          }
        </div>
      </div>
    </div>
  );
}
