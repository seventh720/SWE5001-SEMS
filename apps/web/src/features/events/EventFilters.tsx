import {Select} from "../../shared/components/Select";
export const emptyEventFilters={status:"",timeStatus:"",visibility:""};
export type EventFilterValues=typeof emptyEventFilters;
export function eventFilterQuery(filters:EventFilterValues){return Object.entries(filters).filter(([,v])=>v).map(([k,v])=>`&${k}=${encodeURIComponent(v)}`).join("");}
export function EventFilters({value,onChange}:{value:EventFilterValues;onChange:(value:EventFilterValues)=>void}){
 return <div className="management-filters">
  <Select label="Publication status" value={value.status} onChange={status=>onChange({...value,status})} options={[{value:"",label:"All publication states"},...['DRAFT','PUBLISHING','PUBLISHED','PAUSED','UPDATING','CANCELLING','CANCELLED'].map(value=>({value,label:value[0]+value.slice(1).toLowerCase()}))]}/>
  <Select label="Event time" value={value.timeStatus} onChange={timeStatus=>onChange({...value,timeStatus})} options={[{value:"",label:"All event times"},{value:"UPCOMING",label:"Upcoming"},{value:"ONGOING",label:"Ongoing"},{value:"ENDED",label:"Ended"}]}/>
  <Select label="Visibility" value={value.visibility} onChange={visibility=>onChange({...value,visibility})} options={[{value:"",label:"All audiences"},{value:"PUBLIC",label:"Public"},{value:"ORGANIZATION_ONLY",label:"Members only"}]}/>
 </div>;
}
