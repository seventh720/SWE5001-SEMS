import { HomeLink } from "../../shared/components/HomeLink";
import { FeedbackNotice } from "../../shared/components/FeedbackNotice";
import { useEffect, useState, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest } from "../../shared/api/client";
import { formatDateTime } from "../../shared/components/dateTime";
import { registrationFields, type Requirements } from "../bookings/registration";
import { EventArtwork } from "./EventArtwork";
import type { TicketInventory } from "./TicketEditor";
interface Event {organizationId?:string;organizationName?:string;visibility?:string;id:string;title:string;description:string;location:string;startsAt:string;endsAt:string;capacity:number;category:string;cardTheme:string;registrationRequirements:Requirements;version:number;status:string;publicationError:string|null;cancellationReason?:string|null;}
export function EventSetupPage() {
 const {id}=useParams();const {token}=useAuth();
 const [event,setEvent]=useState<Event|null>(null);const [inventory,setInventory]=useState<TicketInventory|null>(null);
 const [reason,setReason]=useState("");
 const [error,setError]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);const [confirm,setConfirm]=useState<string|null>(null);
 async function load(){const e=await apiRequest<Event>(`/api/v1/organizer/events/${id}`,{},token!);setEvent(e);const i=await apiRequest<TicketInventory>(`/api/v1/organizer/events/${id}/ticket-types`,{},token!);setInventory(i);setError("");}
 useEffect(()=>{void load().catch(e=>setError(e.message));},[id,token]);
 useEffect(()=>{if(!["PUBLISHING","UPDATING","CANCELLING"].includes(event?.status??""))return;const timer=setInterval(()=>void load().catch(e=>setError(e.message)),3000);return()=>clearInterval(timer);},[event?.status,id,token]);
 async function act(){if(!event||!inventory||!confirm)return;setBusy(true);setError("");setMessage("");try{
 const first=confirm==="PUBLISH";const cancelling=confirm==="CANCEL";
 const saved=await apiRequest<Event>(`/api/v1/organizer/events/${id}/${cancelling?"cancel":first?"publish":"revision"}`,{method:first||cancelling?"POST":"PUT",body:JSON.stringify(cancelling?{version:event.version,reason:reason.trim()}:first?{version:event.version,ticketVersion:inventory.version}:{...event,publicationStatus:confirm})},token!);
 setEvent(saved);setConfirm(null);setMessage(saved.status==="CANCELLED"?"Event cancelled. Tickets are invalid; history is retained.":saved.status==="CANCELLING"?"Cancellation is syncing. This page will update automatically.":["PUBLISHING","UPDATING","CANCELLING"].includes(saved.status)?"Publication change is syncing. This page will update automatically.":saved.status==="PAUSED"?"Publication paused. Existing tickets remain valid.":first?"Event published.":"Publication resumed.");
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const previousStatus=useRef<string | undefined>(undefined);
 useEffect(()=>{const previous=previousStatus.current;previousStatus.current=event?.status;if(!event || !["PUBLISHING","UPDATING","CANCELLING"].includes(previous??"") || ["PUBLISHING","UPDATING","CANCELLING"].includes(event.status))return;setMessage(event.status==="CANCELLED"?"Event cancelled. Tickets are invalid; history is retained.":event.publicationError?`Publication update failed. ${event.publicationError}`:event.status==="PAUSED"?"Publication paused. Existing tickets remain valid.":"Publication updated successfully.");},[event]);
 const cancelled=event?.status==="CANCELLED";
 const draft=event?.status==="DRAFT";const pending=["PUBLISHING","UPDATING","CANCELLING"].includes(event?.status??"");
 return <main className="app-shell event-setup-workspace"><div className="page-breadcrumbs"><HomeLink /><Link className="back-link" to={event?.organizationId?`/organizer/events?organizationId=${event.organizationId}`:"/organizations"}>← Back to organization</Link></div>
 <p className="eyebrow">{draft?"PUBLICATION PREVIEW":"PUBLICATION MANAGEMENT"}</p><h1>{event?.title??"Loading event…"}</h1><p>{event?.organizationName} · {event?.visibility==="ORGANIZATION_ONLY"?"Organization members only":"Public event"}</p>
 {error&&<div role="alert" className="error-message">{error}<button disabled={busy} onClick={()=>{setConfirm(null);load().then(()=>setError("")).catch(e=>setError(e.message));}}>Reload event</button></div>}
 <FeedbackNotice message={message} tone={message.startsWith("Publication update failed")?"error":pending?"info":"success"}/>
 {event&&<><p><span className="badge">{event.status}</span> · Capacity {event.capacity}</p>{event.cancellationReason&&<p>Cancellation reason: {event.cancellationReason}</p>}{event.publicationError&&<p role="alert">{event.publicationError}</p>}{pending&&<p role="status">Syncing event status…</p>}</>}
 {event&&inventory&&<>
 <section className="card publication-controls"><h2>{draft?"Ready to publish?":"Publication management"}</h2>
 <p>{event.status==="CANCELLING"?"Cancellation is in progress. New registrations are closed. Ticket invalidation will complete automatically when the admission service is available.":cancelled?"This event is cancelled and cannot be reopened. Orders and previous check-in records are retained.":draft?"Review the saved event and ticket settings before first publication.":"Saved edits update the public event automatically. Pause publication to hide this event and stop new registrations; existing tickets remain valid."}</p>
 <div className="actions">{!pending&&!cancelled&&<Link className="secondary-button" to={`/organizer/events?edit=${id}${event.organizationId?`&organizationId=${event.organizationId}`:""}`}>Edit details & tickets</Link>}
 {event.status==="PUBLISHED"&&<Link className="secondary-button" to={`/events/${id}`}>View event</Link>}
 <button className="primary-button" disabled={busy||pending||cancelled||!inventory.ticketTypes.length} onClick={()=>setConfirm(draft?"PUBLISH":event.status==="PAUSED"?"PUBLISHED":"PAUSED")}>{event.status==="CANCELLING"?"Cancellation pending":cancelled?"Event cancelled":draft?"Publish event":event.status==="PAUSED"?"Resume publication":"Pause publication"}</button>{["PUBLISHED","PAUSED"].includes(event.status)&&<button className="danger-button" disabled={busy} onClick={()=>setConfirm("CANCEL")}>Cancel entire event</button>}</div>
 {confirm&&<div role="group" aria-label="Confirm publication"><p>{confirm==="CANCEL"?"Cancel the entire event permanently? All bookings will be cancelled, unused tickets invalidated, and attendees notified. Previous check-ins are kept as history.":confirm==="PUBLISH"?"Publish this event with the saved ticket types?":confirm==="PAUSED"?"Pause this event? New registrations will stop until you resume publication.":"Restore this event to its configured audience and reopen its scheduled registration windows?"}</p>{confirm==="CANCEL"&&<label>Cancellation reason<textarea maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} required/></label>}<div className="actions"><button className={confirm==="CANCEL"?"danger-button":"primary-button"} disabled={busy||(confirm==="CANCEL"&&!reason.trim())} onClick={act}>Confirm {confirm==="CANCEL"?"event cancellation":confirm==="PUBLISH"?"publication":confirm==="PAUSED"?"pause":"resume"}</button><button disabled={busy} onClick={()=>setConfirm(null)}>{draft?"Keep draft":"Cancel"}</button></div></div>}
 </section>
 <section className="card publication-preview"><EventArtwork category={event.category} theme={event.cardTheme}/><h2>{event.title}</h2><p>{event.location}</p><p>{formatDateTime(event.startsAt)} – {formatDateTime(event.endsAt)}</p><p className="event-description">{event.description}</p><h3>Registration requirements</h3><p>{event.registrationRequirements?([...registrationFields.filter(f=>event.registrationRequirements[f.rule]).map(f=>f.label),event.registrationRequirements.customFieldLabel].filter(Boolean).join(" · ")||"No additional information required."):"No additional information required."}</p><h3>Admission options</h3>{inventory.ticketTypes.length?inventory.ticketTypes.map((t,n)=><article className="preview-ticket" key={t.id??n}><h4>{t.name} · Free</h4><p>{t.quota} places</p><p>Registration: {formatDateTime(t.opensAt)} – {formatDateTime(t.closesAt)}</p></article>):<p>No ticket types configured. Edit this event to add tickets.</p>}</section></>}
 </main>;
}
