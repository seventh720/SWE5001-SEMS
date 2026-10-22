// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {AdminOrganizationsPage} from "./OrganizationsPage";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token",user:{id:"admin",roles:["ADMIN"]}})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
const org={id:"o",name:"Society",slug:"society",status:"ACTIVE",version:0};
function mount(){render(<MemoryRouter><AdminOrganizationsPage/></MemoryRouter>);fireEvent.change(screen.getByLabelText("Organization name"),{target:{value:"Society"}});fireEvent.change(screen.getByLabelText("Organization address"),{target:{value:"society"}});fireEvent.change(screen.getByLabelText("Administrator email"),{target:{value:"owner@example.com"}});}
it("shows the shared success notification only after organization creation succeeds",async()=>{
 let finish!:(response:Response)=>void;let created=false;
 const fetch=vi.fn(async(_path:RequestInfo|URL,options?:RequestInit)=>{
  if(options?.method==="POST")return new Promise<Response>(resolve=>{finish=response=>{created=true;resolve(response)}});
  return json({items:created?[org]:[],totalPages:created?1:0});
 });vi.stubGlobal("fetch",fetch);mount();
 fireEvent.click(screen.getByRole("button",{name:"Create organization"}));
 expect(screen.queryByText("Organization created.")).toBeNull();
 expect((screen.getByRole("button",{name:"Create organization"}) as HTMLButtonElement).disabled).toBe(true);
 finish(json(org,201));
 const notice=await screen.findByRole("status");expect(notice.textContent).toContain("Organization created.");
 expect(screen.getByRole("button",{name:"Dismiss notification"})).toBeTruthy();
 expect((screen.getByLabelText("Organization name") as HTMLInputElement).value).toBe("");
 expect((screen.getByLabelText("Administrator email") as HTMLInputElement).value).toBe("");
 expect(fetch.mock.calls.filter(([,options])=>options?.method==="POST")).toHaveLength(1);
});
it("keeps the form and shows the server error when creation is rejected",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(_path,options)=>options?.method==="POST"?json({detail:"Organization address already exists."},409):json({items:[],totalPages:0})));mount();
 fireEvent.click(screen.getByRole("button",{name:"Create organization"}));
 expect((await screen.findByRole("alert")).textContent).toContain("Organization address already exists.");
 expect(screen.queryByText("Organization created.")).toBeNull();
 expect((screen.getByLabelText("Organization name") as HTMLInputElement).value).toBe("Society");
});
it("confirms creation even if the following list refresh fails",async()=>{
 let created=false;
 vi.stubGlobal("fetch",vi.fn(async(path,options)=>{
  if(options?.method==="POST"){created=true;return json(org,201)}
  if(String(path).includes("/requests?"))return json({items:[],totalPages:0});
  return created?json({detail:"Temporarily unavailable"},503):json({items:[],totalPages:0});
 }));mount();fireEvent.click(screen.getByRole("button",{name:"Create organization"}));
 expect((await screen.findByRole("status")).textContent).toContain("Organization created.");
 expect((await screen.findByRole("alert")).textContent).toContain("Organization created, but the list could not be refreshed.");
});
