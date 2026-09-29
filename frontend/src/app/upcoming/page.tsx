"use client";

import { useState } from "react";

import { Button, ErrorNote, Loading, MovieCard, PageTitle } from "@/components/ui";
import { useApi, type MoviePage } from "@/lib/api";

const SIZE = 50;

export default function UpcomingPage() {
  const [language, setLanguage] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading } = useApi<MoviePage>(
    `/movies/upcoming?size=${SIZE}&page=${page}${language ? `&language=${language}` : ""}`,
  );

  const byMonth = new Map<string, MoviePage["items"]>();
  for (const movie of data?.items ?? []) {
    const month = movie.release_date
      ? new Date(`${movie.release_date}T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" })
      : "Date TBA";
    byMonth.set(month, [...(byMonth.get(month) ?? []), movie]);
  }

  return (
    <div>
      <PageTitle subtitle="Open a movie and tap “Remind me” to get notified on release day.">
        Coming soon
      </PageTitle>
      <div className="mb-6 flex gap-2">
        {[
          ["", "All"],
          ["te", "Telugu"],
          ["hi", "Hindi"],
        ].map(([value, label]) => (
          <Button
            key={value}
            variant={language === value ? "primary" : "ghost"}
            onClick={() => {
              setLanguage(value);
              setPage(1);
            }}
          >
            {label}
          </Button>
        ))}
      </div>
      {error && <ErrorNote message={error} />}
      {loading && !data && <Loading />}
      <div className="space-y-10">
        {[...byMonth].map(([month, movies]) => (
          <section key={month}>
            <h2 className="mb-4 text-xl font-semibold text-amber-400">{month}</h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-x-4 gap-y-6">
              {movies.map((movie) => (
                <MovieCard
                  key={movie.id}
                  movie={movie}
                  caption={movie.release_date ? new Date(`${movie.release_date}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : undefined}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
      {data && data.total > page * SIZE && (
        <div className="mt-8 text-center">
          <Button variant="ghost" onClick={() => setPage(page + 1)}>
            Later releases →
          </Button>
        </div>
      )}
    </div>
  );
}
