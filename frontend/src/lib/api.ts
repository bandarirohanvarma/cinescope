"use client";

import { useCallback, useEffect, useState } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKENS_KEY = "cinescope.tokens";

// ---- Types (mirror the FastAPI schemas) ----

export type Genre = { id: number; name: string };

export type Movie = {
  id: number;
  title: string;
  original_title: string | null;
  original_language: string | null;
  release_date: string | null;
  vote_average: number | null;
  poster_url: string | null;
  genres: Genre[];
};

export type MovieDetail = Movie & {
  overview: string | null;
  tagline: string | null;
  runtime_minutes: number | null;
  status: string | null;
  vote_count: number | null;
  backdrop_url: string | null;
  wikipedia_summary: string | null;
  wikipedia_url: string | null;
};

export type MoviePage = { items: Movie[]; total: number; page: number; size: number };
export type Recommendation = { movie: Movie; score: number; reason: string };
export type RecommendationRow = { title: string; items: Recommendation[] };
export type MovieState = {
  rating: number | null;
  in_watchlist: boolean;
  reminder: boolean;
  times_watched: number;
};
export type DiaryEntry = {
  id: number;
  watched_on: string;
  rating: number | null;
  review: string | null;
  tags: string[];
  is_rewatch: boolean;
  movie: Movie;
};
export type WatchlistItem = { added_at: string; movie: Movie };
export type Reminder = {
  id: number;
  remind_at: string;
  status: string;
  sent_at: string | null;
  movie: Movie;
};
export type User = {
  id: string;
  email: string;
  display_name: string;
  preferences: { region: string; languages: string[]; favorite_genre_ids: number[] };
};
export type Stats = {
  movies_watched: number;
  diary_entries: number;
  hours_watched: number;
  average_rating: number | null;
  top_genres: { name: string; count: number }[];
  by_language: Record<string, number>;
  by_month: { month: string; count: number }[];
  rating_distribution: Record<string, number>;
};

type Tokens = { access_token: string; refresh_token: string };

// ---- Tokens (kept in localStorage for this learning project) ----

export function getTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(TOKENS_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(tokens: Tokens | null) {
  try {
    if (tokens) localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
    else localStorage.removeItem(TOKENS_KEY);
  } catch {
    // storage unavailable (private mode); session won't persist
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function refreshTokens(): Promise<boolean> {
  const tokens = getTokens();
  if (!tokens) return false;
  const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!response.ok) {
    setTokens(null);
    return false;
  }
  setTokens(await response.json());
  return true;
}

/** Call the API. Adds the bearer token and retries once after refreshing it. */
export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const tokens = getTokens();
  const headers = new Headers(init.headers);
  if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);
  if (init.body && typeof init.body === "string") headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (response.status === 401 && tokens && retry && (await refreshTokens())) {
    return api<T>(path, init, false);
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body
    }
    throw new ApiError(response.status, message);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Fetch on mount and whenever `path` changes. Pass null to skip. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const key = `${path}#${version}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api<T>(path)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err: Error) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoadedKey(key));
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const loading = path !== null && loadedKey !== key;
  return { data: path === null ? null : data, error, loading, reload };
}

export const LANGUAGE_NAMES: Record<string, string> = { te: "Telugu", hi: "Hindi" };

export function year(date: string | null) {
  return date ? date.slice(0, 4) : "—";
}

export function formatDate(date: string | null) {
  if (!date) return "TBA";
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
