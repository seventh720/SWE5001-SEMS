// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {OrganizationsPage,AcceptInvitationPage} from "./OrganizationsPage";
import {CheckInPage} from "./StaffPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token",user:{id:"u",roles:["ATTENDEE"]}})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,"","/")});
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
it("uses membership roles rather than global ORGANIZER and clears the old organization on switch",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>{const p=String(input);if(p.includes("/me/organizations"))return json([{id:"a",name:"Society",role:"ORG_ADMIN"},{id:"b",name:"Training",role:"MEMBER"}]);if(p.includes("/events?"))return json({items:[],totalElements:0,totalPages:0});if(p.endsWith("invitations"))return json([]);if(p.includes("/a/"))return json([{userId:"alice",username:"Alice",email:"a@test",role:"ORG_ADMIN",status:"ACTIVE",version:0}]);return json([{userId:"bob",username:"Bob",email:"b@test",role:"MEMBER",status:"ACTIVE",version:0}]);});vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={["/organizations?organizationId=a&section=members"]}><OrganizationsPage/></MemoryRouter>);
 await screen.findByText("Alice");expect(screen.getByRole("link",{name:"Events"}).getAttribute("href")).toContain("organizationId=a");
 fireEvent.click(screen.getByRole("button",{name:/Training/}));fireEvent.click(await screen.findByRole("link",{name:"Members"}));await screen.findByText("Bob");expect(screen.queryByText("Alice")).toBeNull();expect(screen.queryByRole("link",{name:"Manage events →"})).toBeNull();expect(screen.queryByRole("button",{name:"Send invitation"})).toBeNull();
});
it("shows an account-bound invitation link only after successful creation",async()=>{
 let created=false;const fetch=vi.fn(async(input:RequestInfo|URL,opts?:RequestInit)=>{const p=String(input);if(opts?.method==="POST"){created=true;return json({token:"secret-invite",id:"i",expiresAt:"2099-01-01T00:00:00Z"});}if(p.endsWith("/invitations")&&created)return json([{id:"i",email:"member@example.com",role:"MEMBER",status:"PENDING",expiresAt:"2099-01-01T00:00:00Z"}]);if(p.includes("/me/organizations"))return json([{id:"a",name:"Society",role:"ORG_ADMIN"}]);return json([])});vi.stubGlobal("fetch",fetch);render(<MemoryRouter initialEntries={["/organizations?organizationId=a&section=members"]}><OrganizationsPage/></MemoryRouter>);fireEvent.change(await screen.findByLabelText("Email"),{target:{value:"member@example.com"}});fireEvent.click(screen.getByRole("button",{name:"Send invitation"}));await screen.findByDisplayValue(/invitations\/accept#secret-invite/);expect(JSON.parse(fetch.mock.calls.find(c=>c[1]?.method==="POST")![1]!.body as string)).toEqual({email:"member@example.com",role:"MEMBER"});
});
it("accepts a token from the URL fragment and removes it after success",async()=>{
 window.history.replaceState(null,"","/invitations/accept#bound-token");const fetch=vi.fn(async()=>new Response(null,{status:204}));vi.stubGlobal("fetch",fetch);render(<MemoryRouter><AcceptInvitationPage/></MemoryRouter>);fireEvent.click(screen.getByRole("button",{name:"Accept invitation"}));await screen.findByText(/Invitation accepted/);expect(window.location.hash).toBe("");expect(fetch.mock.calls).toHaveLength(1);
});
it("distinguishes duplicate check-in and server rejection",async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(json({alreadyCheckedIn:true,checkedInAt:"2030-01-01T00:00:00Z"})).mockResolvedValueOnce(json({detail:"You are not assigned to this event"},403));vi.stubGlobal("fetch",fetch);render(<MemoryRouter initialEntries={["/staff/events/e"]}><Routes><Route path="/staff/events/:id" element={<CheckInPage/>}/></Routes></MemoryRouter>);fireEvent.change(screen.getByLabelText("Ticket code"),{target:{value:"code"}});fireEvent.click(screen.getByRole("button",{name:"Check in ticket"}));await screen.findByText(/Already checked in/);fireEvent.change(screen.getByLabelText("Ticket code"),{target:{value:"other"}});fireEvent.click(screen.getByRole("button",{name:"Check in ticket"}));await screen.findByRole("alert");await waitFor(()=>expect(screen.queryByText(/Already checked in/)).toBeNull());
});

