import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Loader2,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  User,
  X,
} from 'lucide-react';
import { motion } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Components } from 'react-markdown';
import { cn } from '../lib/utils';
import { auth } from '../firebase';
import chatRobot from '../../robot_1.png';
import { authService } from '../services/auth_service';
import {
  createFeedback,
  createChatSession,
  deleteChatSession,
  listFeedback,
  listChatSessionMessages,
  listChatSessions,
  type ChatSessionMessage,
  type ChatSessionSummary,
  updateChatSession,
} from '../api/ragApi';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  traces?: ToolTrace[];
  suggestions?: string[];
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

type FeedbackVote = 'like' | 'dislike';

type FeedbackState = {
  vote?: FeedbackVote;
  submitting?: boolean;
  error?: string;
  saved_at?: number;
};

const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';
const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || '/api';
const CHAT_SESSIONS_PAGE_SIZE = 10;
const CHAT_HISTORY_ENABLED_KEY = 'bk_chat_history_enabled';

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

const DISLIKE_REASONS: Array<{ code: string; label: string }> = [
  { code: 'incorrect_answer', label: 'Incorrect answer' },
  { code: 'insufficient_information', label: 'Insufficient information' },
  { code: 'not_relevant', label: 'Not relevant to my question' },
  { code: 'too_short', label: 'Too short / low detail' },
  { code: 'hallucination', label: 'Hallucination / made-up content' },
  { code: 'unsafe_content', label: 'Safety issue / sensitive output' },
  { code: 'other', label: 'Other (write custom reason)' },
];

function welcomeMessage(text: string): Message {
  return {
    id: `assistant-welcome-${Date.now()}`,
    role: 'assistant',
    content: text,
    timestamp: new Date(),
  };
}

function toUiMessage(row: ChatSessionMessage): Message {
  return {
    id: row.message_id,
    role: row.role === 'user' ? 'user' : 'assistant',
    content: row.content,
    timestamp: new Date(row.created_at || Date.now()),
    traces: (row.traces || []) as unknown as ToolTrace[],
    suggestions: row.suggestions || [],
  };
}

