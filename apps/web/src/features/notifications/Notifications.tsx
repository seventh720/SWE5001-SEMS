import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";
import {apiRequest} from "../../shared/api/client";
import {formatDateTime} from "../../shared/components/dateTime";
import {HomeLink} from "../../shared/components/HomeLink";
const changed=()=>window.dispatchEvent(new Event("notifications-changed"));
interface Invitation{id:string;organizationId:string;organizationName:string;role:string;status:string;expiresAt:string}
interface Notice{id:string;kind:string;title:string;message:string;link:string;createdAt:string;readAt:string|null}
interface Inbox{items:Invitation[];pendingCount:number;hasMore:boolean}
interface Notices{items:Notice[];unreadCount:number;hasMore:boolean}
const roles:Record<string,string>={ORG_ADMIN:"Organization administrator",ORGANIZER:"Event organizer",MEMBER:"Member"};
export function NotificationBell(){
 const {token}=useAuth();const [count,setCount]=useState<number|null>(null);
 useEffect(()=>{let active=true;setCount(null);async function refresh(){try{const counts=await Promise.all([apiRequest<number>("/api/v1/me/invitations/pending-count",{},token!),apiRequest<number>("/api/v1/me/notifications/unread-count",{},token!),apiRequest<number>("/api/v1/me/membership-notifications/unread-count",{},token!)]);if(active)setCount(counts[0]+counts[1]+counts[2]);}catch{if(active)setCount(null)}}
 void refresh();const timer=setInterval(()=>void refresh(),30000);const listener=()=>void refresh();window.addEventListener("notifications-changed",listener);window.addEventListener("focus",listener);return()=>{active=false;clearInterval(timer);window.removeEventListener("notifications-changed",listener);window.removeEventListener("focus",listener)}},[token]);
 return <Link className="notification-bell" to="/notifications" aria-label={count===null?"Notifications":"Notifications, "+count+" unread or pending"}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg><span>Notifications</span>{count!==null&&count>0&&<span className="notification-count">{count>99?"99+":count}</span>}</Link>
}
export function NotificationsPage(){
 const {token}=useAuth();const [invites,setInvites]=useState<Inbox|null>(null),[notices,setNotices]=useState<Notices|null>(null);
 const [invPage,setInvPage]=useState(0),[page,setPage]=useState(0),[refresh,setRefresh]=useState(0),[error,setError]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 useEffect(()=>{let active=true;setError("");setInvites(null);setNotices(null);
 Promise.all([apiRequest<Inbox>("/api/v1/me/invitations?page="+invPage,{},token!),apiRequest<Notices>("/api/v1/me/notifications?page="+page,{},token!)]).then(([i,n])=>{if(active){setInvites(i);setNotices(n)}}).catch(()=>{if(active)setError("Unable to load notifications. Please sign in again or retry.")});return()=>{active=false}},[token,invPage,page,refresh]);
 useEffect(()=>{const timer=setInterval(()=>setRefresh(v=>v+1),30000);return()=>clearInterval(timer)},[]);
 async function action(path:string,success:string){setBusy(true);setError("");try{await apiRequest(path,{method:"POST"},token!);setMessage(success);setRefresh(v=>v+1);changed()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <main className="app-shell notifications-page"><HomeLink/><header className="organization-heading"><p className="eyebrow">YOUR INBOX</p><h1>Notifications</h1><p>Organization invitations, role changes, ticket updates and reminders in one place.</p></header>
 <div className="actions"><button onClick={()=>{setRefresh(v=>v+1);changed()}}>Refresh</button><button disabled={busy||!notices?.unreadCount} onClick={()=>void action("/api/v1/me/notifications/read-all","Updates marked as read. Pending invitations still need a response.")}>Mark updates as read</button></div>
 {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}{!error&&(!invites||!notices)&&<p role="status">Loading notifications…</p>}
 <section><h2>Organization invitations {invites&&<span className="member-count">{invites.pendingCount} pending</span>}</h2>
 {invites&&!invites.items.length&&<p className="muted">No organization invitations.</p>}
 {invites?.items.map(i=><article className="card notification-card" key={i.id}><div><span className="badge">{i.status==="PENDING"?"Action needed":i.status.toLowerCase()}</span><h3>{i.organizationName}</h3><p>You have been invited as {roles[i.role]}.</p>{i.status==="PENDING"&&<p className="muted">Accept by {formatDateTime(i.expiresAt)}</p>}</div><div className="actions">{i.status==="PENDING"?<><button disabled={busy} className="primary-button" onClick={()=>void action("/api/v1/me/invitations/"+i.id+"/accept","Invitation accepted. You can now open the organization.")}>Accept</button><button disabled={busy} onClick={()=>void action("/api/v1/me/invitations/"+i.id+"/decline","Invitation declined.")}>Decline</button></>:i.status==="ACCEPTED"&&<Link to={"/organizations?organizationId="+i.organizationId}>Open organization →</Link>}</div></article>)}
 {invites&&(invPage>0||invites.hasMore)&&<div className="actions"><button disabled={invPage===0} onClick={()=>setInvPage(v=>v-1)}>Previous invitations</button><button disabled={!invites.hasMore} onClick={()=>setInvPage(v=>v+1)}>More invitations</button></div>}
 </section><MembershipUpdates/><section><h2>Ticket and event updates {notices&&<span className="member-count">{notices.unreadCount} unread</span>}</h2>
 {notices&&!notices.items.length&&<p className="muted">No updates yet. Booking confirmations and reminders will appear here.</p>}
 {notices?.items.map(n=><article className={"card notification-card "+(!n.readAt?"notification-unread":"")} key={n.id}><div><p className="eyebrow">{n.kind.replaceAll("_"," ")}</p><h3>{n.title}</h3><p>{n.message}</p><time className="muted">{formatDateTime(n.createdAt)}</time></div><div className="actions"><Link to={n.link}>View details →</Link>{!n.readAt&&<button disabled={busy} onClick={()=>void action("/api/v1/me/notifications/"+n.id+"/read","Marked as read.")}>Mark as read</button>}</div></article>)}
 {notices&&(page>0||notices.hasMore)&&<div className="actions"><button disabled={page===0} onClick={()=>setPage(v=>v-1)}>Previous updates</button><button disabled={!notices.hasMore} onClick={()=>setPage(v=>v+1)}>More updates</button></div>}
 </section><p className="muted">Saved ticket reminders appear within five minutes before registration opens. Places are not reserved. This inbox refreshes every 30 seconds while open.</p></main>
}

function MembershipUpdates(){
 const {token}=useAuth();const [data,setData]=useState<Notices|null>(null),[page,setPage]=useState(0),[refresh,setRefresh]=useState(0),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;setError("");setData(null);apiRequest<Notices>("/api/v1/me/membership-notifications?page="+page,{},token!).then(v=>{if(active)setData(v)}).catch(()=>{if(active)setError("Unable to load organization role updates.")});return()=>{active=false}},[token,page,refresh]);
 useEffect(()=>{const update=()=>setRefresh(v=>v+1);const timer=setInterval(update,30000);window.addEventListener("notifications-changed",update);return()=>{clearInterval(timer);window.removeEventListener("notifications-changed",update)}},[]);
 async function read(path:string){setBusy(true);setError("");try{await apiRequest("/api/v1/me/membership-notifications/"+path,{method:"POST"},token!);changed()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section><h2>Organization updates {data&&<span className="member-count">{data.unreadCount} unread</span>}</h2>
 {error&&<p role="alert">{error}</p>}{!data&&!error&&<p role="status">Loading role updates…</p>}
 {data&&!data.items.length&&<p className="muted">No organization updates.</p>}
 {!!data?.unreadCount&&<button disabled={busy} onClick={()=>void read("read-all")}>Mark role updates as read</button>}
 {data?.items.map(n=><article className={"card notification-card "+(!n.readAt?"notification-unread":"")} key={n.id}><div><h3>{n.title}</h3><p>{n.message}</p><time className="muted">{formatDateTime(n.createdAt)}</time></div><div className="actions"><Link to={n.link}>View organization →</Link>{!n.readAt&&<button disabled={busy} onClick={()=>void read(n.id+"/read")}>Mark role update as read</button>}</div></article>)}
 {data&&(page>0||data.hasMore)&&<div className="actions"><button disabled={page===0} onClick={()=>setPage(v=>v-1)}>Previous role updates</button><button disabled={!data.hasMore} onClick={()=>setPage(v=>v+1)}>More role updates</button></div>}
 </section>;
}
