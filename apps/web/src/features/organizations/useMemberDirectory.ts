import {useEffect,useState} from "react";
import {apiRequest} from "../../shared/api/client";
import type {Member} from "./OrganizationsPage";
export interface MemberPage {items:Member[];page:number;size:number;totalElements:number;totalMembers:number;totalPages:number}
export function useMemberDirectory(organizationId:string|undefined,token:string|null,size=12){
 const [role,setRoleValue]=useState(""),[status,setStatusValue]=useState("");
 const [search,setSearchValue]=useState(""),[page,setPage]=useState(0),[revision,setRevision]=useState(0);
 const [data,setData]=useState<MemberPage|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
 useEffect(()=>{setPage(0);setSearchValue("");setRoleValue("");setStatusValue("");setData(null)},[organizationId,token]);
 useEffect(()=>{
  let active=true;
  if(!organizationId||!token){setData(null);setLoading(false);return;}
  setLoading(true);setError("");
  const params=new URLSearchParams({page:String(page),size:String(size),search:search.trim()});
  if(role)params.set("role",role);if(status)params.set("status",status);
  apiRequest<MemberPage>(`/api/v1/organizations/${organizationId}/members?${params}`,{},token)
   .then(result=>{if(!active)return;if(page>0&&page>=result.totalPages){setPage(Math.max(0,result.totalPages-1));return;}setData(result)})
   .catch(e=>{if(active){setError(e.message);setData(null)}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[organizationId,token,page,size,search,revision,role,status]);
 function setSearch(value:string){setSearchValue(value);setPage(0)}
 return {role,status,setRole:(value:string)=>{setRoleValue(value);setPage(0)},setStatus:(value:string)=>{setStatusValue(value);setPage(0)},data,loading,error,search,setSearch,page,setPage,reload:()=>setRevision(n=>n+1)};
}
