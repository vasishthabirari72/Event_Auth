import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Config, Member, Task } from "../api";
import text from "../l10n/admin.json";

export function Members({
  config,
  task,
  busy,
}: {
  config: Config;
  task: Task;
  busy: boolean;
}) {
  const [members, setMembers] = useState<Member[]>([]);
  const [selected, setSelected] = useState<Member | null>(null);
  const [query, setQuery] = useState("");
  const [capture, setCapture] = useState(false);
  async function refresh() {
    const values = await api<Member[]>("/members/search", "POST", { query });
    setMembers(values);
    setSelected((previous) =>
      previous
        ? (values.find((value) => value.id === previous.id) ?? previous)
        : null,
    );
  }
  useEffect(() => {
    let alive = true;
    void task(async () => {
      const values = await api<Member[]>("/members");
      if (alive) setMembers(values);
    });
    return () => {
      alive = false;
    };
  }, [task]);
  return (
    <div className="workspace">
      <section className="card">
        <h2>{text.members}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void task(refresh);
          }}
        >
          <label>
            {text.search}
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <button disabled={busy}>{text.search}</button>
        </form>
        <button
          className="secondary"
          onClick={() => {
            setSelected(null);
            setCapture(false);
          }}
        >
          {text.addMember}
        </button>
        <p>
          {text.records}: {members.length}
        </p>
        <ul className="records">
          {members.map((member) => (
            <li key={member.id}>
              <button
                className="record"
                disabled={busy}
                onClick={() =>
                  void task(async () => {
                    setSelected(await api<Member>("/members/" + member.id));
                    setCapture(false);
                  })
                }
              >
                <strong>{member.name}</strong>
                <span>
                  {member.member_code} ·{" "}
                  {member.has_face ? text.faceSaved : text.idOnly}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="card">
        <MemberForm
          key={selected ? selected.id + ":" + selected.revision : "new"}
          member={selected}
          config={config}
          busy={busy}
          task={task}
          onSaved={async (value) => {
            setSelected(value);
            await refresh();
          }}
          onDeleted={async () => {
            setSelected(null);
            setCapture(false);
            await refresh();
          }}
        />
        {selected && (
          <>
            <h3>{text.faceRegistration}</h3>
            {selected.has_face && (
              <img
                className="reference"
                src={"/api/members/" + selected.id + "/photo"}
                alt={text.referencePhoto}
              />
            )}
            <p>
              {config.experimental_face ? text.experimental : text.facePending}
            </p>
            {config.experimental_face && !capture && (
              <button disabled={busy} onClick={() => setCapture(true)}>
                {text.addFace}
              </button>
            )}
            {capture && (
              <FaceCapture
                member={selected}
                config={config}
                onClose={() => {
                  setCapture(false);
                  void task(refresh);
                }}
              />
            )}
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                void task(async () => {
                  await api("/members/" + selected.id + "/consents", "DELETE");
                  setCapture(false);
                  await refresh();
                  setSelected({ ...selected, has_face: false });
                })
              }
            >
              {text.withdraw}
            </button>
          </>
        )}
      </section>
    </div>
  );
}

