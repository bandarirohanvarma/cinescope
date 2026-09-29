"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApi, type Reminder } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/browse", label: "Browse" },
  { href: "/upcoming", label: "Upcoming" },
  { href: "/diary", label: "Diary" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/stats", label: "Stats" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { data: notifications } = useApi<Reminder[]>(user ? "/me/notifications" : null);

  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-zinc-950/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="shrink-0 text-lg font-bold tracking-tight">
          Cine<span className="text-amber-400">Scope</span>
        </Link>
        <nav className="flex min-w-0 flex-1 gap-1 overflow-x-auto text-sm">
          {LINKS.map(({ href, label }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`shrink-0 rounded-md px-3 py-1.5 transition ${
                  active ? "bg-white/10 text-white" : "text-zinc-400 hover:text-white"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        {user ? (
          <div className="flex shrink-0 items-center gap-3 text-sm">
            <Link href="/notifications" className="relative text-zinc-400 hover:text-white" aria-label="Notifications">
              🔔
              {notifications && notifications.length > 0 && (
                <span className="absolute -right-2 -top-1 rounded-full bg-amber-400 px-1.5 text-[10px] font-bold text-zinc-950">
                  {notifications.length}
                </span>
              )}
            </Link>
            <span className="hidden text-zinc-300 sm:inline">{user.display_name}</span>
            <button onClick={logout} className="text-zinc-500 hover:text-white">
              Sign out
            </button>
          </div>
        ) : (
          <Link href="/login" className="shrink-0 rounded-lg bg-amber-400 px-3 py-1.5 text-sm font-medium text-zinc-950">
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}
