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
  ev_url: 'EVConduit address',
  ev_url_hint: 'Leave empty to fetch nothing. Trips are matched on time, not on number.',
  ev_key: 'API key',
  ev_key_hint: 'From EVConduit, on your account. Stored on the server only.',
  ev_marge: 'Clock margin in seconds',
  ev_marge_hint: 'The dashcam and the car never agree exactly. How much difference you still accept.',
  ev_aan: 'Fetch data from the car',
  ev_test: 'Test connection',
  ev_forget: 'Forget fetched data',
  ev_testing: 'Testing\u2026',
  ev_key_yes: 'A key is stored. Leave empty to keep it.',
  ev_key_no: 'No key stored yet.',
  ev_forgotten: 'Erased.',
  auto_title: 'Data from the car',
  auto_from_car: 'Car (CAN bus)',
  auto_from_video: 'Video (measured)',
  auto_diff: 'The car covered {car} km and the video says {video} km — {diff} km apart.',
  auto_diff_none: 'No distance measured from the video for this trip yet.',
  auto_duration: 'Duration',
  auto_energy: 'Energy used',
  auto_consumption: 'Consumption',
  auto_odo: 'Odometer',
  auto_speed_max: 'Top speed',
  auto_speed_mean: 'Average while moving',
  auto_soc: 'Battery',
  auto_vin: 'VIN',
  auto_clock: 'Clock difference',
  auto_clock_val: 'start {start}s, end {end}s against the video',
  auto_refresh: 'Refresh',
  auto_reason_geen_rit: 'No drive from the car matches this time.',
  auto_reason_twijfel: 'There is a drive that looks like this one, but the times differ too much to claim it.',
  auto_reason_geen_tijd: 'This trip has no usable start time.',
  auto_reason_onbereikbaar: 'Could not reach EVConduit.',
  auto_ambiguous: 'Another drive from the car also overlaps this one — the two apps divided the day differently.',
  spoor_title: 'GPS track from the car',
  spoor_coverage: 'measured over {percent}% of the drive',
  spoor_points: '{n} readings',
  spoor_gap: 'largest gap {min} min',
  spoor_km: 'track {km} km',
  spoor_none_no_subject: 'This trip carries no VIN to look positions up by.',
  spoor_none_no_positions: 'No GPS points in this window — nothing is posting a logger to EVConduit.',
  spoor_none_too_few_points: 'One reading is a dot, not a drive.',
  spoor_none_trip_incomplete: 'This trip has no start or end to search between.',
  spoor_none_other: 'No track available.',
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
  need_folder: 'Vul eerst een map in.',
  loading: 'laden…',
  testing: 'Bezig met kijken…', saving: 'Bezig met bewaren…', saved: 'Bewaard.',
  main_folder: 'de hoofdmap',
  days: 'dagen', until: 't/m',
  nothing_indexed: 'nog niets geïndexeerd',
  found: '{n} bruikbare clips gevonden in {where}.',
  nothing_found: 'Geen herkenbare bestandsnamen gevonden.',
  ev_testing: 'Bezig met testen…',
  ev_key_yes: 'Er staat een sleutel. Laat leeg om hem te bewaren.',
  ev_key_no: 'Nog geen sleutel bewaard.',
  ev_forgotten: 'Gewist.',
  auto_title: 'Gegevens van de auto',
  auto_from_car: 'Auto (CAN-bus)',
  auto_from_video: 'Beeld (gemeten)',
  auto_diff: 'De auto reed {car} km, het beeld zegt {video} km — {diff} km verschil.',
  auto_diff_none: 'Voor deze rit is nog geen afstand uit het beeld gemeten.',
  auto_duration: 'Duur',
  auto_energy: 'Verbruikte energie',
  auto_consumption: 'Verbruik',
  auto_odo: 'Kilometerstand',
  auto_speed_max: 'Topsnelheid',
  auto_speed_mean: 'Gemiddeld rijdend',
  auto_soc: 'Accu',
  auto_vin: 'VIN',
  auto_clock: 'Klokverschil',
  auto_clock_val: 'begin {start} s, eind {end} s ten opzichte van het beeld',
  auto_refresh: 'Verversen',
  auto_reason_geen_rit: 'Geen rit van de auto gevonden bij deze tijd.',
  auto_reason_twijfel: 'Er is een rit die erop lijkt, maar de tijden wijken te veel af om hem op te eisen.',
  auto_reason_geen_tijd: 'Deze rit heeft geen bruikbare begintijd.',
  auto_reason_onbereikbaar: 'EVConduit was niet te bereiken.',
  auto_ambiguous: 'Er overlapt nog een rit van de auto — de twee apps hebben de dag anders ingedeeld.',
  spoor_title: 'GPS-spoor van de auto',
  spoor_coverage: 'gemeten over {percent}% van de rit',
  spoor_points: '{n} metingen',
  spoor_gap: 'grootste gat {min} min',
  spoor_km: 'spoor {km} km',
  spoor_none_no_subject: 'Deze rit heeft geen VIN om posities bij op te zoeken.',
  spoor_none_no_positions: 'Geen GPS-punten in dit tijdvak — er post niets naar EVConduit.',
  spoor_none_too_few_points: 'Eén meting is een punt, geen rit.',
  spoor_none_trip_incomplete: 'Deze rit heeft geen begin of eind om tussen te zoeken.',
  spoor_none_other: 'Geen spoor beschikbaar.',
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
  // Het instellingenscherm en de kaart van de rit zetten een paar teksten zelf —
  // bijvoorbeeld of er al een sleutel bewaard is. Die moeten opnieuw opgebouwd.
  if (!$('#instellingen').classList.contains('hidden')) {
    instellingenLaden().catch(() => {});
  }
  if (state.rit) ritOpenen(state.rit, false).catch(() => {});
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
async function dagKiezen(dag) {
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
  ritLijstTekenen(ritten.trips);
  $('#beeldentelling').textContent = t('clips_n', { n: dagdata.moments.length });
  rasterTekenen(dagdata.moments, false);
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
    </button>`).join('');
  $$('.dagrit', el).forEach(b => b.onclick = () => ritOpenen(+b.dataset.id));
}

/* ── Een rit ───────────────────────────────────────────────────────────────── */
let ritmap = null;
let ritlaag = null;
// Het spoor van de auto zit in een eigen laag: het is een andere meting dan de
// route die wij zelf opbouwen, en de twee mogen elkaar niet overschrijven.
let autolaag = null;
let ritgrenzen = null;

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
  rasterTekenen(d.fragmenten.map(f => ({ ...f, day: t.day })), false);
  // De twee oproepen lopen naast elkaar: de gegevens van de auto mogen niet op de
  // route wachten, en andersom. autoTekenen tekent daarna in de kaart die er dan staat.
  const [, auto] = await Promise.all([
    ritRouteTekenen(id, t),
    api(`api/trip/${id}/auto`).catch(() => null),
  ]);
  autoTekenen(auto, t);
  rasterTekenen(d.fragmenten.map(f => ({ ...f, day: rit.day })), false);
  await ritRouteTekenen(id, rit);
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
        + '<div><i class="punt aangenomen"></i>aangenomen plek</div>'
        + '<div><i class="auto"></i>spoor van de auto</div>';
      el.innerHTML = `<div><i></i>${t('track_measured')}</div>`
        + `<div><i class="gereconstrueerd"></i>${t('track_rebuilt')}</div>`
        + `<div><i class="punt"></i>${t('place_known')}</div>`
        + `<div><i class="punt aangenomen"></i>${t('place_assumed')}</div>`;
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
  ritgrenzen = grenzen;
  if (grenzen) ritmap.fitBounds(grenzen.pad(0.25));

  $('#ritpunten').innerHTML = punten.length
    ? punten.map(p => `<span class="wpchip${p.source === 'aangenomen' ? ' aangenomen' : ''}">
        ${p.ts.slice(11, 16)} ${p.label || 'punt'}<i>${p.source}</i></span>`).join('')
    : `<span class="muted">${t('no_known_places')}</span>`;
}

/* ── Gegevens van de auto (EVConduit) ──────────────────────────────────────── */
/* Twee metingen van dezelfde rit: de onze komt uit het beeld, die van de auto uit
   de CAN-bus. Ze naast elkaar zetten is het hele punt. Een verschil tussen de twee
   is informatie; het wegmoffelen ervan zou doen alsof we het zeker weten.

   En waar de auto géén spoor heeft zeggen we dat ook — EVConduit haalt zijn
   posities niet uit de auto maar van een logger die de eigenaar zelf ergens op
   richt. "Geen spoor" is daar de gewone toestand, niet een fout. */

const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const REDEN_SPOOR = {
  no_subject: 'spoor_none_no_subject',
  no_positions: 'spoor_none_no_positions',
  too_few_points: 'spoor_none_too_few_points',
  trip_incomplete: 'spoor_none_trip_incomplete',
};

const minuten = sec => (sec === null || sec === undefined) ? null : `${Math.round(sec / 60)} min`;

function autoKop() {
  return `<div class="autokop"><h3>${esc(t('auto_title'))}</h3>
      <span class="pill">EVConduit</span><div class="spacer"></div>
      <button class="small ghost" id="btn-autoververs">${esc(t('auto_refresh'))}</button></div>`;
}

function autoTekenen(d, trip) {
  const vak = $('#ritauto');
  if (autolaag && ritmap) { ritmap.removeLayer(autolaag); autolaag = null; }
  if (!vak) return;

  // Niets ingesteld: geen leeg vak tonen. Er is niets mis en er is niets te zien.
  if (!d || d.reden === 'geen_evconduit') {
    vak.classList.add('hidden');
    vak.innerHTML = '';
    return;
  }

  const r = d.rit;
  vak.classList.remove('hidden');

  if (!r) {
    const sleutel = { twijfel: 'auto_reason_twijfel', geen_tijd: 'auto_reason_geen_tijd',
                      onbereikbaar: 'auto_reason_onbereikbaar' }[d.reden] || 'auto_reason_geen_rit';
    vak.innerHTML = autoKop()
      + `<p class="muted klein">${esc(t(sleutel))}${d.melding ? ' — ' + esc(d.melding) : ''}</p>`;
    autoKnop(trip);
    return;
  }

  const kmAuto = r.distance_km == null ? null : Number(r.distance_km);
  const kmVideo = trip.km == null ? null : Number(trip.km);
  const verschil = (kmAuto !== null && kmVideo !== null) ? Math.abs(kmAuto - kmVideo) : null;
  const verbruik = (r.energy_kwh != null && kmAuto) ? (Number(r.energy_kwh) / kmAuto * 100) : null;

  const rijen = [
    [t('auto_duration'), minuten(r.duration_seconds)],
    [t('auto_energy'), r.energy_kwh != null ? `${nf(r.energy_kwh, 2)} kWh` : null],
    [t('auto_consumption'), verbruik != null ? `${nf(verbruik, 1)} kWh/100 km` : null],
    [t('auto_odo'), (r.odometer_start != null && r.odometer_end != null)
      ? `${nf(r.odometer_start, 0)} → ${nf(r.odometer_end, 0)} km` : null],
    [t('auto_speed_max'), r.max_speed_kmh != null ? `${nf(r.max_speed_kmh, 0)} km/h` : null],
    [t('auto_speed_mean'), r.mean_moving_speed_kmh != null
      ? `${nf(r.mean_moving_speed_kmh, 0)} km/h` : null],
    [t('auto_soc'), (r.soc_start != null && r.soc_end != null)
      ? `${nf(r.soc_start, 0)}% → ${nf(r.soc_end, 0)}%` : null],
    [t('auto_vin'), r.vin || null],
    // Een constante afwijking is klokverschil tussen dashcam en auto. Zichtbaar,
    // want anders lijkt onze eigen tijd preciezer dan hij is.
    [t('auto_clock'), d.afwijking
      ? t('auto_clock_val').replace('{start}', d.afwijking.start_s)
                           .replace('{end}', d.afwijking.eind_s)
      : null],
  ].filter(x => x[1] != null);

  let h = autoKop();
  h += '<div class="autovgl">'
    + `<div class="autovglvak"><span>${esc(t('auto_from_car'))}</span>`
    + `<b>${kmAuto === null ? '–' : nf(kmAuto) + ' km'}</b></div>`
    + `<div class="autovglvak"><span>${esc(t('auto_from_video'))}</span>`
    + `<b class="${kmVideo === null ? 'onbekend' : ''}">`
    + `${kmVideo === null ? '– km' : nf(kmVideo) + ' km'}</b></div></div>`;

  h += verschil === null
    ? `<p class="muted klein">${esc(t('auto_diff_none'))}</p>`
    : `<p class="autoverschil${verschil >= 1 ? ' groot' : ''}">`
      + esc(t('auto_diff').replace('{car}', nf(kmAuto)).replace('{video}', nf(kmVideo))
                       .replace('{diff}', nf(verschil)))
      + '</p>';

  h += '<dl class="autolijst">' + rijen.map(([k, v]) =>
    `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('') + '</dl>';

  if (d.kandidaten && d.kandidaten.length) {
    h += `<p class="muted klein">${esc(t('auto_ambiguous'))}</p>`;
  }
  h += spoorBlok(d.spoor);
  vak.innerHTML = h;

  spoorTekenen(d.spoor);
  autoKnop(trip);
}

