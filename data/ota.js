const form      = document.getElementById('ota-form');
const fileInput = document.getElementById('file-input');
const btn       = document.getElementById('upload-btn');
const statusEl  = document.getElementById('status');
const progWrap  = document.getElementById('progress-wrap');
const progBar   = document.getElementById('progress-bar');

const setStatus = (cls, msg) => {
  statusEl.className     = cls;
  statusEl.textContent   = msg;
  statusEl.style.display = 'block';
};

// Wrap XHR in a Promise so the upload can be awaited like fetch.
// XHR is kept specifically for upload progress events, which the fetch API
// does not expose.
const uploadFirmware = (file) => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener('progress', ({ loaded, total, lengthComputable }) => {
    if (lengthComputable) {
      progBar.value = Math.round((loaded / total) * 100);
    }
  });

  xhr.addEventListener('load', () => resolve({ status: xhr.status, text: xhr.responseText }));
  xhr.addEventListener('error', () => reject(new Error('network')));

  const fd = new FormData();
  fd.append('firmware', file);

  xhr.open('POST', '/ota');
  xhr.send(fd);
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const file = fileInput.files[0];
  if (!file) { alert('Select a .bin file first.'); return; }

  btn.disabled           = true;
  progWrap.style.display = 'block';
  progBar.value          = 0;
  setStatus('prog', `Uploading ${file.name} (${Math.round(file.size / 1024)} KB)\u2026`);

  try {
    const { status, text } = await uploadFirmware(file);

    progBar.value = 100;

    if (status === 200 && (text.startsWith('OK') || text.startsWith('Reboot'))) {
      setStatus('ok', text);
    } else {
      setStatus('err', text || `Upload failed (HTTP ${status})`);
      btn.disabled = false;
    }
  } catch {
    // XHR fires 'error' when the connection drops — which is exactly what
    // happens when a successful flash causes the board to reboot mid-response.
    progBar.value = 100;
    setStatus('ok', 'Upload complete. Board is rebooting \u2014 reconnect in ~10\u00a0s.');
  }
});
