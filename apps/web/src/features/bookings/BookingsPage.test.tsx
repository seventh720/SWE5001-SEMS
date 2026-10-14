// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { BookingsPage } from "./BookingsPage";
import { HomeLink } from "../../shared/components/HomeLink";
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); });
it("separates cancelled bookings and resets pagination when switching status", async () => {
  sessionStorage.setItem("sems-auth", JSON.stringify({token:"test",user:{id:"u1",username:"Alex",roles:["ATTENDEE"]}}));
  const fetch = vi.fn(async (url: string) => {
    const params = new URL(url,"http://localhost").searchParams;
    const cancelled = params.get("status") === "CANCELLED";
    return new Response(JSON.stringify({items:[{id:"b1",status:cancelled?"CANCELLED":"CONFIRMED",eventTitle:cancelled?"Cancelled workshop":"Confirmed workshop",quantity:1,ticketName:"General",startsAt:"2030-01-01T10:00:00Z",eventLocation:"Campus"}],totalPages:cancelled?1:2}));
  });
  vi.stubGlobal("fetch",fetch);
  render(<AuthProvider><MemoryRouter><BookingsPage /></MemoryRouter></AuthProvider>);
  await screen.findByText("Confirmed workshop");
  expect(screen.getByRole("link",{name:/Back to dashboard/}).getAttribute("href")).toBe("/");
  fireEvent.click(screen.getByRole("button",{name:"Next"}));
  await screen.findByText("Confirmed workshop");
  expect(fetch.mock.calls.some(([url])=>url.includes("page=1"))).toBe(true);
  fireEvent.click(screen.getByRole("button",{name:"Cancelled"}));
  await screen.findByText("Cancelled workshop");
  expect(screen.queryByText("Confirmed workshop")).toBeNull();
  expect(screen.queryByRole("link",{name:/View tickets/})).toBeNull();
  expect(screen.getByRole("link",{name:/View cancellation/})).toBeTruthy();
  expect(fetch.mock.calls.at(-1)?.[0]).toBe("/api/v1/bookings?page=0&size=10&status=CANCELLED");
  expect(screen.getByRole("button",{name:"Cancelled"}).getAttribute("aria-pressed")).toBe("true");
});
it("uses the home destination label for guests", () => {
  render(<AuthProvider><MemoryRouter><HomeLink /></MemoryRouter></AuthProvider>);
  expect(screen.getByRole("link",{name:/Back to home/}).getAttribute("href")).toBe("/");
});
