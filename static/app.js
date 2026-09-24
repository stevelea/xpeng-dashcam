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
  all_trips: 'All trips · {n}', routes_drawn: '{a} of {n} trips · {km} km', no_route_day: 'no route known on this day',
  brakes_title: 'Hard braking', brakes_count: '{n} moments', brakes_count_one: '1 moment',
  brakes_intro: 'Moments where the on-screen speed dropped by at least 11 km/h per second, with 10 seconds before and after.',
  brakes_months: 'Read so far: {maanden}.', brakes_none_read: 'No month read yet.',
  per_second: 'km/h per s',
  brakes_sub: 'hard braking · {van} → {naar} km/h · {daling} km/h per second · {mb} MB',
  cutting: 'cutting…', export_saved: 'Clip saved on the NAS in Exports — {n} camera views.',
  export_failed: 'Export failed',
  weather_pending: 'weather not known yet (KNMI lags ~2 days)', rain: 'rain', drizzle: 'drizzle',
  dry: 'dry', wind: 'wind', gusts: 'gusts', fog: 'fog', snow: 'snow', thunder: 'thunder',
  ice: 'glaze', sky_hidden: 'sky obscured', clear: 'clear', partly_cloudy: 'partly cloudy',
  cloudy: 'overcast', weather_source: 'KNMI station',
  settings: 'Settings', close: 'Close', save: 'Save', test: 'Test folder',
  test_link: 'Test folder', prev_short: '← previous', close_short: 'Close',
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
  brakes_all: 'Hard braking', export_clip: 'Export ±10 s',
  search_time: 'Search by time', search_btn: 'Find footage',
  route_measured: 'route measured', route_rebuilt: 'route reconstructed',
  route_none: 'no route known',
  measure_km: 'Measure distance', build_route: 'Build route', business: 'Business', business_tag: 'business',
  footage: 'Footage', download: 'Download', prev: '\u2190 previous', next: 'next \u2192',
  all_locations: 'All known locations', all: 'All', from: 'from', to: 'to',
  trip: 'Trip', loading: 'loading\u2026',
  days: 'days', until: 'to',
  nothing_indexed: 'nothing indexed yet',
  nothing_found: 'No recognisable file names found.',

  // Tekst die de code zelf opbouwt, dus niet in de HTML staat.
  trips_clips: '{n} trips · {m} clips', clips_n: '{n} clips',
  km_unknown: '– km',
  no_trips: 'No trips on this day.', no_clips: 'No clips.',
  footage_day: 'Clips from this day', footage_trip: 'Clips from this trip',
  trip_range: '{a} to {b}',
  track_measured: 'measured track', track_rebuilt: 'reconstructed',
  place_known: 'known place', place_assumed: 'assumed place',
  measuring: 'measuring…', determining: 'determining…',
  measure_failed: 'Measuring failed: {e}',
  route_failed: 'Building the route failed: {e}',
  pick_date_first: 'Pick a date first.', searching: 'searching…',
  around: 'Around {date} {time}', found_footage: 'Footage found',
  emergency_title: 'Emergency clips', error_n: 'Error: {e}',
  points_n: '{n} points', no_route_points: 'scattered points, no route',
  no_location: 'no location known',
  track_km: 'measured track · {n} km',
  track_road: 'reconstructed · {n} km by road',
  track_assumed: ' · start/end assumed',
  trip_missing: 'Trip {n} does not exist (any more).',
  no_known_places: "No known places for this trip. Photos from that moment or a read sign can fill this in.",
  avg_kmh: '{n} km/h average', camera_front: 'Front', camera_360: '360',
  emergency_tag: 'emergency clip · ', emergency_badge: 'emergency',
  no_image: 'no image yet',
  clips_found: '{n} clips found',
  nothing_then: 'Nothing found. The car was probably stationary then.',
  unknown_place: 'unknown place',
  on_day_at: '{day} at {time}', view_trip: 'view the trip',
  emergency_note: 'Clips the car saved as an incident itself.',
  month_prev: 'previous month', month_next: 'next month',
  legend_recording: 'recording', legend_emergency: 'emergency',
  day_clips: '{n} clips · {gb} GB',
  day_clips_emerg: '{n} clips, {e} emergency · {gb} GB',
};
const TAALNL = {
  all_trips: 'Alle ritten · {n}', routes_drawn: '{a} van {n} ritten · {km} km', no_route_day: 'geen route bekend op deze dag',
  brakes_title: 'Hard remmen', brakes_count: '{n} momenten', brakes_count_one: '1 moment',
  brakes_intro: 'Momenten waarop de snelheid in beeld minstens 11 km/h per seconde daalde, met 10 seconden ervoor en erna.',
  brakes_months: 'Gelezen: {maanden}.', brakes_none_read: 'Nog geen maand gelezen.',
  per_second: 'km/h per s',
  brakes_sub: 'hard remmen · {van} → {naar} km/h · {daling} km/h per seconde · {mb} MB',
  cutting: 'knippen…', export_saved: 'Fragment bewaard op de NAS in Exports — {n} camerabeelden.',
  export_failed: 'Exporteren mislukt',
  weather_pending: 'weer nog niet bekend (KNMI loopt ~2 dagen achter)', rain: 'regen',
  drizzle: 'motregen', dry: 'droog', wind: 'wind', gusts: 'stoten', fog: 'mist', snow: 'sneeuw',
  thunder: 'onweer', ice: 'ijzel', sky_hidden: 'hemel onzichtbaar', clear: 'helder',
  partly_cloudy: 'half bewolkt', cloudy: 'bewolkt', weather_source: 'KNMI-station',
  need_folder: 'Vul eerst een map in.',
  testing: 'Bezig met kijken…', saving: 'Bezig met bewaren…', saved: 'Bewaard.',
  main_folder: 'de hoofdmap',
  days: 'dagen', until: 't/m',
  nothing_indexed: 'nog niets geïndexeerd',
  found: '{n} bruikbare clips gevonden in {where}.',
  nothing_found: 'Geen herkenbare bestandsnamen gevonden.',
  test_link: 'Map testen', prev_short: '← vorige',
  trips_clips: '{n} ritten · {m} opnames', clips_n: '{n} opnames',
  km_unknown: '– km',
  no_trips: 'Geen ritten op deze dag.', no_clips: 'Geen opnames.',
  footage_day: 'Beelden van deze dag', footage_trip: 'Beelden van deze rit',
  trip_range: '{a} tot {b}',
  track_measured: 'gemeten spoor', track_rebuilt: 'gereconstrueerd',
  place_known: 'bekende plek', place_assumed: 'aangenomen plek',
  measuring: 'meten…', determining: 'bepalen…',
  measure_failed: 'Meten mislukt: {e}',
  route_failed: 'Route bepalen mislukt: {e}',
  pick_date_first: 'Kies eerst een datum.', searching: 'zoeken…',
  around: 'Rond {date} {time}', found_footage: 'Gevonden beelden',
  emergency_title: 'Noodopnames', error_n: 'Fout: {e}',
  points_n: '{n} punten', no_route_points: 'losse punten, geen route',
  no_location: 'geen locatie bekend',
  track_km: 'gemeten spoor · {n} km',
  track_road: 'gereconstrueerd · {n} km over de weg',
  track_assumed: ' · begin/eind aangenomen',
  trip_missing: 'Rit {n} bestaat niet (meer).',
  no_known_places: "Geen bekende plekken bij deze rit. Foto's van dat moment of een afgelezen bord kunnen dit vullen.",
  avg_kmh: '{n} km/h gemiddeld', camera_front: 'Voor', camera_360: '360',
  emergency_tag: 'noodopname · ', emergency_badge: 'noodgeval',
  no_image: 'nog geen beeld',
  clips_found: '{n} opnames gevonden',
  nothing_then: 'Niets gevonden. De auto stond toen waarschijnlijk stil.',
  unknown_place: 'onbekende plek',
  on_day_at: '{day} om {time}', view_trip: 'bekijk de rit',
  emergency_note: 'Opnames die de auto zelf als incident bewaarde.',
  month_prev: 'vorige maand', month_next: 'volgende maand',
  legend_recording: 'opname', legend_emergency: 'noodgeval',
  day_clips: '{n} clips · {gb} GB',
  day_clips_emerg: '{n} clips, {e} noodgeval · {gb} GB',
  measure_km: 'Kilometers meten',
  build_route: 'Route bepalen',
  loading: 'laden…',
};