function MemberForm({
  member,
  config,
  busy,
  task,
  onSaved,
  onDeleted,
}: {
  member: Member | null;
  config: Config;
  busy: boolean;
  task: Task;
  onSaved: (value: Member) => Promise<void>;
  onDeleted: () => Promise<void>;
}) {
  const [name, setName] = useState(member?.name ?? "");
  const [mobile, setMobile] = useState(member?.mobile ?? "");
  const [minor, setMinor] = useState(member?.is_minor ?? false);
  const [fields, setFields] = useState<Record<string, string>>(
    member?.custom_fields ?? {},
  );
  const [deleting, setDeleting] = useState(false);
  return (
    <>
      <h2>{member ? text.editMember : text.addMember}</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void task(async () => {
            const value = await api<Member>(
              "/members" + (member ? "/" + member.id : ""),
              member ? "PUT" : "POST",
              {
                name,
                mobile,
                is_minor: minor,
                custom_fields: fields,
                revision: member?.revision ?? 1,
              },
            );
            await onSaved(value);
          });
        }}
      >
        <label>
          {text.name}
          <input
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          {text.mobile}
          <input
            type="tel"
            maxLength={32}
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
          />
        </label>
        {config.member_fields.map((field) => (
          <label key={field.key}>
            {field.label}
            {field.type === "select" ? (
              <select
                required={field.required}
                value={fields[field.key] ?? ""}
                onChange={(e) =>
                  setFields({ ...fields, [field.key]: e.target.value })
                }
              >
                <option value="">{text.choose}</option>
                {field.options.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            ) : (
              <input
                required={field.required}
                maxLength={160}
                value={fields[field.key] ?? ""}
                onChange={(e) =>
                  setFields({ ...fields, [field.key]: e.target.value })
                }
              />
            )}
          </label>
        ))}
        <label className="check">
          <input
            type="checkbox"
            checked={minor}
            onChange={(e) => setMinor(e.target.checked)}
          />
          {text.minor}
        </label>
        <p>{text.idOnlyHelp}</p>
        <button disabled={busy}>{text.saveMember}</button>
      </form>
      {member &&
        (deleting ? (
          <div className="notice danger">
            <p>{text.deleteConfirm}</p>
            <button
              disabled={busy}
              className="dangerButton"
              onClick={() =>
                void task(async () => {
                  await api("/members/" + member.id, "DELETE");
                  await onDeleted();
                })
              }
            >
              {text.deletePermanently}
            </button>
            <button className="secondary" onClick={() => setDeleting(false)}>
              {text.cancel}
            </button>
          </div>
        ) : (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => setDeleting(true)}
          >
            {text.deleteMember}
          </button>
        ))}
    </>
  );
}

