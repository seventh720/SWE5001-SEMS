import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
export function FeedbackNotice({message,tone="success"}:{message:string;tone?:"success"|"info"|"error"}) {
 const [visible,setVisible]=useState(false);
 useEffect(()=>{setVisible(!!message);if(!message||tone!=="success")return;const timer=window.setTimeout(()=>setVisible(false),8000);return()=>window.clearTimeout(timer);},[message,tone]);
 if(!message||!visible)return null;
 return createPortal(<div className={`feedback-notice feedback-${tone}`} role={tone==="error"?"alert":"status"} aria-live={tone==="error"?"assertive":"polite"} aria-atomic="true"><span className="feedback-icon" aria-hidden="true">{tone==="success"?"✓":tone==="error"?"!":"i"}</span><p>{message}</p><button type="button" aria-label="Dismiss notification" onClick={()=>setVisible(false)}>×</button></div>,document.body);
}
