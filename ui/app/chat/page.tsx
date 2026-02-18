"use client";

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import MarkdownRenderer from './MarkdownRenderer';

// SVG Icons as components
const SendIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);

const BackIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
  </svg>
);

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const SettingsIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

interface Message {
  sender: string;
  text: string;
  timestamp: string;
  trace?: any[];
  expandTrace?: boolean;
  images?: string[];
}

interface Agent {
  name: string;
  image?: string;
  icon?: string;
  agentCollaboration: 'SUPERVISOR' | 'DISABLED';
  collaborators?: string[];
}

export default function ChatPage() {
  const [selectedAgents, setSelectedAgents] = useState<Agent[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [instruction, setInstruction] = useState('You are an automotive service assistant AI specializing in vehicle diagnostics and service management. Coordinate sub-agents to fulfill user questions.');
  const [isProcessing, setIsProcessing] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [alwaysCollapseTraces, setAlwaysCollapseTraces] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRequestIdRef = useRef(`req-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`);
  
  const isSupervisorChat = selectedAgents.some(agent => 
    agent.agentCollaboration === 'SUPERVISOR' || (agent as any).agentCollaboration === 'SUPERVISOR_ROUTER'
  );

  const formatTime = (timestamp: any) => new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const sendMessage = async () => {
    if (!input.trim()) return;
    const timestamp = new Date().toISOString();
    const userMessage = { sender: 'You', text: input, timestamp };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    // Insert placeholder trace message immediately
    const chat_request_id = chatRequestIdRef.current;
    setMessages((prev) => [
      ...prev,
      {
        sender: 'AI Agent',
        text: '',
        timestamp: new Date().toISOString(),
        trace: [{ type: 'placeholder', text: 'Trace loading for chat id : ' + chat_request_id }],
        expandTrace: true
      }
    ]);

    
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: input, 
        agents: selectedAgents, 
        agent_instruction: instruction,
        requestId : chat_request_id
      })
    });

    const reader = response.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder('utf-8');
    let finalText = '';
    let stepCount = 0;

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const fullChunk = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);

        if (fullChunk.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(fullChunk.slice(6));
  
            if (parsed.type === 'chunk') {
              finalText += parsed.data;
              setMessages((prev) => {
                const lastMsg = prev[prev.length - 1];
                if (!lastMsg || lastMsg.sender !== 'AI Agent') {
                  return [...prev, { sender: 'AI Agent', text: parsed.data, timestamp: new Date().toISOString(), trace: [{ type: 'placeholder', text: 'Trace loading...' }], expandTrace: true }];
                }
                const updated = [...prev];
                updated[updated.length - 1].text += parsed.data;
                return updated;
              });
            }
  
            else if (['rationale', 'tool', 'observation', 'agent-collaborator', 'knowledge-base', 'error'].includes(parsed.type)) {
              const step = parsed.step !== undefined ? parsed.step : stepCount + 1;
              stepCount = step;
              const agent = parsed.agent || parsed.data?.agent || 'unknown-agent';
              const traceStep = { ...parsed, step, agent };
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                if (!lastMsg || lastMsg.sender !== 'AI Agent') {
                updated.push({ sender: 'AI Agent', text: '', timestamp: new Date().toISOString(), trace: [traceStep], expandTrace: true });
              } else {
                const existing = lastMsg.trace || [];
                const alreadyExists = existing.some(t =>
                  t.step === traceStep.step &&
                  t.type === traceStep.type &&
                  t.text === traceStep.text
                );
                if (!alreadyExists) {
                  lastMsg.trace = [...existing.filter(t => t.type !== 'placeholder'), traceStep];
                  lastMsg.trace.push(existing.find(t => t.type === 'placeholder'));
                  }
                  lastMsg.expandTrace = true;
                }
                return updated;
              });
            }
            else if (parsed.type === 'end') {
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                if (lastMsg && lastMsg.sender === 'AI Agent') {
                lastMsg.text = parsed.finalMessage || finalText;
                lastMsg.timestamp = new Date().toISOString();
                lastMsg.images = parsed.images || (parsed.image ? [parsed.image] : []);
                lastMsg.trace = (lastMsg.trace || []).filter(t => t.type !== 'placeholder');
                  lastMsg.expandTrace = true;
                }
                return updated;
              });
              setIsProcessing(false);
            }
  
          } catch (e) {
            console.error('Error parsing SSE:', e);
            console.error(fullChunk);
          }
        }
        
        boundary = buffer.indexOf('\n\n');
      }  
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const stored = localStorage.getItem('selectedAgents');
    if (stored) setSelectedAgents(JSON.parse(stored));
    const storedInstruction = localStorage.getItem('agent_instruction');
    if (storedInstruction) setInstruction(storedInstruction);
    const storedMessages = localStorage.getItem('chatMessages');
    if (storedMessages) setMessages(JSON.parse(storedMessages));
  }, []);

  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages));
  }, [messages]);

  const clearChat = () => {
    setMessages([]);
    localStorage.removeItem('chatMessages');
    chatRequestIdRef.current = `req-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Fixed Header Section */}
      <div className="fixed top-0 left-0 right-0 z-10">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/" className="text-gray-600 hover:text-gray-900 hover:bg-gray-200 p-1 rounded-full">
                <BackIcon />
              </Link>
              <h1 className="text-xl font-semibold text-gray-900">MA3T Chat</h1>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="p-2 text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md"
                title="Settings"
              >
                <SettingsIcon />
              </button>
              <button
                onClick={clearChat}
                className="p-2 text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md"
                title="Clear Chat"
              >
                <TrashIcon />
              </button>
            </div>
          </div>
        </div>

        {/* Settings Panel - Conditionally Rendered */}
        {showSettings && (
          <div className="bg-white border-b border-gray-200 px-6 py-3">
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Agent Instructions</h3>
              <textarea
                className={`w-full border rounded p-2 text-sm ${isSupervisorChat ? 'bg-gray-100 cursor-not-allowed' : 'border-gray-300'}`}
                placeholder="Enter instructions for the MA3T agents..."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={3}
                disabled={isSupervisorChat}
              />
              {isSupervisorChat && (
                <p className="text-red-500 text-xs mt-1">🔒 Instruction is locked while using a Supervisor agent.</p>
              )}
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <label className="flex items-center cursor-pointer">
                  <div className="relative">
                    <input
                      type="checkbox"
                      checked={alwaysCollapseTraces}
                      onChange={(e) => setAlwaysCollapseTraces(e.target.checked)}
                      className="sr-only"
                    />
                    <div className="w-10 h-5 bg-gray-300 rounded-full shadow-inner"></div>
                    <div
                      className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transform transition-transform ${alwaysCollapseTraces ? 'translate-x-5' : ''}`}
                    ></div>
                  </div>
                  <span className="ml-2 text-sm text-gray-700">
                    {alwaysCollapseTraces ? 'Collapse Traces' : 'Expand Traces'}
                  </span>
                </label>
              </div>
              <button
                onClick={() => setShowSettings(false)}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Close Settings
              </button>
            </div>
          </div>
        )}

        {/* Selected Agents */}
        <div className="bg-white border-b border-gray-200 px-6 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-medium text-gray-700">Selected Agents:</h3>
            {selectedAgents.map((agent, idx) => (
              <div key={idx} className="flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                {agent.image && (
                  <img 
                    src={agent.image} 
                    alt={agent.name} 
                    className="w-5 h-5 rounded-full mr-1" 
                  />
                )}
                <span>{agent.name}</span>
                <span className="ml-1 text-xs px-1.5 py-0.5 rounded bg-blue-200">
                  {isSupervisorChat ? 'Supervisor' : 'Individual'}
                </span>
              </div>
            ))}
            {selectedAgents.length === 0 && (
              <span className="text-sm text-gray-500 italic">No agents selected. Please return to the home page to select agents.</span>
            )}
          </div>
        </div>
      </div>

      {/* Calculate header height for proper padding */}
      <div className="h-[152px]">
        {/* This is a spacer to account for the fixed header height */}
        {showSettings && <div className="h-[120px]"></div>}
      </div>

      {/* Scrollable Chat Area */}
      <div className="flex-1 p-4 overflow-y-auto pb-24">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-gray-400 mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h3 className="text-xl font-medium text-gray-700 mb-2">Start a conversation</h3>
              <p className="text-gray-500 max-w-md mx-auto">
                Ask questions about vehicle service, manufacturing processes, or any automotive-related topic.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, index) => (
                <div key={index} className={`flex ${msg.sender === 'You' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-3xl rounded-lg p-4 ${
                    msg.sender === 'You' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-white border border-gray-200 shadow-sm'
                  }`}>
                    <div className="flex justify-between items-center mb-2">
                      <span className={`font-medium ${msg.sender === 'You' ? 'text-blue-100' : 'text-gray-700'}`}>
                        {msg.sender}
                      </span>
                      <span className={`text-xs ${msg.sender === 'You' ? 'text-blue-200' : 'text-gray-400'}`}>
                        {formatTime(msg.timestamp)}
                      </span>
                    </div>
                    
                    <div className={msg.sender === 'You' ? 'whitespace-pre-wrap text-white' : 'text-gray-800'}>
                      {msg.sender === 'You' ? (
                        msg.text
                      ) : (
                        <MarkdownRenderer content={msg.text} />
                      )}
                    </div>
                    
                    {msg.images && msg.images.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {msg.images.map((url, idx) => (
                          <img
                            key={idx}
                            src={url}
                            alt={`Generated Visual ${idx + 1}`}
                            className="rounded shadow border max-w-full h-auto"
                          />
                        ))}
                      </div>
                    )}
                    
                    {msg.trace && msg.trace.length > 0 && msg.sender !== 'You' && (
                      <details open={!alwaysCollapseTraces && msg.expandTrace} className="mt-3 pt-2 border-t border-gray-200">
                        <summary className="cursor-pointer text-sm font-medium text-blue-600 hover:text-blue-800">
                          🧵 View Trace Steps ({msg.trace.length})
                        </summary>
                        <div className="mt-2 space-y-2">
                          {msg.trace.map((step, stepIdx) => {
                            if (step.type === 'placeholder') return null;
                            
                            return (
                              <details key={stepIdx} className="border rounded bg-gray-50 p-2 text-sm">
                                <summary className="cursor-pointer font-medium text-gray-700">
                                  Step {step.step}: {step.type.charAt(0).toUpperCase() + step.type.slice(1)}
                                </summary>
                                <div className="mt-2 pl-2 border-l-2 border-gray-300">
                                  {step.type === 'rationale' && (
                                    <div className="text-gray-700">
                                      <span className="font-medium">Rationale:</span>{' '}
                                      <span>{step.text}</span>
                                    </div>
                                  )}
                                  {step.type === 'agent-collaborator' && (
                                    <div className="text-gray-700">
                                      <span className="font-medium">Agent - {step.agent}:</span> {step.text}
                                    </div>
                                  )}
                                  {step.type === 'tool' && (
                                    <div className="text-gray-700">
                                      <div><span className="font-medium">Tool:</span> {step.function || step.apiPath || 'Unknown'}</div>
                                      <div><span className="font-medium">Execution:</span> {step.executionType}</div>
                                    </div>
                                  )}
                                  {step.type === 'observation' && (
                                    <div className="text-gray-700">
                                      <span className="font-medium">Observation:</span>
                                      <div className="mt-1 bg-white p-2 rounded border border-gray-200 overflow-auto">
                                        {step.text}
                                      </div>
                                    </div>
                                  )}
                                  {step.type === 'knowledge-base' && (
                                    <div className="text-gray-700">
                                      <span className="font-medium">Knowledge Base Result:</span>
                                      <div className="mt-1 bg-white p-2 rounded border border-gray-200 overflow-auto">
                                        {step.text}
                                      </div>
                                    </div>
                                  )}
                                  {step.type === 'error' && (
                                    <div className="text-red-600">
                                      Error during agent execution: {step.message || step.text}
                                    </div>
                                  )}
                                </div>
                              </details>
                            );
                          })}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              ))}
              {isProcessing && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm max-w-3xl">
                    <div className="flex space-x-2 items-center text-gray-500">
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                      <span className="ml-2">Processing your request...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Fixed Input Area at bottom */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-md z-10">
        <div className="max-w-4xl mx-auto flex">
          <input
            type="text"
            className="flex-1 border border-gray-300 rounded-l-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Ask a question about vehicle service or manufacturing..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            disabled={isProcessing || selectedAgents.length === 0}
          />
          <button
            className={`bg-blue-600 text-white px-4 py-2 rounded-r-md flex items-center justify-center ${
              (isProcessing || selectedAgents.length === 0) 
                ? 'opacity-50 cursor-not-allowed' 
                : 'hover:bg-blue-700'
            }`}
            onClick={sendMessage}
            disabled={isProcessing || selectedAgents.length === 0}
          >
            <SendIcon />
          </button>
        </div>
        {selectedAgents.length === 0 && (
          <div className="max-w-4xl mx-auto mt-2">
            <p className="text-sm text-red-500">Please select agents from the home page to start chatting.</p>
          </div>
        )}
      </div>
    </div>
  );
}
