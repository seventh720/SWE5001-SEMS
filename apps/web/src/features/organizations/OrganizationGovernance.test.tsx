// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {OrganizationRequestPanel,PlatformOrganizationGovernance} from "./OrganizationGovernance";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const org={id:"o",name:"Society",slug:"society",status:"ACTIVE",role:"ORG_ADMIN",version:4};
const json=(data:unknown)=>new Response(JSON.stringify(Array.isArray(data)?{items:data,totalPages:data.length?1:0,hasPending:data.some(r=>r.status==="PENDING")}:data));
it("submits profile changes for review without applying them directly",async()=>{
 const fetch=vi.fn(async(_path,options)=>options?.method==="POST"?json({id:"r"}):json([]));vi.stubGlobal("fetch",fetch);
 render(<OrganizationRequestPanel organization={org}/>);
 await waitFor(()=>expect((screen.getByRole("button",{name:"Submit for review"}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.change(screen.getByLabelText("Requested organization name"),{target:{value:"New Society"}});
 fireEvent.change(screen.getByLabelText("Reason for request"),{target:{value:"New name"}});
 fireEvent.click(screen.getByRole("button",{name:"Submit for review"}));await screen.findByText(/Request submitted/);
 const call=fetch.mock.calls.find(([,o])=>o?.method==="POST")!;expect(call[0]).toBe("/api/v1/organizations/o/requests");expect(JSON.parse(call[1].body)).toMatchObject({name:"New Society",version:4,kind:"UPDATE"});
});
it("requires a matching name for soft deletion and submits the version",async()=>{
 const fetch=vi.fn(async(_path,options)=>options?.method==="DELETE"?new Response(null,{status:204}):json([]));vi.stubGlobal("fetch",fetch);
 const changed=vi.fn(async()=>{});render(<PlatformOrganizationGovernance organizations={[org]} onChanged={changed}/>);
 fireEvent.click(screen.getByRole("button",{name:"Delete Society"}));
 expect((screen.getByRole("button",{name:"Confirm deletion"}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText("Type the organization name to confirm"),{target:{value:"Society"}});
 fireEvent.click(screen.getByRole("button",{name:"Confirm deletion"}));await screen.findByText("Organization change saved.");
 expect(fetch.mock.calls.some(([path,o])=>path==="/api/v1/admin/organizations/o?version=4"&&o?.method==="DELETE")).toBe(true);
});
it("requires review notes and sends approval to the platform review endpoint",async()=>{
 const fetch=vi.fn(async(_path,options)=>options?.method==="POST"?new Response(null,{status:204}):json([{id:"r",organizationId:"o",organizationName:"Society",kind:"CLOSE",reason:"Closing",status:"PENDING"}]));vi.stubGlobal("fetch",fetch);
 render(<PlatformOrganizationGovernance organizations={[org]} onChanged={async()=>{}}/>);
 const approve=await screen.findByRole("button",{name:"Approve request"});expect((approve as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText("Review note for Society"),{target:{value:"Closure agreed"}});fireEvent.click(approve);
 await screen.findByText("Organization change saved.");
 expect(JSON.parse(fetch.mock.calls.find(([,o])=>o?.method==="POST")![1].body)).toEqual({approve:true,note:"Closure agreed"});
});
it("keeps a closing organization visible and prevents reactivation or repeated deletion",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>json([])));
 render(<PlatformOrganizationGovernance organizations={[{...org,status:"CLOSING",closureRequested:true}]} onChanged={vi.fn(async()=>{})}/>);
 expect(screen.getByText(/Closing organization: cancelling unfinished events/)).toBeTruthy();
 expect((screen.getByRole("button",{name:"Activate"}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole("button",{name:`Delete ${org.name}`}) as HTMLButtonElement).disabled).toBe(true);
});
