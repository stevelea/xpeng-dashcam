'use strict';

/* Eén scherm, één beweging: dag kiezen → rit kiezen → beeld kijken.
   Alles wat daarbuiten valt (grote kaart, noodopnames, zoeken) zit links als knop. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ── Taal ───────────────────────────────────────────────────────────────────
   Twee woordenlijsten. De keuze blijft in de browser staan, dus hij onthoudt
   de laatste stand. Ontbreekt een woord in het Engels, dan valt hij terug op
   het Nederlands: liever een Nederlands woord dan een lege plek. */
const TAALEN = {
  settings: 'Settings', close: 'Close', save: 'Save', test: 'Test folder',
  folder_label: 'Folder with your dashcam files',
  folder_hint: 'Sub-folders are included automatically. A year/month layout is not required.',
  folder_normal: 'Sub-folder for normal recordings',
  folder_emergency: 'Sub-folder for emergency recordings',
  folder_flat: 'Are your files not in sub-folders? Leave these two empty. The app then scans the main folder itself.',
  timezone: 'Time zone',
  timezone_hint: 'The time comes from the file name. Without the right time zone every time is wrong.',
  primary_view: 'Main camera',
  primary_view_hint: 'The word after the time in the file name, for example front.',
  need_folder: 'Please fill in a folder first.',
  testing: 'Checking…', saving: 'Saving…', saved: 'Saved.',
  main_folder: 'the main folder',
  found: '{n} usable clips found in {where}.',
  theme: 'Switch theme',
  day_pick: 'Pick a day', emergency_all: 'All emergency clips', map_all: 'Map of everything',
  search_time: 'Search by time', search_btn: 'Find footage',
  route_measured: 'route measured', route_rebuilt: 'route reconstructed',
  route_none: 'no route known',
  measure_km: 'Measure distance', build_route: 'Build route',
  footage: 'Footage', download: 'Download', prev: '\u2190 previous', next: 'next \u2192',
  all_locations: 'All known locations', all: 'All', from: 'from', to: 'to',
  trip: 'Trip', loading: 'loading\u2026',
  days: 'days', until: 'to',
  nothing_indexed: 'nothing indexed yet',
  nothing_found: 'No recognisable file names found.',
};
const TAALNL = {
  need_folder: 'Vul eerst een map in.',
  testing: 'Bezig met kijken…', saving: 'Bezig met bewaren…', saved: 'Bewaard.',
  main_folder: 'de hoofdmap',
  days: 'dagen', until: 't/m',
  nothing_indexed: 'nog niets geïndexeerd',
  found: '{n} bruikbare clips gevonden in {where}.',
  nothing_found: 'Geen herkenbare bestandsnamen gevonden.',
};

let taal = localStorage.getItem('dashcam-taal') || 'nl';

function t(sleutel) {
  if (taal === 'en') return TAALEN[sleutel] ?? TAALNL[sleutel] ?? sleutel;
  return TAALNL[sleutel] ?? TAALEN[sleutel] ?? sleutel;
}

function taalToepassen() {
  document.documentElement.lang = taal;
  $$('[data-i18n]').forEach(el => {
    const k = el.dataset.i18n;
    if (taal === 'en' && TAALEN[k]) el.textContent = TAALEN[k];
    else if (taal === 'nl' && el.dataset.nl) el.textContent = el.dataset.nl;
  });
  $$('[data-i18n-title]').forEach(el => {
    const k = el.dataset.i18nTitle;
    if (taal === 'en' && TAALEN[k]) el.title = TAALEN[k];
    else if (taal === 'nl' && el.dataset.nlTitle) el.title = el.dataset.nlTitle;
  });
  const knop = $('#btn-taal');
  if (knop) knop.textContent = taal === 'nl' ? 'EN' : 'NL';
}

function taalZetten(nieuw) {
  taal = nieuw;
  localStorage.setItem('dashcam-taal', nieuw);
  taalToepassen();
  // Deze twee zijn ooit opgebouwd en kennen de nieuwe taal nog niet
  try { kalenderKeuzes(); kalenderTekenen(); } catch (e) { /* kalender nog leeg */ }
  try { ondertitelZetten(); } catch (e) { /* overzicht nog niet geladen */ }
}

const state = { dag: null, rit: null, momenten: [], open: -1, view: 'front' };

