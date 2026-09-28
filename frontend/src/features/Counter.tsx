import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, apiBlob } from "../api";
import type { Task } from "../api";
import { message } from "./Members";
import text from "../l10n/counter.json";

type Event = {
  id: string;
  name: string;
  status: string;
  slots: { id: string; label: string }[];
  counters: { id: string; label: string }[];
};
type Result = {
  status: string;
  recovered?: boolean;
  previous_status?: string;
  name?: string;
  option?: string;
  counter?: string;
  redeemed_at?: string;
  go_to?: string[];
};
type Request = {
  counter_id: string;
  slot_id: string;
  qr: string;
  request_id: string;
};

export function CounterScreen({ task }: { task: Task }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [eventId, setEventId] = useState("");
  const [counterId, setCounterId] = useState("");
  const [slotId, setSlotId] = useState("");
  const [qr, setQr] = useState("");
  const [camera, setCamera] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState<Request | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sound, setSound] = useState(true);
  const [resultSeconds, setResultSeconds] = useState(2.5);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const flight = useRef(false);
  const blocked = useRef(false);
  const lastQr = useRef("");
  const alive = useRef(true);
  const soundOn = useRef(true);
  const event = events.find((value) => value.id === eventId);
  const stop = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  };
  useEffect(() => {
    alive.current = true;
    void task(async () => {
      const values = await api<Event[]>("/counter/events");
      const settings = await api<{ result_seconds: number; sounds: boolean }>(
        "/counter/settings",
      );
      if (alive.current) {
        setEvents(values);
        setResultSeconds(settings.result_seconds);
        setSound(settings.sounds);
        soundOn.current = settings.sounds;
      }
    });
    return () => {
      alive.current = false;
      stop();
    };
  }, [task]);
  const send = useCallback(async (request: Request) => {
    if (flight.current) return;
    flight.current = true;
    blocked.current = true;
    setBusy(true);
    setError("");
    setPending(request);
    try {
      const response = await api<Result>("/counter/redeem", "POST", request);
      if (!alive.current) return;
      setResult(response);
      setPending(null);
      setQr("");
      if (soundOn.current) {
        try {
          const context = new AudioContext();
          const tone = context.createOscillator();
          const gain = context.createGain();
          gain.gain.value = 0.08;
          tone.frequency.value = response.status === "SERVE" ? 880 : 220;
          tone.connect(gain);
          gain.connect(context.destination);
          tone.start();
          tone.stop(context.currentTime + 0.15);
          tone.onended = () => {
            void context.close();
          };
          navigator.vibrate?.(response.status === "SERVE" ? 80 : [80, 50, 80]);
        } catch {
          /* Audio is optional; text is always authoritative. */
        }
      }
    } catch (cause) {
      if (!alive.current) return;
      if (
        cause instanceof ApiError &&
        (cause.status === 0 || cause.status >= 500)
      ) {
        setError(text.disconnected);
      } else {
        setError(
          message(cause instanceof ApiError ? cause.code : "unexpected"),
        );
        setPending(null);
        blocked.current = false;
      }
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }, []);
  const submit = useCallback(
    (value: string) =>
      send({
        qr: value,
        counter_id: counterId,
        slot_id: slotId,
        request_id: crypto.randomUUID(),
      }),
    [counterId, slotId, send],
  );
  useEffect(() => {
    if (!result) return;
    const timer = window.setTimeout(
      () => {
        setResult(null);
        blocked.current = false;
      },
      result.status === "RECOVERED"
        ? Math.max(6000, resultSeconds * 1000)
        : resultSeconds * 1000,
    );
    return () => window.clearTimeout(timer);
  }, [result, resultSeconds]);
  useEffect(() => {
    if (!camera) return;
    let active = true;
    let timer: number;
    async function tick() {
      try {
        const element = video.current;
        if (
          !blocked.current &&
          !flight.current &&
          element &&
          element.readyState >= 2
        ) {
          const canvas = document.createElement("canvas");
          canvas.width = 800;
          canvas.height = Math.round(
            (800 * element.videoHeight) / element.videoWidth,
          );
          canvas
            .getContext("2d")!
            .drawImage(element, 0, 0, canvas.width, canvas.height);
          const decoded = await api<{ qr: string | null }>(
            "/counter/decode",
            "POST",
            { frame: canvas.toDataURL("image/jpeg", 0.9).split(",")[1] },
          );
          if (active && !blocked.current) setError("");
          if (
            active &&
            !blocked.current &&
            decoded.qr &&
            decoded.qr !== lastQr.current
          ) {
            lastQr.current = decoded.qr;
            await submit(decoded.qr);
          } else if (active && !decoded.qr) lastQr.current = "";
        }
      } catch {
        if (active) setError(text.disconnected);
      }
      if (active) timer = window.setTimeout(() => void tick(), 500);
    }
    void tick();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [camera, submit]);
  async function openCamera() {
    const media = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720, facingMode: "environment" },
      audio: false,
    });
    if (!alive.current) {
      media.getTracks().forEach((track) => track.stop());
      return;
    }
    stream.current = media;
    if (video.current) {
      video.current.srcObject = media;
      await video.current.play();
    }
    setCamera(true);
  }
  return (
    <section className="card counterPanel">
      <h2>{text.title}</h2>
      <p>{text.help}</p>
      <label>
        {text.event}
        <select
          value={eventId}
          disabled={busy || !!pending || camera}
          onChange={(e) => {
            setEventId(e.target.value);
            setSlotId("");
            setCounterId("");
          }}
        >
          <option value="">{text.choose}</option>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} ({e.status})
            </option>
          ))}
        </select>
      </label>
      <label>
        {text.slot}
        <select
          value={slotId}
          disabled={busy || !!pending || camera}
          onChange={(e) => setSlotId(e.target.value)}
        >
          <option value="">{text.choose}</option>
          {event?.slots.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        {text.counter}
        <select
          value={counterId}
          disabled={busy || !!pending || camera}
          onChange={(e) => setCounterId(e.target.value)}
        >
          <option value="">{text.choose}</option>
          {event?.counters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={sound}
          onChange={(e) => {
            setSound(e.target.checked);
            soundOn.current = e.target.checked;
          }}
        />
        {text.sound}
      </label>
      {error && (
        <p role="alert" className="notice danger">
          {error}
        </p>
      )}
      <div hidden={!camera}>
        <video
          ref={video}
          muted
          autoPlay
          playsInline
          aria-label={text.qrCamera}
        />
      </div>
      {pending ? (
        <button disabled={busy} onClick={() => void send(pending)}>
          {text.recover}
        </button>
      ) : (
        <>
          <button
            disabled={!slotId || !counterId || busy}
            onClick={() =>
              camera ? (stop(), setCamera(false)) : void task(openCamera)
            }
          >
            {camera ? text.stopCamera : text.camera}
          </button>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (qr.trim() && !blocked.current) void submit(qr.trim());
            }}
          >
            <label>
              {text.qr}
              <input
                value={qr}
                disabled={busy}
                onChange={(e) => setQr(e.target.value)}
                maxLength={2000}
                autoComplete="off"
              />
            </label>
            <button disabled={!slotId || !counterId || !qr.trim() || busy}>
              {text.redeem}
            </button>
          </form>
        </>
      )}
      {result && (
        <div
          className={
            "counterResult " +
            (result.status === "SERVE"
              ? "serve"
              : ["WRONG_COUNTER", "RECOVERED"].includes(result.status)
                ? "caution"
                : "reject")
          }
          role="status"
          aria-live="assertive"
        >
          <span aria-hidden="true">
            {result.status === "SERVE" ? "✓" : "!"}
          </span>
          <h1>
            {text.states[result.status as keyof typeof text.states] ??
              text.states.INVALID}
          </h1>
          {result.option && <p className="servedOption">{result.option}</p>}
          <p>{result.name}</p>
          {result.counter && (
            <p>
              {result.counter} · {result.redeemed_at}
            </p>
          )}
          {result.go_to && (
            <p>
              {text.goTo} {result.go_to.join(", ")}
            </p>
          )}
          {result.previous_status && (
            <p>
              {text.previous}{" "}
              {text.states[result.previous_status as keyof typeof text.states]}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

type Coupon = {
  coupon_id: string;
  code: string;
  name: string;
  option: string;
  status: string;
  slot_id: string;
};
type Stats = {
  status: string;
  registered: number;
  checked_in: number;
  issued: number;
  served: number;
  fallback: number;
  options: { slot: string; option: string; issued: number; served: number }[];
};
export function Operations({ task, busy }: { task: Task; busy: boolean }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [eventId, setEventId] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [query, setQuery] = useState("");
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [reason, setReason] = useState("");
  const [counterId, setCounterId] = useState("");
  const [notice, setNotice] = useState("");
  const [closing, setClosing] = useState(false);
  const [pdfUrl, setPdfUrl] = useState("");
  const [action, setAction] = useState<{
    coupon: Coupon;
    kind: string;
    request_id: string;
  } | null>(null);
  const closeId = useRef(crypto.randomUUID());
  const event = events.find((e) => e.id === eventId);
  useEffect(() => {
    void task(async () => setEvents(await api<Event[]>("/counter/events")));
  }, [task]);
  useEffect(() => {
    if (eventId)
      void task(async () =>
        setStats(await api<Stats>(`/counter/events/${eventId}/dashboard`)),
      );
  }, [eventId, task]);
  useEffect(
    () => () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    },
    [pdfUrl],
  );
  async function refresh() {
    setStats(await api<Stats>(`/counter/events/${eventId}/dashboard`));
  }
  async function confirmAction() {
    if (!action) return;
    if (action.kind === "lookup") {
      const value = await api<Result>("/counter/lookup-redeem", "POST", {
        coupon_id: action.coupon.coupon_id,
        slot_id: action.coupon.slot_id,
        counter_id: counterId,
        request_id: action.request_id,
        confirmed: true,
      });
      setNotice(text.states[value.status as keyof typeof text.states]);
    } else {
      const value = await api<{ coupon_id: string; status: string }>(
        `/counter/coupons/${action.coupon.coupon_id}/${action.kind}`,
        "POST",
        { reason, request_id: action.request_id, confirmed: true },
      );
      setNotice(
        value.status === "VOID" ? text.states.CANCELLED : text.replacementSaved,
      );
      if (action.kind === "replace") {
        const blob = await apiBlob(`/checkin/coupons/${value.coupon_id}/pdf`);
        setPdfUrl(URL.createObjectURL(blob));
      }
    }
    setAction(null);
    await refresh();
    setCoupons(
      await api<Coupon[]>(`/counter/events/${eventId}/lookup`, "POST", {
        query,
      }),
    );
  }
  return (
    <section className="card">
      <h2>{text.operations}</h2>
      <label>
        {text.event}
        <select
          disabled={busy || !!action}
          value={eventId}
          onChange={(e) => {
            setEventId(e.target.value);
            setCoupons([]);
            setStats(null);
            setNotice("");
            setPdfUrl("");
            setClosing(false);
            setCounterId("");
            closeId.current = crypto.randomUUID();
          }}
        >
          <option value="">{text.choose}</option>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
      </label>
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {pdfUrl && (
        <a
          className="downloadPdf"
          href={pdfUrl}
          download="replacement-coupon.pdf"
        >
          {text.download}
        </a>
      )}
      {stats && (
        <>
          <p>
            {text.registered}: {stats.registered} · {text.checkedIn}:{" "}
            {stats.checked_in} · {text.issued}: {stats.issued} · {text.served}:{" "}
            {stats.served} · {text.fallback}: {stats.fallback}
          </p>
          <p>{text.countHelp}</p>
          <button disabled={busy} onClick={() => void task(refresh)}>
            {text.refresh}
          </button>
          <table>
            <thead>
              <tr>
                <th>{text.slot}</th>
                <th>{text.option}</th>
                <th>{text.issued}</th>
                <th>{text.served}</th>
              </tr>
            </thead>
            <tbody>
              {stats.options.map((o, i) => (
                <tr key={i}>
                  <td>{o.slot}</td>
                  <td>{o.option}</td>
                  <td>{o.issued}</td>
                  <td>{o.served}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <a href={`/api/counter/events/${eventId}/counts.csv`}>
            {text.export}
          </a>
          {stats.status === "LIVE" && (
            <>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void task(async () =>
                    setCoupons(
                      await api<Coupon[]>(
                        `/counter/events/${eventId}/lookup`,
                        "POST",
                        { query },
                      ),
                    ),
                  );
                }}
              >
                <label>
                  {text.lookup}
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    required
                  />
                </label>
                <button disabled={busy}>{text.lookup}</button>
              </form>
              <label>
                {text.counter}
                <select
                  disabled={!!action}
                  value={counterId}
                  onChange={(e) => setCounterId(e.target.value)}
                >
                  <option value="">{text.choose}</option>
                  {event?.counters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              {coupons.map((c) => (
                <div className="notice" key={c.coupon_id}>
                  <p>
                    {c.name} · {c.code} · {c.option} · {c.status}
                  </p>
                  {c.status === "ISSUED" && (
                    <button
                      disabled={busy || !!action || !counterId}
                      onClick={() => {
                        setAction({
                          coupon: c,
                          kind: "lookup",
                          request_id: crypto.randomUUID(),
                        });
                        setNotice("");
                      }}
                    >
                      {text.lookupRedeem}
                    </button>
                  )}
                  {["ISSUED", "VOID"].includes(c.status) && (
                    <button
                      disabled={busy || !!action}
                      onClick={() => {
                        setReason("");
                        setAction({
                          coupon: c,
                          kind: "replace",
                          request_id: crypto.randomUUID(),
                        });
                        setNotice("");
                      }}
                    >
                      {text.replace}
                    </button>
                  )}
                  {c.status === "ISSUED" && (
                    <button
                      disabled={busy || !!action}
                      onClick={() => {
                        setReason("");
                        setAction({
                          coupon: c,
                          kind: "void",
                          request_id: crypto.randomUUID(),
                        });
                        setNotice("");
                      }}
                    >
                      {text.void}
                    </button>
                  )}
                </div>
              ))}
              {action && (
                <div className="notice">
                  <h3>{text.confirmAction}</h3>
                  <p>
                    {action.coupon.code} ·{" "}
                    {action.kind === "lookup"
                      ? text.lookupWarning
                      : text.replaceWarning}
                  </p>
                  {action.kind !== "lookup" && (
                    <label>
                      {text.reason}
                      <input
                        maxLength={256}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    </label>
                  )}
                  <button
                    disabled={
                      busy || (action.kind !== "lookup" && !reason.trim())
                    }
                    onClick={() => void task(confirmAction)}
                  >
                    {text.confirm}
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => setAction(null)}
                  >
                    {text.cancel}
                  </button>
                </div>
              )}
              <label>
                <input
                  type="checkbox"
                  checked={closing}
                  onChange={(e) => setClosing(e.target.checked)}
                />
                {text.closeWarning}
              </label>
              <button
                disabled={busy || !closing || !!action}
                onClick={() =>
                  void task(async () => {
                    await api(`/counter/events/${eventId}/close`, "POST", {
                      request_id: closeId.current,
                      confirmed: true,
                    });
                    await refresh();
                    setNotice(text.closed);
                  })
                }
              >
                {text.close}
              </button>
            </>
          )}
        </>
      )}
    </section>
  );
}
