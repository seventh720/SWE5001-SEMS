// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {InvitationPanel} from "./InvitationPanel";
afterEach(()=>{cleanup();vi.restoreAllMocks()});
it("copies a pending link and renders accepted and expired invitations accurately",async()=>{
 const writeText=vi.fn().mockResolvedValue(undefined);
 Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText}});
 const invitations=[
  {id:"a",email:"pending@example.com",role:"MEMBER",status:"PENDING",expiresAt:"2099-01-01T00:00:00Z"},
  {id:"b",email:"joined@example.com",role:"MEMBER",status:"ACCEPTED",expiresAt:"2099-01-01T00:00:00Z"},
  {id:"c",email:"expired@example.com",role:"MEMBER",status:"PENDING",expiresAt:"2000-01-01T00:00:00Z"},
 ];
 render(<InvitationPanel invitations={invitations} link={{id:"a",email:"pending@example.com",url:"http://localhost/invitations/accept#token",expiresAt:invitations[0].expiresAt}} busy={false} onRevoke={()=>{}} onRefresh={()=>{}}/>);
 fireEvent.click(screen.getByRole("button",{name:"Copy invitation link"}));
 await screen.findByText("Invitation link copied.");
 expect(writeText).toHaveBeenCalledWith("http://localhost/invitations/accept#token");
 expect(screen.getByText("Accepted")).toBeTruthy();
 expect(screen.getByText("Expired")).toBeTruthy();
 expect(screen.getAllByRole("button",{name:"Revoke"})).toHaveLength(1);
});
