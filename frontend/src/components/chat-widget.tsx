"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Message = { role: "user" | "assistant"; content: string; tools?: string[] };

/** Dispatch this event (e.g. from a button) to open the chat window. */
export const OPEN_CINEBOT = "cinebot:open";

const SUGGESTIONS = [
  "What Telugu movies release this month?",
  "Recommend me something like Baahubali",
  "What have I rated highest?",
  "Who composed the music for RRR?",
];

const TOOL_LABELS: Record<string, string> = {
  search_movies: "searched catalog",
  get_movie: "read movie details",
  upcoming_movies: "checked releases",
  my_history: "read your diary",
  recommend: "ran recommender",
  web_search: "searched the web",
};

export function ChatWidget() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN_CINEBOT, show);
    return () => window.removeEventListener(OPEN_CINEBOT, show);
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking, open]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || thinking) return;
    const history: Message[] = [...messages, { role: "user", content }];
    setMessages(history);
    setInput("");
    setThinking(true);
    try {
      const reply = await api<{ answer: string; tools_used: string[] }>("/chat", {
        method: "POST",
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })) }),
      });
      setMessages([...history, { role: "assistant", content: reply.answer, tools: reply.tools_used }]);
    } catch (err) {
      setMessages([
        ...history,
        { role: "assistant", content: `Sorry, something went wrong: ${(err as Error).message}` },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-x-3 bottom-24 z-50 flex h-[min(38rem,calc(100vh-8rem))] flex-col overflow-hidden rounded-2xl bg-zinc-950 shadow-2xl ring-1 ring-white/10 sm:inset-x-auto sm:right-6 sm:w-[26rem]">
          <header className="flex items-center justify-between border-b border-white/5 bg-zinc-900 px-4 py-3">
            <div>
              <p className="font-semibold">CineBot</p>
              <p className="text-xs text-zinc-400">Telugu &amp; Hindi movie assistant</p>
            </div>
            <div className="flex items-center gap-3 text-sm">
              {messages.length > 0 && (
                <button className="text-zinc-500 hover:text-white" onClick={() => setMessages([])}>
                  Clear
                </button>
              )}
              <button className="text-lg text-zinc-400 hover:text-white" aria-label="Close chat" onClick={() => setOpen(false)}>
                ✕
              </button>
            </div>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {!user ? (
              <p className="text-sm text-zinc-400">
                <Link href="/login" className="text-amber-400 hover:underline" onClick={() => setOpen(false)}>
                  Sign in
                </Link>{" "}
                to chat with CineBot.
              </p>
            ) : (
              messages.length === 0 && (
                <div className="space-y-2">
                  <p className="text-sm text-zinc-400">Hi {user.display_name}! Ask me anything about movies.</p>
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="block w-full rounded-xl bg-zinc-900 p-3 text-left text-sm text-zinc-300 ring-1 ring-white/5 hover:ring-amber-400/50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                <div
                  className={`rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "max-w-[85%] whitespace-pre-wrap bg-amber-400 text-zinc-950"
                      : "w-full bg-zinc-900 text-zinc-100 ring-1 ring-white/5"
                  }`}
                >
                  {m.role === "user" ? m.content : <Answer text={m.content} />}
                  {m.tools && m.tools.length > 0 && (
                    <p className="mt-2 flex flex-wrap gap-1">
                      {[...new Set(m.tools)].map((t) => (
                        <span key={t} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-zinc-400">
                          {TOOL_LABELS[t] ?? t}
                        </span>
                      ))}
                    </p>
                  )}
                </div>
              </div>
            ))}
            {thinking && <p className="text-sm text-zinc-500">CineBot is thinking…</p>}
            <div ref={bottom} />
          </div>

          {user && (
            <form
              className="flex gap-2 border-t border-white/5 p-3"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <input
                className="w-full rounded-lg bg-zinc-900 px-3 py-2 text-sm ring-1 ring-white/10 placeholder:text-zinc-500 focus:outline-none focus:ring-amber-400"
                placeholder="Ask CineBot…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                autoFocus
              />
              <button
                type="submit"
                disabled={thinking || !input.trim()}
                className="rounded-lg bg-amber-400 px-3 text-sm font-medium text-zinc-950 disabled:opacity-50"
              >
                Send
              </button>
            </form>
          )}
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close CineBot" : "Open CineBot"}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-amber-400 text-2xl text-zinc-950 shadow-lg shadow-amber-500/20 transition hover:scale-105"
      >
        {open ? "✕" : "🎬"}
      </button>
    </>
  );
}

function Answer({ text }: { text: string }) {
  return (
    <div className="prose prose-sm prose-invert max-w-none prose-headings:mb-1 prose-headings:mt-3 prose-headings:text-amber-300 prose-p:my-1.5 prose-a:text-amber-400 prose-strong:text-white prose-ul:my-1.5 prose-li:my-0.5 prose-table:my-2 prose-table:text-xs prose-th:px-2 prose-td:px-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
