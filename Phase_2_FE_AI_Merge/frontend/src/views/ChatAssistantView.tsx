import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';
import { motion } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Components } from 'react-markdown';
import { cn } from '../lib/utils';
import { auth } from '../firebase';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  traces?: ToolTrace[];
}

interface ToolTrace {
  tool: string;
  query: string;
  top_k: number;
  search_scope: 'text' | 'image' | string;
  index_backend: string;
  result_count: number;
  result_preview: string;
}

const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';
const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:5000/api';

const CHAT_MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => <h1 className="text-2xl font-bold text-slate-900 mt-2 mb-3">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-semibold text-slate-900 mt-4 mb-2">{children}</h2>,
  h3: ({ children }) => <h3 className="text-lg font-semibold text-slate-900 mt-4 mb-2">{children}</h3>,
  p: ({ children }) => <p className="text-sm leading-7 text-slate-700 my-2">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 my-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 my-3 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="text-sm leading-7 text-slate-700">{children}</li>,
  table: ({ children }) => <table className="w-full border-collapse text-sm my-4">{children}</table>,
  th: ({ children }) => <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left">{children}</th>,
  td: ({ children }) => <td className="border border-slate-300 px-2 py-1 align-top">{children}</td>,
  a: ({ href, children }) => {
    const link = String(href || '');
    return (
      <a href={link} target="_blank" rel="noreferrer" className="text-blue-700 hover:text-blue-900 underline underline-offset-2">
        {children}
      </a>
    );
  },
};

function newSessionId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const DEFAULT_SUGGESTIONS = [
  "What documents do I have in my knowledge base?",
  "Show me my quiz performance and learning analytics",
  "Quiz me on the key topics from my lectures",
];

