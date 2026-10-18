// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {act,cleanup,fireEvent,render,screen,within,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {StaffTasksPage,EventStaffPage} from "./StaffPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals()});
const json=(data:unknown)=>new Response(JSON.stringify(data),{status:200});
it("disables entry before opening, counts down, and automatically enables entry at exactly 15 minutes before start",async()=>{
 vi.useFakeTimers();vi.setSystemTime(new Date("2030-01-01T09:44:58Z"));
 vi.stubGlobal("fetch",vi.fn(async()=>json([{eventId:"e",title:"Seminar",startsAt:"2030-01-01T10:00:00Z",endsAt:"2030-01-01T11:00:00Z"}])));
 await act(async()=>{render(<MemoryRouter><StaffTasksPage/></MemoryRouter>)});
 expect((screen.getByRole("button",{name:"Open check-in →"}) as HTMLButtonElement).disabled).toBe(true);
 expect(screen.queryByRole("link",{name:"Open check-in →"})).toBeNull();
 expect(screen.getByRole("timer").textContent).toContain("00h 00m 02s");
 act(()=>vi.advanceTimersByTime(1000));expect(screen.getByRole("timer").textContent).toContain("00h 00m 01s");
 act(()=>vi.advanceTimersByTime(1000));expect(screen.getByRole("link",{name:"Open check-in →"}).getAttribute("href")).toBe("/staff/events/e");
 expect(screen.queryByRole("timer")).toBeNull();expect(screen.getByText("Check-in open")).toBeTruthy();
});
function page(){render(<MemoryRouter initialEntries={["/organizer/events/e/staff"]}><Routes><Route path="/organizer/events/:id/staff" element={<EventStaffPage/>}/></Routes></MemoryRouter>)}
it("shows ticket metrics and check-in progress, then updates on refresh",async()=>{
 let attendance=1;
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
  const path=String(input);
  if(path.endsWith("/summary"))return json({confirmedTickets:5,availableCapacity:5,attendance});
  if(path.includes("/members?"))return json({items:[],totalElements:0,totalMembers:0,totalPages:0});
  if(path.endsWith("/staff"))return json([]);
  return json({organizationId:"o",title:"Test"});
 }));page();
 const panel=await screen.findByRole("region",{name:"Attendance overview"});
 await within(panel).findByText("1 / 5 · 20%");
 expect(within(panel).getByText("4 yet to arrive")).toBeTruthy();
 expect((within(panel).getByRole("progressbar") as HTMLProgressElement).value).toBe(1);
 attendance=3;fireEvent.click(screen.getByRole("button",{name:"Refresh attendance"}));
 await within(panel).findByText("3 / 5 · 60%");expect(within(panel).getByText("2 yet to arrive")).toBeTruthy();
});
it("handles zero confirmed tickets without an invalid percentage",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("/summary")?json({confirmedTickets:0,availableCapacity:10,attendance:0}):String(input).includes("/members?")?json({items:[],totalElements:0,totalMembers:0,totalPages:0}):String(input).endsWith("/staff")?json([]):json({organizationId:"o",title:"Empty"})));
 page();await screen.findByText("0 / 0 · 0%");expect(screen.getByText("No confirmed tickets yet.")).toBeTruthy();
});
it("searches organization members by username or email without losing assignments",async()=>{
 const assigned=[{userId:"alice",active:true}];
 const fetch=vi.fn(async(input:RequestInfo|URL,options?:RequestInit)=>{
  const path=String(input);
  if(options?.method==="PUT"){assigned.push(JSON.parse(options.body as string));return new Response(null,{status:204})}
  if(path.includes("/members?")){
   const query=(new URL(path,"http://localhost").searchParams.get("search")??"").toLowerCase();
   const items=[{userId:"alice",username:"Alice",email:"alice@example.com",status:"ACTIVE"},{userId:"bob",username:"Bob",email:"crew@example.com",status:"ACTIVE"}].filter(m=>m.username.toLowerCase().includes(query)||m.email.includes(query));
   return json({items,totalElements:items.length,totalMembers:2,totalPages:items.length?1:0});
  }
  if(path.endsWith("/staff"))return json(assigned);
  if(path.endsWith("/summary"))return json({confirmedTickets:0,availableCapacity:10,attendance:0});
  return json({organizationId:"o",title:"Test"});
 });vi.stubGlobal("fetch",fetch);page();
 expect((await screen.findByRole("checkbox",{name:"Alice · ACTIVE"}) as HTMLInputElement).checked).toBe(true);
 const search=screen.getByRole("searchbox",{name:"Search organization members"});
 fireEvent.change(search,{target:{value:"  CREW@  "}});
 expect(screen.queryByRole("checkbox",{name:"Alice · ACTIVE"})).toBeNull();
 fireEvent.click(await screen.findByRole("checkbox",{name:"Bob · ACTIVE"}));
 await screen.findByText("1 matching · 2 total members · 2 assigned");
 fireEvent.change(search,{target:{value:"aLi"}});
 expect((await screen.findByRole("checkbox",{name:"Alice · ACTIVE"}) as HTMLInputElement).checked).toBe(true);
 fireEvent.change(search,{target:{value:"unknown"}});await screen.findByText("No organization members match your search.");
 fireEvent.change(search,{target:{value:""}});
 await waitFor(()=>expect(screen.getAllByRole("checkbox").every(box=>(box as HTMLInputElement).checked)).toBe(true));
 expect(fetch.mock.calls.filter(([,options])=>options?.method==="PUT")).toHaveLength(1);
});
it("pages staff candidates on the server and preserves selections across pages",async()=>{
 const people=Array.from({length:13},(_,n)=>({userId:String(n),username:`Crew ${n+1}`,email:`crew${n+1}@example.com`,status:"ACTIVE"}));
 const assigned=[{userId:"0",active:true}];
 const fetch=vi.fn(async(input:RequestInfo|URL,options?:RequestInit)=>{
  const path=String(input);
  if(options?.method==="PUT"){assigned.push(JSON.parse(options.body as string));return new Response(null,{status:204})}
  if(path.includes("/members?")){const page=Number(new URL(path,"http://localhost").searchParams.get("page"));return json({items:people.slice(page*12,(page+1)*12),page,size:12,totalElements:13,totalMembers:13,totalPages:2})}
  if(path.endsWith("/staff"))return json(assigned);
  if(path.endsWith("/summary"))return json({confirmedTickets:0,availableCapacity:10,attendance:0});
  return json({organizationId:"o",title:"Test"});
 });vi.stubGlobal("fetch",fetch);page();
 expect((await screen.findByRole("checkbox",{name:"Crew 1 · ACTIVE"}) as HTMLInputElement).checked).toBe(true);
 fireEvent.click(screen.getByRole("button",{name:"Next"}));fireEvent.click(await screen.findByRole("checkbox",{name:"Crew 13 · ACTIVE"}));
 await screen.findByText("13 matching · 13 total members · 2 assigned");
 fireEvent.click(screen.getByRole("button",{name:"Previous"}));
 expect((await screen.findByRole("checkbox",{name:"Crew 1 · ACTIVE"}) as HTMLInputElement).checked).toBe(true);
 expect(fetch.mock.calls.some(([url])=>String(url).includes("page=1&size=12"))).toBe(true);
});
