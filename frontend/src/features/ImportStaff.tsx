import { useEffect, useState } from "react";
import { api } from "../api";
import type { EventSummary, Task } from "../api";
import text from "../l10n/admin.json";
import { message } from "./Members";

type ImportResult = {
  rows: number;
  errors: { row: number; code: string }[];
  committed: boolean;
};
export function Imports({ task, busy }: { task: Task; busy: boolean }) {
  const [kind, setKind] = useState("members");
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [event, setEvent] = useState("");
  const [content, setContent] = useState("");
  const [format, setFormat] = useState("csv");
  const [result, setResult] = useState<ImportResult | null>(null);
  useEffect(() => {
    void task(async () => setEvents(await api<EventSummary[]>("/events")));
  }, [task]);
  async function run(preview: boolean) {
    setResult(
      await api<ImportResult>("/imports", "POST", {
        kind,
        format,
        content,
        event_id: kind === "choices" ? event : null,
        preview,
      }),
    );
  }
  return (
    <section className="card narrow">
      <h2>{text.imports}</h2>
      <p>{text.importHelp}</p>
      <label>
        {text.importKind}
        <select
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setResult(null);
          }}
        >
          <option value="members">{text.members}</option>
          <option value="choices">{text.choices}</option>
        </select>
      </label>
      {kind === "choices" && (
        <label>
          {text.events}
          <select
            value={event}
            onChange={(e) => {
              setEvent(e.target.value);
              setResult(null);
            }}
          >
            <option value="">{text.choose}</option>
            {events.map((e) => (
              <option value={e.id} key={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {(kind === "members" || event) && (
        <a
          className="buttonLink"
          href={
            "/api/imports/template.csv" +
            (kind === "choices" ? "?event_id=" + event : "")
          }
        >
          {text.downloadTemplate}
        </a>
      )}
      <p>{text.importColumns}</p>
      <label>
        {text.file}
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => {
            setResult(null);
            setContent("");
            const file = e.target.files?.[0];
            if (!file) return;
            void task(async () => {
              if (file.size > 2000000) throw new Error("invalid_import");
              const bytes = new Uint8Array(await file.arrayBuffer());
              let binary = "";
              for (const byte of bytes) binary += String.fromCharCode(byte);
              setContent(btoa(binary));
              setFormat(
                file.name.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv",
              );
            });
          }}
        />
      </label>
      <button
        disabled={busy || !content || (kind === "choices" && !event)}
        onClick={() => void task(() => run(true))}
      >
        {text.previewImport}
      </button>
      {result && (
        <div role="status">
          <p>
            {text.rows}: {result.rows}
          </p>
          {result.errors.length > 0 ? (
            <ul>
              {result.errors.map((error) => (
                <li key={error.row}>
                  {text.row} {error.row}: {message(error.code)}
                </li>
              ))}
            </ul>
          ) : result.committed ? (
            <p className="success">{text.importComplete}</p>
          ) : (
            <>
              <p>{text.importValid}</p>
              <button
                disabled={busy}
                onClick={() => void task(() => run(false))}
              >
                {text.confirmImport}
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
type Staff = { id: string; username: string; role: string };
export function StaffUsers({ task, busy }: { task: Task; busy: boolean }) {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [username, setUsername] = useState("");
  const [role, setRole] = useState("checkin");
  const [pin, setPin] = useState("");
  const [target, setTarget] = useState("");
  const [reset, setReset] = useState("");
  useEffect(() => {
    void task(async () => setStaff(await api<Staff[]>("/staff")));
  }, [task]);
  return (
    <div className="cards">
      <section className="card">
        <h2>{text.addStaff}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void task(async () => {
              await api("/staff", "POST", { username, role, pin });
              setUsername("");
              setPin("");
              setStaff(await api<Staff[]>("/staff"));
            });
          }}
        >
          <label>
            {text.username}
            <input
              required
              pattern="[a-z0-9_-]+"
              maxLength={40}
              autoComplete="off"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label>
            {text.role}
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {["admin", "checkin", "counter"].map((value) => (
                <option key={value} value={value}>
                  {text.roles[value as keyof typeof text.roles]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {text.pin}
            <input
              type="password"
              inputMode="numeric"
              required
              pattern="[0-9]{6,12}"
              autoComplete="new-password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />
          </label>
          <button disabled={busy}>{text.addStaff}</button>
        </form>
      </section>
      <section className="card">
        <h2>{text.resetPin}</h2>
        <p>{text.resetHelp}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void task(async () => {
              await api("/staff/" + target + "/pin", "POST", { pin: reset });
              setReset("");
            });
          }}
        >
          <label>
            {text.staff}
            <select
              required
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">{text.choose}</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.username} · {s.role}
                </option>
              ))}
            </select>
          </label>
          <label>
            {text.newPin}
            <input
              type="password"
              inputMode="numeric"
              required
              pattern="[0-9]{6,12}"
              autoComplete="new-password"
              value={reset}
              onChange={(e) => setReset(e.target.value)}
            />
          </label>
          <button disabled={busy}>{text.resetPin}</button>
        </form>
      </section>
    </div>
  );
}
