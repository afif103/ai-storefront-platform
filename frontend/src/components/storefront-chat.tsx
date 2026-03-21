"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api-client";
import { track } from "@/lib/analytics";

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

function getSessionId(): string {
  let id = localStorage.getItem("session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("session_id", id);
  }
  return id;
}

function parseError(status: number, detail: string): string {
  if (status === 429) return "Too many messages, try again in a few minutes.";
  if (status === 502) return "AI temporarily unavailable. Please try later.";
  try {
    const parsed = typeof detail === "object" ? detail : JSON.parse(detail);
    if (parsed.type === "quota_exhausted") return parsed.message ?? "AI quota exhausted for this store.";
    if (parsed.type === "rate_limited") return "Too many messages, try again in a few minutes.";
    return parsed.message ?? String(detail);
  } catch {
    return String(detail);
  }
}

export function StorefrontChat({
  slug,
  primaryColor,
}: {
  slug: string;
  primaryColor?: string;
}) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    track("chat_message_sent", { chars: text.length });
    setError("");
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    const sessionId = getSessionId();
    const result = await apiFetch<ChatResponse>(
      `/api/v1/storefront/${slug}/ai/chat`,
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, message: text }),
      },
    );

    setSending(false);

    if (result.ok) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.data.reply },
      ]);
    } else {
      setError(parseError(result.status, result.detail));
    }
  }

  const accent = primaryColor ?? "#2563eb";

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => {
            setOpen(true);
            track("chat_open", { path: window.location.pathname });
          }}
          className="fixed right-5 bottom-5 z-50 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition-transform hover:scale-105"
          style={{ backgroundColor: accent }}
          aria-label={t("openChat")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="h-6 w-6"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
            />
          </svg>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed right-5 bottom-5 z-50 flex h-[28rem] w-[22rem] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl sm:h-[32rem] sm:w-96">
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3 text-white"
            style={{ backgroundColor: accent }}
          >
            <span className="text-sm font-semibold">{t("title")}</span>
            <button
              onClick={() => setOpen(false)}
              className="rounded p-1 hover:bg-white/20"
              aria-label={t("closeChat")}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                className="h-4 w-4"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.length === 0 && !sending && (
              <p className="pt-6 text-center text-sm text-gray-400">
                {t("emptyPrompt")}
              </p>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "text-white"
                      : "border border-gray-200 bg-gray-50 text-gray-900"
                  }`}
                  style={msg.role === "user" ? { backgroundColor: accent } : undefined}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-400">
                  {t("thinking")}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="mx-4 mb-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          {/* Input */}
          <form
            onSubmit={handleSend}
            className="flex gap-2 border-t border-gray-200 px-3 py-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("inputPlaceholder")}
              maxLength={4000}
              disabled={sending}
              className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: accent }}
            >
              {t("send")}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
