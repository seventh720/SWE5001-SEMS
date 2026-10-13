// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../features/auth/AuthContext";
import { App } from "./App";

beforeEach(() => {
  sessionStorage.clear();
  // jsdom has no top-layer dialog implementation; native focus trapping is browser-owned.
  HTMLDialogElement.prototype.showModal = vi.fn(
    function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
      this.querySelector<HTMLButtonElement>("button")?.focus();
    },
  );
  HTMLDialogElement.prototype.close = vi.fn(
    function (this: HTMLDialogElement) {
      this.removeAttribute("open");
    },
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function mount() {
  return render(
    <AuthProvider>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </AuthProvider>,
  );
}

it("closes navigation on cancel and returns focus and scrolling to the page", () => {
  mount();
  const trigger = screen.getByRole("button", { name: /Explore/ });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog");
  expect(document.body.style.overflow).toBe("hidden");
  expect(document.activeElement).toBe(
    within(dialog).getByRole("button", { name: "Close navigation" }),
  );
  fireEvent(dialog, new Event("cancel", { cancelable: true }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.body.style.overflow).toBe("");
  expect(document.activeElement).toBe(trigger);
});
it("navigates from the overlay and closes it", () => {
  mount();
  fireEvent.click(screen.getByRole("button", { name: /Explore/ }));
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("link", {
      name: /Join the community/,
    }),
  );
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("heading", { name: "Welcome back" })).toBeTruthy();
});
it("starts with motion paused when the system requests reduced motion", () => {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
  const { container } = mount();
  expect(container.querySelector(".motion-paused")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Enable motion" }));
  expect(container.querySelector(".motion-paused")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Pause motion" }));
  expect(container.querySelector(".motion-paused")).toBeTruthy();
});