function autoKnop(trip) {
  const knop = $('#btn-autoververs');
  if (!knop) return;
  knop.onclick = async () => {
    knop.disabled = true;
    knop.textContent = t('loading');
    try {
      autoTekenen(await api(`api/trip/${state.rit}/auto`, { method: 'POST' }), trip);
    } catch (e) {
      knop.disabled = false;
      knop.textContent = e.message;
    }
  };
}

function spoorBlok(s) {
  if (!s) return '';
  if (!s.beschikbaar) {
    const sleutel = REDEN_SPOOR[s.reden] || 'spoor_none_other';
    return `<div class="autospoor"><h4>${esc(t('spoor_title'))}</h4>`
      + `<p class="muted klein">${esc(t(sleutel))}`
      + `${s.melding ? ' — ' + esc(s.melding) : ''}</p></div>`;
  }
  const stukken = [];
  if (s.dekking != null) {
    stukken.push(t('spoor_coverage').replace('{percent}', Math.round(s.dekking * 100)));
  }
  if (s.punten_bron || s.punten) {
    stukken.push(t('spoor_points').replace('{n}', s.punten_bron || s.punten));
  }
  if (s.grootste_gat_s != null) {
    stukken.push(t('spoor_gap').replace('{min}', (s.grootste_gat_s / 60).toFixed(1)));
  }
  if (s.spoor_km != null) stukken.push(t('spoor_km').replace('{km}', nf(s.spoor_km)));
  return `<div class="autospoor"><h4>${esc(t('spoor_title'))}</h4>`
    + `<p class="klein">${stukken.map(esc).join(' · ')}</p></div>`;
}