function FaceCapture({
  member,
  config,
  onClose,
}: {
  member: Member;
  config: Config;
  onClose: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  const [guardian, setGuardian] = useState("");
  const [consent, setConsent] = useState("");
  const [frames, setFrames] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [working, setWorking] = useState(false);
  const [hint, setHint] = useState("");
  const [rejectedFrame, setRejectedFrame] = useState("");
  const [duplicates, setDuplicates] = useState<Member[]>([]);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const alive = useRef(true);
  function stop() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      stop();
    };
  }, []);
  async function start() {
    setWorking(true);
    try {
      const record = await api<{ id: string }>(
        "/members/" + member.id + "/consents",
        "POST",
        {
          given_by: member.is_minor ? "guardian" : "self",
          guardian_name: guardian,
          text_version: config.consent_version,
          agreed,
        },
      );
      if (!alive.current) return;
      setConsent(record.id);
      const media = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false,
      });
      if (!alive.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      if (video.current) video.current.srcObject = media;
      setRunning(true);
    } catch {
      setHint(text.cameraError);
    } finally {
      if (alive.current) setWorking(false);
    }
  }
  const capture = useCallback(async () => {
    if (!video.current?.videoWidth || working || frames.length >= 3) return;
    setWorking(true);
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = Math.round(
      (640 * video.current.videoHeight) / video.current.videoWidth,
    );
    canvas
      .getContext("2d")
      ?.drawImage(video.current, 0, 0, canvas.width, canvas.height);
    const frame = canvas.toDataURL("image/jpeg", 0.8).split(",")[1];
    try {
      await api("/members/" + member.id + "/face/check", "POST", {
        consent_id: consent,
        frame,
      });
      if (alive.current) {
        setRejectedFrame("");
        setFrames((previous) => [...previous, frame]);
        setHint(text.goodFrame);
      }
    } catch (error) {
      if (alive.current) {
        setRejectedFrame(frame);
        setHint(
          error instanceof ApiError ? message(error.code) : text.cameraError,
        );
      }
    } finally {
      if (alive.current) setWorking(false);
    }
  }, [working, frames.length, consent, member.id]);
  useEffect(() => {
    if (!running || working || frames.length >= 3) return;
    const timer = window.setTimeout(() => void capture(), 1500);
    return () => window.clearTimeout(timer);
  }, [running, working, frames.length, capture]);

  async function save(reviewed: string[] = []) {
    setWorking(true);
    try {
      const result = await api<{ saved: boolean; duplicates: Member[] }>(
        "/members/" + member.id + "/face",
        "POST",
        {
          consent_id: consent,
          frames,
          reviewed_duplicate_ids: reviewed,
        },
      );
      if (result.saved) {
        stop();
        setFrames([]);
        onClose();
      } else {
        setDuplicates(result.duplicates);
        setHint(text.duplicateHelp);
      }
    } catch (error) {
      setHint(
        error instanceof ApiError ? message(error.code) : text.cameraError,
      );
    } finally {
      if (alive.current) setWorking(false);
    }
  }
  return (
    <div className="capture">
      <h3>{text.consent}</h3>
      <p>{config.consent_text}</p>
      {!consent && (
        <>
          {member.is_minor && (
            <label>
              {text.guardian}
              <input
                value={guardian}
                onChange={(e) => setGuardian(e.target.value)}
                maxLength={120}
              />
            </label>
          )}
          <label className="check">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            {text.agree}
          </label>
          <button
            disabled={
              !agreed || working || (member.is_minor && !guardian.trim())
            }
            onClick={() => void start()}
          >
            {text.consentAndCamera}
          </button>
        </>
      )}
      <div className="cameraFrame" hidden={!running}>
        <video
          ref={video}
          autoPlay
          muted
          playsInline
          aria-label={text.camera}
        />
        <div className="oval" aria-hidden="true" />
      </div>
      {running && (
        <>
          <p>{text.captureGuide}</p>
          {rejectedFrame && (
            <details>
              <summary>{text.checkCapturedFrame}</summary>
              <p>{text.checkCapturedFrameHelp}</p>
              <img
                src={"data:image/jpeg;base64," + rejectedFrame}
                alt={text.capturedFrameAlt}
                style={{ width: "100%" }}
              />
            </details>
          )}
          <p>
            {text.frames}: {frames.length}/3
          </p>
          {frames.length < 3 && (
            <button disabled={working} onClick={() => void capture()}>
              {text.captureFrame}
            </button>
          )}
          {frames.length === 3 && (
            <>
              <img
                className="reference"
                src={"data:image/jpeg;base64," + frames[0]}
                alt={text.capturePreview}
              />
              {duplicates.length === 0 && (
                <button disabled={working} onClick={() => void save()}>
                  {text.saveFace}
                </button>
              )}
              <button
                className="secondary"
                disabled={working}
                onClick={() => {
                  setFrames([]);
                  setDuplicates([]);
                }}
              >
                {text.retake}
              </button>
            </>
          )}
        </>
      )}
      {hint && <p role="status">{hint}</p>}
      {duplicates.length > 0 && (
        <>
          <h3>{text.possibleDuplicates}</h3>
          {duplicates.map((value) => (
            <div key={value.id}>
              <p>
                {value.name} · {value.member_code}
              </p>
              <img
                className="reference"
                src={"/api/members/" + value.id + "/photo"}
                alt={text.referencePhoto}
              />
            </div>
          ))}
          <button
            disabled={working}
            onClick={() => void save(duplicates.map((value) => value.id))}
          >
            {text.overrideDuplicate}
          </button>
        </>
      )}
      <button
        className="secondary"
        disabled={working}
        onClick={() => {
          stop();
          setFrames([]);
          onClose();
        }}
      >
        {text.cancelCapture}
      </button>
    </div>
  );
}

export function message(code: string): string {
  return (
    (text.errors as Record<string, string>)[code] ?? text.errors.unexpected
  );
}