export default function ChatAssistantView() {
  const [historyEnabled, setHistoryEnabled] = useState<boolean>(() => {
    const raw = localStorage.getItem(CHAT_HISTORY_ENABLED_KEY);
    return raw !== '0';
  });
  const [historyPanelOpen, setHistoryPanelOpen] = useState(true);
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([welcomeMessage("Hello! I'm your BK-MInD Assistant. I can help you understand your lectures, summarize documents, quiz you on any topic, or analyze your learning progress. How can I help you today?")]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsCursor, setSessionsCursor] = useState<string | null>(null);
  const [sessionsNextCursor, setSessionsNextCursor] = useState<string | null>(null);
  const [sessionsCursorHistory, setSessionsCursorHistory] = useState<string[]>([]);
  const [activeSessionLoading, setActiveSessionLoading] = useState(false);
  const [sessionEditor, setSessionEditor] = useState<{ id: string; title: string } | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [traceJsonOpen, setTraceJsonOpen] = useState<Record<string, boolean>>({});
  const [assistantStatus, setAssistantStatus] = useState<string>('');
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [copyErrorMessageId, setCopyErrorMessageId] = useState<string | null>(null);
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, FeedbackState>>({});
  const [dislikeModal, setDislikeModal] = useState<{
    open: boolean;
    messageId: string;
    query: string;
    response: string;
  }>({
    open: false,
    messageId: '',
    query: '',
    response: '',
  });
  const [dislikeReasonCode, setDislikeReasonCode] = useState<string>('incorrect_answer');
  const [dislikeReasonText, setDislikeReasonText] = useState<string>('');
  const [profileContext, setProfileContext] = useState<{ persona: string; educationDescription: string }>({
    persona: '',
    educationDescription: '',
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionsLoadInFlightRef = useRef(false);
  const selectSessionInFlightRef = useRef<string | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    localStorage.setItem(CHAT_HISTORY_ENABLED_KEY, historyEnabled ? '1' : '0');
  }, [historyEnabled]);

  useEffect(() => {
    let active = true;
    void authService.getMe().then((me) => {
      if (!active) return;
      setProfileContext({
        persona: (me.persona || '').trim(),
        educationDescription: (me.educationDescription || '').trim(),
      });
    }).catch(() => {
      if (!active) return;
      setProfileContext({ persona: '', educationDescription: '' });
    });
    return () => {
      active = false;
    };
  }, []);

  const activeSession = useMemo(
    () => sessions.find((s) => s.session_id === sessionId) || null,
    [sessions, sessionId]
  );

  const loadSessions = async (cursor: string | null = null, pushCurrentCursor = false): Promise<ChatSessionSummary[]> => {
    if (!historyEnabled) return [];
    if (sessionsLoadInFlightRef.current) return sessions;

    sessionsLoadInFlightRef.current = true;
    setSessionsLoading(true);
    try {
      const res = await listChatSessions({
        limit: CHAT_SESSIONS_PAGE_SIZE,
        cursor,
      });
      if (pushCurrentCursor) {
        setSessionsCursorHistory((prev) => [...prev, sessionsCursor || '']);
      }
      setSessions(res.items || []);
      setSessionsNextCursor(res.next_cursor || null);
      setSessionsCursor(cursor);
      return res.items || [];
    } catch (e) {
      console.error('Failed to load chat sessions', e);
      return [];
    } finally {
      setSessionsLoading(false);
      sessionsLoadInFlightRef.current = false;
    }
  };

  const selectSession = async (sid: string) => {
    if (!historyEnabled) return;
    if (selectSessionInFlightRef.current === sid) return;

    selectSessionInFlightRef.current = sid;
    setActiveSessionLoading(true);
    try {
      const res = await listChatSessionMessages(sid, {
        limit: 80,
        newest_first: false,
      });
      const rows = res.items || [];
      const mapped = rows.map(toUiMessage);
      setSessionId(sid);
      void hydrateFeedbackForSession(sid, mapped);
      if (mapped.length > 0) {
        setMessages(mapped);
        const lastAssistantWithSuggestions = [...rows]
          .reverse()
          .find((row) => row.role === 'assistant' && (row.suggestions || []).length > 0);
        if (lastAssistantWithSuggestions) {
          setSuggestions((lastAssistantWithSuggestions.suggestions || []).slice(0, 3));
        } else {
          setSuggestions(DEFAULT_SUGGESTIONS);
        }
      } else {
        setMessages([welcomeMessage('This chat is empty. Ask me anything about your learning materials.')]);
        setSuggestions(DEFAULT_SUGGESTIONS);
      }
    } catch (e) {
      console.error('Failed to load chat messages', e);
      setMessages([welcomeMessage('Could not load chat history. You can still start a new message now.')]);
      setFeedbackByMessageId({});
      setSuggestions(DEFAULT_SUGGESTIONS);
      setSessionId(sid);
    } finally {
      setActiveSessionLoading(false);
      selectSessionInFlightRef.current = null;
    }
  };

  const startNewChat = async () => {
    if (!historyEnabled) {
      setSessionId(newSessionId());
      setMessages([welcomeMessage('New chat started. What would you like to learn now?')]);
      setFeedbackByMessageId({});
      setSuggestions(DEFAULT_SUGGESTIONS);
      setInput('');
      setAssistantStatus('');
      return;
    }

    try {
      const sid = newSessionId();
      const created = await createChatSession({
        session_id: sid,
        title: 'New chat',
        pinned: false,
      });
      setSessionId(created.item.session_id);
      setMessages([welcomeMessage('New chat started. What would you like to learn now?')]);
      setFeedbackByMessageId({});
      setSuggestions(DEFAULT_SUGGESTIONS);
      setInput('');
      setAssistantStatus('');
      await loadSessions(null, false);
    } catch (e) {
      console.error('Failed to create chat session', e);
      const fallbackId = newSessionId();
      setSessionId(fallbackId);
      setMessages([welcomeMessage('New chat started. What would you like to learn now?')]);
      setFeedbackByMessageId({});
      setSuggestions(DEFAULT_SUGGESTIONS);
    }
  };

  useEffect(() => {
    let active = true;

    if (!historyEnabled) {
      setSessions([]);
      setSessionsCursor(null);
      setSessionsNextCursor(null);
      setSessionsCursorHistory([]);
      setSessionEditor(null);
      if (!sessionId) {
        setSessionId(newSessionId());
      }
      return () => {
        active = false;
      };
    }

    const bootstrap = async () => {
      const items = await loadSessions(null, false);
      if (!active) return;
      if (!sessionId && items.length > 0) {
        await selectSession(items[0].session_id);
      }
    };

    void bootstrap();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyEnabled]);

  const handleToggleHistory = () => {
    const next = !historyEnabled;
    setHistoryEnabled(next);

    if (!next) {
      setSessions([]);
      setSessionsCursor(null);
      setSessionsNextCursor(null);
      setSessionsCursorHistory([]);
      setSessionEditor(null);
    }
  };

  const handleTogglePin = async (item: ChatSessionSummary) => {
    if (!historyEnabled) return;
    try {
      await updateChatSession(item.session_id, { pinned: !item.pinned });
      await loadSessions(sessionsCursor, false);
    } catch (e) {
      console.error('Failed to toggle pinned state', e);
    }
  };

  const handleSaveSessionTitle = async () => {
    if (!historyEnabled) return;
    if (!sessionEditor) return;
    const nextTitle = sessionEditor.title.trim();
    if (!nextTitle) return;
    try {
      await updateChatSession(sessionEditor.id, { title: nextTitle });
      setSessionEditor(null);
      await loadSessions(sessionsCursor, false);
    } catch (e) {
      console.error('Failed to update session title', e);
    }
  };

  const handleDeleteSession = async (item: ChatSessionSummary) => {
    if (!historyEnabled) return;
    if (!window.confirm(`Delete chat session "${item.title || 'Untitled chat'}"?`)) return;

    try {
      await deleteChatSession(item.session_id);
      const refreshedItems = await loadSessions(sessionsCursor, false);

      if (item.session_id === sessionId) {
        const replacement = refreshedItems.find((s) => s.session_id !== item.session_id);
        if (replacement) {
          await selectSession(replacement.session_id);
        } else {
          setSessionId('');
          setMessages([welcomeMessage('This session was deleted. Start a new chat when you are ready.')]);
          setSuggestions(DEFAULT_SUGGESTIONS);
        }
      }
    } catch (e) {
      console.error('Failed to delete session', e);
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    let effectiveSessionId = sessionId;
    if (!effectiveSessionId) {
      if (historyEnabled) {
        try {
          const created = await createChatSession({ session_id: newSessionId(), title: input.trim().slice(0, 120) });
          effectiveSessionId = created.item.session_id;
          setSessionId(effectiveSessionId);
        } catch {
          effectiveSessionId = newSessionId();
          setSessionId(effectiveSessionId);
        }
      } else {
        effectiveSessionId = newSessionId();
        setSessionId(effectiveSessionId);
      }
    }

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
        body: JSON.stringify({
          query: userMessage.content,
          top_k: 10,
          session_id: effectiveSessionId,
          persona: profileContext.persona || undefined,
          education_description: profileContext.educationDescription || undefined,
        }),
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
          let payload: {
            type?: string;
            delta?: string;
            message?: string;
            trace?: ToolTrace;
            questions?: string[];
            session_id?: string;
          } = {};
          try {
            payload = JSON.parse(payloadText);
          } catch {
            continue;
          }
          if (payload.type === 'session' && payload.session_id) {
            setSessionId(payload.session_id);
          } else if (payload.type === 'token') {
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

      if (historyEnabled) {
        await loadSessions(null, false);
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
    if (window.confirm('Start a new chat session? Current history remains saved.')) {
      void startNewChat();
    }
  };

  const previousUserQueryForIndex = (assistantIndex: number): string => {
    for (let i = assistantIndex - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') {
        return messages[i].content;
      }
    }
    return '';
  };

  const hydrateFeedbackForSession = async (sid: string, rows: Message[]) => {
    const messageIds = new Set(
      rows
        .filter((m) => m.role === 'assistant' && !m.id.startsWith('assistant-welcome-'))
        .map((m) => m.id)
    );
    if (!messageIds.size) {
      setFeedbackByMessageId({});
      return;
    }

    try {
      const data = await listFeedback({ limit: 200, session_id: sid });
      const next: Record<string, FeedbackState> = {};
      for (const item of data.items || []) {
        const mid = String(item.message_id || '').trim();
        if (!mid || !messageIds.has(mid) || next[mid]) continue;
        const vote = item.vote === 'like' || item.vote === 'dislike' ? item.vote : undefined;
        if (!vote) continue;
        next[mid] = {
          vote,
          submitting: false,
          error: undefined,
        };
      }
      setFeedbackByMessageId(next);
    } catch {
      // Keep chat usable even if feedback lookup fails.
      setFeedbackByMessageId({});
    }
  };

  const copyAssistantMessage = async (messageId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text || '');
      setCopyErrorMessageId((prev) => (prev === messageId ? null : prev));
      setCopiedMessageId(messageId);
      window.setTimeout(() => setCopiedMessageId((prev) => (prev === messageId ? null : prev)), 1400);
    } catch {
      setCopiedMessageId((prev) => (prev === messageId ? null : prev));
      setCopyErrorMessageId(messageId);
      window.setTimeout(() => setCopyErrorMessageId((prev) => (prev === messageId ? null : prev)), 1600);
    }
  };

  const submitFeedback = async (
    messageId: string,
    vote: FeedbackVote,
    queryText: string,
    responseText: string,
    reasonCode?: string,
    reasonText?: string,
  ) => {
    setFeedbackByMessageId((prev) => ({
      ...prev,
      [messageId]: { ...(prev[messageId] || {}), submitting: true, error: undefined },
    }));
    try {
      await createFeedback({
        vote,
        query: queryText || 'N/A',
        response: responseText || 'N/A',
        session_id: sessionId || undefined,
        message_id: messageId || undefined,
        reason_code: reasonCode,
        reason_text: reasonText,
      });
      setFeedbackByMessageId((prev) => ({
        ...prev,
        [messageId]: { vote, submitting: false, error: undefined, saved_at: Date.now() },
      }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to submit feedback';
      setFeedbackByMessageId((prev) => ({
        ...prev,
        [messageId]: { ...(prev[messageId] || {}), submitting: false, error: msg },
      }));
    }
  };

  const openDislikeModal = (messageId: string, queryText: string, responseText: string) => {
    setDislikeReasonCode('incorrect_answer');
    setDislikeReasonText('');
    setDislikeModal({
      open: true,
      messageId,
      query: queryText,
      response: responseText,
    });
  };

  const submitDislike = async () => {
    if (!dislikeModal.open || !dislikeModal.messageId) return;
    const reasonText = dislikeReasonCode === 'other' ? dislikeReasonText.trim() : dislikeReasonText.trim() || undefined;
    await submitFeedback(
      dislikeModal.messageId,
      'dislike',
      dislikeModal.query,
      dislikeModal.response,
      dislikeReasonCode,
      reasonText,
    );
    setDislikeModal({ open: false, messageId: '', query: '', response: '' });
  };


  return (
    <div className={cn(
      'w-full h-full min-h-0 grid gap-4',
      historyPanelOpen ? 'grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)]' : 'grid-cols-1',
    )}>
      {historyPanelOpen && (
      <aside className="min-h-[240px] max-h-full flex flex-col overflow-hidden rounded-2xl border border-sky-100 bg-white shadow-[0_14px_28px_-26px_rgba(14,165,233,0.45)]">
        <div className="px-3 py-2.5 border-b border-sky-100 bg-white space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <button
                type="button"
                onClick={() => setHistoryPanelOpen(false)}
                className="p-1.5 rounded-md text-slate-500 hover:text-sky-700 hover:bg-sky-50 transition-colors"
                title="Hide history panel"
                aria-label="Hide history panel"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
              <h3 className="text-sm font-bold text-slate-800 truncate">Chats</h3>
            </div>
            <button
              type="button"
              onClick={handleToggleHistory}
              className={cn(
                'inline-flex items-center rounded-md border px-2 py-1 text-[11px] font-semibold transition-colors',
                historyEnabled
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                  : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-100',
              )}
              title="Toggle chat history sync"
            >
              {historyEnabled ? 'On' : 'Off'}
            </button>
          </div>
          <button
            type="button"
            onClick={() => void startNewChat()}
            className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50/70 px-2.5 py-2 text-xs font-semibold text-sky-700 hover:bg-sky-100/70"
            title="Start new chat"
          >
            <Plus className="w-3.5 h-3.5" />
            New chat
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto px-2 py-2 space-y-1.5 bg-slate-50/60">
          {!historyEnabled && (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white px-3 py-4 text-xs text-slate-600">
              Chat history sync is turned off. This chat works in local mode only and does not call session APIs.
            </div>
          )}
          {historyEnabled && sessionsLoading && (
            <div className="text-xs text-slate-500 px-2 py-3">Loading chat sessions...</div>
          )}
          {historyEnabled && !sessionsLoading && sessions.length === 0 && (
            <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 px-3 py-4 text-xs text-slate-500">
              No chats yet. Start a new chat to save your conversation history.
            </div>
          )}
          {historyEnabled && sessions.map((s) => {
            const active = s.session_id === sessionId;
            const editing = sessionEditor?.id === s.session_id;
            return (
              <div
                key={s.session_id}
                className={cn(
                  'group relative rounded-lg border transition-colors',
                  active
                    ? 'border-sky-300 bg-sky-50'
                    : 'border-transparent bg-transparent hover:bg-white hover:border-slate-200'
                )}
              >
                {editing ? (
                  <div className="space-y-2 p-2">
                    <input
                      value={sessionEditor.title}
                      onChange={(e) => setSessionEditor({ id: s.session_id, title: e.target.value })}
                      aria-label="Chat title"
                      placeholder="Chat title"
                      className="w-full rounded-md border border-slate-300 px-2 py-1 text-xs"
                      maxLength={120}
                    />
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        className="rounded border border-slate-300 p-1 text-slate-600 hover:bg-slate-100"
                        onClick={() => setSessionEditor(null)}
                        aria-label="Cancel rename"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        className="rounded border border-sky-300 bg-sky-50 p-1 text-sky-700 hover:bg-sky-100"
                        onClick={() => void handleSaveSessionTitle()}
                        aria-label="Save name"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => void selectSession(s.session_id)}
                      className="w-full text-left px-2.5 py-2.5 pr-24"
                    >
                      <p className="text-[13px] font-semibold text-slate-800 truncate flex items-center gap-1.5">
                        {s.pinned ? <Pin className="w-3.5 h-3.5 text-amber-600" /> : <MessageSquare className="w-3.5 h-3.5 text-slate-400" />}
                        <span className="truncate">{s.title || 'Untitled chat'}</span>
                      </p>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {s.message_count} messages
                      </p>
                    </button>
                    <div className="absolute right-2 top-2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => void handleTogglePin(s)}
                        className="rounded-md p-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                        title={s.pinned ? 'Unpin chat' : 'Pin chat'}
                      >
                        {s.pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => setSessionEditor({ id: s.session_id, title: s.title })}
                        className="rounded-md p-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                        title="Rename chat"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteSession(s)}
                        className="rounded-md p-1 text-red-500 hover:bg-red-50"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
        <div className="px-3 py-2 border-t border-sky-100 bg-white flex items-center justify-between">
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 disabled:opacity-40"
            disabled={!historyEnabled || sessionsCursorHistory.length === 0}
            onClick={() => {
              if (sessionsCursorHistory.length === 0) return;
              const prev = sessionsCursorHistory[sessionsCursorHistory.length - 1];
              setSessionsCursorHistory((stack) => stack.slice(0, -1));
              void loadSessions(prev || null, false);
            }}
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Prev
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 disabled:opacity-40"
            disabled={!historyEnabled || !sessionsNextCursor}
            onClick={() => {
              if (!sessionsNextCursor) return;
              void loadSessions(sessionsNextCursor, true);
            }}
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>
      )}

      <div className="min-w-0 h-full flex flex-col overflow-hidden rounded-2xl border border-sky-100 bg-white shadow-[0_18px_36px_-28px_rgba(14,165,233,0.55)]">
        {/* Chat Header */}
        <div className="px-5 sm:px-7 py-3 border-b border-sky-100 flex items-center justify-between bg-sky-50/50">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg sm:text-xl font-black text-slate-900 tracking-tight truncate">BK-MInD Assistant</h2>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                <span className="text-xs font-semibold text-slate-500">
                  {activeSession ? `Session: ${activeSession.title}` : 'Online and ready'}
                </span>
              </div>
            </div>
            <div className="hidden xl:flex items-center gap-2 px-3 py-2 rounded-xl border border-sky-100 bg-white/80 shrink-0">
              <Sparkles className="w-4 h-4 text-sky-600" />
              <span className="text-[11px] font-semibold text-slate-600">
                {profileContext.persona ? `Tone: ${profileContext.persona}` : 'RAG + Agent mode'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setHistoryPanelOpen((prev) => !prev)}
              className="px-3 py-2 text-xs font-semibold text-slate-600 hover:text-sky-700 hover:bg-sky-100 rounded-lg transition-all shrink-0 inline-flex items-center gap-1.5"
              title={historyPanelOpen ? 'Hide history panel' : 'Show history panel'}
            >
              {historyPanelOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
              Chats
            </button>
            <button
              onClick={clearChat}
              className="px-3 py-2 text-sm text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all shrink-0"
              title="Start new chat"
            >
              New Chat
            </button>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-7 custom-scrollbar bg-[radial-gradient(circle_at_top_right,rgba(186,230,253,0.2),transparent_35%)]">
          {activeSessionLoading && (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
              Loading session messages...
            </div>
          )}
          {messages.length <= 1 && !isLoading && !activeSessionLoading && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="rounded-2xl border border-sky-100 bg-white/95 shadow-[0_16px_34px_-28px_rgba(14,165,233,0.55)] p-5 sm:p-6 grid grid-cols-1 md:grid-cols-[1.35fr_0.65fr] gap-5"
            >
              <div className="space-y-3">
                <p className="text-[10px] font-black uppercase tracking-widest text-sky-600">Study assistant</p>
                <h3 className="text-xl font-black text-slate-900 tracking-tight">Ask for summaries, retrieval, quiz prep, or concept breakdowns.</h3>
                <p className="text-sm text-slate-500 leading-relaxed">
                  I can search across indexed lecture files, cite relevant chunks, and generate focused responses for your current learning objective.
                </p>
              </div>
              <div className="hidden md:flex items-center justify-center rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
                <img src={chatRobot} alt="BK-MInD chat assistant" className="h-28 w-auto object-contain animate-float-delayed" />
              </div>
            </motion.div>
          )}
          {messages.map((message, messageIndex) => (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              key={message.id}
              className={cn(
                'flex gap-4',
                message.role === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
              )}
            >
              <div className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm',
                message.role === 'assistant' ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'
              )}>
                {message.role === 'assistant' ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
              </div>
              <div className={cn(
                'space-y-1',
                message.role === 'user' ? 'max-w-[80%] text-right' : 'w-full text-left'
              )}>
                <div className={cn(
                  'px-5 py-4 rounded-xl text-sm font-medium leading-relaxed shadow-sm border',
                  message.role === 'assistant'
                    ? 'bg-white border-slate-100 text-slate-700 rounded-tl-none'
                    : 'bg-blue-600 border-blue-500 text-white rounded-tr-none'
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
                {message.role === 'assistant' && !message.id.startsWith('assistant-welcome-') && (
                  <div className="mt-1 px-2 flex items-center gap-2 text-xs">
                    <button
                      type="button"
                      onClick={() => void copyAssistantMessage(message.id, message.content)}
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-all duration-200 active:scale-95',
                        copiedMessageId === message.id
                          ? 'border-sky-300 bg-sky-50 text-sky-700'
                          : copyErrorMessageId === message.id
                            ? 'border-rose-300 bg-rose-50 text-rose-700'
                            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300',
                      )}
                    >
                      {copiedMessageId === message.id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      {copiedMessageId === message.id ? 'Copied' : copyErrorMessageId === message.id ? 'Copy failed' : 'Copy'}
                    </button>
                    <button
                      type="button"
                      disabled={!!feedbackByMessageId[message.id]?.submitting}
                      onClick={() =>
                        void submitFeedback(
                          message.id,
                          'like',
                          previousUserQueryForIndex(messageIndex),
                          message.content,
                          'helpful',
                        )
                      }
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-all duration-200 active:scale-95 disabled:opacity-60',
                        feedbackByMessageId[message.id]?.vote === 'like'
                          ? 'border-emerald-300 bg-emerald-50 text-emerald-700 shadow-[0_0_0_2px_rgba(16,185,129,0.12)]'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300',
                      )}
                    >
                      {feedbackByMessageId[message.id]?.submitting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ThumbsUp className="w-3.5 h-3.5" />
                      )}
                      {feedbackByMessageId[message.id]?.vote === 'like' ? 'Liked' : 'Like'}
                    </button>
                    <button
                      type="button"
                      disabled={!!feedbackByMessageId[message.id]?.submitting}
                      onClick={() =>
                        openDislikeModal(
                          message.id,
                          previousUserQueryForIndex(messageIndex),
                          message.content,
                        )
                      }
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-all duration-200 active:scale-95 disabled:opacity-60',
                        feedbackByMessageId[message.id]?.vote === 'dislike'
                          ? 'border-rose-300 bg-rose-50 text-rose-700 shadow-[0_0_0_2px_rgba(244,63,94,0.12)]'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300',
                      )}
                    >
                      {feedbackByMessageId[message.id]?.submitting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ThumbsDown className="w-3.5 h-3.5" />
                      )}
                      {feedbackByMessageId[message.id]?.vote === 'dislike' ? 'Disliked' : 'Dislike'}
                    </button>
                    {!!feedbackByMessageId[message.id]?.saved_at && !feedbackByMessageId[message.id]?.error && (
                      <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-emerald-700">
                        <Check className="w-3.5 h-3.5" /> Saved
                      </span>
                    )}
                    {!!feedbackByMessageId[message.id]?.error && (
                      <span className="text-rose-600">{feedbackByMessageId[message.id]?.error}</span>
                    )}
                  </div>
                )}
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
        <div className="px-5 sm:px-7 pt-3 pb-6 border-t border-sky-100 bg-sky-50/30">
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
              aria-label="Send message"
              className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-blue-600 text-white rounded-lg flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>

      {dislikeModal.open && (
        <div className="fixed inset-0 z-50 bg-slate-900/45 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="w-full max-w-xl rounded-2xl border border-sky-100 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h3 className="text-base font-bold text-slate-900">Tell us why this response was not good</h3>
              <button
                type="button"
                onClick={() => setDislikeModal({ open: false, messageId: '', query: '', response: '' })}
                title="Close dialog"
                aria-label="Close dialog"
                className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {DISLIKE_REASONS.map((r) => (
                <label key={r.code} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="dislike-reason"
                    checked={dislikeReasonCode === r.code}
                    onChange={() => setDislikeReasonCode(r.code)}
                  />
                  <span>{r.label}</span>
                </label>
              ))}
            </div>
            <textarea
              value={dislikeReasonText}
              onChange={(e) => setDislikeReasonText(e.target.value)}
              placeholder={dislikeReasonCode === 'other' ? 'Please write your reason...' : 'Optional additional details...'}
              className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm min-h-[90px]"
            />
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDislikeModal({ open: false, messageId: '', query: '', response: '' })}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void submitDislike()}
                className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100"
              >
                Submit feedback
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
