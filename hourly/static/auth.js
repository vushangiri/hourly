'use strict';
const $=s=>document.querySelector(s);
if(localStorage.getItem('hourly-theme')==='dark')$('.shell').classList.add('dark');
if($('#timezone'))$('#timezone').value=Intl.DateTimeFormat().resolvedOptions().timeZone;
for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>{
 const mode=b.dataset.mode;$('#mode').value=mode;$('#heading').textContent={login:'Welcome back.',register:'Make time count.',forgot:'Reset your password.'}[mode];
 $('#registration').classList.toggle('hidden',mode!=='register');$('#name').required=$('#phone').required=mode==='register';
 $('#passwordfield').classList.toggle('hidden',mode==='forgot');$('#password').required=mode!=='forgot';$('#password').autocomplete=mode==='register'?'new-password':'current-password';
 $('#submit').textContent={login:'Sign in',register:'Create account',forgot:'Send reset email'}[mode];
 document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('hidden',x.dataset.mode===mode));$('#error').textContent='';$('#message').textContent='';
};
const resetToken=location.hash.slice(1);if(resetToken)history.replaceState(null,'','/reset');
const form=$('#authform')||$('#resetform');
form.onsubmit=async e=>{e.preventDefault();const b=$('#submit');b.disabled=true;b.classList.add('busy');$('#error').textContent='';
 try{const data=Object.fromEntries(new FormData(form));if($('#resetform'))data.token=resetToken;
 const r=await fetch($('#resetform')?'/reset':'/auth',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':$('meta[name=csrf]').content},body:JSON.stringify(data)});const result=await r.json();if(!r.ok)throw Error(result.error||'Unable to continue.');
 if(data.mode==='forgot')$('#message').textContent=result.message;else location.href=$('#resetform')?'/auth':'/';
 }catch(err){$('#error').textContent=err.message||'Connection failed. Try again.';}finally{b.disabled=false;b.classList.remove('busy');}};
