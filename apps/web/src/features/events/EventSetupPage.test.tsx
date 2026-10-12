// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { EventSetupPage } from "./EventSetupPage";
const fetchMock = vi.fn<typeof fetch>();
const event = {
  id: "e1",
  title: "Seminar",
  capacity: 30,
  startsAt: "2030-01-01T10:00:00Z",
  endsAt: "2030-01-01T12:00:00Z",
  version: 1,
  status: "DRAFT",
  salesConfigured: true,
};
const inventory = {
  version: 1,
  state: "DRAFT",
  ticketTypes: [
    {
      name: "General",
      quota: 30,
      opensAt: "2029-12-01T10:00:00Z",
      closesAt: "2030-01-01T10:00:00Z",
    },
  ],
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
function mount() {
  sessionStorage.setItem(
    "sems-auth",
    JSON.stringify({ token: "token", user: { roles: ["ORGANIZER"] } }),
  );
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/organizer/events/e1/setup"]}>
        <Routes>
          <Route
            path="/organizer/events/:id/setup"
            element={<EventSetupPage />}
          />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
it("requires confirmation and submits the saved event and inventory versions", async () => {
  fetchMock
    .mockResolvedValueOnce(response(event))
    .mockResolvedValueOnce(response(inventory))
    .mockResolvedValueOnce(response({ ...event, status: "PUBLISHED" }));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Publish event" }));
  expect(fetchMock).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Confirm publication" }));
  await screen.findByText("Event published.");
  expect(JSON.parse(fetchMock.mock.calls[2][1]!.body as string)).toEqual({
    version: 1,
    ticketVersion: 1,
  });
  expect(screen.getByRole("link", { name: "View public event" })).toBeTruthy();
});
it("blocks publication until ticket changes are saved and prevents excessive quota", async () => {
  fetchMock
    .mockResolvedValueOnce(response(event))
    .mockResolvedValueOnce(response(inventory));
  mount();
  const quota = await screen.findByLabelText("Quota 1");
  fireEvent.change(quota, { target: { value: "31" } });
  expect(
    (screen.getByRole("button", { name: "Publish event" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  expect(
    (
      screen.getByRole("button", {
        name: "Save ticket types",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("Reduce");
});
it("shows a pending publication rather than claiming it succeeded", async () => {
  fetchMock
    .mockResolvedValueOnce(response(event))
    .mockResolvedValueOnce(response(inventory))
    .mockResolvedValueOnce(response({ ...event, status: "PUBLISHING" }, 202));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Publish event" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm publication" }));
  await screen.findByText(
    "Publication is pending. This page will update automatically.",
  );
  expect(screen.queryByRole("link", { name: "View public event" })).toBeNull();
});