// Datums en getallen volgen de gekozen taal. De maandnamen komen uit de browser,
// dus die hoeven we niet zelf te onderhouden.
const loc = () => (taal === 'en' ? 'en-GB' : 'nl-NL');
const MONTHS = () => Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleDateString(loc(), { month: 'long' }));

const nf = (v, d = 1) => (v === null || v === undefined)
  ? '–' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });

const dayLabel = d => new Date(d + 'T12:00')
  .toLocaleDateString(loc(), { weekday: 'short', day: 'numeric', month: 'short' });
const longDay = d => new Date(d + 'T12:00')
  .toLocaleDateString(loc(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

async function api(pad, opts) {
  const r = await fetch(pad, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

/* ── Thema ─────────────────────────────────────────────────────────────────── */
function themaZetten(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('dashcam-theme', t);
}
$('#btn-theme').onclick = () =>
  themaZetten(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

/* ── Kalender ──────────────────────────────────────────────────────────────── */
const kal = { perDag: {}, jaar: null, maand: null };

function kalenderOpbouwen() {
  const el = $('#kal-dagen');
  el.innerHTML = `
    <div class="kalkop">
      <button class="kalpijl" data-stap="-1" title="vorige maand">‹</button>
      <select class="kal-maand"></select>
      <select class="kal-jaar"></select>
      <button class="kalpijl" data-stap="1" title="volgende maand">›</button>
    </div>
    <div class="kalweek"><span>ma</span><span>di</span><span>wo</span><span>do</span><span>vr</span><span>za</span><span>zo</span></div>
    <div class="kalgrid"></div>
    <div class="kaluitleg">
      <span><i class="stip opname"></i>opname</span>
      <span><i class="stip nood"></i>noodgeval</span>
    </div>`;
  $$('.kalpijl', el).forEach(b => b.onclick = () => {
    const d = new Date(kal.jaar, kal.maand + (+b.dataset.stap), 1);
    maandTonen(d.getFullYear(), d.getMonth());
  });
  $('.kal-maand', el).onchange = ev => maandTonen(kal.jaar, +ev.target.value);
  $('.kal-jaar', el).onchange = ev => maandTonen(+ev.target.value, kal.maand);
}

function kalenderKeuzes() {
  const dagen = Object.keys(kal.perDag).sort();
  if (!dagen.length) return;
  const jaren = [...new Set(dagen.map(d => d.slice(0, 4)))];
  $('.kal-jaar').innerHTML = jaren.map(j => `<option value="${j}">${j}</option>`).join('');
  $('.kal-maand').innerHTML = MONTHS().map((m, i) =>
    `<option value="${i}">${m[0].toUpperCase()}${m.slice(1)}</option>`).join('');
}

function kalenderTekenen() {
  if (kal.jaar === null) return;
  const dagenInMaand = new Date(kal.jaar, kal.maand + 1, 0).getDate();
  const start = (new Date(kal.jaar, kal.maand, 1).getDay() + 6) % 7;
  const vandaag = new Date().toISOString().slice(0, 10);

  let html = '';
  for (let i = 0; i < start; i++) html += '<button class="kaldag leeg"></button>';
  for (let d = 1; d <= dagenInMaand; d++) {
    const iso = `${kal.jaar}-${String(kal.maand + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const info = kal.perDag[iso];
    const klas = ['kaldag'];
    if (info) klas.push('opname');
    if (info?.noodgeval) klas.push('nood');
    if (iso === state.dag) klas.push('actief');
    if (iso === vandaag) klas.push('vandaag');
    const titel = info
      ? `${info.n} clips${info.noodgeval ? `, ${info.noodgeval} noodgeval` : ''} · ${nf(info.gb, 1)} GB`
      : 'geen opnames';
    html += `<button class="${klas.join(' ')}" data-day="${iso}"${info ? '' : ' disabled'}
      title="${titel}">${d}</button>`;
  }
  $('.kalgrid').innerHTML = html;
  $$('.kaldag[data-day]:not(:disabled)').forEach(b => b.onclick = () => dagKiezen(b.dataset.day));

  $('.kal-jaar').value = String(kal.jaar);
  $('.kal-maand').value = String(kal.maand);
  const dagen = Object.keys(kal.perDag).sort();
  const huidig = `${kal.jaar}-${String(kal.maand + 1).padStart(2, '0')}`;
  $$('.kalpijl')[0].disabled = dagen[0].slice(0, 7) >= huidig;
  $$('.kalpijl')[1].disabled = dagen[dagen.length - 1].slice(0, 7) <= huidig;
}

function maandTonen(jaar, maand) {
  kal.jaar = jaar; kal.maand = maand;
  kalenderTekenen();
}

/* ── Een dag ───────────────────────────────────────────────────────────────── */
async function dagKiezen(dag) {
  state.dag = dag;
  ritSluiten();
  const j = +dag.slice(0, 4), m = +dag.slice(5, 7) - 1;
  if (kal.jaar !== j || kal.maand !== m) maandTonen(j, m); else kalenderTekenen();

  $('#dagtitel').textContent = longDay(dag);
  $('#dagritten').innerHTML = '<div class="muted">laden…</div>';
  $('#beeldenkop').textContent = 'Beelden van deze dag';
  $('#grid').innerHTML = '';

  const [ritten, dagdata] = await Promise.all([
    api(`api/trips/${dag}`),
    api(`api/day/${dag}`),
  ]);

  $('#dagtelling').textContent = `${ritten.trips.length} ritten · ${dagdata.moments.length} opnames`;
  ritLijstTekenen(ritten.trips);
  $('#beeldentelling').textContent = `${dagdata.moments.length} opnames`;
  rasterTekenen(dagdata.moments, false);
}

async function ritLijstTekenen(ritten) {
  const el = $('#dagritten');
  if (!ritten.length) {
    el.innerHTML = '<div class="muted">Geen ritten op deze dag.</div>';
    return;
  }
  const soorten = await Promise.all(ritten.map(t =>
    api(`api/trip/${t.id}/route`).then(r => r.geojson ? r.soort : 'geen').catch(() => 'geen')));

  el.innerHTML = ritten.map((t, i) => `<button class="dagrit" data-id="${t.id}">
      <span class="lijn ${soorten[i]}"></span>
      <span class="tijd">${t.start_time}–${t.end_time}</span>
      <span class="km${t.km === null ? ' onbekend' : ''}">${t.km === null ? '– km' : nf(t.km) + ' km'}</span>
      <span class="duur">${t.minutes} min · ${t.clips} clips</span>
    </button>`).join('');
  $$('.dagrit', el).forEach(b => b.onclick = () => ritOpenen(+b.dataset.id));
}

/* ── Een rit ───────────────────────────────────────────────────────────────── */
let ritmap = null;
let ritlaag = null;

function ritSluiten() {
  state.rit = null;
  $('#ritkaart').classList.add('hidden');
}
$('#btn-ritdicht').onclick = () => {
  ritSluiten();
  if (state.dag) dagKiezen(state.dag);
};

async function ritOpenen(id, scrollen = true) {
  state.rit = id;
  const d = await api(`api/trip/${id}/fragmenten`);
  const t = d.trip;

  $('#ritkaart').classList.remove('hidden');
  $('#rittitel').textContent = `${t.start_time} tot ${t.end_time}`;
  $('#beeldenkop').textContent = `Beelden van deze rit`;
  $('#beeldentelling').textContent = `${d.fragmenten.length} opnames`;

  $$('.dagrit').forEach(b => b.classList.toggle('actief', +b.dataset.id === id));
  rasterTekenen(d.fragmenten.map(f => ({ ...f, day: t.day })), false);
  await ritRouteTekenen(id, t);
  // alleen meebewegen als je zelf een rit aanklikt; bij een directe link blijf je bovenaan
  if (scrollen) $('#ritkaart').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function ritRouteTekenen(id, trip) {
  const merk = $('#routemerk');
  merk.className = 'routemerk hidden';

  let d;
  try { d = await api(`api/trip/${id}/route`); } catch { return; }

  if (!ritmap) {
    ritmap = L.map('ritkaartje', { scrollWheelZoom: false }).setView([52.09, 5.12], 11);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(ritmap);
    L.Icon.Default.prototype.options.imagePath = 'vendor/';

    const legenda = L.control({ position: 'bottomleft' });
    legenda.onAdd = () => {
      const el = L.DomUtil.create('div', 'kaartlegenda');
      el.innerHTML = '<div><i></i>gemeten spoor</div>'
        + '<div><i class="gereconstrueerd"></i>gereconstrueerd</div>'
        + '<div><i class="punt"></i>bekende plek</div>'
        + '<div><i class="punt aangenomen"></i>aangenomen plek</div>';
      return el;
    };
    legenda.addTo(ritmap);
  }
  if (ritlaag) { ritmap.removeLayer(ritlaag); ritlaag = null; }

// ── Richting op de lijn ───────────────────────────────────────────────────────
// Een lijn zonder pijlen laat niet zien welke kant je op reed. Leaflet kan dat niet
// zelf, dus zetten we losse pijlpunten op de lijn die met de rijrichting meedraaien.
// Het aantal is vast, niet de afstand: een rit van 5 km en een van 100 km krijgen
// er allebei ongeveer evenveel, zodat het op elke schaal leesbaar blijft.
const PIJLEN_PER_ROUTE = 12;

function meterTussen(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dl = (b[0] - a[0]) * rad, dn = (b[1] - a[1]) * rad;
  const x = Math.sin(dl / 2) ** 2 +
            Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dn / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

function kompashoek(a, b) {
  const rad = Math.PI / 180;
  const dn = (b[1] - a[1]) * rad;
  const y = Math.sin(dn) * Math.cos(b[0] * rad);
  const x = Math.cos(a[0] * rad) * Math.sin(b[0] * rad) -
            Math.sin(a[0] * rad) * Math.cos(b[0] * rad) * Math.cos(dn);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function pijlenLangs(coords, laag, kleur) {
  // coords is [lat, lon]
  if (!coords || coords.length < 2) return;
  const stukken = [];
  let totaal = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    const m = meterTussen(coords[i], coords[i + 1]);
    totaal += m;
    stukken.push({ i, m, tot: totaal });
  }
  if (totaal < 100) return;
  const stap = totaal / (PIJLEN_PER_ROUTE + 1);
  for (let n = 1; n <= PIJLEN_PER_ROUTE; n++) {
    const doel = stap * n;
    const st = stukken.find(x => x.tot >= doel);
    if (!st || !st.m) continue;
    const rest = (doel - (st.tot - st.m)) / st.m;
    const a = coords[st.i], b = coords[st.i + 1];
    const lat = a[0] + (b[0] - a[0]) * rest;
    const lon = a[1] + (b[1] - a[1]) * rest;
    const hoek = kompashoek(a, b);
    L.marker([lat, lon], {
      interactive: false,
      keyboard: false,
      icon: L.divIcon({
        className: 'routepijl',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
        html: `<svg viewBox="0 0 18 18" style="transform:rotate(${hoek}deg)">
                 <path d="M9 1.5 L14.5 15 L9 11.6 L3.5 15 Z"
                       fill="${kleur}" stroke="rgba(0,0,0,.6)" stroke-width="1.2"
                       stroke-linejoin="round"/>
               </svg>`,
      }),
    }).addTo(laag);
  }
}

function beginEindMerk(coords, laag) {
  if (!coords || coords.length < 2) return;
  const maak = (pos, tekst, vul) => L.marker(pos, {
    interactive: false, keyboard: false,
    icon: L.divIcon({ className: 'routemerkje', iconSize: [22, 22], iconAnchor: [11, 11],
                      html: `<span style="background:${vul}">${tekst}</span>` }),
  }).addTo(laag);
  maak(coords[0], 'A', '#4cbf54');
  maak(coords[coords.length - 1], 'B', '#e0574f');
}

  ritlaag = L.layerGroup().addTo(ritmap);
  setTimeout(() => ritmap.invalidateSize(), 60);

  const punten = d.punten || [];
  let grenzen = null;

  if (d.geojson) {
    const gemeten = d.soort === 'gemeten';
    // Een donkere onderlaag onder de lijn: anders verdwijnt hij in de kaart zodra
    // er wegen of water onder liggen.
    L.geoJSON(d.geojson, {
      style: { color: 'rgba(0,0,0,.45)', weight: gemeten ? 9 : 8, opacity: 1 },
    }).addTo(ritlaag);
    const lijn = L.geoJSON(d.geojson, {
      style: { color: gemeten ? '#4cbf54' : '#f0bf63', weight: gemeten ? 5 : 5,
               opacity: 1, dashArray: gemeten ? null : '10 8', lineCap: 'round' },
    }).addTo(ritlaag);
    grenzen = lijn.getBounds();
    // richting: pijlen op de lijn plus een A en een B aan de uiteinden
    const rij = (d.geojson.coordinates || []).map(c => [c[1], c[0]]);
    pijlenLangs(rij, ritlaag, gemeten ? '#4cbf54' : '#f0bf63');
    beginEindMerk(rij, ritlaag);
    const aangenomen = punten.some(p => p.source === 'aangenomen');
    merk.textContent = gemeten
      ? `gemeten spoor · ${nf(d.km)} km`
      : `gereconstrueerd · ${nf(d.km)} km over de weg${aangenomen ? ' · begin/eind aangenomen' : ''}`;
    merk.className = `routemerk ${d.soort}`;
  } else {
    merk.textContent = punten.length ? 'losse punten, geen route' : 'geen locatie bekend';
    merk.className = 'routemerk gereconstrueerd';
  }

  const cirkels = [];
  for (const p of punten) {
    cirkels.push([p.lat, p.lon]);
    // een aangenomen punt is hol: je ziet meteen dat het geredeneerd is, niet gemeten
    const aangenomen = p.source === 'aangenomen';
    L.circleMarker([p.lat, p.lon], {
      radius: 7, weight: 3, color: aangenomen ? '#f0bf63' : '#1a1a1a',
      fillColor: aangenomen ? 'transparent' : '#f0bf63',
      fillOpacity: aangenomen ? 0 : 1, dashArray: aangenomen ? '3 3' : null,
    }).addTo(ritlaag).bindPopup(`<b>${p.label || 'punt'}</b><br>${p.ts.slice(11, 16)} · ${p.source}`);
  }
  if (!grenzen && cirkels.length) grenzen = L.latLngBounds(cirkels);
  if (grenzen) ritmap.fitBounds(grenzen.pad(0.25));

  $('#ritpunten').innerHTML = punten.length
    ? punten.map(p => `<span class="wpchip${p.source === 'aangenomen' ? ' aangenomen' : ''}">
        ${p.ts.slice(11, 16)} ${p.label || 'punt'}<i>${p.source}</i></span>`).join('')
    : '<span class="muted">Geen bekende plekken bij deze rit. '
      + 'Foto\'s van dat moment of een afgelezen bord kunnen dit vullen.</span>';
}

$('#btn-meet').onclick = async ev => {
  if (!state.rit) return;
  ev.target.disabled = true; ev.target.textContent = 'meten…';
  try {
    await api(`api/trip/${state.rit}/measure`, { method: 'POST' });
    await dagKiezen(state.dag);
  } catch (e) { alert(`Meten mislukt: ${e.message}`); }
  finally { ev.target.disabled = false; ev.target.textContent = 'Kilometers meten'; }
};

$('#btn-route').onclick = async ev => {
  if (!state.rit) return;
  ev.target.disabled = true; ev.target.textContent = 'bepalen…';
  try {
    await api(`api/trip/${state.rit}/photos`, { method: 'POST' }).catch(() => {});
    await api(`api/trip/${state.rit}/route`, { method: 'POST' });
    await ritOpenen(state.rit);
  } catch (e) { alert(`Route bepalen mislukt: ${e.message}`); }
  finally { ev.target.disabled = false; ev.target.textContent = 'Route bepalen'; }
};

/* ── Beelden ───────────────────────────────────────────────────────────────── */
function rasterTekenen(momenten, toonDag) {
  state.momenten = momenten;
  const el = $('#grid');
  if (!momenten.length) {
    el.innerHTML = '<div class="empty">Geen opnames.</div>';
    return;
  }
  el.innerHTML = momenten.map((m, i) => {
    const front = m.views.front || m.views.front_and_360;
    const beeld = front.thumb ? `<img loading="lazy" src="thumb/${front.id}" alt="">`
                              : '<div class="wait">nog geen beeld</div>';
    const merk = m.kind === 'noodgeval' ? '<div class="badge emer">noodgeval</div>'
               : (m.views.front_and_360 ? '<div class="badge">360</div>' : '');
    const kmh = m.kmh === undefined ? ''
      : `<span class="kmh${m.kmh === 0 ? ' stil' : ''}">${m.kmh} km/h</span>`;
    const wanneer = toonDag ? `${dayLabel(m.day)} ${m.time.slice(0, 5)}` : m.time.slice(0, 5);
    return `<div class="tile" data-i="${i}">
      <div class="shot">${beeld}${merk}</div>
      <div class="meta"><span>${wanneer}</span>${kmh}</div>
    </div>`;
  }).join('');
  $$('.tile', el).forEach(t => t.onclick = () => spelerOpenen(+t.dataset.i));
}

/* ── Speler ────────────────────────────────────────────────────────────────── */
function spelerOpenen(i) {
  const m = state.momenten[i];
  if (!m) return;
  state.open = i;
  state.view = m.views.front ? 'front' : 'front_and_360';
  $('#player').classList.remove('hidden');
  clipTonen();
}

function clipTonen() {
  const m = state.momenten[state.open];
  const clip = m.views[state.view] || Object.values(m.views)[0];
  $('#p-title').textContent = `${longDay(m.day || state.dag)} — ${m.time}`;
  const snelheid = m.kmh === undefined ? '' : ` · ${m.kmh} km/h gemiddeld`;
  $('#p-sub').textContent =
    `${m.kind === 'noodgeval' ? 'noodopname · ' : ''}${nf(clip.mb, 0)} MB${snelheid}`;
  $('#p-views').innerHTML = Object.keys(m.views).map(v =>
    `<button data-v="${v}" class="${v === state.view ? 'active' : ''}">${v === 'front' ? 'Voor' : '360'}</button>`
  ).join('');
  $$('#p-views button').forEach(b => b.onclick = () => { state.view = b.dataset.v; clipTonen(); });
  $('#p-download').href = `download/${clip.id}`;
  const v = $('#p-video');
  v.src = `video/${clip.id}`;
  v.play().catch(() => {});
  $('#p-prev').disabled = state.open <= 0;
  $('#p-next').disabled = state.open >= state.momenten.length - 1;
}

function spelerSluiten() {
  const v = $('#p-video');
  v.pause(); v.removeAttribute('src'); v.load();
  $('#player').classList.add('hidden');
}
$('#p-close').onclick = spelerSluiten;
$('#player').onclick = ev => { if (ev.target.id === 'player') spelerSluiten(); };
$('#p-prev').onclick = () => { if (state.open > 0) { state.open--; clipTonen(); } };
$('#p-next').onclick = () => { if (state.open < state.momenten.length - 1) { state.open++; clipTonen(); } };
$('#p-video').addEventListener('ended', () => $('#p-next').click());

document.addEventListener('keydown', ev => {
  if (!$('#player').classList.contains('hidden')) {
    if (ev.key === 'Escape') spelerSluiten();
    if (ev.key === 'ArrowLeft') $('#p-prev').click();
    if (ev.key === 'ArrowRight') $('#p-next').click();
    return;
  }
  if (ev.key === 'Escape' && !$('#allekaart').classList.contains('hidden')) kaartSluiten();
});

/* ── Zoeken op tijd ────────────────────────────────────────────────────────── */
$('#btn-search').onclick = async () => {
  const datum = $('#s-date').value, tijd = $('#s-time').value || '12:00';
  if (!datum) { $('#searchinfo').textContent = 'Kies eerst een datum.'; return; }
  $('#searchinfo').textContent = 'zoeken…';
  try {
    const r = await api(`api/search?ts=${datum}T${tijd}&window_min=30`);
    $('#searchinfo').textContent = r.moments.length
      ? `${r.moments.length} opnames gevonden`
      : 'Niets gevonden. De auto stond toen waarschijnlijk stil.';
    ritSluiten();
    $('#dagtitel').textContent = `Rond ${datum} ${tijd}`;
    $('#dagtelling').textContent = '';
    $('#dagritten').innerHTML = '';
    $('#beeldenkop').textContent = 'Gevonden beelden';
    $('#beeldentelling').textContent = `${r.moments.length} opnames`;
    rasterTekenen(r.moments, true);
  } catch (e) { $('#searchinfo').textContent = `Fout: ${e.message}`; }
};

/* ── Noodopnames ───────────────────────────────────────────────────────────── */
// Op een telefoon staat de kalender dichtgeklapt; een dag kiezen klapt hem weer dicht.
$('#btn-kal').onclick = () => $('.kalenderkaart').classList.toggle('open');
$('#kal-dagen').addEventListener('click', e => {
  if (e.target.tagName === 'BUTTON' && window.matchMedia('(max-width: 700px)').matches) {
    $('.kalenderkaart').classList.remove('open');
  }
});
$('#btn-nood').onclick = async ev => {
  ev.target.disabled = true;
  const dagen = Object.values(kal.perDag).filter(d => d.noodgeval);
  const alles = [];
  for (const d of dagen) {
    const r = await api(`api/day/${d.day}?kind=noodgeval`);
    r.moments.forEach(m => { m.day = d.day; alles.push(m); });
  }
  alles.sort((a, b) => b.ts.localeCompare(a.ts));
  ritSluiten();
  $('#dagtitel').textContent = 'Noodopnames';
  $('#dagtelling').textContent = `${alles.length} opnames`;
  $('#dagritten').innerHTML =
    '<div class="muted">Opnames die de auto zelf als incident bewaarde.</div>';
  $('#beeldenkop').textContent = 'Noodopnames';
  $('#beeldentelling').textContent = `${alles.length} opnames`;
  rasterTekenen(alles, true);
  ev.target.disabled = false;
};

/* ── Grote kaart ───────────────────────────────────────────────────────────── */
const groot = { map: null, laag: null, dagen: [] };

function kaartSluiten() { $('#allekaart').classList.add('hidden'); }
$('#btn-kaartdicht').onclick = kaartSluiten;
$('#allekaart').onclick = ev => { if (ev.target.id === 'allekaart') kaartSluiten(); };

$('#btn-alles-kaart').onclick = async () => {
  $('#allekaart').classList.remove('hidden');
  if (!groot.map) {
    groot.map = L.map('kaart', { scrollWheelZoom: true }).setView([52.09, 5.12], 8);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(groot.map);
  }
  setTimeout(() => groot.map.invalidateSize(), 80);
  await locatiesLaden();
};

async function locatiesLaden() {
  const van = $('#k-van').value, tot = $('#k-tot').value;
  const q = new URLSearchParams();
  if (van) q.set('van', van);
  if (tot) q.set('tot', tot);
  const d = await api(`api/locaties?${q}`);

  if (!$('#k-van').min && d.eerste_dag) {
    for (const el of [$('#k-van'), $('#k-tot')]) { el.min = d.eerste_dag; el.max = d.laatste_dag; }
    $('#k-van').value = d.eerste_dag;
    $('#k-tot').value = d.laatste_dag;
    groot.dagen = [d.eerste_dag, d.laatste_dag];
  }

  if (groot.laag) groot.map.removeLayer(groot.laag);
  groot.laag = L.layerGroup().addTo(groot.map);
  $('#kaart-telling').textContent = `${d.punten.length} punten`;
  if (!d.punten.length) return;

  const punten = [];
  for (const p of d.punten) {
    punten.push([p.lat, p.lon]);
    L.circleMarker([p.lat, p.lon], {
      radius: 6, weight: 2, color: '#b08334', fillColor: '#d4a857', fillOpacity: .75,
    }).addTo(groot.laag).bindPopup(
      `<b>${p.label || 'onbekende plek'}</b><br>${p.day} om ${p.ts.slice(11, 16)}`
      + `<br><a href="#" onclick="naarRit('${p.day}',${p.trip_id});return false">bekijk de rit</a>`);
  }
  groot.map.fitBounds(L.latLngBounds(punten).pad(0.15));
}

window.naarRit = async (dag, id) => {
  kaartSluiten();
  await dagKiezen(dag);
  ritOpenen(id);
};

$('#k-van').onchange = locatiesLaden;
$('#k-tot').onchange = locatiesLaden;
$('#k-alles').onclick = () => {
  $('#k-van').value = groot.dagen[0]; $('#k-tot').value = groot.dagen[1];
  locatiesLaden();
};

/* ── Start ─────────────────────────────────────────────────────────────────── */
let laatsteOverzicht = null;

function ondertitelZetten() {
  const o = laatsteOverzicht;
  if (!o) return;
  $('#subtitle').textContent = o.clips
    ? `${o.clips.toLocaleString(loc())} clips · ${o.days.length} ${t('days')} · ${o.first_day} ${t('until')} ${o.last_day}`
    : t('nothing_indexed');
}

async function overzichtLaden() {
  const o = await api('api/overview');
  laatsteOverzicht = o;
  ondertitelZetten();
  kal.perDag = Object.fromEntries(o.days.map(d => [d.day, d]));
  kalenderKeuzes();

  const q = new URLSearchParams(location.search);
  const dag = q.get('dag') || o.days[0]?.day;
  const rit = q.get('rit');

  if (dag) {
    maandTonen(+dag.slice(0, 4), +dag.slice(5, 7) - 1);
    await dagKiezen(dag);
  }
  if (rit) {
    try {
      const t = await api(`api/trip/${rit}`);
      await dagKiezen(t.day);
      await ritOpenen(+rit, false);
    } catch { $('#subtitle').textContent = `Rit ${rit} bestaat niet (meer).`; }
  }
  $('#s-date').value = o.last_day || '';
  $('#s-date').min = o.first_day || '';
  $('#s-date').max = o.last_day || '';
}

/* ── Instellingen ───────────────────────────────────────────────────────────
   De map met de beelden staat niet vast: iedereen zet hier zijn eigen pad. */
function instelMelding(tekst, soort) {
  const el = $('#set-melding');
  el.textContent = tekst;
  el.className = 'instelmelding' + (soort ? ' ' + soort : '');
}

function instelMappen() {
  const m = {};
  const n = $('#set-normaal').value.trim();
  const e = $('#set-nood').value.trim();
  if (n) m.normaal = n;
  if (e) m.noodgeval = e;
  return m;
}

async function instellingenLaden() {
  const c = await api('api/settings');
  $('#set-root').value = c.root || '';
  $('#set-normaal').value = c.folders?.normaal || '';
  $('#set-nood').value = c.folders?.noodgeval || '';
  $('#set-tz').value = c.timezone || '';
  $('#set-view').value = c.primary_view || '';
  instelMelding('');
}

async function instellingenToetsen() {
  const root = $('#set-root').value.trim();
  if (!root) return instelMelding(t('need_folder'), 'fout');
  instelMelding(t('testing'));
  try {
    const mappen = Object.values(instelMappen()).join(',');
    const r = await api(`api/settings/check?root=${encodeURIComponent(root)}&folders=${encodeURIComponent(mappen)}`);
    if (r.ok) {
      const waar = r.submappen.length ? r.submappen.join(', ') : t('main_folder');
      instelMelding(t('found').replace('{n}', r.herkend).replace('{where}', waar), 'goed');
    } else {
      instelMelding(r.reden || t('nothing_found'), 'fout');
    }
  } catch (e) { instelMelding(e.message, 'fout'); }
}

async function instellingenBewaren() {
  instelMelding(t('saving'));
  try {
    await api('api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        root: $('#set-root').value.trim(),
        folders: instelMappen(),
        timezone: $('#set-tz').value.trim(),
        primary_view: $('#set-view').value.trim(),
      }),
    });
    instelMelding(t('saved'), 'goed');
  } catch (e) { instelMelding(e.message, 'fout'); }
}

$('#btn-settings').onclick = () => {
  $('#instellingen').classList.remove('hidden');
  instellingenLaden().catch(e => instelMelding(e.message, 'fout'));
};
$('#btn-insteldicht').onclick = () => $('#instellingen').classList.add('hidden');
$('#btn-instelcheck').onclick = instellingenToetsen;
$('#btn-instelbewaar').onclick = instellingenBewaren;

$$('[data-i18n]').forEach(el => { el.dataset.nl = el.textContent.trim(); });
$$('[data-i18n-title]').forEach(el => { el.dataset.nlTitle = el.title; });
const knopTaal = $('#btn-taal');
if (knopTaal) knopTaal.onclick = () => taalZetten(taal === 'nl' ? 'en' : 'nl');
taalToepassen();

themaZetten(localStorage.getItem('dashcam-theme') || 'dark');
kalenderOpbouwen();
overzichtLaden().catch(e => { $('#subtitle').textContent = `Fout: ${e.message}`; });
