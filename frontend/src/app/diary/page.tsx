"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Empty, ErrorNote, Loading, PageTitle, RequireAuth, StarRating, inputClass } from "@/components/ui";
import { api, formatDate, useApi, type DiaryEntry } from "@/lib/api";

export default function DiaryPage() {
  return (
    <RequireAuth>
      <Diary />
    </RequireAuth>
  );
}

function Diary() {
  const { data, error, reload } = useApi<DiaryEntry[]>("/me/diary");

  return (
    <div>
      <PageTitle subtitle="Every movie you've watched. Log new ones from a movie's page.">Diary</PageTitle>
      {error && <ErrorNote message={error} />}
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty>
          Nothing logged yet. Find a movie in{" "}
          <Link href="/browse" className="text-amber-400 hover:underline">
            Browse
          </Link>{" "}
          and tap &ldquo;Log a watch&rdquo;.
        </Empty>
      ) : (
        <ul className="divide-y divide-white/5">
          {data.map((entry) => (
            <Entry key={entry.id} entry={entry} onChange={reload} />
          ))}
        </ul>
      )}
    </div>
  );
}

function Entry({ entry, onChange }: { entry: DiaryEntry; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(entry.rating);
  const [review, setReview] = useState(entry.review ?? "");

  async function save() {
    await api(`/me/diary/${entry.id}`, { method: "PATCH", body: JSON.stringify({ rating, review: review || null }) });
    setEditing(false);
    onChange();
  }

  async function remove() {
    if (!confirm(`Delete this diary entry for ${entry.movie.title}?`)) return;
    await api(`/me/diary/${entry.id}`, { method: "DELETE" });
    onChange();
  }

  return (
    <li className="flex gap-4 py-4">
      <div className="w-20 shrink-0 text-center">
        <p className="text-2xl font-semibold">{new Date(`${entry.watched_on}T00:00:00`).getDate()}</p>
        <p className="text-xs uppercase text-zinc-500">
          {new Date(`${entry.watched_on}T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
        </p>
      </div>
      <Link href={`/movies/${entry.movie.id}`} className="shrink-0">
        {entry.movie.poster_url ? (
          <img src={entry.movie.poster_url} alt="" className="w-14 rounded-md" />
        ) : (
          <div className="h-20 w-14 rounded-md bg-zinc-800" />
        )}
      </Link>
      <div className="min-w-0 flex-1 space-y-1">
        <Link href={`/movies/${entry.movie.id}`} className="font-medium hover:text-amber-400">
          {entry.movie.title}
        </Link>
        {entry.is_rewatch && <span className="ml-2 text-xs text-zinc-500">↻ rewatch</span>}
        {editing ? (
          <div className="space-y-2">
            <StarRating value={rating} onChange={setRating} size="text-xl" />
            <textarea className={inputClass} rows={2} value={review} onChange={(e) => setReview(e.target.value)} />
            <div className="flex gap-2">
              <Button onClick={save}>Save</Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <>
            {entry.rating !== null && <StarRating value={entry.rating} size="text-base" />}
            {entry.review && <p className="text-sm text-zinc-300">{entry.review}</p>}
            <p className="space-x-3 text-xs text-zinc-500">
              <span>{formatDate(entry.watched_on)}</span>
              <button className="hover:text-white" onClick={() => setEditing(true)}>
                Edit
              </button>
              <button className="hover:text-rose-400" onClick={remove}>
                Delete
              </button>
            </p>
          </>
        )}
      </div>
    </li>
  );
}
