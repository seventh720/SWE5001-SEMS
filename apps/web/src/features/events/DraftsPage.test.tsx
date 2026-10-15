// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { DraftsPage } from "./DraftsPage";
const fetchMock=vi.fn<typeof fetch>();
const event={organizationId:"org1",visibility:"PUBLIC",id:"e1",title:"Workshop",description:"Description",location:"Campus",startsAt:"2030-01-01T10:00:00Z",endsAt:"2030-01-01T12:00:00Z",capacity:20,version:2,status:"PUBLISHED",salesConfigured:true};
const inventory={version:4,ticketTypes:[{id:"t1",name:"General",quota:10,opensAt:"2029-01-01T10:00:00Z",closesAt:event.startsAt}]};
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
function mount(roles=["ORGANIZER"],path="/organizer/events?organizationId=org1&edit=e1") {sessionStorage.setItem("sems-auth",JSON.stringify({token:"token",user:{roles}}));render(<AuthProvider><MemoryRouter initialEntries={[path]}><Routes><Route path="/organizer/events" element={<DraftsPage/>}/><Route path="/" element={<p>Home</p>}/></Routes></MemoryRouter></AuthProvider>);}
beforeEach(()=>{vi.stubGlobal("scrollTo",vi.fn());vi.stubGlobal("fetch",fetchMock);fetchMock.mockReset();fetchMock.mockImplementation(async(input)=>response(String(input).includes("/me/organizations")?[{id:"org1",name:"Society",role:"ORG_ADMIN"}]:String(input).includes("ticket-types")?inventory:String(input).includes("&page=")?{items:[event,{...event,id:"e2",title:"Other event"}],totalPages:1,totalElements:2}:event));});
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();});
it("requires an organization selection before creating an event",async()=>{fetchMock.mockImplementation(async()=>response([]));mount(["ATTENDEE"],"/organizer/events");await screen.findByText("Select an organization");expect((screen.getByRole("button",{name:"Create event"}) as HTMLButtonElement).disabled).toBe(true);expect(fetchMock.mock.calls.some(([p])=>String(p).includes("/organizer/events"))).toBe(false);});
it("edits only the selected event, locks only registration rules, and saves details and tickets together below the ticket fields",async()=>{
 mount();await screen.findByLabelText("Ticket name 1");
 expect(screen.queryByText("Other event")).toBeNull();expect(screen.queryByRole("link",{name:"View public event"})).toBeNull();
 expect(screen.getByLabelText("Full name").closest("fieldset")?.disabled).toBe(true);
 expect(screen.getByLabelText("Quota 1").closest("fieldset")?.disabled).toBe(false);
 fireEvent.change(screen.getByLabelText("Ticket name 1"),{target:{value:"Updated ticket"}});
 expect((screen.getByRole("combobox",{name:/Event visibility/}) as HTMLButtonElement).disabled).toBe(false);
 fireEvent.click(screen.getByRole("combobox",{name:/Event visibility/}));
 fireEvent.click(screen.getByRole("option",{name:"Organization only — active members"}));
 fireEvent.change(screen.getByLabelText("Title"),{target:{value:"Updated title"}});
 const save=screen.getByRole("button",{name:"Save event changes"});
 expect(screen.getByLabelText("Quota 1").compareDocumentPosition(save)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 fireEvent.click(save);await screen.findByText(/Published event updated/);
 expect(window.scrollTo).toHaveBeenCalledTimes(1);
 const call=fetchMock.mock.calls.find(([,opts])=>opts?.method==="PUT")!;
 expect(call[0]).toBe("/api/v1/organizer/events/e1/revision");
 expect(JSON.parse(call[1]!.body as string)).toMatchObject({title:"Updated title",visibility:"ORGANIZATION_ONLY",version:2,ticketConfiguration:{version:4,ticketTypes:[{id:"t1",name:"Updated ticket",quota:10}]}});
});
it("uses publication management for published events and keeps edit inside that page",async()=>{
 mount(["ORGANIZER"],"/organizer/events?organizationId=org1");await screen.findByText("Workshop");expect(screen.getAllByRole("link",{name:"Publication management →"})).toHaveLength(2);expect(screen.queryByRole("button",{name:"Edit event"})).toBeNull();
});
it("keeps the editor open after rejected combined changes",async()=>{
 fetchMock.mockImplementation(async(input,opts)=>opts?.method==="PUT"?response({detail:"Ticket quota is below issued places"},409):response(String(input).includes("/me/organizations")?[{id:"org1",name:"Society",role:"ORG_ADMIN"}]:String(input).includes("ticket-types")?inventory:String(input).includes("&page=")?{items:[event],totalPages:1,totalElements:1}:event));
 mount();await screen.findByLabelText("Quota 1");fireEvent.click(screen.getByRole("button",{name:"Save event changes"}));await screen.findByText(/Ticket quota is below/);expect(screen.getByLabelText("Ticket name 1")).toBeTruthy();
});
it("keeps syncing feedback until the updated event itself is confirmed, even when the list is stale",async()=>{
 let submitted=false;
 let finish:((value:Response)=>void)|undefined;
 fetchMock.mockImplementation(async(input,opts)=>{
  if(String(input).includes("/me/organizations"))return response([{id:"org1",name:"Society",role:"ORG_ADMIN"}]);
  if(opts?.method==="PUT"){submitted=true;return response({...event,status:"UPDATING"});}
  if(String(input).includes("&page="))return response({items:[event],totalPages:1,totalElements:1});
  if(String(input).includes("ticket-types"))return response(inventory);
  if(submitted)return new Promise<Response>(resolve=>{finish=resolve;});
  return response(event);
 });
 mount();await screen.findByLabelText("Ticket name 1");
 fireEvent.click(screen.getByRole("button",{name:"Save event changes"}));
 await screen.findByText(/Update is syncing with ticketing/);
 expect(screen.queryByText(/Event changes saved/)).toBeNull();
 const {act}=await import("@testing-library/react");
 await act(async()=>{finish!(response({...event,version:3}));});
 await screen.findByText(/Event changes saved/);
});
