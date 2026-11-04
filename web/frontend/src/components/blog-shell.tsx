import Link from "next/link";
import type { ReactNode } from "react";

// Shared chrome (nav + footer) for the blog routes so they match the marketing site
// without importing the client-only homepage. Server component — no interactivity.
export function BlogShell({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-white text-slate-900 flex flex-col">
      <nav className="border-b border-slate-200 px-6 py-4 flex items-center justify-between max-w-6xl mx-auto w-full">
        <Link href="/" className="inline-flex items-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-wordmark.png" alt="Doppelganger Labs" className="h-8 w-auto" />
        </Link>
        <div className="flex items-center gap-6 text-sm font-medium">
          <Link href="/research" className="text-slate-600 hover:text-slate-900">Research</Link>
          <Link href="/blog" className="text-slate-600 hover:text-slate-900">Blog</Link>
          <Link href="/biases" className="text-slate-600 hover:text-slate-900">Biases</Link>
          <Link href="/sample-size-calculator" className="text-slate-600 hover:text-slate-900">Calculator</Link>
          <Link href="/security" className="text-slate-600 hover:text-slate-900">Security</Link>
          <Link href="/#login" className="text-blue-700 hover:text-blue-800">Sign in →</Link>
        </div>
      </nav>

      <div className="flex-1">{children}</div>

      <footer className="border-t border-slate-200 text-slate-500 text-sm py-8 mt-16">
        <div className="max-w-3xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>© {new Date().getFullYear()} Doppelganger · A survey pretesting tool</span>
          <a
            href="mailto:hello@doppelgangerlabs.com"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            hello@doppelgangerlabs.com
          </a>
        </div>
      </footer>
    </main>
  );
}
