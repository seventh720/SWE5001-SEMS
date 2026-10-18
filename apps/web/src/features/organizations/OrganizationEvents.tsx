import {EventSearch} from "../events/EventSearch";
import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";
import {apiRequest} from "../../shared/api/client";
import {formatDateTime} from "../../shared/components/dateTime";
import type {Organization} from "./OrganizationsPage";

interface EventSummary {
  id:string; title:string; location:string; startsAt:string; status?:string;
  visibility:string;
}
interface EventPage {items:EventSummary[];totalElements:number;totalPages:number}
export function OrganizationEvents({organization}:{organization:Organization}) {
  const {token}=useAuth();
  const manager=organization.role!=="MEMBER";
  const [keyword,setKeyword]=useState("");
  const [retry,setRetry]=useState(0);
  const [page,setPage]=useState(0);
  const [data,setData]=useState<EventPage|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{
    let active=true;
    setLoading(true);setError("");setData(null);
    const endpoint=manager?"/api/v1/organizer/events":"/api/v1/events";
    apiRequest<EventPage>(endpoint+"?organizationId="+organization.id+"&page="+page+"&size=6&keyword="+encodeURIComponent(keyword),{},token!)
      .then(result=>{if(active){if(page>0&&page>=result.totalPages)setPage(Math.max(0,result.totalPages-1));else setData(result)}})
      .catch(()=>{if(active)setError("Unable to load organization events. Please try again later.")})
      .finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[organization.id,manager,page,token,keyword,retry]);
  return <section className="organization-events" aria-label="Organization events">
    <div className="organization-events-heading"><div><h3>{manager?"Events":"Upcoming events"} {data&&<span className="member-count">{data.totalElements}</span>}</h3>
      <p>{manager?"Create events, manage publication and coordinate your event team.":"Discover public and members-only events from your organization."}</p></div>
      {manager&&<Link className="primary-button" to={"/organizer/events?organizationId="+organization.id+"&create=true"}>Create event</Link>}
    </div>
    <EventSearch onSearch={value=>{setKeyword(value);setPage(0);setRetry(v=>v+1)}}/>
    {loading&&<p role="status">Loading events…</p>}
    {error&&<p role="alert">{error} <button onClick={()=>setRetry(v=>v+1)}>Retry</button></p>}
    {data&&!data.items.length&&keyword&&<p>No events match your search.</p>}
    {data&&!data.items.length&&!keyword&&<div className="organization-events-empty"><h4>{manager?"Your next event starts here":"No upcoming events yet"}</h4><p>{manager?"Create your first event for this organization.":"Check back for new activities from your organization."}</p></div>}
    <div className="organization-event-grid">{data?.items.map(event=><article className="card organization-event-card" key={event.id}>
      <div className="organization-event-meta"><span className="badge">{event.status??"PUBLISHED"}</span><span>{event.visibility==="ORGANIZATION_ONLY"?"Members only":"Public"}</span></div>
      <h4><Link to={manager?"/organizer/events/"+event.id+"/setup":"/events/"+event.id}>{event.title}</Link></h4>
      <p>{formatDateTime(event.startsAt)}</p><p>{event.location}</p>
      <div className="organization-event-actions">{manager?<><Link to={"/organizer/events/"+event.id+"/setup"}>Manage event →</Link><Link to={"/organizer/events/"+event.id+"/staff"}>Staff & attendance</Link></>:<Link to={"/events/"+event.id}>View event →</Link>}</div>
    </article>)}</div>
    {data&&data.totalPages>1&&<div className="actions"><button disabled={page===0} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page+1} of {data.totalPages}</span><button disabled={page+1>=data.totalPages} onClick={()=>setPage(p=>p+1)}>Next</button></div>}
  </section>;
}
