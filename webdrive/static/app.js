// Filename: webdrive/static/app.js
// Frontend JS that talks to the webdrive proxy endpoints (same-origin).
async function fetchDrive() {
  try {
    const res = await fetch('/web/api/drive');
    if (!res.ok) {
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      throw new Error('Failed to fetch drive');
    }
    const data = await res.json();
    renderFiles(data.files || []);
    renderUsage();
  } catch (err) {
    console.error(err);
    document.getElementById('filesGrid').innerHTML = '<div class="text-red-400">Error loading files</div>';
  }
}

function renderFiles(files) {
  const grid = document.getElementById('filesGrid');
  grid.innerHTML = '';
  if (!files || files.length === 0) {
    grid.innerHTML = '<div class="text-slate-400">No files yet</div>';
    return;
  }
  files.forEach(f => {
    const el = document.createElement('div');
    el.className = 'bg-slate-800 p-4 rounded-lg shadow';
    el.innerHTML = `
      <div class="text-sm text-slate-300 truncate">${escapeHtml(f.original_name)}</div>
      <div class="text-xs text-slate-500 mt-1">${(f.size/1024/1024).toFixed(2)} MB</div>
      <div class="mt-3 flex justify-between items-center">
        <button class="downloadBtn text-sm bg-indigo-600 px-3 py-1 rounded">Download</button>
        <div class="text-xs text-slate-400">${new Date(f.created_at).toLocaleString()}</div>
      </div>
    `;
    el.querySelector('.downloadBtn').addEventListener('click', ()=> {
      window.open(`/web/api/files/${f.id}/download`, '_blank');
    });
    grid.appendChild(el);
  });
}

function escapeHtml(unsafe) {
  return (unsafe || '').toString().replace(/[&<"'>]/g, function(m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]); });
}

async function renderUsage() {
  try {
    const res = await fetch('/web/api/usage');
    if (!res.ok) return;
    const u = await res.json();
    const pct = Math.round(((u.used_bytes || 0) / (u.quota_bytes || 1)) * 100);
    const usageDiv = document.getElementById('usage');
    usageDiv.innerHTML = `
      <div class="mb-2 text-sm text-slate-300">${(u.used_bytes/1024/1024).toFixed(2)} MB used of ${(u.quota_bytes/1024/1024/1024).toFixed(1)} GB</div>
      <div class="w-full bg-slate-700 rounded h-3 overflow-hidden">
        <div class="bg-gradient-to-r from-indigo-600 to-cyan-400 h-3" style="width: ${Math.min(100,pct)}%"></div>
      </div>
    `;
  } catch (err) {
    console.error(err);
  }
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append('upload', file, file.name);
  const res = await fetch('/web/api/upload', { method: 'POST', body: fd });
  if (!res.ok) {
    const txt = await res.text();
    alert('Upload failed: ' + txt);
    return;
  }
  await fetchDrive();
}

document.addEventListener('DOMContentLoaded', () => {
  fetchDrive();

  const dropzone = document.getElementById('dropzone');
  dropzone.addEventListener('dragover', (e)=>{ e.preventDefault(); dropzone.classList.add('bg-slate-800'); });
  dropzone.addEventListener('dragleave', (e)=>{ e.preventDefault(); dropzone.classList.remove('bg-slate-800'); });
  dropzone.addEventListener('drop', async (e)=> {
    e.preventDefault();
    dropzone.classList.remove('bg-slate-800');
    const file = e.dataTransfer.files[0];
    if (file) await uploadFile(file);
  });

  const fileInput = document.getElementById('fileInput');
  const uploadButton = document.getElementById('uploadButton');
  fileInput.addEventListener('change', async (e)=>{
    const f = e.target.files[0];
    if (f) await uploadFile(f);
  });
  uploadButton.addEventListener('click', ()=> fileInput.click());

  document.getElementById('refreshBtn').addEventListener('click', ()=> fetchDrive());
});