// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {OrganizerBookingsPage} from "./OrganizerBookingsPage";
import {PreRegistrationsPage} from "./PreRegistrationsPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token",user:{id:"user"}})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
const pre={eventId:"e",ticketTypeId:"t",quantity:1,eventTitle:"Saved title",eventLocation:"Saved venue",ticketName:"General",opensAt:"2000-01-01T00:00:00Z",closesAt:"2099-01-01T00:00:00Z",startsAt:"2099-01-02T00:00:00Z",status:"WAITING",currentEvent:{title:"Current title",location:"Current venue",startsAt:"2099-01-02T00:00:00Z"}};
it("clears registration results after a failed page and retries that same page",async()=>{
 let fail=true;
 const fetch=vi.fn(async(input:RequestInfo|URL)=>String(input).includes('page=1')&&fail?json({detail:"Temporarily unavailable"},503):json({items:[{id:"booking",status:"CONFIRMED",ticketName:"General",quantity:2,createdAt:"2026-10-19T00:00:00Z",attendeeInfo:{realName:"Alice"},customFieldLabel:null}],totalPages:2,totalElements:11}));vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={['/events/e/bookings']}><Routes><Route path='/events/:id/bookings' element={<OrganizerBookingsPage/>}/></Routes></MemoryRouter>);
 await screen.findByText('Alice');fireEvent.click(screen.getByRole('button',{name:'Next'}));
 await screen.findByRole('alert');expect(screen.queryByText('Alice')).toBeNull();
 fail=false;fireEvent.click(screen.getByRole('button',{name:'Retry'}));await screen.findByText('Alice');
 expect(fetch.mock.calls.at(-1)?.[0]).toBe('/api/v1/organizer/events/e/bookings?page=1&size=10');
});
it("shows current event details and does not turn a saved pre-registration into a held ticket",async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>json({items:[pre,{...pre,eventId:'closed',eventTitle:'Closed event',currentEvent:null,status:'CLOSED'}],totalPages:1})));
 render(<MemoryRouter><PreRegistrationsPage/></MemoryRouter>);
 await screen.findByText('Current title');expect(screen.getByText(/Current venue/)).toBeTruthy();
 expect(screen.getByText(/Saved details do not hold places/)).toBeTruthy();
 expect(screen.getAllByRole('link',{name:'Review and book'})).toHaveLength(1);
 expect(screen.getByRole('link',{name:'Review and book'}).getAttribute('href')).toBe('/events/e?preRegistration=t#ticket-t');
 expect(screen.getByText(/Current event details unavailable/)).toBeTruthy();
});
it("preserves a pre-registration when removal fails and permits retry",async()=>{
 let fail=true;const fetch=vi.fn(async(_input:RequestInfo|URL,options?:RequestInit)=>options?.method==='DELETE'?(fail?json({detail:'Removal failed'},503):new Response(null,{status:204})):json({items:fail?[pre]:[],totalPages:1}));vi.stubGlobal('fetch',fetch);
 render(<MemoryRouter><PreRegistrationsPage/></MemoryRouter>);
 await screen.findByText('Current title');fireEvent.click(screen.getByRole('button',{name:'Remove'}));
 await screen.findByRole('alert');expect(screen.getByText('Current title')).toBeTruthy();
 fail=false;fireEvent.click(screen.getByRole('button',{name:'Remove'}));await screen.findByText(/No pre-registrations on this page/);
 expect(screen.queryByRole('alert')).toBeNull();
});
it("returns to a valid page after removing the last pre-registration on the final page",async()=>{
 let removed=false;const fetch=vi.fn(async(input:RequestInfo|URL,options?:RequestInit)=>{
  if(options?.method==='DELETE'){removed=true;return new Response(null,{status:204});}
  const last=String(input).includes('page=1');return json({items:removed&&last?[]:[{...pre,eventId:last?'last':'first',currentEvent:{...pre.currentEvent,title:last?'Final page event':'First page event'}}],totalPages:removed?1:2});
 });vi.stubGlobal('fetch',fetch);render(<MemoryRouter><PreRegistrationsPage/></MemoryRouter>);
 await screen.findByText('First page event');fireEvent.click(screen.getByRole('button',{name:'Next'}));await screen.findByText('Final page event');
 fireEvent.click(screen.getByRole('button',{name:'Remove'}));await screen.findByText('First page event');
 expect(screen.getByText('Page 1')).toBeTruthy();await waitFor(()=>expect(fetch.mock.calls.at(-1)?.[0]).toContain('page=0'));
});
