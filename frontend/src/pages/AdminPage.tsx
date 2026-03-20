import { FormEvent, useEffect, useState } from 'react';
import { api, getAdminToken, setAdminToken } from '../lib/api';

type Dashboard = { sessions: number; messages: number; documents: number; chunks: number };
type ChatLog = { session_id: number; session_title: string; role: string; content: string; created_at: string };

type Config = {
  llm_provider: string;
  openai_model: string;
  rag_top_k: number;
  rag_temperature: number;
  rag_max_output_tokens: number;
};

export default function AdminPage() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [logs, setLogs] = useState<ChatLog[]>([]);
  const [config, setConfig] = useState<Config | null>(null);

  const token = getAdminToken();

  async function login(e: FormEvent) {
    e.preventDefault();
    const { data } = await api.post<{ access_token: string }>('/auth/admin-login', { username, password });
    setAdminToken(data.access_token);
    window.location.reload();
  }

  async function loadAdminData() {
    const headers = { Authorization: `Bearer ${getAdminToken()}` };
    const [d, l, c] = await Promise.all([
      api.get<Dashboard>('/admin/dashboard', { headers }),
      api.get<ChatLog[]>('/admin/chat-logs', { headers }),
      api.get<Config>('/admin/config', { headers }),
    ]);

    setDashboard(d.data);
    setLogs(l.data);
    setConfig(c.data);
  }

  useEffect(() => {
    if (token) {
      loadAdminData().catch(console.error);
    }
  }, [token]);

  async function saveConfig() {
    if (!config) return;
    await api.put('/admin/config', config, {
      headers: { Authorization: `Bearer ${getAdminToken()}` },
    });
    await loadAdminData();
  }

  if (!token) {
    return (
      <section className="mx-auto max-w-md rounded-2xl bg-white/75 p-6 shadow-sm">
        <h2 className="mb-4 font-serif text-2xl font-bold">Admin Login</h2>
        <form onSubmit={login} className="space-y-3">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
            className="w-full rounded-xl border border-ink/20 bg-white px-4 py-3 text-sm"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="Password"
            className="w-full rounded-xl border border-ink/20 bg-white px-4 py-3 text-sm"
          />
          <button className="w-full rounded-xl bg-coral px-4 py-3 text-sm font-semibold text-white">Dang nhap</button>
        </form>
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Chat Sessions" value={dashboard?.sessions ?? 0} />
        <StatCard title="Messages" value={dashboard?.messages ?? 0} />
        <StatCard title="Documents" value={dashboard?.documents ?? 0} />
        <StatCard title="Chunks" value={dashboard?.chunks ?? 0} />
      </section>

      <section className="rounded-2xl bg-white/70 p-4 shadow-sm">
        <h3 className="mb-3 font-semibold">Cau hinh Model</h3>
        {config && (
          <div className="grid gap-3 md:grid-cols-2">
            <input
              className="rounded-xl border border-ink/20 bg-white p-3 text-sm"
              value={config.llm_provider}
              onChange={(e) => setConfig({ ...config, llm_provider: e.target.value })}
            />
            <input
              className="rounded-xl border border-ink/20 bg-white p-3 text-sm"
              value={config.openai_model}
              onChange={(e) => setConfig({ ...config, openai_model: e.target.value })}
            />
            <input
              type="number"
              className="rounded-xl border border-ink/20 bg-white p-3 text-sm"
              value={config.rag_top_k}
              onChange={(e) => setConfig({ ...config, rag_top_k: Number(e.target.value) })}
            />
            <input
              type="number"
              step="0.1"
              className="rounded-xl border border-ink/20 bg-white p-3 text-sm"
              value={config.rag_temperature}
              onChange={(e) => setConfig({ ...config, rag_temperature: Number(e.target.value) })}
            />
            <input
              type="number"
              className="rounded-xl border border-ink/20 bg-white p-3 text-sm md:col-span-2"
              value={config.rag_max_output_tokens}
              onChange={(e) => setConfig({ ...config, rag_max_output_tokens: Number(e.target.value) })}
            />
            <button className="rounded-xl bg-mint px-4 py-3 text-sm font-semibold text-white md:col-span-2" onClick={saveConfig}>
              Luu cau hinh
            </button>
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-white/70 p-4 shadow-sm">
        <h3 className="mb-3 font-semibold">Chat Logs</h3>
        <div className="max-h-[40vh] space-y-2 overflow-auto">
          {logs.map((log, idx) => (
            <div key={idx} className="rounded-xl bg-surf p-3 text-sm">
              <p className="text-xs text-ink/70">Session #{log.session_id} | {log.session_title}</p>
              <p className="mb-1 mt-1 font-semibold">{log.role}</p>
              <p className="line-clamp-3 text-ink/90">{log.content}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
      <p className="text-xs uppercase tracking-[0.16em] text-ink/70">{title}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
    </div>
  );
}
