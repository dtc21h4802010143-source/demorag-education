import { FormEvent, useEffect, useMemo, useState } from 'react';
import ChatBubble from '../components/ChatBubble';
import { API_BASE, api, clearUserToken, getClientId, getUserToken, setUserToken } from '../lib/api';

type Session = { id: number; title: string; created_at: string };
type Message = { role: 'user' | 'assistant'; content: string };
type Quota = { limit: number; used: number; remaining: number };

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [authInfo, setAuthInfo] = useState('');
  const [userToken, setUserTokenState] = useState(getUserToken());

  const [authMode, setAuthMode] = useState<'login' | 'register' | 'forgot' | 'reset'>('login');
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerFullName, setRegisterFullName] = useState('');

  const [resetEmail, setResetEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const clientId = getClientId();
  const activeSession = useMemo(() => sessions.find((s) => s.id === sessionId), [sessions, sessionId]);
  const isLoggedIn = !!userToken;

  function handleAsyncError(error: unknown) {
    // Keep console clean in normal usage; still expose minimal info during development.
    if (!import.meta.env.DEV) return;
    const message = error instanceof Error ? error.message : String(error);
    console.warn(message);
  }

  async function loadQuota() {
    const { data } = await api.get<Quota>(`/chat/quota?client_id=${encodeURIComponent(clientId)}`);
    setQuota(data);
  }

  async function loadSessions() {
    const { data } = await api.get<Session[]>('/chat/sessions');
    setSessions(data);
  }

  async function loadMessages(id: number) {
    const { data } = await api.get<Message[]>(`/chat/sessions/${id}/messages`);
    setMessages(data);
  }

  useEffect(() => {
    loadSessions().catch(handleAsyncError);
    if (!isLoggedIn) {
      loadQuota().catch(handleAsyncError);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('token') || '';
    const emailParam = params.get('email') || '';

    if (tokenParam && emailParam) {
      setResetToken(tokenParam);
      setResetEmail(emailParam);
      setAuthMode('reset');
      setAuthInfo('Vui long nhap mat khau moi de hoan tat khoi phuc tai khoan.');
    }
  }, []);

  async function login(e: FormEvent) {
    e.preventDefault();
    setLoginError('');
    setAuthInfo('');
    try {
      const { data } = await api.post<{ access_token: string }>('/auth/user-login', { username, password });
      setUserToken(data.access_token);
      setUserTokenState(data.access_token);
      setQuota(null);
    } catch {
      setLoginError('Dang nhap that bai');
    }
  }

  async function register(e: FormEvent) {
    e.preventDefault();
    setLoginError('');
    setAuthInfo('');
    try {
      await api.post('/auth/register', {
        username: registerUsername,
        email: registerEmail,
        password: registerPassword,
        full_name: registerFullName || null,
      });

      setUsername(registerUsername);
      setPassword(registerPassword);
      setAuthMode('login');
      setAuthInfo('Tao tai khoan thanh cong. Ban co the dang nhap ngay bay gio.');
      setRegisterUsername('');
      setRegisterEmail('');
      setRegisterPassword('');
      setRegisterFullName('');
    } catch {
      setLoginError('Khong tao duoc tai khoan. Username hoac email co the da ton tai.');
    }
  }

  async function forgotPassword(e: FormEvent) {
    e.preventDefault();
    setLoginError('');
    setAuthInfo('');
    try {
      await api.post('/auth/password-reset-request', { email: resetEmail });
      setAuthInfo('Neu email ton tai trong he thong, link dat lai mat khau da duoc gui.');
      setAuthMode('login');
    } catch {
      setLoginError('Khong gui duoc yeu cau khoi phuc mat khau. Vui long thu lai.');
    }
  }

  async function confirmResetPassword(e: FormEvent) {
    e.preventDefault();
    setLoginError('');
    setAuthInfo('');
    try {
      const { data } = await api.post<{ access_token: string }>('/auth/password-reset-confirm', {
        token: resetToken,
        email: resetEmail,
        new_password: newPassword,
      });

      setUserToken(data.access_token);
      setUserTokenState(data.access_token);
      setQuota(null);
      setAuthMode('login');
      setAuthInfo('Dat lai mat khau thanh cong. Ban da duoc dang nhap.');
      setNewPassword('');

      window.history.replaceState({}, '', window.location.pathname);
    } catch {
      setLoginError('Token dat lai mat khau khong hop le hoac da het han.');
    }
  }

  function logout() {
    clearUserToken();
    setUserTokenState('');
    loadQuota().catch(handleAsyncError);
  }

  async function sendQuestion(e: FormEvent) {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const q = question.trim();
    setQuestion('');
    setIsLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: q }, { role: 'assistant', content: '' }]);

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (userToken) {
      headers.Authorization = `Bearer ${userToken}`;
    }

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ question: q, session_id: sessionId, client_id: clientId }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Chat failed' }));
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', content: err.detail || 'Chat failed' };
          return next;
        });
        if (!isLoggedIn) {
          loadQuota().catch(handleAsyncError);
        }
        return;
      }

      if (!response.body) {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', content: 'Khong nhan duoc du lieu tra loi.' };
          return next;
        });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          if (!event.startsWith('data: ')) continue;
          const payload = JSON.parse(event.replace('data: ', '')) as {
            type: 'meta' | 'token' | 'done';
            content?: string;
            session_id?: number;
            remaining_questions?: number;
          };

          if (payload.type === 'meta' && payload.session_id) {
            setSessionId(payload.session_id);
            loadSessions().catch(handleAsyncError);
            if (!isLoggedIn && typeof payload.remaining_questions === 'number' && quota) {
              setQuota({ ...quota, remaining: payload.remaining_questions, used: quota.limit - payload.remaining_questions });
            }
          }

          if (payload.type === 'token' && payload.content) {
            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              next[lastIndex] = {
                ...next[lastIndex],
                content: `${next[lastIndex].content}${payload.content}`,
              };
              return next;
            });
          }
        }
      }

      if (!isLoggedIn) {
        loadQuota().catch(handleAsyncError);
      }
    } catch (error) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: 'assistant',
          content: 'Khong the ket noi toi may chu. Vui long thu lai sau.',
        };
        return next;
      });
      handleAsyncError(error);
    } finally {
      setIsLoading(false);
    }
  }

  async function deleteCurrentSession() {
    if (!sessionId) return;
    await api.delete(`/chat/sessions/${sessionId}`);
    setSessionId(null);
    setMessages([]);
    await loadSessions();
  }

  async function clearAllHistory() {
    await api.delete('/chat/sessions');
    setSessionId(null);
    setMessages([]);
    await loadSessions();
  }

  return (
    <div className="grid gap-4 md:grid-cols-[280px_1fr]">
      <aside className="rounded-2xl bg-white/70 p-4 shadow-sm">
        <div className="mb-4 rounded-xl bg-surf p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-ink/70">Tai khoan chat</p>
          {isLoggedIn ? (
            <div className="mt-2 space-y-2">
              <p className="text-sm text-mint">Da dang nhap</p>
              <button onClick={logout} className="w-full rounded-lg bg-coral px-3 py-2 text-xs text-white">
                Dang xuat
              </button>
            </div>
          ) : (
            <div className="mt-2 space-y-2">
              <div className="grid grid-cols-3 gap-1 rounded-lg bg-white p-1">
                <button
                  className={`rounded-md px-2 py-1 text-[11px] ${authMode === 'login' ? 'bg-mint text-white' : 'bg-surf text-ink/70'}`}
                  onClick={() => {
                    setAuthMode('login');
                    setLoginError('');
                    setAuthInfo('');
                  }}
                >
                  Dang nhap
                </button>
                <button
                  className={`rounded-md px-2 py-1 text-[11px] ${authMode === 'register' ? 'bg-mint text-white' : 'bg-surf text-ink/70'}`}
                  onClick={() => {
                    setAuthMode('register');
                    setLoginError('');
                    setAuthInfo('');
                  }}
                >
                  Tao tk
                </button>
                <button
                  className={`rounded-md px-2 py-1 text-[11px] ${authMode === 'forgot' || authMode === 'reset' ? 'bg-mint text-white' : 'bg-surf text-ink/70'}`}
                  onClick={() => {
                    setAuthMode('forgot');
                    setLoginError('');
                    setAuthInfo('');
                  }}
                >
                  Quen pass
                </button>
              </div>

              {authMode === 'login' && (
                <form onSubmit={login} className="space-y-2">
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="username"
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="password"
                  />
                  <button className="w-full rounded-lg bg-mint px-3 py-2 text-xs text-white">Dang nhap de chat full</button>
                </form>
              )}

              {authMode === 'register' && (
                <form onSubmit={register} className="space-y-2">
                  <input
                    value={registerUsername}
                    onChange={(e) => setRegisterUsername(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="username moi"
                    required
                    minLength={3}
                  />
                  <input
                    type="email"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="email"
                    required
                  />
                  <input
                    type="password"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="password"
                    required
                    minLength={6}
                  />
                  <input
                    value={registerFullName}
                    onChange={(e) => setRegisterFullName(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="ho va ten (khong bat buoc)"
                  />
                  <button className="w-full rounded-lg bg-mint px-3 py-2 text-xs text-white">Tao tai khoan</button>
                </form>
              )}

              {authMode === 'forgot' && (
                <form onSubmit={forgotPassword} className="space-y-2">
                  <input
                    type="email"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="email de khoi phuc mat khau"
                    required
                  />
                  <button className="w-full rounded-lg bg-mint px-3 py-2 text-xs text-white">Gui link khoi phuc</button>
                </form>
              )}

              {authMode === 'reset' && (
                <form onSubmit={confirmResetPassword} className="space-y-2">
                  <input
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="email"
                    required
                  />
                  <input
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="reset token"
                    required
                  />
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full rounded-lg border border-ink/20 bg-white px-3 py-2 text-xs"
                    placeholder="mat khau moi"
                    required
                    minLength={6}
                  />
                  <button className="w-full rounded-lg bg-mint px-3 py-2 text-xs text-white">Dat lai mat khau</button>
                </form>
              )}

              {!!authInfo && <p className="text-xs text-emerald-700">{authInfo}</p>}
              {!!loginError && <p className="text-xs text-red-600">{loginError}</p>}
            </div>
          )}

          {!isLoggedIn && quota && (
            <p className="mt-2 text-xs text-ink/70">Khach: con {quota.remaining}/{quota.limit} cau hoi</p>
          )}
        </div>

        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Lich su chat</h2>
          <button
            className="rounded-lg bg-mint px-3 py-1 text-xs text-white"
            onClick={() => {
              setSessionId(null);
              setMessages([]);
            }}
          >
            New
          </button>
        </div>

        <div className="mb-3 flex gap-2">
          <button onClick={deleteCurrentSession} className="flex-1 rounded-lg bg-amber-600 px-3 py-1 text-xs text-white">
            Xoa phien
          </button>
          <button onClick={clearAllHistory} className="flex-1 rounded-lg bg-coral px-3 py-1 text-xs text-white">
            Xoa tat ca
          </button>
        </div>

        <div className="space-y-2">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setSessionId(s.id);
                loadMessages(s.id).catch(handleAsyncError);
              }}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm ${sessionId === s.id ? 'bg-mint text-white' : 'bg-surf'}`}
            >
              {s.title}
            </button>
          ))}
        </div>
      </aside>

      <section className="flex h-[75vh] flex-col rounded-2xl bg-white/70 p-4 shadow-sm">
        <div className="mb-4 border-b border-ink/10 pb-3">
          <h1 className="font-serif text-xl font-bold">{activeSession?.title || 'Hoi tro ly giao duc'}</h1>
        </div>

        <div className="flex-1 space-y-3 overflow-auto pr-1">
          {messages.length === 0 ? (
            <div className="rounded-xl bg-surf p-4 text-sm text-ink/70">Dang nhap de chat khong gioi han, khach duoc 5 cau hoi.</div>
          ) : (
            messages.map((msg, idx) => <ChatBubble key={idx} role={msg.role} content={msg.content} />)
          )}
        </div>

        <form onSubmit={sendQuestion} className="mt-4 flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Nhap cau hoi..."
            className="flex-1 rounded-xl border border-ink/20 bg-white px-4 py-3 text-sm outline-none focus:border-mint"
          />
          <button type="submit" disabled={isLoading} className="rounded-xl bg-mint px-5 py-3 text-sm font-medium text-white disabled:opacity-50">
            {isLoading ? 'Dang tra loi...' : 'Gui'}
          </button>
        </form>
      </section>
    </div>
  );
}
