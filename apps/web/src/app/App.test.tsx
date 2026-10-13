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

it("expands navigation in the page, toggles closed and supports Escape", () => {
  mount();
  const trigger = screen.getByRole("button", { name: /Explore/ });
  fireEvent.click(trigger);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.body.style.overflow).toBe("");
  expect(
    screen.getByRole("navigation", { name: "Explore navigation" }),
  ).toBeTruthy();
  fireEvent.click(trigger);
  expect(
    screen.queryByRole("navigation", { name: "Explore navigation" }),
  ).toBeNull();
  fireEvent.click(trigger);
  fireEvent.keyDown(trigger, { key: "Escape" });
  expect(
    screen.queryByRole("navigation", { name: "Explore navigation" }),
  ).toBeNull();
  expect(document.activeElement).toBe(trigger);
});
it("closes expanded navigation after following a link", () => {
  mount();
  fireEvent.click(screen.getByRole("button", { name: /Explore/ }));
  fireEvent.click(
    within(
      screen.getByRole("navigation", { name: "Explore navigation" }),
    ).getByRole("link", { name: /Join the community/ }),
  );
  expect(
    screen.queryByRole("navigation", { name: "Explore navigation" }),
  ).toBeNull();
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
