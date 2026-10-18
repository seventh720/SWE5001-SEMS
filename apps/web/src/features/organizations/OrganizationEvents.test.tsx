// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {OrganizationEvents} from "./OrganizationEvents";
import type {Organization} from "./OrganizationsPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const org={id:"org",name:"Society",role:"ORGANIZER"} as Organization;
const json=(value:unknown)=>new Response(JSON.stringify(value));
it("searches all organization events and resets the page",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>{
  const query=new URL(String(input),"http://localhost").searchParams;
  const title=query.get("keyword")?"Found event":query.get("page")==="1"?"Older event":"Recent event";
  return json({items:[{id:"event",title,startsAt:"2030-01-01T12:00:00Z",location:"Campus",visibility:"PUBLIC"}],totalPages:2,totalElements:7});
 });vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter><OrganizationEvents organization={org}/></MemoryRouter>);
 await screen.findByText("Recent event");fireEvent.click(screen.getByRole("button",{name:"Next"}));
 await screen.findByText("Older event");fireEvent.change(screen.getByRole("searchbox"),{target:{value:"A & B"}});
 fireEvent.submit(screen.getByRole("search"));await screen.findByText("Found event");
 expect(fetch.mock.calls.at(-1)?.[0]).toContain("page=0&size=6&keyword=A%20%26%20B");
});
it("recovers when the last page shrinks and uses public discovery for members",async()=>{
 const fetch=vi.fn(async(input:RequestInfo|URL)=>{
  const page=new URL(String(input),"http://localhost").searchParams.get("page");
  return json(page==="1"?{items:[],totalPages:1,totalElements:1}:{items:[{id:"event",title:"Visible event",startsAt:"2030-01-01T12:00:00Z",visibility:"PUBLIC"}],totalPages:2,totalElements:7});
 });vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter><OrganizationEvents organization={{...org,role:"MEMBER"}}/></MemoryRouter>);
 await screen.findByText("Visible event");fireEvent.click(screen.getByRole("button",{name:"Next"}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3));
 expect(fetch.mock.calls.at(-1)?.[0]).toBe("/api/v1/events?organizationId=org&page=0&size=6&keyword=");
 expect(screen.queryByRole("link",{name:"Create event"})).toBeNull();
});
