// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {act,cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import decode from "jsqr";
import {TicketCamera} from "./TicketCamera";
import {CheckInPage} from "./StaffPage";
vi.mock("jsqr",()=>({default:vi.fn()}));
vi.mock("../auth/AuthContext",()=>({useAuth:()=>({token:"token"})}));
const credential="a".repeat(48);
let stop:ReturnType<typeof vi.fn>;
let getUserMedia:ReturnType<typeof vi.fn>;
beforeEach(()=>{
 stop=vi.fn();
 getUserMedia=vi.fn().mockResolvedValue({getTracks:()=>[{stop}]});
 vi.stubGlobal("isSecureContext",true);
 Object.defineProperty(navigator,"mediaDevices",{configurable:true,value:{getUserMedia,enumerateDevices:vi.fn().mockResolvedValue([])}});
 vi.spyOn(HTMLMediaElement.prototype,"play").mockResolvedValue(undefined);
 vi.spyOn(HTMLMediaElement.prototype,"readyState","get").mockReturnValue(4);
 vi.spyOn(HTMLVideoElement.prototype,"videoWidth","get").mockReturnValue(640);
 vi.spyOn(HTMLVideoElement.prototype,"videoHeight","get").mockReturnValue(480);
 vi.spyOn(HTMLCanvasElement.prototype,"getContext").mockReturnValue({drawImage:vi.fn(),getImageData:()=>({data:new Uint8ClampedArray(4),width:1,height:1})} as unknown as CanvasRenderingContext2D);
 vi.mocked(decode).mockReturnValue(null);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();vi.clearAllMocks()});
