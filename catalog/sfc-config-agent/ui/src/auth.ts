/**
 * auth.ts — Cognito OAuth2 PKCE helpers (zero npm dependencies)
 *
 * Environment variables (set in .env.local):
 *   VITE_COGNITO_DOMAIN      e.g. https://sfc-cp-123456789012-us-east-1.auth.us-east-1.amazoncognito.com
 *   VITE_COGNITO_CLIENT_ID   e.g. 3abc1234xyz…
 *   VITE_COGNITO_REDIRECT_URI  e.g. http://localhost:5173/  (must match Cognito app client)
 *
 * Token storage: sessionStorage (cleared when the tab is closed).
 */

const _env = (import.meta as unknown as { env: Record<string, string> }).env;

const DOMAIN       = _env.VITE_COGNITO_DOMAIN ?? "";
const CLIENT_ID    = _env.VITE_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI = _env.VITE_COGNITO_REDIRECT_URI ?? window.location.origin + "/";

const STORAGE_ID_TOKEN    = "sfc_id_token";
const STORAGE_ACCESS_TOKEN = "sfc_access_token";
const STORAGE_EXPIRES_AT  = "sfc_expires_at";
const STORAGE_PKCE_VERIFIER = "sfc_pkce_verifier";

// ── PKCE helpers ──────────────────────────────────────────────────────────────

async function _generateVerifier(): Promise<string> {
  const array = new Uint8Array(48);
  crypto.getRandomValues(array);
  return _base64url(array);
}

async function _deriveChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return _base64url(new Uint8Array(digest));
}

function _base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

function _randomState(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return _base64url(array);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Redirect the browser to the Cognito Hosted UI (PKCE authorization request).
 * Stores the code_verifier in sessionStorage so handleCallback() can use it.
 */
export async function login(): Promise<void> {
  const verifier   = await _generateVerifier();
  const challenge  = await _deriveChallenge(verifier);
  const state      = _randomState();

  sessionStorage.setItem(STORAGE_PKCE_VERIFIER, verifier);
  sessionStorage.setItem("sfc_pkce_state", state);

  const params = new URLSearchParams({
    response_type: "code",
    client_id:     CLIENT_ID,
    redirect_uri:  REDIRECT_URI,
    scope:         "openid email profile",
    code_challenge_method: "S256",
    code_challenge: challenge,
    state,
  });

  window.location.href = `${DOMAIN}/oauth2/authorize?${params}`;
}

/**
 * Exchange the authorization code (from the URL ?code= param) for tokens.
 * Call this on the redirect-back page; it clears the code from the URL
 * and stores tokens in sessionStorage.
 * Returns true if a code was present and exchanged, false otherwise.
 */
export async function handleCallback(): Promise<boolean> {
  const url    = new URL(window.location.href);
  const code   = url.searchParams.get("code");
  const state  = url.searchParams.get("state");

  if (!code) return false;

  // Optional: validate state to guard against CSRF
  const storedState = sessionStorage.getItem("sfc_pkce_state");
  if (storedState && state !== storedState) {
    console.error("OAuth state mismatch — possible CSRF");
    return false;
  }

  const verifier = sessionStorage.getItem(STORAGE_PKCE_VERIFIER);
  if (!verifier) {
    console.error("Missing PKCE verifier — cannot exchange code");
    return false;
  }

  const body = new URLSearchParams({
    grant_type:    "authorization_code",
    client_id:     CLIENT_ID,
    redirect_uri:  REDIRECT_URI,
    code,
    code_verifier: verifier,
  });

  const resp = await fetch(`${DOMAIN}/oauth2/token`, {
    method:  "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body:    body.toString(),
  });

  if (!resp.ok) {
    console.error("Token exchange failed", await resp.text());
    return false;
  }

  const tokens = await resp.json() as {
    id_token: string;
    access_token: string;
    expires_in: number;
  };

  const expiresAt = Date.now() + tokens.expires_in * 1000;
  sessionStorage.setItem(STORAGE_ID_TOKEN,     tokens.id_token);
  sessionStorage.setItem(STORAGE_ACCESS_TOKEN, tokens.access_token);
  sessionStorage.setItem(STORAGE_EXPIRES_AT,   String(expiresAt));

  // Clean up PKCE state and remove code from URL
  sessionStorage.removeItem(STORAGE_PKCE_VERIFIER);
  sessionStorage.removeItem("sfc_pkce_state");
  window.history.replaceState({}, document.title, REDIRECT_URI);

  return true;
}

/**
 * Returns the stored id_token if it is still valid (with a 60-second buffer),
 * or null if absent / expired.
 */
export function getIdToken(): string | null {
  const token     = sessionStorage.getItem(STORAGE_ID_TOKEN);
  const expiresAt = Number(sessionStorage.getItem(STORAGE_EXPIRES_AT) ?? "0");
  if (!token || Date.now() > expiresAt - 60_000) return null;
  return token;
}

/**
 * Returns true when a valid (non-expired) token is present.
 */
export function isAuthenticated(): boolean {
  return getIdToken() !== null;
}

/**
 * Decode the id_token payload and return the relevant user claims.
 * No signature verification — the token was already verified by the Lambda
 * authorizer server-side; this is display-only.
 */
export interface UserInfo {
  /** Cognito username (sub claim) */
  sub: string;
  /** Email address (if the email scope was requested) */
  email?: string;
  /** Cognito preferred_username */
  username?: string;
}

export function getUser(): UserInfo | null {
  const token = getIdToken();
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    // Pad base64url → standard base64 before decoding
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    const claims = JSON.parse(json) as Record<string, string>;
    return {
      sub: claims["sub"] ?? "",
      email: claims["email"],
      username: claims["cognito:username"] ?? claims["preferred_username"],
    };
  } catch {
    return null;
  }
}

/**
 * Clear all stored tokens and redirect to the Cognito logout endpoint.
 */
export function logout(): void {
  sessionStorage.removeItem(STORAGE_ID_TOKEN);
  sessionStorage.removeItem(STORAGE_ACCESS_TOKEN);
  sessionStorage.removeItem(STORAGE_EXPIRES_AT);

  const params = new URLSearchParams({
    client_id:  CLIENT_ID,
    logout_uri: REDIRECT_URI,
  });
  window.location.href = `${DOMAIN}/logout?${params}`;
}
