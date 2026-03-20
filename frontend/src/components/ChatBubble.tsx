type Props = {
  role: 'user' | 'assistant';
  content: string;
};

export default function ChatBubble({ role, content }: Props) {
  const isUser = role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm md:max-w-[70%] ${
          isUser ? 'bg-mint text-white' : 'bg-white text-ink'
        }`}
      >
        {content}
      </div>
    </div>
  );
}
