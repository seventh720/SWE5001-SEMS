// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {OrganizationMembersPage} from "./OrganizationMembersPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const members=Array.from({length:25},(_,i)=>({userId:String(i),username:`Person ${i+1}`,email:`person${i+1}@example.com`,role:"MEMBER",status:"ACTIVE",version:0}));
const json=(data:unknown)=>new Response(JSON.stringify(data),{status:200});
function page(role="ORG_ADMIN"){
 const fetch=vi.fn(async(input:RequestInfo|URL,options?:RequestInit)=>{
  if(options?.method==="PUT")return new Response(null,{status:204});
  if(String(input).endsWith("/me/organizations"))return json([{id:"o",name:"Society",role}]);
  const params=new URL(String(input),"http://localhost").searchParams;const page=Number(params.get("page"));const size=Number(params.get("size"));const query=(params.get("search")??"").toLowerCase();
  const filtered=members.filter(m=>m.username.toLowerCase().includes(query)||m.email.toLowerCase().includes(query));
  return json({items:filtered.slice(page*size,(page+1)*size),page,size,totalElements:filtered.length,totalMembers:members.length,totalPages:Math.ceil(filtered.length/size)});
 });vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={["/organizations/o/members"]}><Routes><Route path="/organizations/:id/members" element={<OrganizationMembersPage/>}/></Routes></MemoryRouter>);
 return fetch;
}
it("paginates members, searches across all pages and resets to the first page",async()=>{
 const fetch=page();await screen.findByText("Person 1");expect(screen.getAllByRole("article")).toHaveLength(12);expect(screen.queryByText("Person 13")).toBeNull();
 fireEvent.click(screen.getByRole("button",{name:"Next"}));await screen.findByText("Person 13");expect(fetch.mock.calls.some(([url])=>String(url).includes("page=1&size=12"))).toBe(true);
 fireEvent.click(screen.getByRole("button",{name:"Next"}));await screen.findByText("Person 25");expect(screen.getAllByRole("article")).toHaveLength(1);
 const search=screen.getByRole("searchbox",{name:"Search members"});
 fireEvent.change(search,{target:{value:" PERSON2@ "}});await screen.findByText("Person 2");expect(screen.getByText(/Page 1 of 1/)).toBeTruthy();
 fireEvent.change(search,{target:{value:"missing"}});await screen.findByText("No members match your search.");
 fireEvent.change(search,{target:{value:""}});await waitFor(()=>expect(screen.getAllByRole("article")).toHaveLength(12));
});
it("preserves versioned role updates on the full directory",async()=>{
 const fetch=page();await screen.findByText("Person 1");fireEvent.click(screen.getByRole("combobox",{name:/Role for Person 1 /}));fireEvent.click(screen.getByRole("option",{name:"Event organizer"}));await screen.findByText("Membership updated.");
 const mutation=fetch.mock.calls.find(([,options])=>options?.method==="PUT")!;
 expect(mutation[0]).toBe("/api/v1/organizations/o/members/0");expect(JSON.parse(mutation[1]!.body as string)).toMatchObject({role:"ORGANIZER",version:0});
});
it("allows ordinary members to browse but hides management controls",async()=>{
 page("MEMBER");await screen.findByText("Person 1");expect(screen.queryByRole("combobox",{name:/Role for/})).toBeNull();expect(screen.queryByRole("combobox",{name:/Status for/})).toBeNull();expect(screen.getByRole("link",{name:"← Back to organization"}).getAttribute("href")).toContain("organizationId=o&section=members");
});
it("ignores an older search response that arrives after the current query",async()=>{
 let resolveSlow!:(value:Response)=>void;
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
  const url=String(input);if(url.endsWith("/me/organizations"))return json([{id:"o",name:"Society",role:"MEMBER"}]);
  const query=new URL(url,"http://localhost").searchParams.get("search");
  if(query==="slow")return new Promise<Response>(resolve=>{resolveSlow=resolve});
  return json({items:[{...members[0],username:query==="fast"?"Latest result":"Initial"}],page:0,size:12,totalElements:1,totalMembers:25,totalPages:1});
 }));
 render(<MemoryRouter initialEntries={["/organizations/o/members"]}><Routes><Route path="/organizations/:id/members" element={<OrganizationMembersPage/>}/></Routes></MemoryRouter>);
 await screen.findByText("Initial");const search=screen.getByRole("searchbox",{name:"Search members"});
 fireEvent.change(search,{target:{value:"slow"}});fireEvent.change(search,{target:{value:"fast"}});await screen.findByText("Latest result");
 resolveSlow(json({items:[{...members[0],username:"Stale result"}],page:0,size:12,totalElements:1,totalMembers:25,totalPages:1}));
 await waitFor(()=>expect(screen.queryByText("Stale result")).toBeNull());expect(screen.getByText("Latest result")).toBeTruthy();
});

it("resets pagination and combines member role and status filters",async()=>{
 const fetch=page();await screen.findByText("Person 1");
 fireEvent.click(screen.getByRole("button",{name:"Next"}));await screen.findByText("Person 13");
 fireEvent.click(screen.getByRole("combobox",{name:/Filter by role/}));fireEvent.click(screen.getByRole("option",{name:"Event organizer"}));
 await waitFor(()=>expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("page=0&size=12&search=&role=ORGANIZER"));
 fireEvent.click(screen.getByRole("combobox",{name:/Filter by member status/}));fireEvent.click(screen.getByRole("option",{name:"Suspended"}));
 await waitFor(()=>expect(String(fetch.mock.calls.at(-1)?.[0])).toContain("role=ORGANIZER&status=SUSPENDED"));
});
