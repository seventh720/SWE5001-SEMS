import {useEffect,useState} from "react";
import {formatDateTime} from "../../shared/components/dateTime";
export interface Invitation {id:string;email:string;role:string;status:string;expiresAt:string}
export interface InvitationLink {id:string;email:string;url:string;expiresAt:string}
const roles:Record<string,string>={MEMBER:"Member",ORGANIZER:"Event organizer",ORG_ADMIN:"Organization administrator"};
export function InvitationPanel({invitations,link,busy,onRevoke,onRefresh}:{invitations:Invitation[];link:InvitationLink|null;busy:boolean;onRevoke:(id:string)=>void;onRefresh:()=>void}) {
 const [copyMessage,setCopyMessage]=useState("");
 useEffect(()=>setCopyMessage(""),[link?.id]);
 const activeLink=link&&invitations.some(i=>i.id===link.id&&i.status==="PENDING"&&new Date(i.expiresAt).getTime()>Date.now());
 async function copy(){try{await navigator.clipboard.writeText(link!.url);setCopyMessage("Invitation link copied.")}catch{setCopyMessage("Select the link and copy it manually.")}}
 return <section className="invitations-panel" aria-label="Invitations">
  {activeLink&&<div className="invitation-share card" key={link.id}>
   <span className="badge">Ready to share</span><h3>Invite {link.email}</h3>
   <p>An invitation has been sent to their Notifications. You can also share this link. They must sign in with <strong>{link.email}</strong> and accept it.</p>
   <label>Invitation link<input readOnly value={link.url} onFocus={e=>e.target.select()}/></label>
   <div className="actions"><button type="button" onClick={()=>void copy()}>Copy invitation link</button><span className="muted">Valid until {formatDateTime(link.expiresAt)}</span></div>
   {copyMessage&&<p role="status">{copyMessage}</p>}
  </div>}
  <div className="invitation-heading"><h3>Invitations <span className="member-count">{invitations.length}</span></h3><button type="button" disabled={busy} onClick={onRefresh}>Refresh invitations</button></div>
  {!invitations.length&&<p className="muted">No invitations yet. Send an invitation above to a registered user.</p>}
  <div className="invitation-list">{invitations.map(i=>{
   const state=i.status==="PENDING"&&new Date(i.expiresAt).getTime()<=Date.now()?"EXPIRED":i.status;
   const labels:Record<string,string>={PENDING:"Awaiting acceptance",ACCEPTED:"Accepted",REVOKED:"Revoked",EXPIRED:"Expired",DECLINED:"Declined"};
   return <article className="card invitation-record" key={i.id}><div><strong>{i.email}</strong><p>{roles[i.role]}</p><span className="muted">{state==="PENDING"?"Expires "+formatDateTime(i.expiresAt):state==="ACCEPTED"?"Invitation accepted. Membership is managed in Members.":state==="EXPIRED"?"This link has expired. Create a new invitation to try again.":"This invitation link is no longer valid."}</span></div><div className="invitation-record-actions"><span className={"invitation-status invitation-status-"+state.toLowerCase()}>{labels[state]??state}</span>{state==="PENDING"&&<button type="button" disabled={busy} onClick={()=>onRevoke(i.id)}>Revoke</button>}</div></article>
  })}</div>
 </section>;
}
