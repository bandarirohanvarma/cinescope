"use client";

import Link from "next/link";

import { OPEN_CINEBOT } from "@/components/chat-widget";
import { MovieRow } from "@/components/ui";
import { useApi, type MoviePage, type RecommendationRow } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user } = useAuth();
  const recs = useApi<RecommendationRow[]>(user ? "/recommendations" : null);
  const upcoming = useApi<MoviePage>("/movies/upcoming?size=20");
  const telugu = useApi<MoviePage>("/movies?language=te&size=20");
  const hindi = useApi<MoviePage>("/movies?language=hi&size=20");
  const topTelugu = useApi<MoviePage>("/movies?language=te&sort=rating&size=20");

  const hero = telugu.data?.items[0];

  return (
    <div className="space-y-10">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-500/20 via-zinc-900 to-zinc-950 p-8 ring-1 ring-white/5 sm:p-12">
        {hero?.poster_url && (
          <img
            src={hero.poster_url}
            alt=""
            className="pointer-events-none absolute -right-10 top-0 hidden h-full rotate-6 opacity-30 sm:block"
          />
        )}
        <div className="relative max-w-xl space-y-4">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-amber-400">
            Telugu · Hindi
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            {user ? `Welcome back, ${user.display_name}.` : "Your movies, your taste."}
          </h1>
          <p className="text-lg text-zinc-300">
            Log what you watch, get picks tuned to you, never miss a release, and ask CineBot
            anything.
          </p>
          <div className="flex flex-wrap gap-3">
            {user ? (
              <button
                onClick={() => window.dispatchEvent(new Event(OPEN_CINEBOT))}
                className="rounded-lg bg-amber-400 px-4 py-2 font-medium text-zinc-950"
              >
                Ask CineBot
              </button>
            ) : (
              <Link href="/register" className="rounded-lg bg-amber-400 px-4 py-2 font-medium text-zinc-950">
                Create free account
              </Link>
            )}
            <Link href="/browse" className="rounded-lg bg-white/10 px-4 py-2 font-medium">
              Browse movies
            </Link>
          </div>
        </div>
      </section>

      {recs.data?.map((row) => (
        <MovieRow
          key={row.title}
          title={row.title}
          movies={row.items.map((r) => r.movie)}
        />
      ))}
      {user && recs.data && recs.data[0]?.items.length > 0 && !recs.data[1] && (
        <p className="text-sm text-zinc-500">
          Rate a few movies you loved (4★+) to get &ldquo;Because you liked…&rdquo; picks.
        </p>
      )}
      <MovieRow title="Coming soon" movies={upcoming.data?.items ?? []} href="/upcoming" />
      <MovieRow title="Popular in Telugu" movies={telugu.data?.items ?? []} href="/browse?language=te" />
      <MovieRow title="Popular in Hindi" movies={hindi.data?.items ?? []} href="/browse?language=hi" />
      <MovieRow
        title="Top rated Telugu"
        movies={topTelugu.data?.items ?? []}
        href="/browse?language=te&sort=rating"
      />
    </div>
  );
}
