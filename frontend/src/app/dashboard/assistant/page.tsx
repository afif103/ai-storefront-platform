"use client";

import { useEffect, useRef, useState } from "react";
import { RequireAuth } from "@/components/require-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { apiFetch } from "@/lib/api-client";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  conversation_id: string;
  reply: string;
  usage: {
    tokens_in: number;
    tokens_out: number;
    cost_usd: string;
  };
}

function AssistantContent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setError("");
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    const result = await apiFetch<ChatResponse>(
      "/api/v1/tenants/me/ai/chat",
      {
        method: "POST",
        body: JSON.stringify({ message: text }),
      }
    );

    setSending(false);

    if (result.ok) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.data.reply },
      ]);
    } else {
      const detail = result.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else {
        const parsed = typeof detail === "object" ? detail : JSON.parse(detail);
        const msg = parsed.message ?? detail;
        const type = parsed.type;
        if (type === "quota_exhausted") {
          setError("AI token quota exhausted for this month.");
        } else if (type === "rate_limited") {
          setError("Rate limit reached. Please wait a moment.");
        } else {
          setError(String(msg));
        }
      }
    }
  }

  return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 py-6">
        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {messages.length === 0 && (
            <div className="rounded-lg border bg-white p-8 text-center">
              <p className="text-gray-500">
                Ask me about your orders, donations, pledges, or products.
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "border bg-white text-gray-900"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-lg border bg-white px-4 py-3 text-sm text-gray-400">
                Thinking...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-3 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Input */}
        <form
          onSubmit={handleSend}
          className="flex gap-2 border-t bg-white px-4 py-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            maxLength={2000}
            disabled={sending}
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </main>
  );
}

export default function AssistantPage() {
  return (
    <RequireAuth>
      <DashboardShell>
        <AssistantContent />
      </DashboardShell>
    </RequireAuth>
  );
}
