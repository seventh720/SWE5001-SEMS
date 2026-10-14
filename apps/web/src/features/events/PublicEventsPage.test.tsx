// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { PublicEventsPage } from "./PublicEventsPage";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("browses anonymously and encodes search terms", async () => {
  const mock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(
      new Response(JSON.stringify({ items: [], totalPages: 0 })),
    );
  vi.stubGlobal("fetch", mock);
  render(
    <AuthProvider><MemoryRouter>
      <PublicEventsPage />
    </MemoryRouter></AuthProvider>,
  );
  await screen.findByText("No upcoming events found.");
  fireEvent.change(screen.getByLabelText("Search events"), {
    target: { value: "Seminar & workshop" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByText("No upcoming events found.");
  expect(mock.mock.calls[1][0]).toContain("keyword=Seminar%20%26%20workshop");
  expect(mock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
});
it("combines a real category filter with the search query", async () => {
  const mock = vi
    .fn<typeof fetch>()
    .mockImplementation(
      async () => new Response(JSON.stringify({ items: [], totalPages: 0 })),
    );
  vi.stubGlobal("fetch", mock);
  render(
    <AuthProvider><MemoryRouter>
      <PublicEventsPage />
    </MemoryRouter></AuthProvider>,
  );
  await screen.findByText("No upcoming events found.");
  fireEvent.click(screen.getByRole("combobox", { name: /Filter by category/ }));
  fireEvent.click(screen.getByRole("option", { name: "Technology" }));
  await screen.findByText("No upcoming events found.");
  expect(mock.mock.lastCall?.[0]).toContain("category=TECH");
});

it("targets the selected ticket and loads its pre-registration details", async()=>{
 const {PublicEventDetail}=await import("./PublicEventsPage");const {AuthProvider}=await import("../auth/AuthContext");const {Routes,Route}=await import("react-router-dom");
 const scroll=vi.fn();HTMLElement.prototype.scrollIntoView=scroll;
 sessionStorage.setItem("sems-auth",JSON.stringify({token:"test",user:{id:"u1",roles:["ATTENDEE"]}}));
 const ticket={id:"t2",name:"Reserved option",available:10,opensAt:"2020-01-01T00:00:00Z",closesAt:"2099-01-01T00:00:00Z"};
 vi.stubGlobal("fetch",vi.fn().mockImplementation(async(url:string)=>new Response(JSON.stringify(url.includes("pre-registrations")?{ticketTypeId:"t2",quantity:2,attendeeInfo:{}}:url.endsWith("ticket-types")?{ticketTypes:[{...ticket,id:"t1",name:"Other option"},ticket]}:{id:"e1",title:"Workshop",location:"Campus",description:"Workshop details",startsAt:"2099-01-02T00:00:00Z",endsAt:"2099-01-02T02:00:00Z"}))));
 try {
 render(<AuthProvider><MemoryRouter initialEntries={["/events/e1?preRegistration=t2#ticket-t2"]}><Routes><Route path="/events/:id" element={<PublicEventDetail/>}/></Routes></MemoryRouter></AuthProvider>);
 await screen.findByText(/Saved pre-registration loaded/);
 const {waitFor}=await import("@testing-library/react");await waitFor(()=>expect(document.activeElement?.id).toBe("ticket-t2"));
 expect(scroll).toHaveBeenCalled();expect((screen.getByLabelText("Quantity for ticket t2") as HTMLInputElement).value).toBe("2");
 }finally{sessionStorage.clear();delete (HTMLElement.prototype as {scrollIntoView?:unknown}).scrollIntoView;}
});