it("submits a scanned ticket once, stops the camera and waits for Scan next ticket",async()=>{
 vi.mocked(decode).mockReturnValue({data:credential} as NonNullable<ReturnType<typeof decode>>);
 const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({alreadyCheckedIn:false,checkedInAt:null}),{status:200}));vi.stubGlobal("fetch",fetch);
 render(<MemoryRouter initialEntries={["/staff/events/e"]}><Routes><Route path="/staff/events/:id" element={<CheckInPage/>}/></Routes></MemoryRouter>);
 expect(getUserMedia).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole("button",{name:"Open camera to scan"}));
 await screen.findByText("Check-in successful.");
 expect(fetch).toHaveBeenCalledTimes(1);
 expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({credential});
 expect(stop).toHaveBeenCalled();
 expect(screen.queryByLabelText("Camera preview")).toBeNull();
 expect(screen.getByRole("button",{name:"Scan next ticket"})).toBeTruthy();
 expect(getUserMedia).toHaveBeenCalledWith(expect.objectContaining({audio:false,video:expect.objectContaining({facingMode:{ideal:"environment"}})}));
});
it("releases camera access granted after the scanner was closed",async()=>{
 let resolve!:(value:unknown)=>void;getUserMedia.mockReturnValue(new Promise(r=>resolve=r));
 const view=render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 await waitFor(()=>expect(getUserMedia).toHaveBeenCalled());view.unmount();
 await act(async()=>resolve({getTracks:()=>[{stop}]}));
 expect(stop).toHaveBeenCalledTimes(1);
});
it("explains denied permission and allows retry",async()=>{
 getUserMedia.mockRejectedValueOnce(new DOMException("Denied","NotAllowedError"));
 const view=render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 expect((await screen.findByRole("alert")).textContent).toContain("permission was denied");
 fireEvent.click(screen.getByRole("button",{name:"Retry camera"}));
 await screen.findByText(/Point the camera/);view.unmount();expect(stop).toHaveBeenCalled();
});
it("explains HTTPS on an insecure phone connection without requesting a camera",async()=>{
 vi.stubGlobal("isSecureContext",false);render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 expect((await screen.findByRole("alert")).textContent).toContain("HTTPS");expect(getUserMedia).not.toHaveBeenCalled();
});
it("ignores unrelated QR content without posting it",async()=>{
 vi.mocked(decode).mockReturnValue({data:"https://example.com"} as NonNullable<ReturnType<typeof decode>>);
 const scan=vi.fn();render(<TicketCamera onScan={scan} onClose={vi.fn()}/>);
 await screen.findByText(/not a SEMS ticket/);expect(scan).not.toHaveBeenCalled();
});
it("stops the stream on camera switching and requests the selected PC webcam",async()=>{
 navigator.mediaDevices.enumerateDevices=vi.fn().mockResolvedValue([{kind:"videoinput",deviceId:"one",label:"Built-in"},{kind:"videoinput",deviceId:"two",label:"USB webcam"}]);
 render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 fireEvent.click(await screen.findByRole("combobox",{name:/Camera/}));
 fireEvent.click(screen.getByRole("option",{name:"USB webcam"}));
 await waitFor(()=>expect(getUserMedia).toHaveBeenCalledWith({audio:false,video:{deviceId:{exact:"two"}}}));expect(stop).toHaveBeenCalled();
});
it("releases the camera when the tab goes into the background",async()=>{
 const close=vi.fn();render(<TicketCamera onScan={vi.fn()} onClose={close}/>);
 await screen.findByText(/Point the camera/);
 vi.spyOn(document,"hidden","get").mockReturnValue(true);
 fireEvent(document,new Event("visibilitychange"));expect(stop).toHaveBeenCalled();expect(close).toHaveBeenCalledTimes(1);
});
it("lets mobile users start blocked playback without requesting camera permission again",async()=>{
 vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new DOMException("Gesture required","NotAllowedError"));
 render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 fireEvent.click(await screen.findByRole("button",{name:"Start preview"}));
 await screen.findByText(/Point the camera/);
 expect(getUserMedia).toHaveBeenCalledTimes(1);
 expect(screen.queryByRole("alert")).toBeNull();
});
it("distinguishes video playback failure from a camera permission failure",async()=>{
 vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new DOMException("Interrupted","AbortError"));
 render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 expect((await screen.findByRole("alert")).textContent).toContain("video playback failed");
 expect(stop).toHaveBeenCalled();
});
it("fits the complete portrait camera frame and updates on orientation changes",async()=>{
 render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 await screen.findByText(/Point the camera/);
 const video=screen.getByLabelText("Camera preview") as HTMLVideoElement;
 vi.spyOn(HTMLVideoElement.prototype,"videoWidth","get").mockReturnValue(720);
 vi.spyOn(HTMLVideoElement.prototype,"videoHeight","get").mockReturnValue(1280);
 fireEvent(video,new Event("resize"));
 expect(Number(video.style.aspectRatio)).toBe(720/1280);
 vi.spyOn(HTMLVideoElement.prototype,"videoWidth","get").mockReturnValue(1280);
 vi.spyOn(HTMLVideoElement.prototype,"videoHeight","get").mockReturnValue(720);
 fireEvent(video,new Event("resize"));
 expect(Number(video.style.aspectRatio)).toBe(1280/720);
});
it("releases the stream when closed while waiting for a playback gesture",async()=>{
 vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new DOMException("Gesture required","NotAllowedError"));
 const scan=vi.fn();const view=render(<TicketCamera onScan={scan} onClose={vi.fn()}/>);
 await screen.findByRole("button",{name:"Start preview"});view.unmount();
 await act(async()=>{});expect(stop).toHaveBeenCalled();expect(scan).not.toHaveBeenCalled();
});
it("stops the stream and reports unreadable camera frames",async()=>{
 vi.spyOn(HTMLCanvasElement.prototype,"getContext").mockReturnValue({drawImage:()=>{throw new Error('Frame unavailable')},getImageData:vi.fn()} as unknown as CanvasRenderingContext2D);
 render(<TicketCamera onScan={vi.fn()} onClose={vi.fn()}/>);
 expect((await screen.findByRole('alert')).textContent).toContain('Unable to read camera frames');expect(stop).toHaveBeenCalled();
});
