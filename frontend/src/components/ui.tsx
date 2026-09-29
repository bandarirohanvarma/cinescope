"use client";

import Link from "next/link";
import { useState } from "react";

import { LANGUAGE_NAMES, type Movie, year } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function MovieCard({ movie, caption }: { movie: Movie; caption?: string }) {
  return (
    <Link
      href={`/movies/${movie.id}`}
      className="group block w-36 shrink-0 sm:w-40"
      title={movie.title}
    >
      <div className="aspect-[2/3] overflow-hidden rounded-xl bg-zinc-800 ring-1 ring-white/5 transition group-hover:ring-amber-400/60">
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center p-3 text-center text-sm text-zinc-500">
            {movie.title}
          </div>
        )}
      </div>
      <p className="mt-2 truncate text-sm font-medium text-zinc-100">{movie.title}</p>
      <p className="flex items-center gap-2 text-xs text-zinc-500">
        <span>{year(movie.release_date)}</span>
        {movie.original_language && <span>· {LANGUAGE_NAMES[movie.original_language] ?? movie.original_language}</span>}
        {movie.vote_average ? <span className="text-amber-400">★ {movie.vote_average.toFixed(1)}</span> : null}
      </p>
      {caption && <p className="truncate text-xs text-zinc-400">{caption}</p>}
    </Link>
  );
}

export function MovieRow({
  title,
  movies,
  captions,
  href,
}: {
  title: string;
  movies: Movie[];
  captions?: string[];
  href?: string;
}) {
  if (movies.length === 0) return null;
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        {href && (
          <Link href={href} className="text-sm text-amber-400 hover:underline">
            See all
          </Link>
        )}
      </div>
      <div className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:thin]">
        {movies.map((movie, i) => (
          <MovieCard key={movie.id} movie={movie} caption={captions?.[i]} />
        ))}
      </div>
    </section>
  );
}

export function MovieGrid({ movies }: { movies: Movie[] }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-x-4 gap-y-6">
      {movies.map((movie) => (
        <MovieCard key={movie.id} movie={movie} />
      ))}
    </div>
  );
}

/** Five stars, each clickable on its left (half) or right (full) side. */
export function StarRating({
  value,
  onChange,
  size = "text-2xl",
}: {
  value: number | null;
  onChange?: (rating: number) => void;
  size?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = hover ?? value ?? 0;
  return (
    <div className={`inline-flex ${size}`} onMouseLeave={() => setHover(null)}>
      {[1, 2, 3, 4, 5].map((star) => {
        const fill = shown >= star ? 100 : shown >= star - 0.5 ? 50 : 0;
        return (
          <span key={star} className="relative inline-block leading-none">
            <span className="text-zinc-700">★</span>
            <span
              className="absolute inset-0 overflow-hidden text-amber-400"
              style={{ width: `${fill}%` }}
            >
              ★
            </span>
            {onChange &&
              [star - 0.5, star].map((rating, half) => (
                <button
                  key={rating}
                  type="button"
                  aria-label={`${rating} stars`}
                  className={`absolute inset-y-0 w-1/2 cursor-pointer ${half ? "right-0" : "left-0"}`}
                  onMouseEnter={() => setHover(rating)}
                  onClick={() => onChange(rating)}
                />
              ))}
          </span>
        );
      })}
    </div>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const styles =
    variant === "primary"
      ? "bg-amber-400 text-zinc-950 hover:bg-amber-300"
      : "bg-white/5 text-zinc-100 ring-1 ring-white/10 hover:bg-white/10";
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export const inputClass =
  "w-full rounded-lg bg-zinc-900 px-3 py-2 text-sm text-zinc-100 ring-1 ring-white/10 placeholder:text-zinc-500 focus:outline-none focus:ring-amber-400";

export function PageTitle({ children, subtitle }: { children: React.ReactNode; subtitle?: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-3xl font-semibold tracking-tight">{children}</h1>
      {subtitle && <p className="mt-1 text-zinc-400">{subtitle}</p>}
    </header>
  );
}

export function Loading() {
  return <p className="py-12 text-center text-zinc-500">Loading…</p>;
}

export function ErrorNote({ message }: { message: string }) {
  return <p className="rounded-lg bg-rose-500/10 p-3 text-sm text-rose-300">{message}</p>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border border-dashed border-white/10 p-10 text-center text-zinc-400">{children}</div>;
}

/** Renders children only for signed-in users; otherwise a sign-in prompt. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user)
    return (
      <Empty>
        <Link href="/login" className="text-amber-400 hover:underline">
          Sign in
        </Link>{" "}
        to see this page.
      </Empty>
    );
  return <>{children}</>;
}
