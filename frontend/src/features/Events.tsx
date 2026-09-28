import { useEffect, useState } from "react";
import { api } from "../api";
import type { Config, EventDetail, EventSummary, Member, Task } from "../api";
import text from "../l10n/admin.json";

type SlotDraft = { label: string; options: string };
type Draft = {
  name: string;
  date: string;
  venue: string;
  slots: SlotDraft[];
  counters: { label: string; serves: string[] }[];
};

export function Events({
  config,
  task,
  busy,
}: {
  config: Config;
  task: Task;
  busy: boolean;
}) {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selected, setSelected] = useState<EventDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [member, setMember] = useState("");
  const [choices, setChoices] = useState<Record<string, string>>({});
  async function refresh() {
    setEvents(await api<EventSummary[]>("/events"));
  }
  useEffect(() => {
    let active = true;
    void task(async () => {
      const [eventRows, memberRows] = await Promise.all([
        api<EventSummary[]>("/events"),
        api<Member[]>("/members"),
      ]);
      if (active) {
        setEvents(eventRows);
        setMembers(memberRows);
      }
    });
    return () => {
      active = false;
    };
  }, [task]);
  const fresh = (): Draft => ({
    name: "",
    date: "",
    venue: "",
    slots: [{ label: "", options: config.default_options.join(", ") }],
    counters: [{ label: "", serves: [] }],
  });
  const [draft, setDraft] = useState<Draft>(fresh);
  function loadForEdit(event: EventDetail) {
    setDraft({
      name: event.name,
      date: event.date,
      venue: event.venue,
      slots: event.slots.map((s) => ({
        label: s.label,
        options: s.options.map((o) => o.label).join(", "),
      })),
      counters: event.counters.map((c) => ({
        label: c.label,
        serves: event.slots.flatMap((s, si) =>
          s.options.flatMap((o, oi) =>
            c.serves.includes(o.id) ? [`S${si + 1}/O${oi + 1}`] : [],
          ),
        ),
      })),
    });
    setEditing(true);
  }
  const paths = draft.slots.flatMap((s, si) =>
    s.options
      .split(",")
      .map((o) => o.trim())
      .filter(Boolean)
      .map((o, oi) => ({
        path: `S${si + 1}/O${oi + 1}`,
        label: s.label + " / " + o,
      })),
  );
  return (
    <div className="workspace">
      <section className="card">
        <h2>{text.events}</h2>
        <button
          onClick={() => {
            setSelected(null);
            setDraft(fresh());
            setEditing(true);
          }}
        >
          {text.addEvent}
        </button>
        <ul className="records">
          {events.map((event) => (
            <li key={event.id}>
              <button
                className="record"
                disabled={busy}
                onClick={() =>
                  void task(async () => {
                    setSelected(await api<EventDetail>("/events/" + event.id));
                    setEditing(false);
                    setChoices({});
                    setMember("");
                  })
                }
              >
                <strong>{event.name}</strong>
                <span>
                  {event.date} · {event.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="card">
        {editing ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void task(async () => {
                const value = await api<EventDetail>(
                  "/events" + (selected ? "/" + selected.id : ""),
                  selected ? "PUT" : "POST",
                  {
                    name: draft.name,
                    date: draft.date,
                    venue: draft.venue,
                    revision: selected?.revision ?? 1,
                    slots: draft.slots.map((s, si) => ({
                      code: `S${si + 1}`,
                      label: s.label,
                      options: s.options
                        .split(",")
                        .map((o) => o.trim())
                        .filter(Boolean)
                        .map((o, oi) => ({ code: `O${oi + 1}`, label: o })),
                    })),
                    counters: draft.counters,
                  },
                );
                setSelected(value);
                setEditing(false);
                await refresh();
              });
            }}
          >
            <h2>{selected ? text.editEvent : text.addEvent}</h2>
            <label>
              {text.eventName}
              <input
                required
                maxLength={120}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>
            <label>
              {text.date}
              <input
                required
                type="date"
                value={draft.date}
                onChange={(e) => setDraft({ ...draft, date: e.target.value })}
              />
            </label>
            <label>
              {text.venue}
              <input
                maxLength={160}
                value={draft.venue}
                onChange={(e) => setDraft({ ...draft, venue: e.target.value })}
              />
            </label>
            {draft.slots.map((slot, index) => (
              <fieldset key={index}>
                <legend>
                  {text.slot} {index + 1}
                </legend>
                <label>
                  {text.slotName}
                  <input
                    required
                    maxLength={80}
                    value={slot.label}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        slots: draft.slots.map((s, i) =>
                          i === index ? { ...s, label: e.target.value } : s,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  {text.options}
                  <input
                    required
                    value={slot.options}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        slots: draft.slots.map((s, i) =>
                          i === index ? { ...s, options: e.target.value } : s,
                        ),
                        counters: draft.counters.map((c) => ({
                          ...c,
                          serves: [],
                        })),
                      })
                    }
                  />
                </label>
              </fieldset>
            ))}
            {draft.slots.length < 6 && (
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setDraft({
                    ...draft,
                    slots: [
                      ...draft.slots,
                      { label: "", options: config.default_options.join(", ") },
                    ],
                  })
                }
              >
                {text.addSlot}
              </button>
            )}
            {draft.counters.map((counter, index) => (
              <fieldset key={index}>
                <legend>
                  {text.counter} {index + 1}
                </legend>
                <label>
                  {text.counterName}
                  <input
                    required
                    maxLength={80}
                    value={counter.label}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        counters: draft.counters.map((c, i) =>
                          i === index ? { ...c, label: e.target.value } : c,
                        ),
                      })
                    }
                  />
                </label>
                <p>{text.serves}</p>
                {paths.map((path) => (
                  <label className="check" key={path.path}>
                    <input
                      type="checkbox"
                      checked={counter.serves.includes(path.path)}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          counters: draft.counters.map((c, i) =>
                            i === index
                              ? {
                                  ...c,
                                  serves: e.target.checked
                                    ? [...c.serves, path.path]
                                    : c.serves.filter((p) => p !== path.path),
                                }
                              : c,
                          ),
                        })
                      }
                    />
                    {path.label}
                  </label>
                ))}
              </fieldset>
            ))}
            {draft.counters.length < 2 && (
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setDraft({
                    ...draft,
                    counters: [...draft.counters, { label: "", serves: [] }],
                  })
                }
              >
                {text.addCounter}
              </button>
            )}
            <button disabled={busy}>{text.saveEvent}</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditing(false)}
            >
              {text.cancel}
            </button>
          </form>
        ) : selected ? (
          <>
            <h2>{selected.name}</h2>
            <p>
              {selected.date} · {selected.venue} · {selected.status}
            </p>
            {selected.status === "DRAFT" &&
              selected.registrations.length === 0 && (
                <button
                  className="secondary"
                  onClick={() => loadForEdit(selected)}
                >
                  {text.editEvent}
                </button>
              )}
            <h3>{text.choices}</h3>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void task(async () => {
                  await api("/events/" + selected.id + "/choices", "POST", {
                    member_id: member,
                    choices,
                  });
                  setSelected(await api<EventDetail>("/events/" + selected.id));
                });
              }}
            >
              <label>
                {text.member}
                <select
                  required
                  value={member}
                  onChange={(e) => {
                    setMember(e.target.value);
                    setChoices(
                      selected.registrations.find(
                        (r) => r.member_id === e.target.value,
                      )?.choices ?? {},
                    );
                  }}
                >
                  <option value="">{text.choose}</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} · {m.member_code}
                    </option>
                  ))}
                </select>
              </label>
              {selected.slots.map((slot) => (
                <label key={slot.id}>
                  {slot.label}
                  <select
                    required
                    value={choices[slot.id] ?? ""}
                    onChange={(e) =>
                      setChoices({ ...choices, [slot.id]: e.target.value })
                    }
                  >
                    <option value="">{text.choose}</option>
                    {slot.options.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <button disabled={busy || selected.status === "CLOSED"}>
                {text.saveChoices}
              </button>
            </form>
            <h3>{text.optionCounts}</h3>
            <p>
              {text.registered}: {selected.registrations.length}
            </p>
            <table>
              <thead>
                <tr>
                  <th>{text.slot}</th>
                  <th>{text.option}</th>
                  <th>{text.count}</th>
                </tr>
              </thead>
              <tbody>
                {selected.slots.flatMap((s) =>
                  s.options.map((o) => (
                    <tr key={o.id}>
                      <td>{s.label}</td>
                      <td>{o.label}</td>
                      <td>{o.count}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
            <a
              className="buttonLink"
              href={"/api/events/" + selected.id + "/counts.csv"}
            >
              {text.exportCounts}
            </a>
            {selected.status === "DRAFT" && (
              <button
                disabled={busy}
                onClick={() =>
                  void task(async () => {
                    await api("/events/" + selected.id + "/ready", "POST");
                    setSelected(
                      await api<EventDetail>("/events/" + selected.id),
                    );
                    await refresh();
                  })
                }
              >
                {text.markReady}
              </button>
            )}
          </>
        ) : (
          <p>{text.pickEvent}</p>
        )}
      </section>
    </div>
  );
}
