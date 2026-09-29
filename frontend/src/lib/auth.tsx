"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, API_URL, getTokens, setTokens, type User } from "./api";

type AuthContextValue = {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const loadUser = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/users/me"));
    } catch {
      setTokens(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      let current: User | null = null;
      if (getTokens()) {
        try {
          current = await api<User>("/users/me");
        } catch {
          setTokens(null);
        }
      }
      if (active) {
        setUser(current);
        setReady(true);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
      });
      if (!response.ok) throw new Error("Incorrect email or password");
      setTokens(await response.json());
      await loadUser();
    },
    [loadUser],
  );

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const tokens = await api<{ access_token: string; refresh_token: string }>(
        "/auth/register",
        {
          method: "POST",
          body: JSON.stringify({ email, password, display_name: displayName }),
        },
      );
      setTokens(tokens);
      await loadUser();
    },
    [loadUser],
  );

  const logout = useCallback(() => {
    setTokens(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
