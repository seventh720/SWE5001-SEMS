// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor,act} from "@testing-library/react";
import {MemoryRouter,Routes,Route,useLocation} from "react-router-dom";
import {AuthProvider,useAuth} from "./AuthContext";
import {AuthPage} from "./AuthPage";
import {SessionRecovery} from "./SessionRecovery";
import {apiRequest} from "../../shared/api/client";
const user={id:"alice",username:"Alice",email:"alice@example.com",roles:["ATTENDEE"]};
function Probe(){const {token,login}=useAuth();const l=useLocation();return <><p>Ticket page {l.pathname}{l.search}{l.hash}</p><p>Token: {token}</p><button onClick={()=>void apiRequest("/api/v1/bookings",{},token!).catch(()=>{})}>Request</button><button onClick={()=>void login(user.email,"Password123")}>New login</button></>}
function mount(){render(<AuthProvider><MemoryRouter initialEntries={["/events/e1?preRegistration=t1#ticket-t1"]}><SessionRecovery/><Routes><Route path="/login" element={<AuthPage/>}/><Route path="/events/:id" element={<Probe/>}/></Routes></MemoryRouter></AuthProvider>)}
beforeEach(()=>sessionStorage.clear());afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.useRealTimers();sessionStorage.clear()});
it("expires a restored JWT and preserves the full return URL and pending booking",async()=>{
 const token="e30."+btoa(JSON.stringify({exp:Math.floor(Date.now()/1000)-1}))+".signature";
 sessionStorage.setItem("sems-auth",JSON.stringify({token,user}));
 sessionStorage.setItem("sems-booking:alice:e1:t1",JSON.stringify({requestKey:"original"}));
 vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({accessToken:"fresh",expiresIn:3600,user}))));
 mount();await screen.findByText(/Your session has expired/);
 expect(sessionStorage.getItem("sems-auth")).toBeNull();
 fireEvent.change(screen.getByLabelText("Email"),{target:{value:user.email}});fireEvent.change(screen.getByLabelText("Password"),{target:{value:"Password123"}});fireEvent.submit(screen.getByLabelText("Email").closest("form")!);
 await screen.findByText("Ticket page /events/e1?preRegistration=t1#ticket-t1");
 expect(JSON.parse(sessionStorage.getItem("sems-booking:alice:e1:t1")!).requestKey).toBe("original");
 expect(JSON.parse(sessionStorage.getItem("sems-auth")!).expiresAt-Date.now()).toBeGreaterThan(3590000);
});
it("401 expires the matching session but 403 does not",async()=>{
 sessionStorage.setItem("sems-auth",JSON.stringify({token:"old",user}));
 const fetch=vi.fn().mockResolvedValueOnce(new Response("{}",{status:403})).mockResolvedValueOnce(new Response("{}",{status:401}));vi.stubGlobal("fetch",fetch);mount();
 fireEvent.click(screen.getByText("Request"));await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(1));expect(sessionStorage.getItem("sems-auth")).not.toBeNull();
 fireEvent.click(screen.getByText("Request"));await screen.findByText(/Your session has expired/);expect(sessionStorage.getItem("sems-auth")).toBeNull();
});
it("ignores a late 401 from the previous token after a new login",async()=>{
 sessionStorage.setItem("sems-auth",JSON.stringify({token:"old",user}));
 let finish!:(r:Response)=>void;
 vi.stubGlobal("fetch",vi.fn().mockImplementationOnce(()=>new Promise<Response>(r=>{finish=r})).mockResolvedValueOnce(new Response(JSON.stringify({accessToken:"new",expiresIn:3600,user}))));
 mount();fireEvent.click(screen.getByText("Request"));fireEvent.click(screen.getByText("New login"));await screen.findByText("Token: new");
 await act(async()=>finish(new Response("{}",{status:401})));expect(screen.getByText("Token: new")).toBeTruthy();
});
it("expires an idle session at its deadline",async()=>{
 vi.useFakeTimers();sessionStorage.setItem("sems-auth",JSON.stringify({token:"old",user,expiresAt:Date.now()+1000}));mount();
 await act(async()=>vi.advanceTimersByTime(1000));expect(screen.getByText(/Your session has expired/)).toBeTruthy();
});
