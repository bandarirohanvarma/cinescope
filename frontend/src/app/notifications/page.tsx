"use client";

import Link from "next/link";

import { Empty, Loading, PageTitle, RequireAuth } from "@/components/ui";
import { formatDate, useApi, type Reminder } from "@/lib/api";

export default function NotificationsPage() {
  return (
    <RequireAuth>
      <Notifications />
    </RequireAuth>
  );
}

function ReminderList({ items, empty, verb }: { items: Reminder[] | null; empty: string; verb: string }) {
  if (!items) return <Loading />;
  if (items.length === 0) return <Empty>{empty}</Empty>;
  return (
    <ul className="space-y-2">
      {items.map((r) => (
        <li key={r.id}>
          <Link href={`/movies/${r.movie.id}`} className="flex items-center gap-3 rounded-xl bg-zinc-900 p-3 ring-1 ring-white/5 hover:ring-amber-400/50">
            {r.movie.poster_url && <img src={r.movie.poster_url} alt="" className="w-10 rounded" />}
            <span className="flex-1">
              <span className="font-medium">{r.movie.title}</span>
              <span className="block text-sm text-zinc-400">
                {verb} {formatDate(r.movie.release_date)}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Notifications() {
  const sent = useApi<Reminder[]>("/me/notifications");
  const pending = useApi<Reminder[]>("/me/reminders");
  return (
    <div className="max-w-2xl space-y-8">
      <PageTitle>Notifications</PageTitle>
      <section className="space-y-3">
        <h2 className="font-semibold">Released</h2>
        <ReminderList items={sent.data} empty="No releases yet from your reminders." verb="Released" />
      </section>
      <section className="space-y-3">
        <h2 className="font-semibold">Upcoming reminders</h2>
        <ReminderList items={pending.data} empty="No reminders set. Tap “Remind me” on an upcoming movie." verb="Releases" />
      </section>
    </div>
  );
}
