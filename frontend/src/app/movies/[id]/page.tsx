"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, Loading, MovieRow, StarRating, inputClass } from "@/components/ui";
import {
  api,
  formatDate,
  LANGUAGE_NAMES,
  useApi,
  type MovieDetail,
  type MovieState,
  type Recommendation,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function MoviePage() {
  const { id } = useParams<{ id: string }>();
  const { data: movie, error } = useApi<MovieDetail>(`/movies/${id}`);
  const similar = useApi<Recommendation[]>(`/movies/${id}/similar`);

  if (error) return <ErrorNote message={error} />;
  if (!movie) return <Loading />;

  const upcoming = movie.release_date !== null && new Date(movie.release_date) > new Date();

  return (
    <div className="space-y-10">
      <section className="relative -mx-4 -mt-8 overflow-hidden sm:mx-0 sm:rounded-2xl">
        {movie.backdrop_url && (
          <img src={movie.backdrop_url} alt="" className="absolute inset-0 h-full w-full object-cover opacity-25" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/70 to-transparent" />
        <div className="relative flex flex-col gap-6 p-6 sm:flex-row sm:p-10">
          {movie.poster_url && (
            <img src={movie.poster_url} alt="" className="w-40 shrink-0 self-start rounded-xl shadow-2xl ring-1 ring-white/10 sm:w-56" />
          )}
          <div className="min-w-0 space-y-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{movie.title}</h1>
              {movie.original_title && movie.original_title !== movie.title && (
                <p className="text-zinc-400">{movie.original_title}</p>
              )}
            </div>
            <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-300">
              <span>{formatDate(movie.release_date)}</span>
              {movie.original_language && <span>· {LANGUAGE_NAMES[movie.original_language] ?? movie.original_language}</span>}
              {movie.runtime_minutes ? <span>· {Math.floor(movie.runtime_minutes / 60)}h {movie.runtime_minutes % 60}m</span> : null}
              {movie.vote_average ? (
                <span className="text-amber-400">
                  · ★ {movie.vote_average.toFixed(1)} <span className="text-zinc-500">({movie.vote_count} votes)</span>
                </span>
              ) : null}
              {upcoming && <span className="rounded bg-amber-400/15 px-2 text-amber-300">Upcoming</span>}
            </p>
            <div className="flex flex-wrap gap-2">
              {movie.genres.map((g) => (
                <Link key={g.id} href={`/browse?genre_id=${g.id}`} className="rounded-full bg-white/5 px-3 py-1 text-xs ring-1 ring-white/10 hover:bg-white/10">
                  {g.name}
                </Link>
              ))}
            </div>
            {movie.tagline && <p className="italic text-zinc-400">&ldquo;{movie.tagline}&rdquo;</p>}
            {movie.overview && <p className="max-w-3xl leading-relaxed text-zinc-200">{movie.overview}</p>}
            <Actions movieId={movie.id} upcoming={upcoming} />
          </div>
        </div>
      </section>

      {movie.wikipedia_summary && (
        <section className="max-w-3xl space-y-2">
          <h2 className="text-lg font-semibold">From Wikipedia</h2>
          <p className="leading-relaxed text-zinc-300">{movie.wikipedia_summary}</p>
          {movie.wikipedia_url && (
            <a href={movie.wikipedia_url} target="_blank" rel="noreferrer" className="text-sm text-amber-400 hover:underline">
              Read more on Wikipedia →
            </a>
          )}
        </section>
      )}

      <MovieRow title="More like this" movies={similar.data?.map((s) => s.movie) ?? []} />
    </div>
  );
}

function Actions({ movieId, upcoming }: { movieId: number; upcoming: boolean }) {
  const { user } = useAuth();
  const state = useApi<MovieState>(user ? `/me/movies/${movieId}` : null);
  const [logging, setLogging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user)
    return (
      <p className="text-sm text-zinc-400">
        <Link href="/login" className="text-amber-400 hover:underline">
          Sign in
        </Link>{" "}
        to rate, log, save or get a reminder.
      </p>
    );
  const s = state.data;
  if (!s) return null;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      state.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {!upcoming && (
        <div className="flex items-center gap-3">
          <StarRating
            value={s.rating}
            onChange={(rating) =>
              run(() => api(`/me/ratings/${movieId}`, { method: "PUT", body: JSON.stringify({ rating }) }))
            }
          />
          {s.rating && (
            <button className="text-xs text-zinc-500 hover:text-white" onClick={() => run(() => api(`/me/ratings/${movieId}`, { method: "DELETE" }))}>
              clear
            </button>
          )}
          {s.times_watched > 0 && <span className="text-xs text-zinc-400">Watched {s.times_watched}×</span>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {!upcoming && (
          <Button onClick={() => setLogging((v) => !v)} disabled={busy}>
            + Log a watch
          </Button>
        )}
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => run(() => api(`/me/watchlist/${movieId}`, { method: s.in_watchlist ? "DELETE" : "PUT" }))}
        >
          {s.in_watchlist ? "✓ In watchlist" : "+ Watchlist"}
        </Button>
        {upcoming && (
          <Button
            variant={s.reminder ? "ghost" : "primary"}
            disabled={busy}
            onClick={() => run(() => api(`/me/reminders/${movieId}`, { method: s.reminder ? "DELETE" : "PUT" }))}
          >
            {s.reminder ? "🔔 Reminder set" : "🔔 Remind me"}
          </Button>
        )}
      </div>
      {logging && (
        <LogForm
          movieId={movieId}
          initialRating={s.rating}
          onDone={() => {
            setLogging(false);
            state.reload();
          }}
        />
      )}
      {error && <ErrorNote message={error} />}
    </div>
  );
}

function LogForm({ movieId, initialRating, onDone }: { movieId: number; initialRating: number | null; onDone: () => void }) {
  const [watchedOn, setWatchedOn] = useState(new Date().toISOString().slice(0, 10));
  const [rating, setRating] = useState<number | null>(initialRating);
  const [review, setReview] = useState("");
  const [rewatch, setRewatch] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/me/diary", {
        method: "POST",
        body: JSON.stringify({ movie_id: movieId, watched_on: watchedOn, rating, review: review || null, is_rewatch: rewatch }),
      });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-lg space-y-3 rounded-xl bg-zinc-900/80 p-4 ring-1 ring-white/10">
      <div className="flex flex-wrap items-center gap-4">
        <label className="text-sm text-zinc-400">
          Watched on{" "}
          <input type="date" className={`${inputClass} mt-1`} value={watchedOn} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setWatchedOn(e.target.value)} required />
        </label>
        <div className="text-sm text-zinc-400">
          Rating
          <div>
            <StarRating value={rating} onChange={setRating} />
          </div>
        </div>
      </div>
      <textarea className={inputClass} rows={3} placeholder="Your thoughts (optional)" value={review} onChange={(e) => setReview(e.target.value)} />
      <label className="flex items-center gap-2 text-sm text-zinc-400">
        <input type="checkbox" checked={rewatch} onChange={(e) => setRewatch(e.target.checked)} /> Rewatch
      </label>
      {error && <ErrorNote message={error} />}
      <Button type="submit">Save to diary</Button>
    </form>
  );
}