it("does not report empty memberships when the organization request fails", async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>json({title:"Not Found"},404)));
 render(<MemoryRouter><OrganizationsPage/></MemoryRouter>);
 expect(screen.queryByText("You have no active organization memberships.")).toBeNull();
 expect((await screen.findByRole("alert")).textContent).toContain("Unable to load your organizations");
 expect(screen.queryByText("You have no active organization memberships.")).toBeNull();
});

it("defaults to scoped events and separates member management",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>{
  const p=String(input);
  if(p.includes("/me/organizations"))return json([{id:"a",name:"Society",role:"ORG_ADMIN"}]);
  if(p.includes("/organizer/events?"))return json({items:[{id:"e",title:"Society seminar",startsAt:"2030-01-01T00:00:00Z",location:"Campus",status:"DRAFT",visibility:"ORGANIZATION_ONLY"}],totalElements:1,totalPages:1});
  return json([]);
 });vi.stubGlobal("fetch",fetch);
 const {container}=render(<MemoryRouter initialEntries={["/organizations?organizationId=a"]}><OrganizationsPage/></MemoryRouter>);
 await screen.findByText("Society seminar");
 expect(screen.getByRole("link",{name:"Create event"}).getAttribute("href")).toBe("/organizer/events?organizationId=a&create=true");
 expect(screen.queryByText("Invite a registered user")).toBeNull();
 fireEvent.click(screen.getByRole("link",{name:"Members"}));
 await screen.findByText("Invite a registered user");
 expect(screen.queryByText("Society seminar")).toBeNull();
 fireEvent.click(screen.getByRole("combobox",{name:/Organization role/}));
 fireEvent.click(screen.getByRole("option",{name:"Event organizer"}));
 expect(screen.getByRole("combobox",{name:/Organization role/}).textContent).toContain("Event organizer");
 expect(container.querySelector("select")).toBeNull();
});

it("uses member discovery without manager controls",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>String(input).includes("/me/organizations")
  ?json([{id:"b",name:"Training",role:"MEMBER"}])
  :json({items:[],totalElements:0,totalPages:0}));
 vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={["/organizations?organizationId=b"]}><OrganizationsPage/></MemoryRouter>);
 await screen.findByText("No upcoming events yet");
 expect(fetch.mock.calls.some(([url])=>String(url).startsWith("/api/v1/events?organizationId=b"))).toBe(true);
 expect(fetch.mock.calls.some(([url])=>String(url).includes("/organizer/events"))).toBe(false);
 expect(screen.queryByRole("link",{name:"Create event"})).toBeNull();
});

it("explains duplicate members before creating an invitation",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>String(input).includes("/me/organizations")?json([{id:"a",name:"Society",role:"ORG_ADMIN"}]):String(input).endsWith("/members")?json([{userId:"m",username:"Team",email:"tm10@123.com",role:"MEMBER",status:"ACTIVE",version:0}]):json([]));
 vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={["/organizations?organizationId=a&section=members"]}><OrganizationsPage/></MemoryRouter>);
 await screen.findByText("Team");
 fireEvent.change(screen.getByLabelText("Email"),{target:{value:"tm10@123.com"}});
 fireEvent.click(screen.getByRole("button",{name:"Send invitation"}));
 expect((await screen.findByRole("alert")).textContent).toContain("already in this organization");
 expect(fetch.mock.calls.some(c=>(c as unknown as [string,RequestInit])[1]?.method==="POST")).toBe(false);
});

it("shows registration guidance returned by the invitation endpoint",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL,opts?:RequestInit)=>opts?.method==="POST"?json({detail:"This email is not registered. Ask the person to create an account first, then invite them again."},404):String(input).includes("/me/organizations")?json([{id:"a",name:"Society",role:"ORG_ADMIN"}]):json([])));
 render(<MemoryRouter initialEntries={["/organizations?organizationId=a&section=members"]}><OrganizationsPage/></MemoryRouter>);
 fireEvent.change(await screen.findByLabelText("Email"),{target:{value:"new@example.com"}});
 fireEvent.click(screen.getByRole("button",{name:"Send invitation"}));
 expect((await screen.findByRole("alert")).textContent).toContain("not registered");
 expect(screen.queryByRole("button",{name:"Copy invitation link"})).toBeNull();
});
