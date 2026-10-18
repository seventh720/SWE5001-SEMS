import {useMemberDirectory} from "./useMemberDirectory";
import {useEffect,useState} from "react";
import {Link,useParams} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";
import {apiRequest} from "../../shared/api/client";
import {Select} from "../../shared/components/Select";
import {type Member,type Organization,roles,roleNames} from "./OrganizationsPage";

const PAGE_SIZE=12;
export function OrganizationMembersPage(){
 const {id}=useParams();const {token}=useAuth();
 const [org,setOrg]=useState<Organization>();
 const directory=useMemberDirectory(org?.id,token,PAGE_SIZE);
 const {data,search,setSearch,page,setPage}=directory;
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 useEffect(()=>{
  let active=true;setLoading(true);setError("");setMessage("");setOrg(undefined);
  apiRequest<Organization[]>("/api/v1/me/organizations",{},token!)
   .then(orgs=>{if(active)setOrg(orgs.find(o=>o.id===id))})
   .catch(e=>{if(active)setError(e.message)})
   .finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[id,token]);
 async function update(member:Member,patch:Partial<Member>){
  setBusy(true);setError("");setMessage("");
  try{
   await apiRequest(`/api/v1/organizations/${id}/members/${member.userId}`,{method:"PUT",body:JSON.stringify({...member,...patch})},token!);
   const orgs=await apiRequest<Organization[]>("/api/v1/me/organizations",{},token!);
   const current=orgs.find(o=>o.id===id);setOrg(current);
   if(!current){setMessage("Your organization access has changed.");return;}
   directory.reload();
   setMessage("Membership updated.");
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const query=search.trim();
 const pages=Math.max(1,data?.totalPages??0);const currentPage=page;
 const visible=data?.items??[];
 const admin=org?.role==="ORG_ADMIN";
 return <main className="app-shell organization-members-page">
  <Link to={`/organizations?organizationId=${id}&section=members`}>← Back to organization</Link>
  <p className="eyebrow">{org?.name??"ORGANIZATION"}</p><h1>All members</h1>
  <p>{admin?"Search your organization and manage member roles and access.":"Search your organization's member directory."}</p>
  {(error||directory.error)&&<p role="alert">{error||directory.error}</p>}{message&&<p role="status">{message}</p>}
  {loading?<p role="status">Loading members…</p>:org&&<>
   <div className="member-directory-toolbar"><label>Search members<input type="search" placeholder="Search by username or email" value={search} maxLength={200} onChange={e=>setSearch(e.target.value)}/></label><p role="status">{data?.totalElements??0} matching · {data?.totalMembers??0} total</p></div>
   {directory.loading?<p role="status">Loading members…</p>:!visible.length?<p>{query?"No members match your search.":"No members in this organization."}</p>:<>
    <div className="member-directory-list">{visible.map(m=><article className="card member-directory-row" key={m.userId}>
     <div className="member-directory-person"><strong>{m.username}</strong><p>{m.email}</p></div>
     {admin?<><Select label={`Role for ${m.username}`} value={m.role} disabled={busy} options={roles.map(r=>({value:r,label:roleNames[r]}))} onChange={value=>void update(m,{role:value})}/><Select label={`Status for ${m.username}`} value={m.status} disabled={busy} options={[{value:"ACTIVE",label:"Active"},{value:"SUSPENDED",label:"Suspended"},{value:"REMOVED",label:"Removed"}]} onChange={value=>void update(m,{status:value})}/></>:<p>{roleNames[m.role]} · {m.status}</p>}
    </article>)}</div>
    <nav className="member-pagination" aria-label="Member pages"><button disabled={currentPage===0||busy} onClick={()=>setPage(currentPage-1)}>Previous</button><span>Page {currentPage+1} of {pages} · {currentPage*PAGE_SIZE+1}–{Math.min((currentPage+1)*PAGE_SIZE,data?.totalElements??0)} of {data?.totalElements??0}</span><button disabled={currentPage+1>=pages||busy} onClick={()=>setPage(currentPage+1)}>Next</button></nav>
   </>}
  </>}
 </main>;
}
