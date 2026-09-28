import { useCallback, useEffect, useState } from "react";
import { api, ApiError, setCsrf } from "./api";
import type { Config, StaffSession } from "./api";
import type { CSSProperties } from "react";
import { Members, message } from "./features/Members";
import { CounterScreen, Operations } from "./features/Counter";
import { Checkin } from "./features/Checkin";
import { Events } from "./features/Events";
import { Imports, StaffUsers } from "./features/ImportStaff";
import text from "./l10n/admin.json";

export function App() {
  const [session, setSession] = useState<StaffSession | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [tab, setTab] = useState("members");
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const task = useCallback(async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status === 401 &&
        cause.code !== "login_failed"
      ) {
        setSession(null);
        setConfig(null);
        setCsrf("");
      }
      setError(message(cause instanceof ApiError ? cause.code : "unexpected"));
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => {
    let active = true;
    void api<StaffSession>("/auth/session")
      .then(async (value) => {
        const settings =
          value.role === "admin" ? await api<Config>("/config") : null;
        if (active) {
          setCsrf(value.csrf);
          setSession(value);
          setConfig(settings);
        }
      })
      .catch((cause) => {
        if (active && (!(cause instanceof ApiError) || cause.status !== 401))
          setError(
            message(cause instanceof ApiError ? cause.code : "unexpected"),
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <main style={{ "--brand": config?.primary_color } as CSSProperties}>
      <header>
        <span className="brandMark" aria-hidden="true">
          E
        </span>
        <strong>{config?.organization ?? text.product}</strong>
        {session && (
          <button
            className="secondary logout"
            disabled={busy}
            onClick={() =>
              void task(async () => {
                await api("/auth/logout", "POST");
                setSession(null);
                setConfig(null);
                setCsrf("");
                setTab("members");
              })
            }
          >
            {text.signOut}
          </button>
        )}
      </header>
      <section
        className="intro"
        hidden={
          ["checkin", "counter"].includes(session?.role ?? "") ||
          (session?.role === "admin" && ["checkin", "counter"].includes(tab))
        }
      >
        <h1>{text.welcome}</h1>
        <p>{text.welcomeHelp}</p>
      </section>
      {error && (
        <p className="notice danger" role="alert">
          {error}
        </p>
      )}
      {busy && <p role="status">{text.busy}</p>}
      {loading ? (
        <p>{text.loading}</p>
      ) : !session ? (
        <section className="card narrow">
          <h2>{text.signIn}</h2>
          <p>{text.loginHelp}</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void task(async () => {
                const value = await api<StaffSession>("/auth/login", "POST", {
                  username,
                  pin,
                });
                setPin("");
                setCsrf(value.csrf);
                setSession(value);
                if (value.role === "admin")
                  setConfig(await api<Config>("/config"));
              });
            }}
          >
            <label>
              {text.username}
              <input
                required
                autoComplete="username"
                pattern="[a-z0-9_-]+"
                maxLength={40}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label>
              {text.pin}
              <input
                required
                type="password"
                inputMode="numeric"
                autoComplete="current-password"
                pattern="[0-9]{6,12}"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
              />
            </label>
            <button disabled={busy}>{text.signIn}</button>
          </form>
          <p>{text.setupHelp}</p>
        </section>
      ) : session.role === "checkin" ? (
        <Checkin admin={false} task={task} busy={busy} />
      ) : session.role === "counter" ? (
        <CounterScreen task={task} />
      ) : session.role !== "admin" ? (
        <p className="notice">{text.rolePending}</p>
      ) : (
        config && (
          <>
            <nav aria-label={text.navigation}>
              {(
                [
                  "members",
                  "events",
                  "imports",
                  "staff",
                  "checkin",
                  "counter",
                  "operations",
                ] as const
              ).map((value) => (
                <button
                  key={value}
                  className={tab === value ? "" : "secondary"}
                  aria-current={tab === value ? "page" : undefined}
                  disabled={busy}
                  onClick={() => {
                    setTab(value);
                    setError("");
                  }}
                >
                  {text[value]}
                </button>
              ))}
            </nav>
            {tab === "members" && (
              <Members config={config} task={task} busy={busy} />
            )}
            {tab === "events" && (
              <Events config={config} task={task} busy={busy} />
            )}
            {tab === "imports" && <Imports task={task} busy={busy} />}
            {tab === "staff" && <StaffUsers task={task} busy={busy} />}
            {tab === "checkin" && <Checkin admin task={task} busy={busy} />}
            {tab === "counter" && <CounterScreen task={task} />}
            {tab === "operations" && <Operations task={task} busy={busy} />}
          </>
        )
      )}
      <footer>{text.m1Pending}</footer>
    </main>
  );
}
