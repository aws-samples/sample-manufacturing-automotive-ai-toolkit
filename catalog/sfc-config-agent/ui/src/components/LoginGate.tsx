/**
 * LoginGate — wraps the entire app.
 *
 * Behaviour:
 *  1. On mount: if the URL contains ?code=… (Cognito redirect-back),
 *     exchange the code for tokens via handleCallback(), then navigate to "/".
 *  2. If a valid token is already in sessionStorage, render children immediately.
 *  3. Otherwise render a centred sign-in card (dark theme, matches index.css design system).
 */

import { useEffect, useState } from "react";
import { login, handleCallback, isAuthenticated } from "../auth";

interface Props {
  children: React.ReactNode;
}

export default function LoginGate({ children }: Props) {
  // "checking"  — resolving the callback / verifying stored token
  // "authed"    — valid token present, render children
  // "unauthed"  — no valid token, show sign-in card
  const [state, setState] = useState<"checking" | "authed" | "unauthed">("checking");

  useEffect(() => {
    (async () => {
      // 1. Cognito redirect-back with ?code=
      const hasCode = new URL(window.location.href).searchParams.has("code");
      if (hasCode) {
        const ok = await handleCallback();
        if (ok) {
          setState("authed");
          return;
        }
        // Exchange failed — fall through to sign-in card
      }

      // 2. Already authenticated?
      if (isAuthenticated()) {
        setState("authed");
        return;
      }

      setState("unauthed");
    })();
  }, []);

  if (state === "checking") {
    // Minimal full-screen spinner while resolving
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0d1117]">
        <span className="spinner w-6 h-6 border-2 border-sky-400 border-t-transparent" />
      </div>
    );
  }

  if (state === "authed") {
    return <>{children}</>;
  }

  // ── Sign-in card ────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#0d1117] px-4">
      {/* Logo / wordmark */}
      <div className="flex items-center gap-2.5 mb-8 select-none">
        <svg
          viewBox="0 0 24 24"
          className="w-9 h-9 text-sky-400 shrink-0"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="2,20 9,7 13,13 16,9 22,20" />
          <polyline points="14.3,11 16,9 17.7,11.4" />
        </svg>
        <span className="font-mono text-sky-400 font-semibold text-base tracking-widest uppercase">
          SFC Control Plane
        </span>
      </div>

      {/* Card */}
      <div className="card w-full max-w-sm flex flex-col items-center gap-5 py-8 px-6">
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-slate-200 font-medium text-base">Sign in to continue</p>
          <p className="text-slate-500 text-sm">
            Authentication is required to access the Control Plane.
          </p>
        </div>

        <button
          className="btn btn-primary w-full justify-center mt-1"
          onClick={() => void login()}
        >
          {/* Lock icon */}
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          Sign in with Cognito
        </button>
      </div>
    </div>
  );
}
