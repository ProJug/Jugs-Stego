/* Query helper */
const $ = (q) => document.querySelector(q);

/* Tabs */
function switchTab(target) {
    document.querySelectorAll('.tab').forEach(t => {
        const active = t.id === `tab-${target}`;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.panel').forEach(p => {
        p.classList.toggle('active', p.id === `panel-{target}`); // intentional? no.
    });
    // Fix: correct panel toggle
    document.querySelectorAll('.panel').forEach(p => {
        p.classList.toggle('active', p.id === `panel-${target}`);
    });
}
$('#tab-encrypt').addEventListener('click', () => switchTab('encrypt'));
$('#tab-decrypt').addEventListener('click', () => switchTab('decrypt'));

/* Status and enablement */
function setStatus(sel, msg, type) {
    const el = $(sel);
    el.className = `status${type ? ' ' + type : ''}`;
    el.textContent = msg || '';
}
function enable(sel, on) { $(sel).disabled = !on; }

/* Dropzones */
function wireDropzone(id) {
    const dz = $(id);
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
    dz.addEventListener('drop', e => {
        e.preventDefault(); dz.classList.remove('drag');
        const targetId = dz.getAttribute('data-target');
        const input = document.getElementById(targetId);
        if (e.dataTransfer.files?.length) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change'));
        }
    });
}
['#drop-cover', '#drop-payload', '#drop-stego'].forEach(wireDropzone);

/* Image previews */
function previewImage(inputSel, wrapSel, imgSel) {
    const inp = $(inputSel), wrap = $(wrapSel), img = $(imgSel);
    function update() {
        const f = inp.files[0];
        if (!f) { wrap.hidden = true; img.src = ''; return; }
        wrap.hidden = false;
        img.src = URL.createObjectURL(f);
    }
    inp.addEventListener('change', update);
    update();
}
previewImage('#embed-cover', '#preview-cover-wrap', '#preview-cover');
previewImage('#extract-stego', '#preview-stego-wrap', '#preview-stego');

/* File chips */
function setChip(chipId, nameId, file) {
    const chip = document.querySelector(chipId);
    const name = document.querySelector(nameId);
    if (file) {
        const size = file.size < 1024 ? `${file.size} B`
            : file.size < (1024 * 1024) ? `${(file.size / 1024).toFixed(1)} KB`
                : `${(file.size / 1024 / 1024).toFixed(2)} MB`;
        name.textContent = `${file.name} · ${size}`;
        chip.hidden = false;
    } else {
        chip.hidden = true;
    }
}

/* Enable logic */
function refreshEncryptEnable() {
    const haveCover = !!$('#embed-cover').files[0];
    const havePass = !!$('#embed-pass').value.trim();
    const haveMsg = !!$('#embed-message').value.trim();
    const haveFile = !!$('#embed-file').files[0];
    enable('#btn-capacity', haveCover);
    enable('#btn-embed', haveCover && havePass && (haveMsg || haveFile));
}
function refreshDecryptEnable() {
    const haveStego = !!$('#extract-stego').files[0];
    const havePass = !!$('#extract-pass').value.trim();
    enable('#btn-extract', haveStego && havePass);
}

/* Wire changes */
['#embed-cover', '#embed-file', '#embed-message', '#embed-pass'].forEach(s => {
    $(s).addEventListener('input', refreshEncryptEnable);
    $(s).addEventListener('change', refreshEncryptEnable);
});
['#extract-stego', '#extract-pass'].forEach(s => {
    $(s).addEventListener('input', refreshDecryptEnable);
    $(s).addEventListener('change', refreshDecryptEnable);
});

/* Capacity bar */
function showCapacity(show) { $('#capacity-wrap').hidden = !show; }
function setCapacityDisplay(bytes, usedBytes = null) {
    const bar = $('#capacity-bar'), txt = $('#capacity-text');
    if (!bytes) { bar.style.width = '0%'; txt.textContent = ''; showCapacity(false); return; }
    showCapacity(true);
    txt.textContent = `Capacity: ${bytes.toLocaleString()} bytes`;
    const pct = usedBytes != null ? Math.min(100, Math.round(usedBytes / bytes * 100)) : 0;
    bar.style.width = pct + '%';
}

