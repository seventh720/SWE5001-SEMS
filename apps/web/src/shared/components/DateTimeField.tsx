import { useEffect, useId, useRef, useState } from "react";
import {useOverlay} from "./useOverlay";
import { Select } from "./Select";
import { singaporeInput, validDateTime } from "./dateTime";
const months = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const pad = (n: number) => String(n).padStart(2, "0");
export function DateTimeField({
  label,
  value,
  onChange,
  disabled = false,
  after,
  atOrBefore,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  after?: string;
  atOrBefore?: string;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  const controls = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  useOverlay(open && !disabled, panel, controls, 380, Infinity);
  const [draft, setDraft] = useState("");
  const date = validDateTime(draft)
    ? draft
    : singaporeInput(new Date().toISOString());
  const year = Number(date.slice(0, 4)),
    month = Number(date.slice(5, 7)) - 1,
    day = Number(date.slice(8, 10));
  const valid = (s: string) =>
    validDateTime(s) &&
    (!after || !validDateTime(after) || s > after) &&
    (!atOrBefore || !validDateTime(atOrBefore) || s <= atOrBefore);
  const error =
    value && !valid(value)
      ? "Choose a valid date/time within the event schedule."
      : "";
  useEffect(() => {
    input.current?.setCustomValidity(error);
  }, [error]);
  useEffect(() => {
    if (!open) return;
    const dismiss = (e: PointerEvent) => {
      if (e.target instanceof Node && !root.current?.contains(e.target))
        setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  function shift(delta: number) {
    const next = new Date(Date.UTC(year, month + delta, 1));
    const y = next.getUTCFullYear(),
      m = next.getUTCMonth();
    if (y < 1900 || y > 9999) return;
    const d = Math.min(day, new Date(Date.UTC(y, m + 1, 0)).getUTCDate());
    setDraft(`${y}-${pad(m + 1)}-${pad(d)}${date.slice(10)}`);
  }
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const offset = new Date(Date.UTC(year, month, 1)).getUTCDay();
  return (
    <div
      className="date-time-field"
      ref={root}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.preventDefault();
          close();
        }
      }}
    >
      <label htmlFor={id}>{label}</label>
      <div className="date-time-controls" ref={controls}>
        <input
          id={id}
          ref={input}
          type="text"
          disabled={disabled}
          required
          maxLength={16}
          placeholder="YYYY-MM-DD HH:mm"
          pattern="[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}"
          value={value.replace("T", " ")}
          onChange={(e) => onChange(e.target.value.replace(" ", "T"))}
          aria-describedby={`${id}-hint`}
          aria-invalid={!!error}
        />
        <button
          type="button"
          ref={trigger}
          disabled={disabled}
          aria-label={`Choose ${label.toLowerCase()}`}
          aria-expanded={open}
          aria-controls={`${id}-calendar`}
          onClick={() => {
            if (open) close();
            else {
              setDraft(
                validDateTime(value)
                  ? value
                  : validDateTime(after ?? "")
                    ? after!
                    : singaporeInput(new Date().toISOString()),
              );
              setOpen(true);
            }
          }}
        >
          Calendar
        </button>
      </div>
      <span id={`${id}-hint`} className={error ? "field-error" : "muted"}>
        {error || "Singapore time · 24-hour"}
      </span>
      {open && !disabled && (
        <section
          id={`${id}-calendar`}
          ref={panel}
          className="english-calendar"
          aria-label={`${label} calendar`}
          lang="en"
        >
          <div className="calendar-month">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => shift(-1)}
            >
              ‹
            </button>
            <strong aria-live="polite">
              {months[month]} {year}
            </strong>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => shift(1)}
            >
              ›
            </button>
          </div>
          <div className="calendar-days">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <span key={d}>{d}</span>
            ))}
            {Array.from({ length: offset }, (_, n) => (
              <span key={`blank-${n}`} />
            ))}
            {Array.from({ length: days }, (_, n) => n + 1).map((d) => (
              <button
                type="button"
                key={d}
                aria-label={`${months[month]} ${d}, ${year}`}
                aria-pressed={d === day}
                onClick={() =>
                  setDraft(`${date.slice(0, 8)}${pad(d)}${date.slice(10)}`)
                }
              >
                {d}
              </button>
            ))}
          </div>
          <div className="calendar-time">
            <Select
              label="Hour"
              value={date.slice(11, 13)}
              options={Array.from({ length: 24 }, (_, n) => ({
                value: pad(n),
                label: pad(n),
              }))}
              onChange={(v) =>
                setDraft(`${date.slice(0, 11)}${v}${date.slice(13)}`)
              }
            />
            <Select
              label="Minute"
              value={date.slice(14, 16)}
              options={Array.from({ length: 60 }, (_, n) => ({
                value: pad(n),
                label: pad(n),
              }))}
              onChange={(v) => setDraft(`${date.slice(0, 14)}${v}`)}
            />
          </div>
          {!valid(date) && (
            <p className="field-error">
              Select a time within the event schedule.
            </p>
          )}
          <div className="actions">
            <button
              type="button"
              className="primary-button"
              disabled={!valid(date)}
              onClick={() => {
                onChange(date);
                close();
              }}
            >
              Apply
            </button>
            <button type="button" className="secondary-button" onClick={close}>
              Cancel
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
