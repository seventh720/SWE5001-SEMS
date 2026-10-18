import {useState, type FormEvent} from "react";
export function EventSearch({onSearch, disabled=false}:{onSearch:(keyword:string)=>void;disabled?:boolean}) {
 const [text,setText]=useState("");
 function submit(e:FormEvent){e.preventDefault();onSearch(text.trim());}
 return <form className="event-search" role="search" aria-label="Search events" onSubmit={submit}>
  <label>Search events<input type="search" placeholder="Search by event title" maxLength={200} value={text} disabled={disabled} onChange={e=>setText(e.target.value)}/></label>
  <div className="actions"><button type="submit" disabled={disabled}>Search</button><button type="button" disabled={disabled||!text} onClick={()=>{setText("");onSearch("")}}>Clear</button></div>
 </form>;
}
