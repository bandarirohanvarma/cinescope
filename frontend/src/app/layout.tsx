import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { ChatWidget } from "@/components/chat-widget";
import { Nav } from "@/components/nav";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CineScope",
  description: "Track, rate and discover Telugu and Hindi movies.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-zinc-950 text-zinc-100">
        <AuthProvider>
          <Nav />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
          <footer className="border-t border-white/5 px-4 py-6 text-center text-xs text-zinc-500">
            Movie data from TMDB. This product uses the TMDB API but is not endorsed or certified
            by TMDB. Summaries from Wikipedia (CC BY-SA).
          </footer>
          <ChatWidget />
        </AuthProvider>
      </body>
    </html>
  );
}