export default function ChatAssistantView() {
  const [sessionId, setSessionId] = useState<string>(() => newSessionId());
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hello! I'm your BK-MInD Assistant. I can help you understand your lectures, summarize documents, quiz you on any topic, or analyze your learning progress. How can I help you today?",
      timestamp: new Date()
    }
  ]);
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [traceJsonOpen, setTraceJsonOpen] = useState<Record<string, boolean>>({});
  const [assistantStatus, setAssistantStatus] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setAssistantStatus('Planning tool calls...');

    try {
      const aid = (Date.now() + 1).toString();

      const currentUser = auth.currentUser;
      const token = currentUser ? await currentUser.getIdToken() : localStorage.getItem(LOCAL_AUTH_TOKEN_KEY);
      const uid = currentUser?.uid || localStorage.getItem(LOCAL_AUTH_UID_KEY) || 'default';

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          'X-User-Id': uid,
        },
        body: JSON.stringify({ query: userMessage.content, top_k: 10, session_id: sessionId }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Chat stream failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let finalHadToken = false;

      const appendAssistant = (delta: string, replace = false) => {
        if (!delta) return;
        setMessages(prev => {
          const idx = prev.findIndex((m) => m.id === aid);
          if (idx < 0) {
            return [
              ...prev,
              {
                id: aid,
                role: 'assistant',
                content: delta,
                timestamp: new Date()
              }
            ];
          }
          const next = [...prev];
          next[idx] = {
            ...next[idx],
            content: replace ? delta : `${next[idx].content || ''}${delta}`
          };
          return next;
        });
      };

      const appendAssistantTrace = (trace: ToolTrace) => {
        setMessages(prev => {
          const idx = prev.findIndex((m) => m.id === aid);
          if (idx < 0) {
            return [
              ...prev,
              {
                id: aid,
                role: 'assistant',
                content: '',
                traces: [trace],
                timestamp: new Date()
              }
            ];
          }
          const next = [...prev];
          const old = next[idx];
          next[idx] = {
            ...old,
            traces: [...(old.traces || []), trace]
          };
          return next;
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split('\n\n');
        buf = parts.pop() || '';

        for (const evt of parts) {
          const line = evt
            .split('\n')
            .find((x) => x.startsWith('data:'));
          if (!line) continue;
          const payloadText = line.slice(5).trim();
          if (!payloadText) continue;
          let payload: { type?: string; delta?: string; message?: string; trace?: ToolTrace; questions?: string[] } = {};
          try {
            payload = JSON.parse(payloadText);
          } catch {
            continue;
          }
          if (payload.type === 'token') {
            finalHadToken = true;
            appendAssistant(payload.delta || '');
          } else if (payload.type === 'tool_trace' && payload.trace) {
            appendAssistantTrace(payload.trace);
          } else if (payload.type === 'status') {
            setAssistantStatus(payload.message || 'Thinking...');
          } else if (payload.type === 'suggestions' && Array.isArray(payload.questions)) {
            setSuggestions(payload.questions.slice(0, 3).filter(Boolean));
          } else if (payload.type === 'error') {
            throw new Error(payload.message || 'Chat agent error');
          }
        }
      }

      if (!finalHadToken) {
        appendAssistant('No response generated. Ensure Strands is installed and RAG indexes are available.', true);
      }
    } catch (error) {
      console.error("Chat Error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "I encountered an error while processing your request. Please try again later.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setAssistantStatus('');
    }
  };

  const clearChat = () => {
    if (window.confirm('Are you sure you want to clear the chat history?')) {
      setSessionId(newSessionId());
      setSuggestions(DEFAULT_SUGGESTIONS);
      setMessages([
        {
          id: '1',
          role: 'assistant',
          content: "Chat cleared. How can I help you now?",
          timestamp: new Date()
        }
      ]);
    }
  };


  return (
    <div className="mx-auto h-full flex flex-col overflow-hidden">
      {/* Chat Header */}
      <div className="px-8 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">BK-MInD Assistant</h2>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">Online & Ready</span>
            </div>
          </div>
        </div>
        <button
          onClick={clearChat}
          className="px-3 py-2 text-sm text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
          title="Clear Chat"
        >
          {/* <Trash2 className="w-5 h-5" /> */}
          Clear Chat
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
        {messages.map((message) => (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            key={message.id}
            className={cn(
              "flex gap-4",
              message.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
            )}
          >
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm",
              message.role === 'assistant' ? "bg-blue-100 text-blue-600" : "bg-slate-100 text-slate-600"
            )}>
              {message.role === 'assistant' ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
            </div>
            <div className={cn(
              "space-y-1",
              message.role === 'user' ? "max-w-[80%] text-right" : "w-full text-left"
            )}>
              <div className={cn(
                "px-5 py-4 rounded-xl text-sm font-medium leading-relaxed shadow-sm border",
                message.role === 'assistant'
                  ? "bg-white border-slate-100 text-slate-700 rounded-tl-none"
                  : "bg-blue-600 border-blue-500 text-white rounded-tr-none"
              )}>
                {message.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-li:my-1 prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-code:text-sky-700">
                    {(message.traces || []).map((trace, idx) => (
                      <div key={`${message.id}-trace-${idx}`} className="not-prose mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[11px] font-bold uppercase tracking-wider text-sky-700">
                            Tool Call: {trace.tool}
                          </p>
                          <button
                            type="button"
                            onClick={() => {
                              const key = `${message.id}-trace-${idx}`;
                              setTraceJsonOpen((prev) => ({ ...prev, [key]: !prev[key] }));
                            }}
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-100"
                          >
                            {(traceJsonOpen[`${message.id}-trace-${idx}`] ?? true) ? 'Show Preview' : 'Show JSON'}
                          </button>
                        </div>
                        <p className="text-xs text-slate-600 mt-1">
                          scope=<span className="font-semibold">{trace.search_scope}</span> | top_k=<span className="font-semibold">{trace.top_k}</span>
                        </p>
                        <p className="text-xs text-slate-600">index=<span className="font-semibold">{trace.index_backend}</span></p>
                        <p className="text-xs text-slate-700 mt-1">
                          query: <span className="font-medium">{trace.query}</span>
                        </p>
                        <p className="text-xs text-slate-700 mt-2">
                          result_count: <span className="font-semibold">{trace.result_count}</span>
                        </p>
                        <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-white p-2 text-[11px] leading-relaxed text-slate-700 border border-slate-200 max-h-72">
                          {(traceJsonOpen[`${message.id}-trace-${idx}`] ?? true)
                            ? JSON.stringify(trace, null, 2)
                            : trace.result_preview}
                        </pre>
                      </div>
                    ))}
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={CHAT_MARKDOWN_COMPONENTS}>
                      {message.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  message.content
                )}
              </div>
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-tighter px-2">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </motion.div>
        ))}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-4 mr-auto"
          >
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 bg-blue-100 text-blue-600">
              <Bot className="w-5 h-5" />
            </div>
            <div className="space-y-1 w-full text-left">
              <div className="px-4 py-3 rounded-lg text-xs font-semibold leading-relaxed border bg-blue-50 border-blue-100 text-blue-700 rounded-tl-none">
                {assistantStatus || 'Thinking...'}
              </div>
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="px-8 pt-3 pb-8 border-t border-slate-100 bg-slate-50/30">
        {/* Suggestion chips — always visible; updates to follow-ups after each response */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
          {suggestions.map((s, i) => (
            <button
              key={`${s}-${i}`}
              onClick={() => setInput(s)}
              disabled={isLoading}
              className="p-3 bg-white border border-slate-200 rounded-lg text-left hover:border-blue-300 hover:shadow-sm hover:bg-blue-50/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <p className="text-xs font-medium text-slate-600 leading-snug line-clamp-2">{s}</p>
            </button>
          ))}
        </div>
        <form onSubmit={handleSend} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message here..."
            className="w-full pl-5 pr-16 py-4 bg-white border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all shadow-sm"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-blue-600 text-white rounded-lg flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
}