let taal = localStorage.getItem('dashcam-taal') || 'nl';

function t(sleutel, waarden) {
  const ruw = taal === 'en'
    ? (TAALEN[sleutel] ?? TAALNL[sleutel] ?? sleutel)
    : (TAALNL[sleutel] ?? TAALEN[sleutel] ?? sleutel);
  if (!waarden) return ruw;
  return ruw.replace(/{(\w+)}/g, (_, k) => waarden[k] ?? `{${k}}`);
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
  $$('.kaartlegenda').forEach(legendaVullen);
}

const state = { dag: null, rit: null, momenten: [], open: -1, view: 'front' };

// Datums en getallen volgen de gekozen taal. De maandnamen komen uit de browser,
// dus die hoeven we niet zelf te onderhouden.
const loc = () => (taal === 'en' ? 'en-GB' : 'nl-NL');
const MONTHS = () => Array.from({ length: 12 }, (_, i) =>
  new Date(2000, i, 1).toLocaleDateString(loc(), { month: 'long' }));
// Korte weekdagnamen, net als de maanden uit de browser.
const WEEKDAYS = () => Array.from({ length: 7 }, (_, i) =>
  new Date(2024, 0, 1 + i).toLocaleDateString(loc(), { weekday: 'short' }));

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
      <button class="kalpijl" data-stap="-1" title="${t('month_prev')}">‹</button>
      <select class="kal-maand"></select>
      <select class="kal-jaar"></select>
      <button class="kalpijl" data-stap="1" title="${t('month_next')}">›</button>
    </div>
    <div class="kalweek">${WEEKDAYS().map(d => `<span>${d}</span>`).join('')}</div>
    <div class="kalgrid"></div>
    <div class="kaluitleg">
      <span><i class="stip opname"></i>${t('legend_recording')}</span>
      <span><i class="stip nood"></i>${t('legend_emergency')}</span>
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
      ? info.noodgeval
        ? t('day_clips_emerg', { n: info.n, e: info.noodgeval, gb: nf(info.gb, 1) })
        : t('day_clips', { n: info.n, gb: nf(info.gb, 1) })
      : t('no_clips');
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
async function dagKiezen(dag, autoRit = true) {
  state.dag = dag;
  ritSluiten();
  const j = +dag.slice(0, 4), m = +dag.slice(5, 7) - 1;
  if (kal.jaar !== j || kal.maand !== m) maandTonen(j, m); else kalenderTekenen();

  $('#dagtitel').textContent = longDay(dag);
  $('#dagritten').innerHTML = `<div class="muted">${t('loading')}</div>`;
  $('#beeldenkop').textContent = t('footage_day');
  $('#grid').innerHTML = '';

  const [ritten, dagdata] = await Promise.all([
    api(`api/trips/${dag}`),
    api(`api/day/${dag}`),
  ]);

  $('#dagtelling').textContent = t('trips_clips', { n: ritten.trips.length, m: dagdata.moments.length });
  await ritLijstTekenen(ritten.trips);
  $('#beeldentelling').textContent = t('clips_n', { n: dagdata.moments.length });
  rasterTekenen(dagdata.moments, false);
  // Zonder dit blijft de kaart leeg tot je zelf een rit aanklikt, en dat leest als
  // "er is geen route". Alle ritten van de dag tekenen laat meteen zien wat er is;
  // klik je er een aan, dan blijft alleen die over.
  if (autoRit) await dagRoutesTekenen(ritten.trips);
}

