import { DateTimeField } from "../../shared/components/DateTimeField";
import { singaporeInput } from "../../shared/components/dateTime";
export interface TicketRow { id?: string; name: string; quota: number; opensAt: string; closesAt: string; }
export interface TicketInventory { version: number; ticketTypes: TicketRow[]; }
export function initialTicket(capacity = 1, start = ""): TicketRow {return {name:"General admission",quota:capacity,opensAt:singaporeInput(new Date().toISOString()),closesAt:start};}
export function TicketEditor({tickets,onChange,capacity,startsAt,disabled}:{tickets:TicketRow[];onChange:(rows:TicketRow[])=>void;capacity:number;startsAt:string;disabled:boolean}) {
 const total=tickets.reduce((sum,t)=>sum+t.quota,0);
 function change(index:number,key:keyof TicketRow,value:string|number){onChange(tickets.map((t,n)=>n===index?{...t,[key]:value}:t));}
 return <section className="inline-ticket-setup"><h3>Tickets & registration window</h3><p className="muted">Times use Singapore time (UTC+08:00). Existing tickets remain valid when you save changes. Quotas must cover issued places.</p>
 <fieldset className="ticket-fields" disabled={disabled}>
 {tickets.map((t,n)=><div className="ticket-row" key={t.id ?? `new-${n}`}><div className="form-grid">
 <label>Ticket name {n+1}<input required maxLength={100} value={t.name} onChange={e=>change(n,"name",e.target.value)}/></label>
 <label>Quota {n+1}<input required type="number" min={1} max={capacity} value={t.quota} onChange={e=>change(n,"quota",Number(e.target.value))}/></label>
 <DateTimeField label={`Sales open ${n+1}`} value={t.opensAt} atOrBefore={startsAt} onChange={v=>change(n,"opensAt",v)}/>
 <DateTimeField label={`Sales close ${n+1}`} value={t.closesAt} after={t.opensAt} atOrBefore={startsAt} onChange={v=>change(n,"closesAt",v)}/>
 </div>{tickets.length>1&&<button type="button" className="secondary-button" onClick={()=>onChange(tickets.filter((_,i)=>i!==n))}>Remove ticket type {n+1}</button>}</div>)}
 <p>Total allocation: {total} / {capacity}</p>{total>capacity&&<p role="alert">Reduce the total quota to fit the event capacity.</p>}
 <button type="button" className="secondary-button" disabled={tickets.length>=20} onClick={()=>onChange([...tickets,{...initialTicket(1,startsAt),name:""}])}>Add ticket type</button>
 </fieldset></section>;
}
