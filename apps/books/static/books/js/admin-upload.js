(async () => {
    const root=document.body;
    const response=await fetch(root.dataset.translationsUrl||'',{headers:{'Accept':'application/json'}});
    if(!response.ok)throw new Error(`translation bundle ${response.status}`);
    const translations=(await response.json()).translations||{};
    const tr=(key,params={})=>{const template=translations[key];if(typeof template!=='string')throw new Error(`Missing translation: js.upload.${key}`);return template.replace(/\{([a-zA-Z0-9_]+)\}/g,(_,name)=>String(params[name]??''))};
    const csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;
    const type=document.getElementById('assetType'),files=document.getElementById('files'),selectedFiles=document.getElementById('selectedFiles');
    const results=document.getElementById('results'),list=document.getElementById('resultList'),error=document.getElementById('error'),progress=document.getElementById('progress');
    let links=[];
    const esc=(value='')=>String(value??'').replace(/[&<>'"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[char]));
    const csvCell=(value='')=>{let text=String(value??'');if(/^[=+@-]/.test(text))text="'"+text;return `"${text.replaceAll('\"','\"\"')}"`};
    document.querySelectorAll('[data-type]').forEach(btn=>btn.addEventListener('click',()=>{
        document.querySelectorAll('[data-type]').forEach(x=>x.classList.toggle('active',x===btn));type.value=btn.dataset.type;
        const cover=type.value==='cover';files.accept=cover?'image/*':'.pdf';
        document.getElementById('assetTitle').textContent=cover?tr('cover_title'):tr('pdf_title');
        document.getElementById('assetHint').textContent=cover?tr('cover_hint'):tr('pdf_hint');
        document.getElementById('assetIcon').dataset.feather=cover?'image':'file-text';files.value='';selectedFiles.textContent=tr('none_selected');links=[];results.classList.add('hidden');feather.replace();
    }));
    files.addEventListener('change',()=>{const chosen=[...files.files];selectedFiles.textContent=chosen.length?tr('selected_files',{count:chosen.length.toLocaleString('fa-IR'),names:chosen.slice(0,2).map(file=>file.name).join(', '),more:chosen.length>2?'…':''}):tr('none_selected')});
    document.getElementById('assetForm').addEventListener('submit',async e=>{
        e.preventDefault();error.classList.add('hidden');results.classList.add('hidden');progress.classList.remove('hidden');
        const fd=new FormData();fd.append('fileType',type.value);[...files.files].forEach(file=>fd.append('files',file));
        try{const response=await fetch(document.body.dataset.uploadUrl || '',{method:'POST',headers:{'X-CSRFToken':csrf},body:fd});const data=await response.json();if(!response.ok||!data.success)throw new Error(data.message||tr('upload_failed'));links=data.links||[];render()}
        catch(err){error.textContent=err.message;error.classList.remove('hidden')}finally{progress.classList.add('hidden')}
    });
    function render(){list.innerHTML=links.map((x,i)=>`<div class="result-row"><strong class="text-sm">${esc(x.fileName)}</strong><code title="${esc(x.link)}">${esc(x.link)}</code><button class="copy" data-copy="${i}" title="${tr('copy_link')}"><i data-feather="copy"></i></button></div>`).join('');results.classList.remove('hidden');feather.replace()}
    list.addEventListener('click',e=>{const b=e.target.closest('[data-copy]');if(b){navigator.clipboard.writeText(links[b.dataset.copy].link);b.innerHTML='<i data-feather="check"></i>';feather.replace()}});
    document.getElementById('copyAll').addEventListener('click',()=>navigator.clipboard.writeText(links.map(x=>x.link).join('\n')));
    document.getElementById('downloadCsv').addEventListener('click',()=>{const body='filename,url\n'+links.map(x=>`${csvCell(x.fileName)},${csvCell(x.link)}`).join('\n');const blob=new Blob(['\ufeff'+body],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`library-${type.value}-links.csv`;a.click();URL.revokeObjectURL(a.href)});
    feather.replace();
})();
