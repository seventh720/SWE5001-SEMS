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

it("turns an opening pre-registration into a direct registration button", async () => {
  vi.useFakeTimers({toFake:["Date","setInterval","clearInterval"]});
  vi.setSystemTime(new Date("2030-01-01T00:00:00Z"));
  try {
    sessionStorage.setItem("sems-auth",JSON.stringify({token:"test",user:{id:"u1",username:"Alex",roles:["ATTENDEE"]}}));
    const item={eventId:"e1",ticketTypeId:"t1",eventTitle:"Opening workshop",opensAt:"2030-01-01T00:00:02Z",closesAt:"2030-01-02T00:00:00Z",startsAt:"2030-01-03T00:00:00Z",status:"WAITING"};
    const fetch=vi.fn().mockImplementation(async (url:string)=>new Response(JSON.stringify({items:url.includes("pre-registrations")?[{...item,status:Date.now()>=Date.parse(item.opensAt)?"READY":"WAITING"}]:[]})));
    vi.stubGlobal("fetch",fetch);
    render(<AuthProvider><MemoryRouter><App/></MemoryRouter></AuthProvider>);
    await screen.findByRole("link",{name:"Review pre-registration →"});
    const {act}=await import("@testing-library/react");await act(async()=>{vi.advanceTimersByTime(3000);});
    const link=await screen.findByRole("link",{name:"Register now →"});
    expect(link.className).toBe("primary-button");
    expect(link.getAttribute("href")).toBe("/events/e1?preRegistration=t1#ticket-t1");
    expect(fetch.mock.calls.filter(c=>String(c[0]).includes("pre-registrations"))).toHaveLength(2);
  } finally {vi.useRealTimers();}
});
it("does not offer registration for closed, ended or sold-out reservations", async()=>{
 sessionStorage.setItem("sems-auth",JSON.stringify({token:"test",user:{id:"u1",username:"Alex",roles:["ATTENDEE"]}}));
 const base={ticketTypeId:"t1",eventTitle:"Unavailable",opensAt:"2020-01-01T00:00:00Z",closesAt:"2099-01-01T00:00:00Z",startsAt:"2099-01-02T00:00:00Z"};
 vi.stubGlobal("fetch",vi.fn().mockImplementation(async(url:string)=>new Response(JSON.stringify({items:url.includes("pre-registrations")?[{...base,eventId:"paused",status:"CLOSED"},{...base,eventId:"sold",status:"SOLD_OUT"},{...base,eventId:"ended",status:"READY",startsAt:"2020-02-01T00:00:00Z"}]:[]}))));
 render(<AuthProvider><MemoryRouter><App/></MemoryRouter></AuthProvider>);
 await screen.findByText("Currently sold out");expect(screen.queryByRole("link",{name:"Register now →"})).toBeNull();
});
