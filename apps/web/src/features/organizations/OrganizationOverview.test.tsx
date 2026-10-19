// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {OrganizationOverview} from "./OrganizationOverview";
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
it("shows organization-wide totals and calculates a weighted ticket rate",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>json({totalEvents:13,validTickets:40,checkedIn:15,updatedAt:"2030-01-01T00:00:00Z"})));
 render(<OrganizationOverview organizationId="org"/>);
 await screen.findByText("37.5%");expect(screen.getByText("13")).toBeTruthy();expect(screen.getByText("40")).toBeTruthy();expect(screen.getByText("15")).toBeTruthy();
});
it("does not report an unavailable overview as zero, and supports retry",async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(json({},503)).mockResolvedValueOnce(json({totalEvents:0,validTickets:0,checkedIn:0,updatedAt:"2030-01-01T00:00:00Z"}));vi.stubGlobal("fetch",fetch);
 render(<OrganizationOverview organizationId="org"/>);await screen.findByRole("alert");expect(screen.queryByText("0")).toBeNull();
 fireEvent.click(screen.getByRole("button",{name:"Refresh overview"}));await screen.findByText("No valid tickets yet");expect(screen.getByText("—")).toBeTruthy();expect(screen.queryByRole("alert")).toBeNull();
});
