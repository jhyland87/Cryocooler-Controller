
const GROUP_ORDER = [
  'timestamp',
  'state',
  'cold_head',
  'dac',
  'rms',
  'relay',
  'indicator',
  'status',
  'cooling',
  'waveform',
  'system',
  'accelerometer',
  'firmware',
];



function groupOf(key) {
  const i = key.indexOf('.');
  return i > 0 ? key.slice(0, i) : key;
}

function fieldOf(key) {
  const i = key.indexOf('.');
  return i > 0 ? key.slice(i + 1) : key;
}

function cssClass(key, value) {
  if (key === 'indicator.fault' && value) return 'fault';
  if (key === 'indicator.ready' && value) return 'ready';
  if (key === 'relay.alarm'     && value) return 'warn';
  return '';
}

function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

function formatEpoch(value) {
  if (!value || value === 0) return `${value} (not synced)`;
  return `${value}<br/>${new Date(value * 1000).toUTCString()}`;
}

function objectToTable(obj) {
  return Object.entries(obj).map(([k,v])=>`<tr><td>${k}</td><td>${typeof v === 'object'
    ? objectToTable(v)
    : v}</td></tr>`).join('');
}

const overrides = {};

overrides['mod'] = (key, mods) => {

  let ret = `<table>
  <thead>
    <tr>
      <th>Service</th>
      <th>init</th>
      <th>service</th>
    </tr>
  </thead>
  <tbody>`;

  for(const [svc, svcStatus] of Object.entries(mods)){
    ret += `<tr><td>${svc}</td>`;

    for( const [svcName, svcVal] of Object.entries(svcStatus)){
      ret+= `<td class="centered">${svcVal}</td>`;
    }
    ret += `</tr>`;
  }
  ret += `</tbody></table>`

  return ret
}

async function refresh() {
  try {
    const data = await (await fetch('/api/telemetry')).json();

    // Group flat dot-notation keys by prefix
    const groups = {};
    for (const [key, value] of Object.entries(data)) {
      const g = groupOf(key);
      (groups[g] = groups[g] || []).push([key, value]);
    }

    const ordered = GROUP_ORDER.filter(g => groups[g]);
    const extra   = Object.keys(groups).filter(g => !GROUP_ORDER.includes(g));

    document.getElementById('dash').innerHTML = [...ordered, ...extra].map(g => {
      const rows = groups[g].map(([key, value]) => {
        if ( typeof overrides[key] === 'function'){
          return overrides[key](key, value);
        }

        //const display = key === 'timestamp' ? formatEpoch(value) : value;
        if ( typeof value === 'object'){
          return objectToTable(value)
        }

        return `<tr>
          <td>${fieldOf(key)}</td>
          <td class="${cssClass(key, value)}">${objectToTable(value)}</td>
        </tr>`;
      }).join('');
      return `<div class="group">
        <div class="gt">${g.replace(/_/g, ' ')}</div>
        <table>${rows}</table>
      </div>`;
    }).join('');

    setStatus('Updated: ' + new Date().toLocaleTimeString());
  } catch (e) {
    setStatus('Error: ' + e.message);
  }
}

let timer = null;

function setRefresh() {
  const checked = document.getElementById('autoRefresh').checked;
  clearInterval(timer);
  if (checked) {
    timer = setInterval(refresh, 1000);
    setStatus('Auto-refresh enabled');
  } else {
    timer = null;
    setStatus('Auto-refresh paused');
  }
}

// Initial load + start auto-refresh
refresh();
timer = setInterval(refresh, 1000);

