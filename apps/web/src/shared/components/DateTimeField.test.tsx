// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DateTimeField } from "./DateTimeField";
import { Select } from "./Select";
import { validDateTime, toInstant, singaporeInput } from "./dateTime";
afterEach(cleanup);
it("validates real calendar dates and converts Singapore time without browser timezone", () => {
  expect(validDateTime("2028-02-29T23:59")).toBe(true);
  expect(validDateTime("2027-02-29T12:00")).toBe(false);
  expect(validDateTime("2028-04-31T12:00")).toBe(false);
  expect(validDateTime("2028-01-01T24:00")).toBe(false);
  expect(toInstant("2030-01-01T08:00")).toBe("2030-01-01T00:00:00.000Z");
  expect(singaporeInput("2029-12-31T16:30:00Z")).toBe("2030-01-01T00:30");
});
it("uses an English leap-year calendar and clamps day when changing months", () => {
  const change = vi.fn();
  const { container } = render(
    <DateTimeField
      label="Starts at"
      value="2028-01-31T10:30"
      onChange={change}
    />,
  );
  expect(container.querySelector('input[type="datetime-local"]')).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Choose starts at" }));
  fireEvent.click(screen.getByRole("button", { name: "Next month" }));
  expect(
    screen
      .getByRole("button", { name: "February 29, 2028" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(change).toHaveBeenCalledWith("2028-02-29T10:30");
  expect(screen.queryByLabelText("Starts at calendar")).toBeNull();
});
it("blocks an end before the start and disables editing fixed event dates", () => {
  const { rerender } = render(
    <DateTimeField
      label="Ends at"
      value="2030-01-01T10:00"
      after="2030-01-01T11:00"
      onChange={() => {}}
    />,
  );
  expect(
    (screen.getByLabelText("Ends at") as HTMLInputElement).checkValidity(),
  ).toBe(false);
  rerender(
    <DateTimeField
      label="Ends at"
      value="2030-01-01T12:00"
      disabled
      onChange={() => {}}
    />,
  );
  expect(
    (
      screen.getByRole("button", {
        name: "Choose ends at",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
it("supports keyboard navigation and selection without a native select", () => {
  const change = vi.fn();
  const { container } = render(
    <Select
      label="Category"
      value="A"
      options={[
        { value: "A", label: "Art" },
        { value: "B", label: "Music" },
      ]}
      onChange={change}
    />,
  );
  expect(container.querySelector("select")).toBeNull();
  const trigger = screen.getByRole("combobox");
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  expect(document.activeElement).toBe(
    screen.getByRole("option", { name: "Art" }),
  );
  fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
  expect(document.activeElement).toBe(
    screen.getByRole("option", { name: "Music" }),
  );
  fireEvent.click(document.activeElement!);
  expect(change).toHaveBeenCalledWith("B");
  expect(document.activeElement).toBe(trigger);
});
it("keeps the calendar open when dismissing a nested time selector and restores trigger focus", () => {
 render(<DateTimeField label="Starts at" value="2026-10-24T14:00" onChange={vi.fn()}/>);
 const trigger=screen.getByRole("button",{name:"Choose starts at"});
 fireEvent.click(trigger);
 fireEvent.click(screen.getByRole("combobox",{name:"Hour 14"}));
 fireEvent.keyDown(document.activeElement!,{key:"Escape"});
 expect(screen.queryByRole("listbox")).toBeNull();
 expect(screen.getByLabelText("Starts at calendar")).toBeTruthy();
 fireEvent.keyDown(document.activeElement!,{key:"Escape"});
 expect(screen.queryByLabelText("Starts at calendar")).toBeNull();
 expect(document.activeElement).toBe(trigger);
});
it("dismisses the calendar on an outside click without applying its draft", () => {
 const change=vi.fn();
 render(<DateTimeField label="Starts at" value="2026-10-24T14:00" onChange={change}/>);
 fireEvent.click(screen.getByRole("button",{name:"Choose starts at"}));
 fireEvent.click(screen.getByRole("button",{name:"October 25, 2026"}));
 fireEvent.pointerDown(document.body);
 expect(screen.queryByLabelText("Starts at calendar")).toBeNull();
 expect(change).not.toHaveBeenCalled();
});
