import{_ as G,u as K,c as i,a as X,b as M,A as Z,d as t,w as tt,v as st,F as g,r as S,e as _,E as et,t as l,j as I,g as v,f as T,h as R,i as c,I as lt}from"../index.js";const ot={class:"pl-page"},nt={class:"pl-content"},dt={class:"pl-card"},at={class:"pl-autocomplete"},it={key:0,class:"pl-dropdown"},ct=["onMousedown"],ut={key:0,class:"pl-check"},rt={key:0,class:"pl-chips"},pt=["onClick"],_t={class:"pl-actions"},ht=["disabled"],vt={key:0,class:"pl-spinner"},mt={key:1,class:"pl-error"},yt={key:0,class:"pl-kpi-row"},kt={class:"pl-kpi"},bt={class:"pl-kpi__num"},ft={class:"pl-kpi"},gt={class:"pl-kpi__num"},wt={class:"pl-kpi"},xt={class:"pl-kpi__num"},Ot={class:"pl-kpi"},$t={class:"pl-kpi__num"},St={class:"pl-kpi pl-kpi--loss"},Rt={class:"pl-kpi__num"},Wt={class:"pl-kpi__num"},qt={key:1,class:"pl-section"},Lt={class:"pl-section__hd"},Et={class:"pl-section__count"},It={class:"pl-table-wrap"},Qt={class:"pl-table"},Ft={class:"pl-td-num"},Ct={class:"pl-td-wo"},Tt={class:"pl-td-item"},Dt={class:"pl-td-num"},Pt={class:"pl-td-num"},Ut={class:"pl-td-num"},Nt={class:"pl-td-num"},Mt={class:"pl-td-num pl-loss"},At={class:"pl-td-num"},jt={class:"pl-tfoot"},zt={class:"pl-td-num"},Vt={class:"pl-td-num"},Bt={class:"pl-td-num"},Jt={class:"pl-td-num pl-loss"},Yt={class:"pl-td-num"},Ht={key:2,class:"pl-section"},Gt={class:"pl-section__hd"},Kt={class:"pl-section__count"},Xt={class:"pl-table-wrap"},Zt={class:"pl-table"},ts={class:"pl-td-num"},ss={class:"pl-td-wo"},es=["href"],ls={class:"pl-td-item"},os={class:"pl-td-num"},ns={class:"pl-td-num"},ds={key:3,class:"pl-section"},as={class:"pl-section__hd"},is={class:"pl-section__count"},cs={class:"pl-table-wrap"},us={class:"pl-table"},rs={class:"pl-td-num"},ps={class:"pl-td-wo"},_s=["href"],hs={class:"pl-td-item"},vs={class:"pl-td-num"},ms={class:"pl-td-num"},ys={key:4,class:"pl-section"},ks={class:"pl-section__hd"},bs={class:"pl-section__count"},fs={class:"pl-table-wrap"},gs={class:"pl-table"},ws={class:"pl-td-num"},xs={class:"pl-td-wo"},Os=["href"],$s={class:"pl-td-item"},Ss={class:"pl-td-num"},Rs={class:"pl-td-num"},Ws={__name:"ProcessLossPage",setup(qs){const D=K(),W=v(""),w=v([]),Q=v(!1),r=v([]),q=v(!1),L=v(""),m=v([]),y=v([]),k=v([]),p=v([]),F=R(()=>p.value.length||m.value.length||y.value.length||k.value.length),x=R(()=>p.value.reduce((o,e)=>o+(e.sent_qty||0),0)),O=R(()=>p.value.reduce((o,e)=>o+(e.return_qty||0),0)),E=R(()=>p.value.reduce((o,e)=>o+(e.received_qty||0),0)),$=R(()=>p.value.reduce((o,e)=>o+(e.process_loss_qty||0),0)),b=R(()=>{const o=x.value-O.value;return o>0?$.value/o*100:0});let P=null;function U(){Q.value=!0,clearTimeout(P),P=setTimeout(async()=>{try{const o=await T("knit_process_loss_wo_search",{search:W.value||""});w.value=(o==null?void 0:o.message)||[]}catch{w.value=[]}},300)}function A(){setTimeout(()=>{Q.value=!1},200)}function j(o){r.value.includes(o)||r.value.push(o),W.value="",w.value=[],Q.value=!1}function z(o){r.value=r.value.filter(e=>e!==o)}function V(){r.value=[],W.value="",w.value=[],m.value=[],y.value=[],k.value=[],p.value=[],L.value=""}async function B(){if(r.value.length){q.value=!0,L.value="";try{const o=await T("knit_process_loss_details",{work_orders:JSON.stringify(r.value)}),e=(o==null?void 0:o.message)||{};m.value=e.sent||[],y.value=e.return||[],k.value=e.received||[];const s=await T("knit_process_loss_summary",{work_orders:JSON.stringify(r.value),sent:JSON.stringify(m.value),return_rows:JSON.stringify(y.value),received:JSON.stringify(k.value)});p.value=(s==null?void 0:s.message)||[]}catch(o){L.value=o.message||"Calculation failed.",console.error("Process loss error:",o)}finally{q.value=!1}}}function n(o){return o!=null?Number(o).toFixed(3):"–"}function N(o){return o>10?"pl-pct-badge--high":o>5?"pl-pct-badge--mid":"pl-pct-badge--low"}function J(o){return o>10?"pl-row--high":o>5?"pl-row--mid":""}function Y(){const o=r.value.join(", "),e=new Date().toLocaleDateString("en-IN"),s=[];s.push("PRANERA SERVICES AND SOLUTIONS PVT. LTD."),s.push("Process Loss Report"),s.push("Work Orders: "+o),s.push("Date: "+e),s.push(""),s.push("PROCESS LOSS SUMMARY"),s.push("#,Work Order,Item Code,UOM,WO Qty,Sent Qty,Return Qty,Received Qty,Loss Qty,Loss %"),p.value.forEach((a,f)=>{s.push([f+1,a.work_order,a.item_code,a.uom,n(a.wo_qty),n(a.sent_qty),n(a.return_qty),n(a.received_qty),n(a.process_loss_qty),n(a.process_loss_percentage)+"%"].join(","))}),s.push(["Totals","","","","",x.value.toFixed(3),O.value.toFixed(3),E.value.toFixed(3),$.value.toFixed(3),b.value.toFixed(2)+"%"].join(",")),s.push(""),s.push("SENT DETAILS"),s.push("#,Work Order,Stock Entry,Item Code,WO Item,UOM,WO Qty,Sent Qty"),m.value.forEach((a,f)=>{s.push([f+1,a.work_order,a.stock_entry,a.item_code,a.wo_item_code,a.uom,n(a.wo_qty),n(a.sent_qty)].join(","))}),s.push(""),s.push("RETURN DETAILS"),s.push("#,Work Order,Stock Entry,Item Code,WO Item,UOM,WO Qty,Return Qty"),y.value.forEach((a,f)=>{s.push([f+1,a.work_order,a.stock_entry,a.item_code,a.wo_item_code,a.uom,n(a.wo_qty),n(a.return_qty)].join(","))}),s.push(""),s.push("RECEIVED DETAILS"),s.push("#,Work Order,Stock Entry,Item Code,UOM,WO Qty,Received Qty"),k.value.forEach((a,f)=>{s.push([f+1,a.work_order,a.stock_entry,a.item_code,a.uom,n(a.wo_qty),n(a.received_qty)].join(","))});const u=s.join(`
`),d=new Blob([u],{type:"text/csv;charset=utf-8;"}),h=URL.createObjectURL(d),C=document.createElement("a");C.href=h,C.download="process_loss_"+r.value.join("_")+".csv",C.click(),URL.revokeObjectURL(h)}function H(){const o=r.value.join(", "),e=new Date().toLocaleDateString("en-IN"),s=`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Process Loss Report</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: Arial, sans-serif; font-size: 11px; color: #111; padding: 24px; }
  .hd  { text-align:center; margin-bottom:16px; }
  .hd h1 { font-size:15px; font-weight:800; }
  .hd h2 { font-size:12px; font-weight:600; color:#555; margin-top:2px; }
  .hd p  { font-size:10px; color:#777; margin-top:4px; }
  .kpi-row { display:flex; gap:10px; margin-bottom:16px; }
  .kpi { flex:1; border:1px solid #ddd; border-radius:6px; padding:8px 10px; text-align:center; }
  .kpi b { display:block; font-size:14px; }
  .kpi span { font-size:9px; color:#888; text-transform:uppercase; }
  .section { margin-bottom:20px; }
  .section-title { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;
    background:#f1f5f9; padding:6px 10px; border-left:3px solid #0f6e56; margin-bottom:6px; }
  table { width:100%; border-collapse:collapse; font-size:10px; }
  th { background:#0f6e56; color:white; padding:5px 7px; text-align:left; white-space:nowrap; }
  td { padding:4px 7px; border-bottom:1px solid #e5e7eb; }
  tr:nth-child(even) td { background:#f9fafb; }
  tfoot td { background:#f1f5f9; font-weight:700; border-top:2px solid #0f6e56; }
  .num { text-align:right; font-family:monospace; }
  .loss { color:#ea580c; font-weight:700; }
  @media print { body { padding:10px; } }
</style>
</head>
<body>
<div class="hd">
  <h1>PRANERA SERVICES AND SOLUTIONS PVT. LTD.</h1>
  <h2>Process Loss Report</h2>
  <p>Work Orders: ${o} &nbsp;|&nbsp; Date: ${e}</p>
</div>

<div class="kpi-row">
  <div class="kpi"><b>${p.value.length}</b><span>Items</span></div>
  <div class="kpi"><b>${x.value.toFixed(3)}</b><span>Total Sent</span></div>
  <div class="kpi"><b>${O.value.toFixed(3)}</b><span>Total Return</span></div>
  <div class="kpi"><b>${E.value.toFixed(3)}</b><span>Total Received</span></div>
  <div class="kpi"><b class="loss">${$.value.toFixed(3)}</b><span>Process Loss</span></div>
  <div class="kpi"><b>${b.value.toFixed(2)}%</b><span>Avg Loss %</span></div>
</div>

<div class="section">
  <div class="section-title">📊 Process Loss Summary</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Item Code</th><th>UOM</th><th>WO Qty</th><th>Sent Qty</th><th>Return Qty</th><th>Received Qty</th><th>Loss Qty</th><th>Loss %</th></tr></thead>
    <tbody>
      ${p.value.map((d,h)=>`<tr>
        <td class="num">${h+1}</td><td>${d.work_order}</td><td>${d.item_code}</td><td>${d.uom}</td>
        <td class="num">${n(d.wo_qty)}</td><td class="num">${n(d.sent_qty)}</td>
        <td class="num">${n(d.return_qty)}</td><td class="num">${n(d.received_qty)}</td>
        <td class="num loss">${n(d.process_loss_qty)}</td><td class="num">${n(d.process_loss_percentage)}%</td>
      </tr>`).join("")}
    </tbody>
    <tfoot><tr>
      <td colspan="5">Totals</td>
      <td class="num">${x.value.toFixed(3)}</td>
      <td class="num">${O.value.toFixed(3)}</td>
      <td class="num">${E.value.toFixed(3)}</td>
      <td class="num loss">${$.value.toFixed(3)}</td>
      <td class="num">${b.value.toFixed(2)}%</td>
    </tr></tfoot>
  </table>
</div>

<div class="section">
  <div class="section-title">📤 Sent Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>WO Item</th><th>UOM</th><th>WO Qty</th><th>Sent Qty</th></tr></thead>
    <tbody>
      ${m.value.map((d,h)=>`<tr>
        <td class="num">${h+1}</td><td>${d.work_order}</td><td>${d.stock_entry}</td><td>${d.item_code}</td>
        <td>${d.wo_item_code||""}</td><td>${d.uom}</td>
        <td class="num">${n(d.wo_qty)}</td><td class="num">${n(d.sent_qty)}</td>
      </tr>`).join("")}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">↩ Return Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>WO Item</th><th>UOM</th><th>WO Qty</th><th>Return Qty</th></tr></thead>
    <tbody>
      ${y.value.map((d,h)=>`<tr>
        <td class="num">${h+1}</td><td>${d.work_order}</td><td>${d.stock_entry}</td><td>${d.item_code}</td>
        <td>${d.wo_item_code||""}</td><td>${d.uom}</td>
        <td class="num">${n(d.wo_qty)}</td><td class="num">${n(d.return_qty)}</td>
      </tr>`).join("")}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">📥 Received Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>UOM</th><th>WO Qty</th><th>Received Qty</th></tr></thead>
    <tbody>
      ${k.value.map((d,h)=>`<tr>
        <td class="num">${h+1}</td><td>${d.work_order}</td><td>${d.stock_entry}</td><td>${d.item_code}</td>
        <td>${d.uom}</td><td class="num">${n(d.wo_qty)}</td><td class="num">${n(d.received_qty)}</td>
      </tr>`).join("")}
    </tbody>
  </table>
</div>

</body></html>`,u=window.open("","_blank");u.document.write(s),u.document.close(),setTimeout(()=>{u.print()},500)}return(o,e)=>(c(),i("div",ot,[X(Z,{title:"Process Loss",active:"",username:M(D).username,designation:M(D).designation,"show-back":!0},null,8,["username","designation"]),t("div",nt,[t("div",dt,[e[1]||(e[1]=t("div",{class:"pl-card__title"},"Select Work Orders",-1)),t("div",at,[tt(t("input",{"onUpdate:modelValue":e[0]||(e[0]=s=>W.value=s),class:"pl-input",placeholder:"Search Work Order…",onInput:U,onFocus:U,onBlur:A},null,544),[[st,W.value]]),Q.value&&w.value.length?(c(),i("div",it,[(c(!0),i(g,null,S(w.value,s=>(c(),i("div",{key:s,class:I(["pl-dropdown__item",{"pl-dropdown__item--added":r.value.includes(s)}]),onMousedown:lt(u=>j(s),["prevent"])},[t("span",null,l(s),1),r.value.includes(s)?(c(),i("span",ut,"✓")):_("",!0)],42,ct))),128))])):_("",!0)]),r.value.length?(c(),i("div",rt,[(c(!0),i(g,null,S(r.value,s=>(c(),i("div",{class:"pl-chip",key:s},[t("span",null,l(s),1),t("button",{class:"pl-chip__rm",onClick:u=>z(s)},"✕",8,pt)]))),128))])):_("",!0),t("div",_t,[t("button",{class:"pl-btn pl-btn--primary",onClick:B,disabled:!r.value.length||q.value},[q.value?(c(),i("span",vt)):_("",!0),et(" "+l(q.value?"Processing…":"⚙ Calculate Process Loss"),1)],8,ht),r.value.length||F.value?(c(),i("button",{key:0,class:"pl-btn pl-btn--ghost",onClick:V},"✕ Clear")):_("",!0),F.value?(c(),i(g,{key:1},[t("button",{class:"pl-btn pl-btn--excel",onClick:Y},"⬇ Excel"),t("button",{class:"pl-btn pl-btn--pdf",onClick:H},"⬇ PDF")],64)):_("",!0)]),L.value?(c(),i("div",mt,"⚠ "+l(L.value),1)):_("",!0)]),F.value?(c(),i("div",yt,[t("div",kt,[t("div",bt,l(p.value.length),1),e[2]||(e[2]=t("div",{class:"pl-kpi__lbl"},"Items",-1))]),t("div",ft,[t("div",gt,l(x.value.toFixed(3)),1),e[3]||(e[3]=t("div",{class:"pl-kpi__lbl"},"Total Sent",-1))]),t("div",wt,[t("div",xt,l(O.value.toFixed(3)),1),e[4]||(e[4]=t("div",{class:"pl-kpi__lbl"},"Total Return",-1))]),t("div",Ot,[t("div",$t,l(E.value.toFixed(3)),1),e[5]||(e[5]=t("div",{class:"pl-kpi__lbl"},"Total Received",-1))]),t("div",St,[t("div",Rt,l($.value.toFixed(3)),1),e[6]||(e[6]=t("div",{class:"pl-kpi__lbl"},"Process Loss",-1))]),t("div",{class:I(["pl-kpi",b.value>5?"pl-kpi--warn":"pl-kpi--ok"])},[t("div",Wt,l(b.value.toFixed(2))+"%",1),e[7]||(e[7]=t("div",{class:"pl-kpi__lbl"},"Avg Loss %",-1))],2)])):_("",!0),p.value.length?(c(),i("div",qt,[t("div",Lt,[e[8]||(e[8]=t("span",{class:"pl-section__icon"},"📊",-1)),e[9]||(e[9]=t("span",null,"Process Loss Summary",-1)),t("span",Et,l(p.value.length)+" items",1)]),t("div",It,[t("table",Qt,[e[11]||(e[11]=t("thead",null,[t("tr",null,[t("th",null,"#"),t("th",null,"Work Order"),t("th",null,"Item Code"),t("th",null,"UOM"),t("th",null,"WO Qty"),t("th",null,"Sent Qty"),t("th",null,"Return Qty"),t("th",null,"Received Qty"),t("th",null,"Loss Qty"),t("th",null,"Loss %")])],-1)),t("tbody",null,[(c(!0),i(g,null,S(p.value,(s,u)=>(c(),i("tr",{key:u,class:I(J(s.process_loss_percentage))},[t("td",Ft,l(u+1),1),t("td",Ct,l(s.work_order),1),t("td",Tt,l(s.item_code),1),t("td",null,l(s.uom),1),t("td",Dt,l(n(s.wo_qty)),1),t("td",Pt,l(n(s.sent_qty)),1),t("td",Ut,l(n(s.return_qty)),1),t("td",Nt,l(n(s.received_qty)),1),t("td",Mt,l(n(s.process_loss_qty)),1),t("td",At,[t("span",{class:I(["pl-pct-badge",N(s.process_loss_percentage)])},l(n(s.process_loss_percentage))+"%",3)])],2))),128))]),t("tfoot",null,[t("tr",jt,[e[10]||(e[10]=t("td",{colspan:"5"},"Totals",-1)),t("td",zt,l(x.value.toFixed(3)),1),t("td",Vt,l(O.value.toFixed(3)),1),t("td",Bt,l(E.value.toFixed(3)),1),t("td",Jt,l($.value.toFixed(3)),1),t("td",Yt,[t("span",{class:I(["pl-pct-badge",N(b.value)])},l(b.value.toFixed(2))+"%",3)])])])])])])):_("",!0),m.value.length?(c(),i("div",Ht,[t("div",Gt,[e[12]||(e[12]=t("span",{class:"pl-section__icon"},"📤",-1)),e[13]||(e[13]=t("span",null,"Sent Details",-1)),t("span",Kt,l(m.value.length)+" entries",1)]),t("div",Xt,[t("table",Zt,[e[14]||(e[14]=t("thead",null,[t("tr",null,[t("th",null,"#"),t("th",null,"Work Order"),t("th",null,"Stock Entry"),t("th",null,"Item Code"),t("th",null,"WO Item"),t("th",null,"UOM"),t("th",null,"WO Qty"),t("th",null,"Sent Qty")])],-1)),t("tbody",null,[(c(!0),i(g,null,S(m.value,(s,u)=>(c(),i("tr",{key:u},[t("td",ts,l(u+1),1),t("td",ss,l(s.work_order),1),t("td",null,[t("a",{href:`/app/stock-entry/${s.stock_entry}`,target:"_blank",class:"pl-link"},l(s.stock_entry),9,es)]),t("td",ls,l(s.item_code),1),t("td",null,l(s.wo_item_code),1),t("td",null,l(s.uom),1),t("td",os,l(n(s.wo_qty)),1),t("td",ns,l(n(s.sent_qty)),1)]))),128))])])])])):_("",!0),y.value.length?(c(),i("div",ds,[t("div",as,[e[15]||(e[15]=t("span",{class:"pl-section__icon"},"↩",-1)),e[16]||(e[16]=t("span",null,"Return Details",-1)),t("span",is,l(y.value.length)+" entries",1)]),t("div",cs,[t("table",us,[e[17]||(e[17]=t("thead",null,[t("tr",null,[t("th",null,"#"),t("th",null,"Work Order"),t("th",null,"Stock Entry"),t("th",null,"Item Code"),t("th",null,"WO Item"),t("th",null,"UOM"),t("th",null,"WO Qty"),t("th",null,"Return Qty")])],-1)),t("tbody",null,[(c(!0),i(g,null,S(y.value,(s,u)=>(c(),i("tr",{key:u},[t("td",rs,l(u+1),1),t("td",ps,l(s.work_order),1),t("td",null,[t("a",{href:`/app/stock-entry/${s.stock_entry}`,target:"_blank",class:"pl-link"},l(s.stock_entry),9,_s)]),t("td",hs,l(s.item_code),1),t("td",null,l(s.wo_item_code),1),t("td",null,l(s.uom),1),t("td",vs,l(n(s.wo_qty)),1),t("td",ms,l(n(s.return_qty)),1)]))),128))])])])])):_("",!0),k.value.length?(c(),i("div",ys,[t("div",ks,[e[18]||(e[18]=t("span",{class:"pl-section__icon"},"📥",-1)),e[19]||(e[19]=t("span",null,"Received Details",-1)),t("span",bs,l(k.value.length)+" entries",1)]),t("div",fs,[t("table",gs,[e[20]||(e[20]=t("thead",null,[t("tr",null,[t("th",null,"#"),t("th",null,"Work Order"),t("th",null,"Stock Entry"),t("th",null,"Item Code"),t("th",null,"UOM"),t("th",null,"WO Qty"),t("th",null,"Received Qty")])],-1)),t("tbody",null,[(c(!0),i(g,null,S(k.value,(s,u)=>(c(),i("tr",{key:u},[t("td",ws,l(u+1),1),t("td",xs,l(s.work_order),1),t("td",null,[t("a",{href:`/app/stock-entry/${s.stock_entry}`,target:"_blank",class:"pl-link"},l(s.stock_entry),9,Os)]),t("td",$s,l(s.item_code),1),t("td",null,l(s.uom),1),t("td",Ss,l(n(s.wo_qty)),1),t("td",Rs,l(n(s.received_qty)),1)]))),128))])])])])):_("",!0)])]))}},Es=G(Ws,[["__scopeId","data-v-e9133422"]]);export{Es as default};
