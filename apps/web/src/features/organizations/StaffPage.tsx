import {useMemberDirectory} from "./useMemberDirectory";
import {countdown,useNow} from "../../shared/components/Countdown";
import {TicketCamera} from "./TicketCamera";
import {formatDateTime} from "../../shared/components/dateTime";
import {useCallback,useEffect,useRef,useState,type FormEvent} from "react";
import {useParams,Link} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";
import {apiRequest} from "../../shared/api/client";
import {HomeLink} from "../../shared/components/HomeLink";
interface Task {eventId:string;organizationId:string;title:string;startsAt:string;endsAt:string}
interface Assignment {userId:string;active:boolean}
export function StaffTasksPage(){const {token}=useAuth();const now=useNow();const [tasks,setTasks]=useState<Task[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);useEffect(()=>{let active=true;setLoading(true);setError("");setTasks([]);apiRequest<Task[]>("/api/v1/me/staff-assignments",{},token!).then(v=>{if(active)setTasks(v)}).catch(()=>{if(active)setError("Unable to load your check-in tasks. Please sign in again or try again later.")}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[token]);return <main className="app-shell"><HomeLink/><h1>My check-in tasks</h1>{loading&&<p role="status">Loading check-in tasks…</p>}{error&&<p role="alert">{error}</p>}{!loading&&!error&&!tasks.length&&<p>No active event assignments.</p>}{tasks.map(t=>{
 const opensAt=new Date(Date.parse(t.startsAt)-15*60*1000).toISOString();
 const open=now>=Date.parse(opensAt);
 return <article className="card staff-task-card" key={t.eventId}>
  <div className="staff-task-heading"><h2>{t.title}</h2><span className={`check-in-badge ${open?"is-open":""}`}>{open?"Check-in open":"Not open yet"}</span></div>
  <p>Event starts: {formatDateTime(t.startsAt)}</p>
  <p>Check-in opens: {formatDateTime(opensAt)}</p>
  {!open&&<div className="check-in-countdown" role="timer" aria-label="Time until check-in opens"><span>Check-in opens in</span><strong>{countdown(opensAt,now)}</strong></div>}
  {open?<Link className="staff-open-link" to={`/staff/events/${t.eventId}`}>Open check-in →</Link>:<button type="button" disabled>Open check-in →</button>}
 </article>;
 })}</main>}
export function CheckInPage(){
 const {id}=useParams();const {token}=useAuth();
 const [code,setCode]=useState(""),[result,setResult]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false),[camera,setCamera]=useState(false),[scanned,setScanned]=useState(false);
 const submitting=useRef(false);
 const closeCamera=useCallback(()=>setCamera(false),[]);
 async function checkIn(credential:string){
  if(submitting.current||!credential.trim())return;
  submitting.current=true;setBusy(true);setResult("");setError("");setCamera(false);setCode(credential);
  try{const r=await apiRequest<{alreadyCheckedIn:boolean;checkedInAt:string}>(`/api/v1/events/${id}/check-ins`,{method:"POST",body:JSON.stringify({credential:credential.trim()})},token!);setResult(`${r.alreadyCheckedIn?"Already checked in — no duplicate entry recorded.":"Check-in successful."} ${r.checkedInAt?formatDateTime(r.checkedInAt):""}`);setCode("")}
  catch(e){setError((e as Error).message)}finally{submitting.current=false;setBusy(false)}
 }
 function submit(e:FormEvent){e.preventDefault();void checkIn(code)}
 return <main className="app-shell check-in-page"><Link to="/staff">My check-in tasks</Link><h1>Event check-in</h1><p>Check-in opens 15 minutes before the event starts. Early check-ins are not accepted.</p>
  <p>Scan a ticket with your phone or computer camera. On a computer, you can also use a USB scanner or paste a ticket code.</p>
  {!camera&&<div className="attendance-actions"><button disabled={busy} onClick={()=>{setResult("");setError("");setCamera(true)}}>{scanned?"Scan next ticket":"Open camera to scan"}</button></div>}
  {camera&&<TicketCamera key={id} onClose={closeCamera} onScan={credential=>{setScanned(true);void checkIn(credential)}}/>}
  {busy&&<p role="status">Checking ticket…</p>}{result&&<p className="check-in-result" role="status">{result}</p>}{error&&<p role="alert">{error}</p>}
  <form onSubmit={submit}><label>Ticket code<input required maxLength={128} autoComplete="off" spellCheck={false} disabled={busy||camera} value={code} onChange={e=>setCode(e.target.value)}/></label><button disabled={busy||camera}>Check in ticket</button></form>
 </main>
}
export function EventStaffPage(){const {id}=useParams();const {token}=useAuth();const [organizationId,setOrganizationId]=useState<string>(),[assigned,setAssigned]=useState<Assignment[]>([]),[summary,setSummary]=useState<{confirmedTickets:number;availableCapacity:number;attendance:number;salesState?:string}|null>(null),[title,setTitle]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false),[refreshing,setRefreshing]=useState(false);
 const directory=useMemberDirectory(organizationId,token);const {search:memberSearch,setSearch:setMemberSearch}=directory;
 async function load(){const e=await apiRequest<{organizationId:string;title:string}>(`/api/v1/organizer/events/${id}`,{},token!);setTitle(e.title);setOrganizationId(e.organizationId);const [a,s]=await Promise.all([apiRequest<Assignment[]>(`/api/v1/organizer/events/${id}/staff`,{},token!),apiRequest<typeof summary>(`/api/v1/organizer/events/${id}/summary`,{},token!)]);setAssigned(a);setSummary(s)}useEffect(()=>{void load().catch(e=>setError(e.message))},[id,token]);
 async function change(userId:string,active:boolean){setBusy(true);setError("");try{await apiRequest(`/api/v1/organizer/events/${id}/staff`,{method:"PUT",body:JSON.stringify({userId,active})},token!);await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function refresh(){setRefreshing(true);setError("");try{await load()}catch(e){setError((e as Error).message)}finally{setRefreshing(false)}}
 const query=memberSearch.trim().toLocaleLowerCase();
 const visibleMembers=directory.data?.items??[];
 const cancelled=summary?.salesState==="CANCELLED";
 const percent=summary&&summary.confirmedTickets>0?Math.min(100,Math.round(summary.attendance/summary.confirmedTickets*100)):0;
 return <main className="app-shell"><HomeLink/><h1>Staff and attendance</h1><h2>{title}</h2>{error&&<p role="alert">{error}</p>}
 <section className="attendance-panel" aria-labelledby="attendance-heading" aria-busy={refreshing}>
  <div className="attendance-panel-heading"><div><h2 id="attendance-heading">Attendance overview</h2><p>Ticket allocation and arrival progress</p></div><button disabled={busy||refreshing} onClick={()=>void refresh()}>{refreshing?"Refreshing…":"Refresh attendance"}</button></div>
  {summary?<>
   <dl className="attendance-metrics">
    <div><dt>Confirmed tickets</dt><dd>{summary.confirmedTickets}</dd><span>Places booked</span></div>
    <div><dt>Available ticket places</dt><dd>{summary.availableCapacity}</dd><span>Still available to book</span></div>
    <div className="attendance-checked"><dt>Checked in</dt><dd>{summary.attendance}</dd><span>{cancelled?"Historical check-ins":`${Math.max(0,summary.confirmedTickets-summary.attendance)} yet to arrive`}</span></div>
   </dl>
   {cancelled?<p role="status">Event cancelled. Tickets are invalid and check-in is closed. Previous attendance is retained.</p>:<><div className="attendance-progress-heading"><span>Check-in progress</span><strong>{summary.attendance} / {summary.confirmedTickets} · {percent}%</strong></div>
   <progress className="attendance-progress" aria-label="Check-in progress" value={summary.attendance} max={Math.max(1,summary.confirmedTickets)}/>
   {summary.confirmedTickets===0&&<p className="attendance-empty">No confirmed tickets yet.</p>}</>}
  </>:<p role="status">{error?"Attendance is unavailable. Try refreshing.":"Loading attendance…"}</p>}
 </section>
 <h2>Assigned staff</h2><p>Select the members who can check in tickets for this event.</p>
 <div className="staff-search"><label>Search organization members<input type="search" placeholder="Search by username or email" maxLength={200} value={memberSearch} onChange={e=>setMemberSearch(e.target.value)}/></label><p role="status">{directory.data?.totalElements??0} matching · {directory.data?.totalMembers??0} total members · {assigned.filter(a=>a.active).length} assigned</p></div>
 {directory.error&&<p role="alert">{directory.error}</p>}{directory.loading&&<p role="status">Loading members…</p>}
 {!directory.loading&&query&&visibleMembers.length===0&&<p>No organization members match your search.</p>}
 {!directory.loading&&visibleMembers.map(m=><label className="card staff-member-option" key={m.userId}><input type="checkbox" disabled={busy||cancelled||m.status!=="ACTIVE"&&!assigned.some(a=>a.userId===m.userId&&a.active)} checked={assigned.some(a=>a.userId===m.userId&&a.active)} onChange={e=>void change(m.userId,e.target.checked)}/>{m.username} · {m.status}</label>)}<nav className="member-pagination" aria-label="Staff member pages"><button disabled={directory.loading||busy||directory.page===0} onClick={()=>directory.setPage(directory.page-1)}>Previous</button><span>Page {directory.page+1} of {Math.max(1,directory.data?.totalPages??0)}</span><button disabled={directory.loading||busy||directory.page+1>=(directory.data?.totalPages??0)} onClick={()=>directory.setPage(directory.page+1)}>Next</button></nav></main>
}