function spoorTekenen(s) {
  if (!s || !s.beschikbaar || !s.geojson || !ritmap) return;
  autolaag = L.layerGroup().addTo(ritmap);
  // Zelfde behandeling als ons eigen gemeten spoor: een donkere onderlaag zodat de
  // lijn niet in de kaart verdwijnt, maar een eigen kleur — het is een andere bron.
  L.geoJSON(s.geojson, { style: { color: 'rgba(0,0,0,.45)', weight: 9, opacity: 1 } })
    .addTo(autolaag);
  const lijn = L.geoJSON(s.geojson, {
    style: { color: '#5aa9e6', weight: 5, opacity: 1, lineCap: 'round' },
  }).addTo(autolaag);
  pijlenLangs((s.geojson.coordinates || []).map(c => [c[1], c[0]]), autolaag, '#5aa9e6');

  // Meebewegen zodat het spoor van de auto in beeld komt ook als onze eigen route
  // ergens anders ligt.
  const b = lijn.getBounds();
  if (b && b.isValid()) {
    ritgrenzen = ritgrenzen ? ritgrenzen.extend(b) : b;
    ritmap.fitBounds(ritgrenzen.pad(0.25));
  }
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
  const snelheid = m.kmh === undefined ? '' : ' · ' + t('avg_kmh', { n: m.kmh });
  $('#p-sub').textContent =
    `${m.kind === 'noodgeval' ? t('emergency_tag') : ''}${nf(clip.mb, 0)} MB${snelheid}`;
  $('#p-views').innerHTML = Object.keys(m.views).map(v =>
    `<button data-v="${v}" class="${v === state.view ? 'active' : ''}">${v === 'front' ? t('camera_front') : t('camera_360')}</button>`
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
      const ritData = await api(`api/trip/${rit}`);
      await dagKiezen(ritData.day);
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
  // De sleutel komt nooit terug van de server; het veld blijft dus leeg en zegt
  // alleen of er al een bewaard is.
  const ev = c.evconduit || {};
  $('#set-ev-url').value = ev.url || '';
  $('#set-ev-key').value = '';
  $('#set-ev-marge').value = ev.marge_s ?? 180;
  $('#set-ev-aan').checked = ev.aan !== false;
  $('#set-ev-keyhint').textContent = ev.heeft_sleutel ? t('ev_key_yes') : t('ev_key_no');
  $('#set-ev-melding').textContent = '';
  instelMelding('');
}

async function evconduitToetsen() {
  const melding = $('#set-ev-melding');
  melding.className = 'instelmelding';
  melding.textContent = t('ev_testing');
  try {
    const r = await api('api/evconduit/toets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: $('#set-ev-url').value.trim(),
        sleutel: $('#set-ev-key').value,
      }),
    });
    if (!r.ok) {
      melding.textContent = r.reden || '?';
      melding.className = 'instelmelding fout';
    } else if (r.ritten) {
      melding.textContent = `${r.ritten} ritten · ${r.nieuwste ? r.nieuwste.slice(0, 16).replace('T', ' ') : ''}`;
      melding.className = 'instelmelding goed';
    } else {
      melding.textContent = r.melding || '';
      melding.className = 'instelmelding';
    }
  } catch (e) {
    melding.textContent = e.message;
    melding.className = 'instelmelding fout';
  }
}

