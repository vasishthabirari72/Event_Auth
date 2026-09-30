import { useEffect, useRef, useState } from "react";
import { api, apiBlob, ApiError } from "../api";
import type { Task } from "../api";
import text from "../l10n/checkin.json";
import { message } from "./Members";

type Event = {
  id: string;
  name: string;
  status: string;
  slots: { id: string; label: string }[];
};
type Member = {
  id: string;
  name: string;
  member_code: string;
  option: string;
  has_photo: boolean;
};
type Coupon = { id: string; code: string; status: string; issued_at: string };
type Result = {
  band: string;
  member?: Member;
  ticket?: string;
  already_issued?: boolean;
  coupon?: Coupon;
};

export function Checkin({
  admin,
  task,
  busy,
  onEditChoices,
}: {
  admin: boolean;
  task: Task;
  busy: boolean;
  onEditChoices?: (eventId: string) => void;
}) {
  const [events, setEvents] = useState<Event[]>([]);
  const [eventId, setEventId] = useState("");
  const [slotId, setSlotId] = useState("");
  const [mode, setMode] = useState("ready");
  const [agreed, setAgreed] = useState(false);
  const [query, setQuery] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [coupon, setCoupon] = useState<Coupon | null>(null);
  const [url, setUrl] = useState("");
  const [captureError, setCaptureError] = useState("");
  const [rejectedFrame, setRejectedFrame] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const alive = useRef(true);
  const event = events.find((value) => value.id === eventId);
  const stop = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  };
  useEffect(() => {
    alive.current = true;
    void task(async () => {
      const values = await api<Event[]>("/checkin/events");
      if (alive.current) setEvents(values);
    });
    return () => {
      alive.current = false;
      stop();
    };
  }, [task]);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  function reset() {
    stop();
    setCaptureError("");
    setRejectedFrame("");
    setResult(null);
    setCoupon(null);
    setUrl("");
    setMembers([]);
    setAgreed(false);
    setMode("ready");
  }
  async function openCamera() {
    const media = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: "user" },
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
    setMode("camera");
  }
  async function capture() {
    const element = video.current;
    if (!element?.videoWidth || element.readyState < 2) return;
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = Math.round(
      (640 * element.videoHeight) / element.videoWidth,
    );
    canvas
      .getContext("2d")!
      .drawImage(element, 0, 0, canvas.width, canvas.height);
    const frame = canvas.toDataURL("image/jpeg", 0.9);
    setCaptureError("");
    setRejectedFrame("");
    try {
      const value = await api<Result>(`/checkin/slots/${slotId}/face`, "POST", {
        frame: frame.split(",")[1],
        consent_confirmed: agreed,
      });
      if (!alive.current) return;
      setResult(value);
      setMode("result");
      if (value.band === "no_match") stop();
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        if (alive.current) {
          setCaptureError(message(error.code));
          setRejectedFrame(frame);
        }
        return;
      }
      throw error;
    }
  }

  async function download(value: Coupon) {
    const blob = await apiBlob(`/checkin/coupons/${value.id}/pdf`);
    if (alive.current) setUrl(URL.createObjectURL(blob));
  }
  async function confirm() {
    const value = await api<Coupon>(
      `/checkin/confirm/${result!.ticket}`,
      "POST",
      { confirmed: true },
    );
    if (!alive.current) return;
    stop();
    setCoupon(value);
    setMode("issued");
    await download(value);
  }
  function searchMode() {
    stop();
    setCaptureError("");
    setRejectedFrame("");
    setResult(null);
    setMode("search");
  }
  return (
    <section className="card checkinPanel">
      <h2>{text.title}</h2>
      <p>{text.experimental}</p>
      {!events.length && <p>{text.noEvents}</p>}
      <label>
        {text.event}
        <select
          value={eventId}
          disabled={busy}
          onChange={(e) => {
            reset();
            setEventId(e.target.value);
            setSlotId("");
          }}
        >
          <option value="">{text.chooseEvent}</option>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} ({e.status})
            </option>
          ))}
        </select>
      </label>
      {event?.status === "READY" &&
        (admin ? (
          <button
            disabled={busy}
            onClick={() =>
              void task(async () => {
                await api(`/checkin/events/${eventId}/start`, "POST");
                setEvents(await api<Event[]>("/checkin/events"));
              })
            }
          >
            {text.startEvent}
          </button>
        ) : (
          <p>{text.askAdmin}</p>
        ))}
      {event?.status === "LIVE" && (
        <label>
          {text.slot}
          <select
            disabled={busy}
            value={slotId}
            onChange={(e) => {
              reset();
              setSlotId(e.target.value);
            }}
          >
            <option value="">{text.chooseSlot}</option>
            {event.slots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <div
        className={
          mode === "result" &&
          (result?.band === "high" || result?.band === "medium")
            ? "comparisonCamera"
            : undefined
        }
        hidden={
          !slotId ||
          !(
            mode === "camera" ||
            (mode === "result" &&
              result?.band !== "fallback" &&
              result?.band !== "no_match")
          )
        }
      >
        <video
          ref={video}
          muted
          autoPlay
          playsInline
          aria-label={text.liveCamera}
        />
      </div>
      {slotId && mode === "ready" && (
        <>
          {admin && onEditChoices ? (
            <details>
              <summary>{text.changeChoice}</summary>
              <p>{text.changeChoiceHelp}</p>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => onEditChoices(eventId)}
              >
                {text.editChoices}
              </button>
            </details>
          ) : (
            <p>{text.askChoiceChange}</p>
          )}
          <label>
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            {text.consent}
          </label>
          <button
            disabled={busy || !agreed}
            onClick={() => void task(openCamera)}
          >
            {text.scan}
          </button>
          <button className="secondary" disabled={busy} onClick={searchMode}>
            {text.search}
          </button>
        </>
      )}
      {slotId && mode === "camera" && (
        <>
          {captureError && (
            <p className="notice danger" role="alert">
              {captureError}
            </p>
          )}
          {rejectedFrame && (
            <details>
              <summary>{text.inspectCapture}</summary>
              <p>{text.inspectHelp}</p>
              <img
                className="rejectedCapture"
                src={rejectedFrame}
                alt={text.rejectedCapture}
              />
              <a
                className="downloadPdf"
                href={rejectedFrame}
                download="checkin-debug.jpg"
              >
                {text.saveCapture}
              </a>
            </details>
          )}
          <button disabled={busy} onClick={() => void task(capture)}>
            {text.capture}
          </button>
          <button className="secondary" disabled={busy} onClick={searchMode}>
            {text.search}
          </button>
        </>
      )}
      {slotId && mode === "search" && (
        <>
          <p>{text.searchHelp}</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void task(async () => {
                setMembers(
                  await api<Member[]>(
                    `/checkin/slots/${slotId}/search`,
                    "POST",
                    { query },
                  ),
                );
              });
            }}
          >
            <label>
              {text.search}
              <input
                required
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <button disabled={busy}>{text.search}</button>
          </form>
          {members.map((m) => (
            <button
              className="secondary"
              key={m.id}
              disabled={busy}
              onClick={() =>
                void task(async () => {
                  const value = await api<Result>(
                    `/checkin/slots/${slotId}/fallback`,
                    "POST",
                    { member_id: m.id },
                  );
                  setResult(value);
                  setMode("result");
                })
              }
            >
              {m.name} · {m.member_code}
            </button>
          ))}
          <button className="secondary" disabled={busy} onClick={reset}>
            {text.back}
          </button>
        </>
      )}
      {slotId && mode === "result" && result && (
        <div
          className={
            result.band === "medium"
              ? "notice warning comparisonMatch"
              : result.band === "high"
                ? "notice comparisonMatch"
                : "notice"
          }
        >
          {result.band === "no_match" ? (
            <>
              <p>{text.noMatch}</p>
              <button disabled={busy} onClick={reset}>
                {text.retry}
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={searchMode}
              >
                {text.search}
              </button>
            </>
          ) : (
            <>
              <h3>
                {result.member?.name} · {result.member?.member_code}
              </h3>
              <p className="entitlementChoice">{result.member?.option}</p>
              {result.member?.has_photo && (
                <img
                  className="referencePhoto"
                  src={`/api/checkin/slots/${slotId}/members/${result.member.id}/photo`}
                  alt={text.referencePhoto}
                />
              )}
              {result.already_issued ? (
                <>
                  <p className="danger">
                    {text.alreadyIssued} {result.coupon?.code} ·{" "}
                    {result.coupon?.issued_at}
                  </p>
                  <button
                    disabled={busy || result.coupon?.status !== "ISSUED"}
                    onClick={() =>
                      void task(async () => {
                        stop();
                        setCoupon(result.coupon!);
                        setMode("issued");
                        await download(result.coupon!);
                      })
                    }
                  >
                    {text.retryPdf}
                  </button>
                  <button className="secondary" disabled={busy} onClick={reset}>
                    {text.next}
                  </button>
                </>
              ) : (
                <>
                  <p>
                    {result.band === "medium"
                      ? text.isThisPerson
                      : result.band === "fallback"
                        ? text.verifyFallback
                        : text.verifyFace}
                  </p>
                  <button disabled={busy} onClick={() => void task(confirm)}>
                    {result.band === "medium" ? text.yes : text.confirm}
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={searchMode}
                  >
                    {result.band === "medium" ? text.no : text.wrongPerson}
                  </button>
                </>
              )}
            </>
          )}
        </div>
      )}
      {slotId && mode === "issued" && coupon && (
        <div className="notice">
          <p>
            {text.issued} {coupon.code}
          </p>
          <p>{text.pdfHelp}</p>
          {url ? (
            <a
              className="downloadPdf"
              href={url}
              download={`coupon-${coupon.code}.pdf`}
            >
              {text.download}
            </a>
          ) : (
            <button
              disabled={busy}
              onClick={() => void task(() => download(coupon))}
            >
              {text.retryPdf}
            </button>
          )}
          <button disabled={busy} className="secondary" onClick={reset}>
            {text.next}
          </button>
        </div>
      )}
    </section>
  );
}
