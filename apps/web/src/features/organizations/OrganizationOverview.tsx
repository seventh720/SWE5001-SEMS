import {useEffect,useState} from "react";
import {useAuth} from "../auth/AuthContext";
import {apiRequest} from "../../shared/api/client";
import {formatDateTime} from "../../shared/components/dateTime";

interface Overview {totalEvents:number;validTickets:number;checkedIn:number;updatedAt:string}
export function OrganizationOverview({organizationId}:{organizationId:string}){
 const {token}=useAuth();
 const [data,setData]=useState<Overview|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
 const [refresh,setRefresh]=useState(0);
 useEffect(()=>{
  let active=true;setLoading(true);setError("");setData(null);
  apiRequest<Overview>(`/api/v1/organizer/organizations/${organizationId}/overview`,{},token!)
   .then(value=>{if(active)setData(value)})
   .catch(()=>{if(active)setError("Organization overview is unavailable. Please try again.")})
   .finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[organizationId,token,refresh]);
 const rate=data&&data.validTickets>0?`${(data.checkedIn/data.validTickets*100).toFixed(1)}%`:"—";
 return <section className="organization-overview" aria-labelledby="organization-overview-title" aria-busy={loading}>
  <div className="organization-overview-heading"><div><p className="eyebrow">ALL-TIME ORGANIZATION TOTALS</p><h3 id="organization-overview-title">Organization at a glance</h3></div><button disabled={loading} onClick={()=>setRefresh(n=>n+1)}>{loading?"Refreshing…":"Refresh overview"}</button></div>
  {error&&<p role="alert">{error}</p>}
  {loading?<p role="status">Loading organization overview…</p>:data&&<>
   <dl className="organization-overview-metrics">
    <div><dt>Total events</dt><dd>{data.totalEvents.toLocaleString()}</dd><p>Including drafts and cancelled events</p></div>
    <div><dt>Valid tickets</dt><dd>{data.validTickets.toLocaleString()}</dd><p>Including tickets already checked in</p></div>
    <div><dt>Checked in</dt><dd>{data.checkedIn.toLocaleString()}</dd><p>Across events in this organization</p></div>
    <div><dt>Check-in rate</dt><dd>{rate}</dd><p>{data.validTickets?"Checked in ÷ valid tickets":"No valid tickets yet"}</p></div>
   </dl>
   <p className="organization-overview-note">Ticket totals exclude cancelled tickets and cancelled events. Ended events remain included. Updated {formatDateTime(data.updatedAt)}.</p>
   <p className="organization-overview-note">Browse the events below to manage details or view staff and attendance. Filters apply to the event list; these totals cover the whole organization.</p>
  </>}
 </section>;
}
