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
interface Event {organizationId?:string;organizationName?:string;visibility?:string;id:string;title:string;description:string;location:string;startsAt:string;endsAt:string;capacity:number;category:string;cardTheme:string;registrationRequirements:Requirements;version:number;status:string;publicationError:string|null;}
export function EventSetupPage() {
 const {id}=useParams();const {token}=useAuth();
 const [event,setEvent]=useState<Event|null>(null);const [inventory,setInventory]=useState<TicketInventory|null>(null);
 const [error,setError]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);const [confirm,setConfirm]=useState<string|null>(null);
 async function load(){const [e,i]=await Promise.all([apiRequest<Event>(`/api/v1/organizer/events/${id}`,{},token!),apiRequest<TicketInventory>(`/api/v1/organizer/events/${id}/ticket-types`,{},token!)]);setEvent(e);setInventory(i);}
 useEffect(()=>{void load().catch(e=>setError(e.message));},[id,token]);
 useEffect(()=>{if(!["PUBLISHING","UPDATING"].includes(event?.status??""))return;const timer=setInterval(()=>void load().catch(e=>setError(e.message)),3000);return()=>clearInterval(timer);},[event?.status,id,token]);
 async function act(){if(!event||!inventory||!confirm)return;setBusy(true);setError("");setMessage("");try{
 const first=confirm==="PUBLISH";
 const saved=await apiRequest<Event>(`/api/v1/organizer/events/${id}/${first?"publish":"revision"}`,{method:first?"POST":"PUT",body:JSON.stringify(first?{version:event.version,ticketVersion:inventory.version}:{...event,publicationStatus:confirm})},token!);
 setEvent(saved);setConfirm(null);setMessage(["PUBLISHING","UPDATING"].includes(saved.status)?"Publication change is syncing. This page will update automatically.":saved.status==="PAUSED"?"Publication paused. Existing tickets remain valid.":first?"Event published.":"Publication resumed.");
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const previousStatus=useRef<string | undefined>(undefined);
 useEffect(()=>{const previous=previousStatus.current;previousStatus.current=event?.status;if(!event || !["PUBLISHING","UPDATING"].includes(previous??"") || ["PUBLISHING","UPDATING"].includes(event.status))return;setMessage(event.publicationError?`Publication update failed. ${event.publicationError}`:event.status==="PAUSED"?"Publication paused. Existing tickets remain valid.":"Publication updated successfully.");},[event]);
 const draft=event?.status==="DRAFT";const pending=["PUBLISHING","UPDATING"].includes(event?.status??"");
 return <main className="app-shell event-setup-workspace"><div className="page-breadcrumbs"><HomeLink /><Link className="back-link" to={event?.organizationId?`/organizer/events?organizationId=${event.organizationId}`:"/organizations"}>← Back to organization</Link></div>
 <p className="eyebrow">{draft?"PUBLICATION PREVIEW":"PUBLICATION MANAGEMENT"}</p><h1>{event?.title??"Loading event…"}</h1><p>{event?.organizationName} · {event?.visibility==="ORGANIZATION_ONLY"?"Organization members only":"Public event"}</p>
 {error&&<div role="alert" className="error-message">{error}<button disabled={busy} onClick={()=>{setConfirm(null);load().then(()=>setError("")).catch(e=>setError(e.message));}}>Reload event</button></div>}
 <FeedbackNotice message={message} tone={message.startsWith("Publication update failed")?"error":pending?"info":"success"}/>
 {event&&inventory&&<><p><span className="badge">{event.status}</span> · Capacity {event.capacity}</p>{event.publicationError&&<p role="alert">{event.publicationError}</p>}
 <section className="card publication-controls"><h2>{draft?"Ready to publish?":"Publication management"}</h2>
 <p>{draft?"Review the saved event and ticket settings before first publication.":"Saved edits update the public event automatically. Pause publication to hide this event and stop new registrations; existing tickets remain valid."}</p>
 <div className="actions">{!pending&&<Link className="secondary-button" to={`/organizer/events?edit=${id}${event.organizationId?`&organizationId=${event.organizationId}`:""}`}>Edit details & tickets</Link>}
 {event.status==="PUBLISHED"&&<Link className="secondary-button" to={`/events/${id}`}>View event</Link>}
 <button className="primary-button" disabled={busy||pending||!inventory.ticketTypes.length} onClick={()=>setConfirm(draft?"PUBLISH":event.status==="PAUSED"?"PUBLISHED":"PAUSED")}>{draft?"Publish event":event.status==="PAUSED"?"Resume publication":"Pause publication"}</button></div>
 {pending&&<p role="status">Syncing publication status…</p>}
 {confirm&&<div role="group" aria-label="Confirm publication"><p>{confirm==="PUBLISH"?"Publish this event with the saved ticket types?":confirm==="PAUSED"?"Pause this event? New registrations will stop until you resume publication.":"Restore this event to its configured audience and reopen its scheduled registration windows?"}</p><div className="actions"><button disabled={busy} onClick={act}>Confirm {confirm==="PUBLISH"?"publication":confirm==="PAUSED"?"pause":"resume"}</button><button disabled={busy} onClick={()=>setConfirm(null)}>{draft?"Keep draft":"Cancel"}</button></div></div>}
 </section>
 <section className="card publication-preview"><EventArtwork category={event.category} theme={event.cardTheme}/><h2>{event.title}</h2><p>{event.location}</p><p>{formatDateTime(event.startsAt)} – {formatDateTime(event.endsAt)}</p><p className="event-description">{event.description}</p><h3>Registration requirements</h3><p>{event.registrationRequirements?([...registrationFields.filter(f=>event.registrationRequirements[f.rule]).map(f=>f.label),event.registrationRequirements.customFieldLabel].filter(Boolean).join(" · ")||"No additional information required."):"No additional information required."}</p><h3>Admission options</h3>{inventory.ticketTypes.length?inventory.ticketTypes.map((t,n)=><article className="preview-ticket" key={t.id??n}><h4>{t.name} · Free</h4><p>{t.quota} places</p><p>Registration: {formatDateTime(t.opensAt)} – {formatDateTime(t.closesAt)}</p></article>):<p>No ticket types configured. Edit this event to add tickets.</p>}</section></>}
 </main>;
}
