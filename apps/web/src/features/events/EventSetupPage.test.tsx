// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { EventSetupPage } from "./EventSetupPage";
const fetchMock=vi.fn<typeof fetch>();
const event={id:"e1",title:"Seminar",description:"Community seminar",location:"Campus",capacity:30,startsAt:"2030-01-01T10:00:00Z",endsAt:"2030-01-01T12:00:00Z",version:1,status:"DRAFT",salesConfigured:true};
const inventory={version:2,ticketTypes:[{id:"t1",name:"General",quota:30,opensAt:"2029-12-01T10:00:00Z",closesAt:event.startsAt}]};
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
function mount(){sessionStorage.setItem("sems-auth",JSON.stringify({token:"token",user:{roles:["ORGANIZER"]}}));render(<AuthProvider><MemoryRouter initialEntries={["/organizer/events/e1/setup"]}><Routes><Route path="/organizer/events/:id/setup" element={<EventSetupPage/>}/></Routes></MemoryRouter></AuthProvider>);}
beforeEach(()=>{fetchMock.mockReset();vi.stubGlobal("fetch",fetchMock);});afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();});
it("previews saved details and requires confirmation for initial publication",async()=>{
 fetchMock.mockResolvedValueOnce(response(event)).mockResolvedValueOnce(response(inventory)).mockResolvedValueOnce(response({...event,status:"PUBLISHED"}));mount();
 fireEvent.click(await screen.findByRole("button",{name:"Publish event"}));expect(fetchMock).toHaveBeenCalledTimes(2);
 expect(screen.queryByLabelText("Quota 1")).toBeNull();expect(screen.getByText("Community seminar")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Confirm publication"}));await screen.findByText("Event published.");
 expect(JSON.parse(fetchMock.mock.calls[2][1]!.body as string)).toEqual({version:1,ticketVersion:2});expect(screen.getByRole("heading",{name:"Publication management"})).toBeTruthy();
});
it.each([["PUBLISHED","Pause publication","Confirm pause","PAUSED"],["PAUSED","Resume publication","Confirm resume","PUBLISHED"]])("manages %s via recoverable revision",async(status,button,confirm,next)=>{
 fetchMock.mockResolvedValueOnce(response({...event,status})).mockResolvedValueOnce(response(inventory)).mockResolvedValueOnce(response({...event,status:next}));mount();
 fireEvent.click(await screen.findByRole("button",{name:button}));fireEvent.click(screen.getByRole("button",{name:confirm}));await screen.findByText(next==="PAUSED"?"Publication paused. Existing tickets remain valid.":"Publication resumed.");
 expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/organizer/events/e1/revision");expect(JSON.parse(fetchMock.mock.calls[2][1]!.body as string).publicationStatus).toBe(next);
});
it("reports pending synchronization without claiming publication completed",async()=>{
 fetchMock.mockResolvedValueOnce(response(event)).mockResolvedValueOnce(response(inventory)).mockResolvedValueOnce(response({...event,status:"PUBLISHING"},202));mount();fireEvent.click(await screen.findByRole("button",{name:"Publish event"}));fireEvent.click(screen.getByRole("button",{name:"Confirm publication"}));await screen.findByText(/Publication change is syncing/);expect(screen.queryByRole("link",{name:"View event"})).toBeNull();
});
it("requires a reason for permanent cancellation and removes edit/resume controls",async()=>{
 fetchMock.mockResolvedValueOnce(response({...event,status:"PAUSED"})).mockResolvedValueOnce(response(inventory)).mockResolvedValueOnce(response({...event,status:"CANCELLED",cancellationReason:"Venue unavailable"}));mount();
 fireEvent.click(await screen.findByRole("button",{name:"Cancel entire event"}));
 const confirm=screen.getByRole("button",{name:"Confirm event cancellation"}) as HTMLButtonElement;
 expect(confirm.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText("Cancellation reason"),{target:{value:"Venue unavailable"}});
 fireEvent.click(confirm);await screen.findByText("Event cancelled. Tickets are invalid; history is retained.");
 expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/organizer/events/e1/cancel");
 expect(JSON.parse(fetchMock.mock.calls[2][1]!.body as string)).toEqual({version:1,reason:"Venue unavailable"});
 expect(screen.queryByRole("link",{name:"Edit details & tickets"})).toBeNull();
 expect(screen.queryByRole("button",{name:"Resume publication"})).toBeNull();
});
it("shows durable pending cancellation without allowing edits or another cancellation",async()=>{
 fetchMock.mockResolvedValueOnce(response({...event,status:"CANCELLING"})).mockResolvedValueOnce(response(inventory));mount();
 await screen.findByText("CANCELLING");expect(screen.queryByRole("button",{name:"Cancel entire event"})).toBeNull();
 expect(screen.queryByRole("link",{name:"Edit details & tickets"})).toBeNull();
 expect((screen.getByRole("button",{name:"Cancellation pending"}) as HTMLButtonElement).disabled).toBe(true);
});

it("shows durable cancellation status even when ticket inventory is unavailable",async()=>{
 fetchMock.mockResolvedValueOnce(response({...event,status:"CANCELLING",cancellationReason:"Venue unavailable"})).mockResolvedValueOnce(response({detail:"Admission unavailable"},503));mount();
 await screen.findByText("CANCELLING");await screen.findByText("Syncing event status…");
 expect(screen.getByText("Cancellation reason: Venue unavailable")).toBeTruthy();
 await screen.findByRole("alert");expect(screen.queryByRole("button",{name:"Cancel entire event"})).toBeNull();
});

it.each(["PUBLISHED","PAUSED"])("prevents editing or reopening an ended %s event",async(status)=>{
 fetchMock.mockResolvedValueOnce(response({...event,status,endsAt:"2020-01-01T00:00:00Z"})).mockResolvedValueOnce(response(inventory));mount();
 const button=await screen.findByRole("button",{name:"Event ended"});expect((button as HTMLButtonElement).disabled).toBe(true);
 expect(screen.queryByRole("link",{name:"Edit details & tickets"})).toBeNull();
 expect(screen.getByText(/This event has ended and cannot/)).toBeTruthy();
});
