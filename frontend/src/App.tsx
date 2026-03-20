import { NavLink, Route, Routes } from 'react-router-dom';
import ChatPage from './pages/ChatPage.tsx';

export default function App() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_10%_10%,#fff1d6_0%,#f8f4eb_35%,#dff3f0_100%)] text-ink">
      <header className="border-b border-ink/10 bg-white/65 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div>
            <p className="font-serif text-2xl font-bold tracking-tight">Tro Ly Giao Duc</p>
            <p className="text-xs uppercase tracking-[0.2em] text-mint">LLM + RAG Assistant</p>
          </div>
          <nav className="flex gap-2 text-sm">
            <NavLink to="/" className={({ isActive }) => `rounded-full px-4 py-2 ${isActive ? 'bg-mint text-white' : 'bg-white/80'}`}>
              Chat
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 animate-rise">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/reset-password" element={<ChatPage />} />
        </Routes>
      </main>
    </div>
  );
}