/* Chips + clear */
$('#embed-cover').addEventListener('change', () => {
    const f = $('#embed-cover').files[0];
    setChip('#chip-cover', '#chip-cover-name', f);
    setCapacityDisplay(null);
    setStatus('#embed-status', '');
});
$('#embed-file').addEventListener('change', () => {
    const f = $('#embed-file').files[0];
    setChip('#chip-payload', '#chip-payload-name', f);
});
$('#extract-stego').addEventListener('change', () => {
    const f = $('#extract-stego').files[0];
    setChip('#chip-stego', '#chip-stego-name', f);
    $('#extract-output').hidden = true;
    setStatus('#extract-status', '');
});
$('#chip-cover-x').addEventListener('click', () => {
    $('#embed-cover').value = ''; setChip('#chip-cover', '#chip-cover-name', null);
    setCapacityDisplay(null);
    $('#preview-cover-wrap').hidden = true;
    refreshEncryptEnable();
});
$('#chip-payload-x').addEventListener('click', () => {
    $('#embed-file').value = ''; setChip('#chip-payload', '#chip-payload-name', null);
    refreshEncryptEnable();
});
$('#chip-stego-x').addEventListener('click', () => {
    $('#extract-stego').value = ''; setChip('#chip-stego', '#chip-stego-name', null);
    $('#preview-stego-wrap').hidden = true;
    refreshDecryptEnable();
});

/* Fetch util */
async function postForm(url, fd, expectJson) {
    const res = await fetch(url, { method: 'POST', body: fd });
    const ctype = res.headers.get('content-type') || '';
    if (!res.ok) {
        let msg = `${res.status} ${res.statusText}`;
        try { const j = await res.json(); if (j?.detail) msg = j.detail; } catch { }
        throw new Error(msg);
    }
    if (expectJson || ctype.includes('application/json')) return await res.json();
    return await res.blob();
}
function downloadBlobWithName(blob, res, fallback) {
    // Try to read filename from Content-Disposition
    let filename = fallback;
    const cd = res.headers.get('content-disposition') || '';
    const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    if (m) {
        filename = decodeURIComponent((m[1] || m[2]).trim());
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

/* Buttons */
$('#btn-capacity').addEventListener('click', async () => {
    const cover = $('#embed-cover').files[0];
    if (!cover) return;
    const fd = new FormData(); fd.append('cover', cover);
    setStatus('#embed-status', 'Calculating capacity…');
    try {
        const j = await postForm('/api/capacity', fd, true);
        setCapacityDisplay(j.capacity_bytes);
        setStatus('#embed-status', `Capacity: ${j.capacity_bytes} bytes`, 'ok');
    } catch (e) { setStatus('#embed-status', e.message, 'err'); }
});

$('#btn-embed').addEventListener('click', async () => {
    const cover = $('#embed-cover').files[0];
    const file = $('#embed-file').files[0];
    const msg = $('#embed-message').value;
    const pass = $('#embed-pass').value;
    if (!cover || !pass || (!file && !msg)) return;

    const fd = new FormData();
    fd.append('cover', cover);
    fd.append('passphrase', pass);
    if (file) fd.append('payload', file); else fd.append('message', msg);

    setStatus('#embed-status', 'Embedding…');
    enable('#btn-embed', false);
    try {
        try {
            const capFd = new FormData(); capFd.append('cover', cover);
            const cap = await postForm('/api/capacity', capFd, true);
            const plainLen = file ? file.size : new Blob([msg]).size;
            const overhead = 36 + 16;
            setCapacityDisplay(cap.capacity_bytes, plainLen + overhead);
        } catch { }
        const blob = await postForm('/api/embed', fd, false);
        // embed always returns image/png; filename already in headers but we know it
        downloadBlobWithName(blob, new Response(blob, { headers: { 'content-disposition': 'attachment; filename="stego.png"' } }), 'stego.png');
        setStatus('#embed-status', 'Done. Downloaded stego.png', 'ok');
    } catch (e) { setStatus('#embed-status', e.message, 'err'); }
    finally { refreshEncryptEnable(); }
});

$('#btn-extract').addEventListener('click', async () => {
    const stego = $('#extract-stego').files[0];
    const pass = $('#extract-pass').value;
    if (!stego || !pass) return;

    const out = $('#extract-output');
    setStatus('#extract-status', 'Extracting…');
    out.hidden = true; enable('#btn-extract', false);
    try {
        const fd = new FormData(); fd.append('stego', stego); fd.append('passphrase', pass);
        const res = await fetch('/api/extract', { method: 'POST', body: fd });
        if (!res.ok) {
            let msg = `${res.status} ${res.statusText}`;
            try { const j = await res.json(); if (j?.detail) msg = j.detail; } catch { }
            throw new Error(msg);
        }
        const ctype = res.headers.get('content-type') || '';
        if (ctype.includes('application/json')) {
            const j = await res.json();
            if (j.type === 'text') {
                out.textContent = j.data; out.hidden = false;
                setStatus('#extract-status', 'Decrypted text shown below.', 'ok');
            } else {
                setStatus('#extract-status', 'Unknown JSON type.', 'err');
            }
        } else {
            const blob = await res.blob();
            // Use filename from Content-Disposition if present
            downloadBlobWithName(blob, res, 'extracted.bin');
            setStatus('#extract-status', 'Binary downloaded.', 'ok');
        }
    } catch (e) { setStatus('#extract-status', e.message, 'err'); }
    finally { refreshDecryptEnable(); }
});

/* Initial */
refreshEncryptEnable();
refreshDecryptEnable();
