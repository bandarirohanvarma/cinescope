"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, inputClass } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm py-10">
      <h1 className="mb-6 text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <form onSubmit={submit} className="space-y-3">
        {mode === "register" && (
          <input className={inputClass} placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
        )}
        <input className={inputClass} type="email" placeholder="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          className={inputClass}
          type="password"
          placeholder={mode === "register" ? "Password (8+ characters)" : "Password"}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          minLength={mode === "register" ? 8 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <ErrorNote message={error} />}
        <Button type="submit" disabled={busy} className="w-full">
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-zinc-400">
        {mode === "login" ? (
          <>
            New here?{" "}
            <Link href="/register" className="text-amber-400 hover:underline">
              Create an account
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link href="/login" className="text-amber-400 hover:underline">
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
