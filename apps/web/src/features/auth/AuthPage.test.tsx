// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import { AuthPage } from "./AuthPage";
const fetchMock = vi.fn<typeof fetch>();
const user = {
  id: "alice",
  username: "Alice",
  email: "alice@example.com",
  roles: ["ATTENDEE"],
  status: "ACTIVE",
};
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
function Account() {
  const { user, logout } = useAuth();
  return (
    <>
      <p>Account: {user?.username}</p>
      <button onClick={logout}>Logout</button>
    </>
  );
}
function EventDetailProbe() {
  const location = useLocation();
  return (
    <p>
      Event detail {location.pathname}
      {location.search}
    </p>
  );
}
function mount() {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/" element={<Account />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}
function credentials() {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: user.email },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "Password123" },
  });
}
beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
it("logs in through the real provider, persists the session and clears it on logout", async () => {
  fetchMock.mockResolvedValue(response({ accessToken: "token", user }));
  mount();
  credentials();
  fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
  await screen.findByText("Account: Alice");
  expect(JSON.parse(sessionStorage.getItem("sems-auth")!).token).toBe("token");
  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/login");
  fireEvent.click(screen.getByText("Logout"));
  expect(sessionStorage.getItem("sems-auth")).toBeNull();
});
it("shows login errors and allows a subsequent successful attempt", async () => {
  fetchMock
    .mockResolvedValueOnce(
      response({ detail: "Invalid email or password" }, 401),
    )
    .mockResolvedValueOnce(response({ accessToken: "token", user }));
  mount();
  credentials();
  fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
  await screen.findByText("Invalid email or password");
  expect(sessionStorage.getItem("sems-auth")).toBeNull();
  fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
  await screen.findByText("Account: Alice");
});
it("registers before logging in and preserves the server-assigned role", async () => {
  fetchMock
    .mockResolvedValueOnce(response(user, 201))
    .mockResolvedValueOnce(response({ accessToken: "token", user }));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  credentials();
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "Alice" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Register and login" }));
  await screen.findByText("Account: Alice");
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
    "/api/v1/auth/register",
    "/api/v1/auth/login",
  ]);
  expect(JSON.parse(sessionStorage.getItem("sems-auth")!).user.roles).toEqual([
    "ATTENDEE",
  ]);
});
it("returns to the intended event page after login", async () => {
  fetchMock.mockResolvedValue(response({ accessToken: "token", user }));
  render(
    <AuthProvider>
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/login",
            state: {
              from: { pathname: "/events/e1", search: "?keyword=Open" },
            },
          },
        ]}
      >
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/events/:id" element={<EventDetailProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
  credentials();
  fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
  expect(
    await screen.findByText("Event detail /events/e1?keyword=Open"),
  ).toBeTruthy();
});

it("shows a duplicate username error and lets the user choose another name", async () => {
  fetchMock
    .mockResolvedValueOnce(
      response({ detail: "Username is already registered" }, 409),
    )
    .mockResolvedValueOnce(response({ ...user, username: "alice2" }, 201))
    .mockResolvedValueOnce(
      response({ accessToken: "token", user: { ...user, username: "alice2" } }),
    );
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  credentials();
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "Alice" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Register and login" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Username is already registered",
  );
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "alice2" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Register and login" }));
  await screen.findByText("Account: alice2");
});
