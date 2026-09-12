"use client";

import { createClient, SupabaseClient, User } from "@supabase/supabase-js";
import { ReactNode, useCallback, useEffect, useState } from "react";
import Link from "next/link";

export type Account = {
  email: string;
  getAccessToken: () => Promise<string>;
  signOut: () => Promise<void>;
};

export function AccountGate({
  children,
}: {
  children: (account?: Account) => ReactNode;
}) {
  const [client, setClient] = useState<SupabaseClient | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [local, setLocal] = useState(false);
  const [mode, setMode] = useState<"login" | "signup" | "reset" | "password">(
    "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    let dispose: (() => void) | undefined;
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch("/api/auth/config", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error(
            "Unable to load account settings. Please reload to retry.",
          );
        const config = await response.json();
        if (!active) return;
        if (config.provider === "local") {
          setLocal(true);
          setReady(true);
          return;
        }
        if (
          config.provider !== "supabase" ||
          !config.url ||
          !config.publishableKey
        )
          throw new Error(
            "Account settings are incomplete. Contact the workspace administrator.",
          );
        const supabase = createClient(config.url, config.publishableKey, {
          auth: {
            flowType: "pkce",
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true,
          },
        });
        setClient(supabase);
        const { data } = supabase.auth.onAuthStateChange((event, session) => {
          if (!active) return;
          setUser(session?.user ?? null);
          setPassword("");
          if (event === "PASSWORD_RECOVERY") setMode("password");
          if (event === "SIGNED_OUT") {
            setMode("login");
            window.history.replaceState({}, "", "/");
          }
          setReady(true);
        });
        dispose = () => {
          data.subscription.unsubscribe();
          void supabase.auth.stopAutoRefresh();
        };
        const { error: sessionError } = await supabase.auth.getSession();
        if (active && sessionError) {
          setError(
            "This sign-in link has expired or is invalid. Request a new link.",
          );
          setReady(true);
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    })();
    return () => {
      active = false;
      controller.abort();
      dispose?.();
    };
  }, []);

  const getAccessToken = useCallback(async () => {
    if (!client) throw new Error("Please sign in.");
    const { data, error } = await client.auth.getSession();
    if (error || !data.session)
      throw new Error("Your session has expired. Please sign in again.");
    return data.session.access_token;
  }, [client]);

  const signOut = useCallback(async () => {
    if (!client) return;
    const { error } = await client.auth.signOut({ scope: "local" });
    if (error) throw new Error(error.message);
  }, [client]);

  if (local) return children();
  if (ready && user && mode !== "password")
    return (
      <div key={user.id}>
        {children({
          email: user.email || "Your account",
          getAccessToken,
          signOut,
        })}
      </div>
    );

  const heading =
    mode === "signup"
      ? "Make room for your next idea."
      : mode === "reset"
        ? "Reset your password."
        : mode === "password"
          ? "Choose a new password."
          : "Pick up where you left off.";
  return (
    <main className="account-page">
      <section className="account-story" aria-label="About your workspace">
        <Link href="/" className="account-brand">
          AutoQA<span>WORKSPACE</span>
        </Link>
        <div>
          <p className="account-eyebrow">YOUR WORK, KEPT TOGETHER</p>
          <h1>
            One place to think.
            <br />
            More room to do.
          </h1>
          <p>
            Bring a document, explore a question, and keep building on what you
            find. Your conversations and files will be here when you return.
          </p>
        </div>
        <span className="account-caption">Research · Analysis · Documents</span>
      </section>
      <section className="account-panel">
        <form
          className="account-form"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!client || busy) return;
            setBusy(true);
            setError("");
            setNotice("");
            try {
              const redirectTo = window.location.origin + "/";
              if (mode === "signup") {
                const { error, data } = await client.auth.signUp({
                  email,
                  password,
                  options: { emailRedirectTo: redirectTo },
                });
                if (error) throw error;
                if (!data.session)
                  setNotice(
                    "Check your email for a confirmation link, then return here to sign in.",
                  );
              } else if (mode === "reset") {
                const { error } = await client.auth.resetPasswordForEmail(
                  email,
                  { redirectTo },
                );
                if (error) throw error;
                setNotice(
                  "If this address has an account, a password reset link will arrive shortly. Open it in this browser.",
                );
              } else if (mode === "password") {
                const { error } = await client.auth.updateUser({ password });
                if (error) throw error;
                setMode("login");
              } else {
                const { error } = await client.auth.signInWithPassword({
                  email,
                  password,
                });
                if (error) throw error;
              }
              setPassword("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p className="account-eyebrow">
            {mode === "signup" ? "CREATE YOUR ACCOUNT" : "WELCOME TO AUTOQA"}
          </p>
          <h2>{heading}</h2>
          <p className="account-description">
            {mode === "login"
              ? "Sign in to your saved tasks, conversations, and files."
              : "Use your email to securely access your workspace."}
          </p>
          {error && (
            <p role="alert" className="account-error">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="account-notice">
              {notice}
            </p>
          )}
          {!ready && !error && (
            <p role="status">Connecting to your workspace…</p>
          )}
          {ready && client && (
            <>
              {mode !== "password" && (
                <label>
                  Email address
                  <input
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={254}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
              )}
              {mode !== "reset" && (
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete={
                      mode === "login" ? "current-password" : "new-password"
                    }
                    required
                    minLength={mode === "login" ? 1 : 12}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {mode !== "login" && (
                    <small>Use at least 12 characters.</small>
                  )}
                </label>
              )}
              <button className="button primary" disabled={busy} type="submit">
                {busy
                  ? "Please wait…"
                  : mode === "signup"
                    ? "Create account"
                    : mode === "reset"
                      ? "Send reset link"
                      : mode === "password"
                        ? "Save password"
                        : "Sign in"}
              </button>
              <div className="account-links">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setMode(mode === "login" ? "signup" : "login");
                    setNotice("");
                    setError("");
                    setPassword("");
                  }}
                >
                  {mode === "login"
                    ? "New here? Create an account"
                    : "Back to sign in"}
                </button>
                {mode === "login" && (
                  <button
                    type="button"
                    onClick={() => {
                      setMode("reset");
                      setNotice("");
                      setError("");
                      setPassword("");
                    }}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
            </>
          )}
        </form>
      </section>
    </main>
  );
}
