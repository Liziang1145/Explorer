/* Protocol field interpretation shared by dashboard and physical preview. */
window.OperatorView={
 read(item){const d=item?.data||{},body=d.body||{},event=d.event||{},cache=item?.age_ms||0,age=d.age_ms==null?null:d.age_ms+cache;return {body,event,age,fresh:!item?.error&&d.fresh===true&&age<300,available:d.available===true}},
 number(value,n=2){return typeof value==='number'&&Number.isFinite(value)?value.toFixed(n):'—'},
 pose(body,key,fresh){const p=body[String(key)],bit=Number(key)-3,mask=Number(body['1']||0);if(!fresh||!(mask&(1<<bit))||!Array.isArray(p?.['1']))return '跟踪无效 / 未更新';return p['1'].map(v=>this.number(v)).join(' / ')+' m\n'+(p['2']||[]).map(v=>this.number(v,3)).join(' / ')},
 controls(body,fresh){const c=body['11']||{},valid=fresh?Number(c['7']||0):0;return [['左扳机',0,'1'],['右扳机',1,'2'],['左侧握',2,'3'],['右侧握',3,'4'],['左摇杆',4,'5'],['右摇杆',5,'6']].map(([name,bit,key])=>[name,valid&(1<<bit)?(Array.isArray(c[key])?c[key].map(v=>this.number(v)).join(' / '):this.number(c[key])):'无效'])},
 buttons(body,fresh){const f=body['13'];return ['A','B','X','Y'].map((name,bit)=>({name,valid:fresh&&f?.['0']===1&&!!(f['1']&(1<<bit)),pressed:fresh&&!!(f?.['2']&(1<<bit))}))}
};
