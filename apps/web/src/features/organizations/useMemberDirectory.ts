import {useEffect,useState} from "react";
import {apiRequest} from "../../shared/api/client";
import type {Member} from "./OrganizationsPage";
export interface MemberPage {items:Member[];page:number;size:number;totalElements:number;totalMembers:number;totalPages:number}
export function useMemberDirectory(organizationId:string|undefined,token:string|null,size=12){
 const [search,setSearchValue]=useState(""),[page,setPage]=useState(0),[revision,setRevision]=useState(0);
 const [data,setData]=useState<MemberPage|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
 useEffect(()=>{setPage(0);setSearchValue("");setData(null)},[organizationId,token]);
 useEffect(()=>{
  let active=true;
  if(!organizationId||!token){setData(null);setLoading(false);return;}
  setLoading(true);setError("");
  const params=new URLSearchParams({page:String(page),size:String(size),search:search.trim()});
  apiRequest<MemberPage>(`/api/v1/organizations/${organizationId}/members?${params}`,{},token)
   .then(result=>{if(!active)return;if(page>0&&page>=result.totalPages){setPage(Math.max(0,result.totalPages-1));return;}setData(result)})
   .catch(e=>{if(active){setError(e.message);setData(null)}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[organizationId,token,page,size,search,revision]);
 function setSearch(value:string){setSearchValue(value);setPage(0)}
 return {data,loading,error,search,setSearch,page,setPage,reload:()=>setRevision(n=>n+1)};
}
