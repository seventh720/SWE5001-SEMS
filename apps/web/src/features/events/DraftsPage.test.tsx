// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { DraftsPage } from "./DraftsPage";
const fetchMock = vi.fn<typeof fetch>();
const draft = {
  id: "e1",
  title: "Seminar",
  description: "A seminar",
  location: "Campus",
  startsAt: "2030-01-01T10:00:00Z",
  endsAt: "2030-01-01T11:00:00Z",
  capacity: 10,
  version: 2,
  status: "DRAFT",
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
function mount(roles = ["ORGANIZER"]) {
  sessionStorage.setItem(
    "sems-auth",
    JSON.stringify({ token: "token", user: { username: "organizer", roles } }),
  );
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/organizer/events"]}>
        <Routes>
          <Route path="/organizer/events" element={<DraftsPage />} />
          <Route path="/" element={<p>Home</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  sessionStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
it("does not request organizer data for an attendee", async () => {
  mount(["ATTENDEE"]);
  await screen.findByText("Home");
  expect(fetchMock).not.toHaveBeenCalled();
});
it("submits an edit with its loaded version and refreshes the list", async () => {
  fetchMock
    .mockResolvedValueOnce(
      response({ items: [draft], totalPages: 1, totalElements: 1 }),
    )
    .mockResolvedValueOnce(response(draft))
    .mockResolvedValueOnce(response({ ...draft, version: 3 }))
    .mockResolvedValueOnce(
      response({ items: [draft], totalPages: 1, totalElements: 1 }),
    );
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Edit draft" }));
  await screen.findByDisplayValue("Seminar");
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Updated seminar" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await screen.findByText("Draft saved.");
  const options = fetchMock.mock.calls[2][1]!;
  expect(options.method).toBe("PUT");
  expect(JSON.parse(options.body as string)).toMatchObject({
    version: 2,
    title: "Updated seminar",
  });
});
it("keeps edits visible and offers reload after a version conflict", async () => {
  fetchMock
    .mockResolvedValueOnce(
      response({ items: [draft], totalPages: 1, totalElements: 1 }),
    )
    .mockResolvedValueOnce(response(draft))
    .mockResolvedValueOnce(
      response({ detail: "Event changed; reload before editing" }, 409),
    );
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Edit draft" }));
  await screen.findByDisplayValue("Seminar");
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Event changed",
  );
  expect(screen.getByLabelText("Title")).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Reload latest draft" }),
  ).toBeTruthy();
});
