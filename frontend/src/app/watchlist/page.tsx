"use client";

import { Empty, ErrorNote, Loading, MovieGrid, PageTitle, RequireAuth } from "@/components/ui";
import { useApi, type WatchlistItem } from "@/lib/api";

export default function WatchlistPage() {
  return (
    <RequireAuth>
      <Watchlist />
    </RequireAuth>
  );
}

function Watchlist() {
  const { data, error } = useApi<WatchlistItem[]>("/me/watchlist");
  return (
    <div>
      <PageTitle subtitle="Movies you want to watch. Logging a watch removes it from here.">Watchlist</PageTitle>
      {error && <ErrorNote message={error} />}
      {!data ? <Loading /> : data.length === 0 ? <Empty>Your watchlist is empty.</Empty> : <MovieGrid movies={data.map((w) => w.movie)} />}
    </div>
  );
}
