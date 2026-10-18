// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AdminUsersPage } from "./AdminUsersPage";
const auth = vi.hoisted(() => ({
  token: "admin-token",
  user: { roles: ["ADMIN"] },
}));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
const fetchMock = vi.fn<typeof fetch>();
const user = {
  id: "alice",
  username: "Alice",
  email: "alice@example.com",
  status: "ACTIVE",
  roles: ["ATTENDEE"],
};
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
function mount() {
  render(
    <MemoryRouter initialEntries={["/admin/users"]}>
      <Routes>
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/" element={<p>Dashboard</p>} />
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  auth.user.roles = ["ADMIN"];
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("prevents removing the last role and saves additional roles with authentication", async () => {
  fetchMock
    .mockResolvedValueOnce(response({items:[user],totalPages:1}))
    .mockResolvedValueOnce(
      response({ ...user, roles: ["ATTENDEE", "ADMIN"] }),
    );
  mount();
  const attendee = await screen.findByLabelText("Attendee");
  fireEvent.click(attendee);
  expect((attendee as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByLabelText("System Administrator"));
  fireEvent.click(screen.getByRole("button", { name: "Save roles" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/admin/users/alice/roles");
  expect(fetchMock.mock.calls[1][1]?.headers).toMatchObject({
    Authorization: "Bearer admin-token",
  });
  expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string).roles).toEqual([
    "ATTENDEE",
    "ADMIN",
  ]);
  await screen.findByRole("button", { name: "Save roles" });
});
it("retains selected roles after a failed save and permits retry", async () => {
  fetchMock
    .mockResolvedValueOnce(response({items:[user],totalPages:1}))
    .mockResolvedValueOnce(response({ detail: "Unable to save roles" }, 500))
    .mockResolvedValueOnce(response({ ...user, roles: ["ATTENDEE", "ADMIN"] }));
  mount();
  fireEvent.click(await screen.findByLabelText("System Administrator"));
  fireEvent.click(screen.getByRole("button", { name: "Save roles" }));
  await screen.findByText("Unable to save roles");
  expect(
    (screen.getByLabelText("System Administrator") as HTMLInputElement).checked,
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Save roles" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  await waitFor(() =>
    expect(screen.queryByText("Unable to save roles")).toBeNull(),
  );
});
it("redirects non-admin users without requesting user data", () => {
  auth.user.roles = ["ATTENDEE"];
  mount();
  expect(screen.getByText("Dashboard")).toBeTruthy();
  expect(fetchMock).not.toHaveBeenCalled();
});
