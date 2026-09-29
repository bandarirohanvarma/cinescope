"use client";

import { Empty, ErrorNote, Loading, PageTitle, RequireAuth } from "@/components/ui";
import { LANGUAGE_NAMES, useApi, type Stats } from "@/lib/api";

export default function StatsPage() {
  return (
    <RequireAuth>
      <StatsView />
    </RequireAuth>
  );
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-zinc-900 p-5 ring-1 ring-white/5">
      <p className="text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-sm text-zinc-400">{label}</p>
    </div>
  );
}

function Bars({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <section className="rounded-xl bg-zinc-900 p-5 ring-1 ring-white/5">
      <h2 className="mb-4 font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-zinc-500">No data yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.label} className="grid grid-cols-[6rem_1fr_2rem] items-center gap-3 text-sm">
              <span className="truncate text-zinc-300">{row.label}</span>
              <span className="h-2.5 rounded-full bg-white/5">
                <span className="block h-full rounded-full bg-amber-400" style={{ width: `${(row.value / max) * 100}%` }} />
              </span>
              <span className="text-right tabular-nums text-zinc-400">{row.value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StatsView() {
  const { data, error } = useApi<Stats>("/me/stats");
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;
  if (data.diary_entries === 0) return <Empty>Log some movies in your diary to see your stats.</Empty>;

  const ratings = ["0.5", "1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0"].map((r) => ({
    label: `${r}★`,
    value: data.rating_distribution[r] ?? 0,
  }));

  return (
    <div className="space-y-6">
      <PageTitle>Your movie stats</PageTitle>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Movies watched" value={data.movies_watched} />
        <Tile label="Diary entries" value={data.diary_entries} />
        <Tile label="Hours watched" value={data.hours_watched} />
        <Tile label="Average rating" value={data.average_rating ? `${data.average_rating}★` : "—"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Bars title="Top genres" rows={data.top_genres.map((g) => ({ label: g.name, value: g.count }))} />
        <Bars
          title="Languages"
          rows={Object.entries(data.by_language).map(([lang, n]) => ({ label: LANGUAGE_NAMES[lang] ?? lang, value: n }))}
        />
        <Bars title="Watched per month" rows={data.by_month.map((m) => ({ label: m.month, value: m.count }))} />
        <Bars title="Your ratings" rows={ratings} />
      </div>
    </div>
  );
}