async function ritLijstTekenen(ritten) {
  const el = $('#dagritten');
  if (!ritten.length) {
    el.innerHTML = `<div class="muted">${t('no_trips')}</div>`;
    return;
  }
  const soorten = await Promise.all(ritten.map(t =>
    api(`api/trip/${t.id}/route`).then(r => r.geojson ? r.soort : 'geen').catch(() => 'geen')));

  el.innerHTML = ritten.map((rit, i) => `<button class="dagrit" data-id="${rit.id}">
      <span class="lijn ${soorten[i]}"></span>
      <span class="tijd">${rit.start_time}–${rit.end_time}</span>
      <span class="km${rit.km === null ? ' onbekend' : ''}">${rit.km === null ? t('km_unknown') : nf(rit.km) + ' km'}</span>
      <span class="duur">${rit.minutes} min · ${rit.clips} clips</span>
      ${rit.zakelijk ? `<span class="zak">${t('business_tag')}</span>` : ''}
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
  const rit = d.trip;   // niet `t`: dat is de vertaalfunctie

  $('#ritkaart').classList.remove('hidden');
  $('#rittitel').textContent = t('trip_range', { a: rit.start_time, b: rit.end_time });
  $('#beeldenkop').textContent = t('footage_trip');
  $('#beeldentelling').textContent = t('clips_n', { n: d.fragmenten.length });

  $$('.dagrit').forEach(b => b.classList.toggle('actief', +b.dataset.id === id));
  $('#btn-meet').disabled = $('#btn-route').disabled = $('#btn-zakelijk').disabled = false;
  zakelijkTonen(rit.zakelijk);
  ritWeerTonen(id);
  rasterTekenen(d.fragmenten.map(f => ({ ...f, day: rit.day })), false);
  await ritRouteTekenen(id, rit);
  // alleen meebewegen als je zelf een rit aanklikt; bij een directe link blijf je bovenaan
  if (scrollen) $('#ritkaart').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* Weer tijdens de rit: KNMI-uurgegevens van het dichtstbijzijnde station, alleen Nederland.
   Geen plek of buitenland: niets tonen. KNMI loopt ~2 dagen achter: dat zeggen we dan ook. */
async function ritWeerTonen(id) {
  const el = $('#ritweer');
  el.className = 'pill hidden';
  let w;
  try { w = await api(`api/trip/${id}/weer`); } catch { return; }
  if (state.rit !== id) return;               // intussen een andere rit gekozen
  if (w.status === 'nog_niet') { el.textContent = t('weather_pending'); el.title = ''; el.className = 'pill'; return; }
  if (w.status !== 'ok') return;
  const delen = [`${nf(w.temp, 1)} °C`];
  delen.push(w.neerslag_mm > 0.05 ? `${nf(w.neerslag_mm, 1)} mm ${t('rain')}` : w.regen ? t('drizzle') : t('dry'));
  delen.push(`${t('wind')} ${nf(w.wind, 0)} m/s${w.windstoot >= 10 ? ` (${t('gusts')} ${nf(w.windstoot, 0)})` : ''}`);
  [[w.mist, 'fog'], [w.sneeuw, 'snow'], [w.onweer, 'thunder'], [w.ijzel, 'ice']]
    .forEach(([aan, k]) => { if (aan) delen.push(t(k)); });
  if (w.bewolking != null) {
    delen.push(w.bewolking === 9 ? t('sky_hidden') : w.bewolking <= 2 ? t('clear')
      : w.bewolking <= 5 ? t('partly_cloudy') : t('cloudy'));
  }
  el.textContent = delen.join(' · ');
  el.title = `${t('weather_source')} ${w.station} (${nf(w.station_km, 0)} km), ${w.uurvak_ut}`;
  el.className = 'pill';
}

/* Zakelijk of privé. Alleen het vinkje; een declaratie hoort in een andere app (GET api/zakelijk). */
function zakelijkTonen(aan) {
  $('#btn-zakelijk').classList.toggle('aan', !!aan);
  $('#btn-zakelijk').setAttribute('aria-pressed', aan ? 'true' : 'false');
}
$('#btn-zakelijk').onclick = async () => {
  if (!state.rit) return;
  const nieuw = $('#btn-zakelijk').getAttribute('aria-pressed') !== 'true';
  const r = await fetch(`api/trip/${state.rit}/zakelijk`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ zakelijk: nieuw }),
  });
  if (!r.ok) { alert('Opslaan mislukt'); return; }
  zakelijkTonen(nieuw);
  const knop = document.querySelector(`.dagrit[data-id="${state.rit}"]`);
  if (knop) {
    knop.querySelector('.zak')?.remove();
    if (nieuw) knop.insertAdjacentHTML('beforeend', '<span class="zak">zakelijk</span>');
  }
};

// Los, zodat een taalwissel de legenda van een al getekende kaart kan bijwerken.
function legendaVullen(el) {
  el.innerHTML = `<div><i></i>${t('track_measured')}</div>`
    + `<div><i class="gereconstrueerd"></i>${t('track_rebuilt')}</div>`
    + `<div><i class="punt"></i>${t('place_known')}</div>`
    + `<div><i class="punt aangenomen"></i>${t('place_assumed')}</div>`;
}

function kaartKlaar() {
  if (ritmap) return ritmap;
  ritmap = L.map('ritkaartje', { scrollWheelZoom: false }).setView([52.09, 5.12], 11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(ritmap);
  L.Icon.Default.prototype.options.imagePath = 'vendor/';

  const legenda = L.control({ position: 'bottomleft' });
  legenda.onAdd = () => {
    const el = L.DomUtil.create('div', 'kaartlegenda');
    legendaVullen(el);
    return el;
  };
  legenda.addTo(ritmap);
  return ritmap;
}

/* Alle ritten van een dag in één kaart. Bewust zonder pijlen en zonder A/B: met vier
   ritten over elkaar wordt dat een kluwen. Klik je een lijn aan, dan opent die rit en
   krijg je wel het volle beeld. */
async function dagRoutesTekenen(ritten) {
  $('#routemerk').className = 'routemerk hidden';
  $('#ritpunten').innerHTML = '';
  $$('.dagrit').forEach(b => b.classList.remove('actief'));
  $('#btn-meet').disabled = $('#btn-route').disabled = $('#btn-zakelijk').disabled = true;
  zakelijkTonen(false);
  $('#ritweer').className = 'pill hidden';
  if (!ritten.length) { $('#ritkaart').classList.add('hidden'); return; }

  $('#ritkaart').classList.remove('hidden');
  $('#rittitel').textContent = t('all_trips', { n: ritten.length });
  kaartKlaar();
  if (ritlaag) { ritmap.removeLayer(ritlaag); ritlaag = null; }
  ritlaag = L.layerGroup().addTo(ritmap);
  setTimeout(() => ritmap.invalidateSize(), 60);

  const routes = await Promise.all(ritten.map(t =>
    api(`api/trip/${t.id}/route`).catch(() => null)));

  let grenzen = null, km = 0, getekend = 0;
  routes.forEach((d, i) => {
    if (!d || !d.geojson) return;
    const t = ritten[i];
    const gemeten = d.soort === 'gemeten';
    km += d.km || 0;
    getekend++;
    L.geoJSON(d.geojson, { style: { color: 'rgba(0,0,0,.45)', weight: 8, opacity: 1 } })
      .addTo(ritlaag);
    const lijn = L.geoJSON(d.geojson, {
      style: { color: gemeten ? '#4cbf54' : '#f0bf63', weight: 5, opacity: 1,
               dashArray: gemeten ? null : '10 8', lineCap: 'round' },
    }).addTo(ritlaag);
    lijn.bindTooltip(`${t.start_time}–${t.end_time} · ${nf(d.km)} km`, { sticky: true });
    lijn.on('click', () => ritOpenen(t.id));
    grenzen = grenzen ? grenzen.extend(lijn.getBounds()) : lijn.getBounds();
  });

  const merk = $('#routemerk');
  if (getekend) {
    merk.textContent = t('routes_drawn', { a: getekend, n: ritten.length, km: nf(km) });
    merk.className = 'routemerk gemeten';
    ritmap.fitBounds(grenzen.pad(0.15));
  } else {
    merk.textContent = t('no_route_day');
    merk.className = 'routemerk gereconstrueerd';
  }
}

async function ritRouteTekenen(id, trip) {
  const merk = $('#routemerk');
  merk.className = 'routemerk hidden';

  let d;
  try { d = await api(`api/trip/${id}/route`); } catch { return; }

  kaartKlaar();
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
      ? t('track_km', { n: nf(d.km) })
      : t('track_road', { n: nf(d.km) }) + (aangenomen ? t('track_assumed') : '');
    merk.className = `routemerk ${d.soort}`;
  } else {
    merk.textContent = punten.length ? t('no_route_points') : t('no_location');
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
    : `<span class="muted">${t('no_known_places')}</span>`;
}

$('#btn-meet').onclick = async ev => {
  if (!state.rit) return;
  ev.target.disabled = true; ev.target.textContent = t('measuring');
  try {
    await api(`api/trip/${state.rit}/measure`, { method: 'POST' });
    await dagKiezen(state.dag);
  } catch (e) { alert(t('measure_failed', { e: e.message })); }
  finally { ev.target.disabled = false; ev.target.textContent = t('measure_km'); }
};

$('#btn-route').onclick = async ev => {
  if (!state.rit) return;
  ev.target.disabled = true; ev.target.textContent = t('determining');
  try {
    await api(`api/trip/${state.rit}/photos`, { method: 'POST' }).catch(() => {});
    await api(`api/trip/${state.rit}/route`, { method: 'POST' });
    await ritOpenen(state.rit);
  } catch (e) { alert(t('route_failed', { e: e.message })); }
  finally { ev.target.disabled = false; ev.target.textContent = t('build_route'); }
};

/* ── Beelden ───────────────────────────────────────────────────────────────── */
function rasterTekenen(momenten, toonDag) {
  state.momenten = momenten;
  const el = $('#grid');
  if (!momenten.length) {
    el.innerHTML = `<div class="empty">${t('no_clips')}</div>`;
    return;
  }
  el.innerHTML = momenten.map((m, i) => {
    const front = m.views.front || m.views.front_and_360;
    const beeld = front.thumb ? `<img loading="lazy" src="thumb/${front.id}" alt="">`
                              : `<div class="wait">${t('no_image')}</div>`;
    const merk = m.kind === 'noodgeval' ? `<div class="badge emer">${t('emergency_badge')}</div>`
               : m.kind === 'rem' ? `<div class="badge emer">−${nf(m.daling, 0)} ${t('per_second')}</div>`
               : (m.views.front_and_360 ? '<div class="badge">360</div>' : '');
    const kmh = m.kind === 'rem' ? `<span class="kmh">${m.van_kmh} → ${m.naar_kmh} km/h</span>`
      : m.kmh === undefined ? ''
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
  const snelheid = m.kmh === undefined ? '' : ' · ' + t('avg_kmh', { n: m.kmh });
  $('#p-sub').textContent = m.kind === 'rem'
    ? t('brakes_sub').replace('{van}', m.van_kmh).replace('{naar}', m.naar_kmh)
        .replace('{daling}', nf(m.daling, 0)).replace('{mb}', nf(clip.mb, 0))
    : `${m.kind === 'noodgeval' ? t('emergency_tag') : ''}${nf(clip.mb, 0)} MB${snelheid}`;
  $('#p-views').innerHTML = Object.keys(m.views).map(v =>
    `<button data-v="${v}" class="${v === state.view ? 'active' : ''}">${v === 'front' ? t('camera_front') : t('camera_360')}</button>`
  ).join('');
  $$('#p-views button').forEach(b => b.onclick = () => { state.view = b.dataset.v; clipTonen(); });
  $('#p-download').href = clip.url ? `${clip.url}?download=1` : `download/${clip.id}`;
  const v = $('#p-video');
  v.src = clip.url || `video/${clip.id}`;
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
// Venster in minuten waarbinnen rond een tijdstip wordt gezocht.
const ZOEK_VENSTER = 30;

// Gedeeld door de zoekknop en door een deeplink zoals
//   ?dag=2026-07-02&tijd=17:35
// zodat een andere app (bijvoorbeeld een rittenoverzicht) naar het juiste
// moment kan linken.
async function zoekOpTijd(datum, tijd, venster = ZOEK_VENSTER) {
  if (!datum) { $('#searchinfo').textContent = t('pick_date_first'); return; }
  $('#s-date').value = datum;
  if (tijd) $('#s-time').value = tijd;
  $('#searchinfo').textContent = t('searching');
  try {
    const r = await api(`api/search?ts=${datum}T${tijd || '12:00'}&window_min=${venster}`);
    $('#searchinfo').textContent = r.moments.length
      ? t('clips_found', { n: r.moments.length })
      : t('nothing_then');
    ritSluiten();
    $('#dagtitel').textContent = t('around', { date: datum, time: tijd || '12:00' });
    $('#dagtelling').textContent = '';
    $('#dagritten').innerHTML = '';
    $('#beeldenkop').textContent = t('found_footage');
    $('#beeldentelling').textContent = t('clips_n', { n: r.moments.length });
    rasterTekenen(r.moments, true);
  } catch (e) { $('#searchinfo').textContent = t('error_n', { e: e.message }); }
}

$('#btn-search').onclick = () => {
  const datum = $('#s-date').value, tijd = $('#s-time').value || '12:00';
  return zoekOpTijd(datum, tijd);
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
  $('#dagtitel').textContent = t('emergency_title');
  $('#dagtelling').textContent = t('clips_n', { n: alles.length });
  $('#dagritten').innerHTML = `<div class="muted">${t('emergency_note')}</div>`;
  $('#beeldenkop').textContent = t('emergency_title');
  $('#beeldentelling').textContent = t('clips_n', { n: alles.length });
  rasterTekenen(alles, true);
  ev.target.disabled = false;
};

/* Hard remmen: herkend uit de snelheid in beeld (remmen.py), elk met een filmpje van ±10 s. */
$('#btn-rem').onclick = async ev => {
  ev.target.disabled = true;
  try {
    const r = await api('api/remmen');
    r.momenten.forEach(m => { m.kmh = undefined; });
    ritSluiten();
    const telling = r.momenten.length === 1 ? t('brakes_count_one')
      : t('brakes_count').replace('{n}', r.momenten.length);
    // Welke maanden al gelezen zijn komt uit de database, zodat de tekst niet veroudert
    const maanden = r.maanden.map(k => new Date(+k.slice(0, 4), +k.slice(5, 7) - 1, 1)
      .toLocaleDateString(taal === 'en' ? 'en-GB' : 'nl-NL', { month: 'long', year: 'numeric' }));
    const gelezen = maanden.length ? t('brakes_months').replace('{maanden}', maanden.join(', '))
      : r.momenten.length ? '' : t('brakes_none_read');
    $('#dagtitel').textContent = t('brakes_title');
    $('#dagtelling').textContent = telling;
    $('#dagritten').innerHTML = `<div class="muted">${t('brakes_intro')} ${gelezen}</div>`;
    $('#beeldenkop').textContent = t('brakes_title');
    $('#beeldentelling').textContent = telling;
    rasterTekenen(r.momenten, true);
  } finally { ev.target.disabled = false; }
};

/* Exporteer ±10 s rond het punt waar de video staat, voor alle camerabeelden. */
$('#p-export').onclick = async ev => {
  const m = state.momenten[state.open];
  if (!m) return;
  const tijd = $('#p-video').currentTime || 0;   // niet 't': dat is de vertaalfunctie
  // Een remfilmpje begint zelf al 10 s vóór het moment
  const offset = m.kind === 'rem' ? tijd - 10 : tijd;
  ev.target.disabled = true;
  const oud = ev.target.textContent;
  ev.target.textContent = t('cutting');
  try {
    const r = await api('api/fragment', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ts: m.ts, offset, voor: 10, na: 10 }),
    });
    const v = r.views[state.view] || Object.values(r.views)[0];
    const a = document.createElement('a');
    a.href = `${v.url}?download=1`;
    a.download = '';
    document.body.appendChild(a); a.click(); a.remove();
    $('#p-sub').textContent = t('export_saved').replace('{n}', Object.keys(r.views).length);
  } catch (e) { alert(`${t('export_failed')}: ${e.message}`); }
  finally { ev.target.disabled = false; ev.target.textContent = oud; }
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
  $('#kaart-telling').textContent = t('points_n', { n: d.punten.length });
  if (!d.punten.length) return;

  const punten = [];
  for (const p of d.punten) {
    punten.push([p.lat, p.lon]);
    L.circleMarker([p.lat, p.lon], {
      radius: 6, weight: 2, color: '#b08334', fillColor: '#d4a857', fillOpacity: .75,
    }).addTo(groot.laag).bindPopup(
      `<b>${p.label || t('unknown_place')}</b><br>${t('on_day_at', { day: p.day, time: p.ts.slice(11, 16) })}`
      + `<br><a href="#" onclick="naarRit('${p.day}',${p.trip_id});return false">${t('view_trip')}</a>`);
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
  // Deeplink naar een moment, bijvoorbeeld vanuit een rittenoverzicht:
  //   ?dag=2026-07-02&tijd=17:35          (standaard 30 minuten ervoor/erna)
  //   ?dag=2026-07-02&tijd=17:35&venster=90
  const tijd = q.get('tijd') || q.get('time');
  const venster = +(q.get('venster') || q.get('window') || ZOEK_VENSTER);

  // Vul het zoekformulier eerst, zodat een deeplink daarop voortbouwt.
  $('#s-date').value = o.last_day || '';
  $('#s-date').min = o.first_day || '';
  $('#s-date').max = o.last_day || '';

  if (tijd) {
    // Zoeken kan op zichzelf staan; de dag wordt er toch bij gezocht.
    if (dag) maandTonen(+dag.slice(0, 4), +dag.slice(5, 7) - 1);
    await zoekOpTijd(dag, tijd, Number.isFinite(venster) && venster > 0 ? venster : ZOEK_VENSTER);
  } else if (dag) {
    maandTonen(+dag.slice(0, 4), +dag.slice(5, 7) - 1);
    await dagKiezen(dag);
  }
  if (rit) {
    try {
      const t = await api(`api/trip/${rit}`);
      await dagKiezen(t.day, false);
      await ritOpenen(+rit, false);
    } catch { $('#subtitle').textContent = t('trip_missing', { n: rit }); }
  }
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
overzichtLaden().catch(e => { $('#subtitle').textContent = t('error_n', { e: e.message }); });
