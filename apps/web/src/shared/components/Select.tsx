import { useEffect, useId, useRef, useState } from "react";
export function Select({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  function focus(n: number) {
    root.current
      ?.querySelectorAll<HTMLButtonElement>('[role="option"]')
      [n]?.focus();
  }
  useEffect(() => {
    if (open)
      focus(
        Math.max(
          0,
          options.findIndex((o) => o.value === value),
        ),
      );
  }, [open]);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div
      className="custom-select"
      ref={root}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
      }}
    >
      <span id={`${id}-label`} className="field-label">
        {label}
      </span>
      <button
        type="button"
        ref={trigger}
        role="combobox"
        disabled={disabled}
        aria-expanded={open}
        aria-controls={`${id}-options`}
        aria-labelledby={`${id}-label ${id}-value`}
        aria-haspopup="listbox"
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span id={`${id}-value`}>
          {options.find((o) => o.value === value)?.label ?? "Choose an option"}
        </span>
        <span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div
          id={`${id}-options`}
          role="listbox"
          aria-labelledby={`${id}-label`}
          className="select-options"
          onKeyDown={(e) => {
            const i = Array.from(
              root.current!.querySelectorAll('[role="option"]'),
            ).indexOf(document.activeElement!);
            if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              close();
            } else if (
              ["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)
            ) {
              e.preventDefault();
              focus(
                e.key === "Home"
                  ? 0
                  : e.key === "End"
                    ? options.length - 1
                    : (i + (e.key === "ArrowDown" ? 1 : -1) + options.length) %
                      options.length,
              );
            }
          }}
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="option"
              aria-selected={o.value === value}
              onClick={() => {
                onChange(o.value);
                close();
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
