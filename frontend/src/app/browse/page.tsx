"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, Empty, ErrorNote, Loading, MovieGrid, PageTitle, inputClass } from "@/components/ui";
import { useApi, type Genre, type MoviePage } from "@/lib/api";

const SIZE = 30;

export default function BrowsePage() {
  return (
    <Suspense fallback={<Loading />}>
      <Browse />
    </Suspense>
  );
}

function Browse() {
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const genres = useApi<Genre[]>("/genres");

  const page = Number(params.get("page") ?? 1);
  const query = new URLSearchParams(params);
  query.set("size", String(SIZE));
  const { data, error, loading } = useApi<MoviePage>(`/movies?${query}`);

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    router.push(`/browse?${next}`);
  }

  // Search as you type, debounced.
  useEffect(() => {
    if (q === (params.get("q") ?? "")) return;
    const timer = setTimeout(() => update({ q }), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const pages = data ? Math.ceil(data.total / SIZE) : 0;

  return (
    <div>
      <PageTitle subtitle={data ? `${data.total.toLocaleString()} movies` : undefined}>Browse</PageTitle>
      <div className="mb-6 grid gap-3 sm:grid-cols-[1fr_auto_auto_auto_auto]">
        <input
          className={inputClass}
          placeholder="Search titles…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className={inputClass} value={params.get("language") ?? ""} onChange={(e) => update({ language: e.target.value })}>
          <option value="">Telugu + Hindi</option>
          <option value="te">Telugu</option>
          <option value="hi">Hindi</option>
        </select>
        <select className={inputClass} value={params.get("genre_id") ?? ""} onChange={(e) => update({ genre_id: e.target.value })}>
          <option value="">All genres</option>
          {genres.data?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <input
          className={`${inputClass} sm:w-24`}
          type="number"
          placeholder="Year"
          value={params.get("year") ?? ""}
          onChange={(e) => update({ year: e.target.value.length === 4 || !e.target.value ? e.target.value : params.get("year") ?? "" })}
        />
        <select className={inputClass} value={params.get("sort") ?? "popularity"} onChange={(e) => update({ sort: e.target.value })}>
          <option value="popularity">Most popular</option>
          <option value="rating">Highest rated</option>
          <option value="release_date">Newest</option>
          <option value="title">A–Z</option>
        </select>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No movies match.</Empty> : data && <MovieGrid movies={data.items} />}

      {pages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-3">
          <Button variant="ghost" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
            ← Prev
          </Button>
          <span className="text-sm text-zinc-400">
            Page {page} of {pages}
          </span>
          <Button variant="ghost" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}