async function evconduitVergeet() {
  const melding = $('#set-ev-melding');
  try {
    await api('api/evconduit/vergeet', { method: 'POST' });
    melding.textContent = t('ev_forgotten');
    melding.className = 'instelmelding goed';
  } catch (e) {
    melding.textContent = e.message;
    melding.className = 'instelmelding fout';
  }
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
        evconduit: {
          url: $('#set-ev-url').value.trim(),
          // Leeg laten betekent "laat de bewaarde sleutel staan".
          sleutel: $('#set-ev-key').value,
          marge_s: $('#set-ev-marge').value,
          aan: $('#set-ev-aan').checked,
        },
      }),
    });
    // Opnieuw lezen: dan staat er meteen of de sleutel nu bewaard is.
    await instellingenLaden();
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
$('#btn-evtoets').onclick = evconduitToetsen;
$('#btn-evvergeet').onclick = evconduitVergeet;

$$('[data-i18n]').forEach(el => { el.dataset.nl = el.textContent.trim(); });
$$('[data-i18n-title]').forEach(el => { el.dataset.nlTitle = el.title; });
const knopTaal = $('#btn-taal');
if (knopTaal) knopTaal.onclick = () => taalZetten(taal === 'nl' ? 'en' : 'nl');
taalToepassen();

themaZetten(localStorage.getItem('dashcam-theme') || 'dark');
kalenderOpbouwen();
overzichtLaden().catch(e => { $('#subtitle').textContent = `Fout: ${e.message}`; });
