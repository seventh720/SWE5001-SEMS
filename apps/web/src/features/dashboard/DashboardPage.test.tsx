// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { App } from "../../app/App";
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});
function mount(roles: string[]) {
  sessionStorage.setItem(
    "sems-auth",
    JSON.stringify({
      token: "test",
      user: { id: "u1", username: "Alex", roles },
    }),
  );
  const fetch = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ items: [] }))),
    );
  vi.stubGlobal("fetch", fetch);
  render(
    <AuthProvider>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </AuthProvider>,
  );
  return fetch;
}
it("replaces marketing with attendee plans without requesting organizer data", async () => {
  const fetch = mount(["ATTENDEE"]);
  await screen.findByText(/No upcoming bookings/);
  expect(screen.getByRole("heading", { name: "Hello, Alex." })).toBeTruthy();
  expect(screen.queryByText("GOOD THINGS HAPPEN TOGETHER")).toBeNull();
  expect(fetch.mock.calls.some((c) => String(c[0]).includes("organizer"))).toBe(
    false,
  );
});
it("shows organizer and administrator workspaces for assigned roles", async () => {
  mount(["ADMIN"]);
  await screen.findByRole("heading", { name: "Organizer workspace" });
  expect(screen.getByRole("link", { name: "Manage users" })).toBeTruthy();
});
it("shows the real staff availability without fabricated assignments", async () => {
  mount(["STAFF"]);
  await screen.findByText(
    /Staff assignment and check-in are not available yet/,
  );
  expect(
    screen.queryByRole("heading", { name: "Organizer workspace" }),
  ).toBeNull();
});
