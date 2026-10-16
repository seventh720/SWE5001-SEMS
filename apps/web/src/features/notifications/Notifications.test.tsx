// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {NotificationsPage,NotificationBell} from "./Notifications";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const response=(value:unknown)=>new Response(JSON.stringify(value));
it("counts pending invitations and unread updates in the navigation",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input)=>response(String(input).includes("pending-count")?2:3)));
 render(<MemoryRouter><NotificationBell/></MemoryRouter>);
 await screen.findByRole("link",{name:"Notifications, 5 unread or pending"});
});
it("accepts an invitation in the inbox and keeps updates separate",async()=>{
 let accepted=false;
 const fetch=vi.fn(async(input,opts)=>{
  const p=String(input);
  if(opts?.method==="POST"){accepted=true;return new Response(null,{status:204})}
  if(p.includes("/invitations"))return response({items:[{id:"i",organizationId:"o",organizationName:"Student Society",role:"MEMBER",status:accepted?"ACCEPTED":"PENDING",expiresAt:"2099-01-01T00:00:00Z"}],pendingCount:accepted?0:1,hasMore:false});
  return response({items:[{id:"n",kind:"BOOKING_CONFIRMED",title:"Booking confirmed",message:"Seminar",link:"/bookings/b",createdAt:"2030-01-01T00:00:00Z",readAt:null}],unreadCount:1,hasMore:false});
 });
 vi.stubGlobal("fetch",fetch);render(<MemoryRouter><NotificationsPage/></MemoryRouter>);
 fireEvent.click(await screen.findByRole("button",{name:"Accept"}));
 await screen.findByRole("link",{name:"Open organization →"});
 expect(fetch.mock.calls.some(([p,o])=>String(p)==="/api/v1/me/invitations/i/accept"&&o?.method==="POST")).toBe(true);
 expect(screen.getByText("Booking confirmed")).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Decline"})).toBeNull();
});
it("keeps a rejected action visible",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input,opts)=>{
  if(opts?.method==="POST")return new Response(JSON.stringify({detail:"Invitation expired or revoked"}),{status:409});
  return response(String(input).includes("/invitations")?{items:[{id:"i",organizationName:"Society",role:"MEMBER",status:"PENDING",expiresAt:"2099-01-01T00:00:00Z"}],pendingCount:1,hasMore:false}:{items:[],unreadCount:0,hasMore:false});
 }));
 render(<MemoryRouter><NotificationsPage/></MemoryRouter>);
 fireEvent.click(await screen.findByRole("button",{name:"Accept"}));
 await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("expired or revoked"));
});
