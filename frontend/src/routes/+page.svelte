<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';

  const BMSIT = {
    name: 'BMSIT College, Avalahalli, Yelahanka',
    lat: 13.1344,
    lng: 77.5693,
  };

  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let markers = $state<any[]>([]);
  let dispatchStatus = $state('');
  let etaLabel = $state('');
  let ambulances = $state<any[]>([]);
  let hospitals = $state<any[]>([]);
  let selectedHospital = $state<any>(null);
  let assignedUnit = $state('');
  let constraints = $state<any>(null);
  let confidence = $state<number | null>(null);
  let reason = $state('');
  let candidates = $state<any[]>([]);
  let pickupMinutes = $state<number | null>(null);
  let transportMinutes = $state<number | null>(null);
  let monitor = $state<any>(null);
  let extraRoutes = $state<any[]>([]);
  let corridor = $state<any>(null);
  let activeMissions = $state<any[]>([]);
  let selectedAmbulanceId = $state('');
  let assignedIds = $derived(new Set([assignedUnit, ...activeMissions.map((m) => m.ambulance_id)].filter(Boolean)));
  let availableCount = $derived(ambulances.filter((a) => a.status === 'available').length);
  let conflictReason = $derived(
    monitor?.mission?.conflict?.reason ||
      activeMissions.find((m) => m.conflict?.reason)?.conflict?.reason ||
      ''
  );

  function applyPayload(payload: any) {
    if (!payload) return;
    pickupRoute = payload.pickup_route || [];
    dropRoute = payload.drop_route || payload.route || [];
    selectedHospital = payload.hospital;
    assignedUnit = payload.ambulance_id || '';
    constraints = payload.constraints;
    confidence = payload.confidence ?? null;
    reason = payload.reason || '';
    candidates = payload.candidates || [];
    pickupMinutes = payload.pickup_minutes ?? null;
    transportMinutes = payload.transport_minutes ?? null;
    const mins = payload.eta_minutes ?? Math.round((payload.eta_seconds || 0) / 60);
    if (mins) etaLabel = `${mins} min`;
    if (payload.hospital_name) {
      const phase = payload.phase || 'pickup';
      dispatchStatus =
        phase === 'complete'
          ? `Trip complete · ${payload.hospital_name}`
          : `Nearest 🚑 ${assignedUnit || 'unit'} → ${payload.hospital_name}`;
    }
    markers = buildMarkers();
  }

  function postMarkers(posts: any[] = []) {
    return posts.map((p) => postToMarker(p, true));
  }

  function extraRoutesFor(missions: any[], selectedId: string) {
    const extras: any[] = [];
    for (const m of missions) {
      if (!m || m.ambulance_id === selectedId) continue;
      const pickup = m.pickup_route || [];
      const drop = m.drop_route || m.route || [];
      if (pickup.length > 1) {
        extras.push({ id: `${m.id}-pickup`, points: pickup, color: '#fb7185', kind: 'pickup', label: `${m.ambulance_id} pickup` });
      }
      if (drop.length > 1) {
        extras.push({
          id: `${m.id}-drop`,
          points: drop,
          color: m.conflict?.status === 'rerouted' ? '#a855f7' : '#38bdf8',
          kind: 'drop',
          label: `${m.ambulance_id} → ${m.hospital_name || 'hospital'}`,
        });
      }
    }
    for (const r of corridor?.extra_routes || []) {
      if (r.kind === 'overlap') extras.push(r);
    }
    return extras;
  }

  function focusMission(mission: any | null) {
    if (!mission || mission.phase === 'complete') return;
    selectedAmbulanceId = mission.ambulance_id || selectedAmbulanceId;
    applyPayload(mission);
    extraRoutes = extraRoutesFor(activeMissions, selectedAmbulanceId);
  }

  function selectAmbulance(id: string) {
    selectedAmbulanceId = id;
    const hit =
      activeMissions.find((m) => m.ambulance_id === id) ||
      (monitor?.mission?.ambulance_id === id ? monitor.mission : null);
    if (hit && hit.phase !== 'complete') focusMission(hit);
    else extraRoutes = extraRoutesFor(activeMissions, id);
    markers = buildMarkers();
  }

  function buildMarkers(fleet = ambulances, hosp = hospitals, extra: any[] = []) {
    const hospitalId = selectedHospital?.id;
    const assigned = new Set(activeMissions.map((m) => m.ambulance_id).filter(Boolean));
    if (assignedUnit) assigned.add(assignedUnit);
    const fleetMarks = fleet.map((a: any) => ({
      position: [a.lat, a.lng] as [number, number],
      popup: `🚑 ${a.id} · ${a.label}<br/><span style="font-weight:600;color:#6B6B6B">${a.status}${assigned.has(a.id) ? ' · assigned' : ''}</span>`,
      type: 'ambulance',
      id: a.id,
      ambulanceId: a.id,
      hasMission: assigned.has(a.id),
    }));
    const hospMarks = hosp.map((h: any) => ({
      position: [h.lat, h.lng] as [number, number],
      popup: `🏥 ${h.name}<br/>Beds ${h.available_beds}/${h.total_beds}`,
      type: hospitalId === h.id ? 'hospital_selected' : 'hospital',
    }));
    return [
      { position: [BMSIT.lat, BMSIT.lng] as [number, number], popup: `📍 ${BMSIT.name}`, type: 'incident' },
      ...hospMarks,
      ...fleetMarks,
      ...(monitor?.patient?.lat
        ? [{ position: [monitor.patient.lat, monitor.patient.lng] as [number, number], popup: `Patient · ${monitor.patient.name || 'unknown'}`, type: 'incident' }]
        : []),
      ...postMarkers(corridor?.posts || []),
      ...extra,
    ];
  }

  function clearMissionUi() {
    pickupRoute = [];
    dropRoute = [];
    extraRoutes = [];
    etaLabel = '';
    selectedHospital = null;
    assignedUnit = '';
    constraints = null;
    confidence = null;
    reason = '';
    candidates = [];
    pickupMinutes = null;
    transportMinutes = null;
    dispatchStatus = '';
    selectedAmbulanceId = '';
    extraRoutes = extraRoutesFor(activeMissions, '');
    markers = buildMarkers();
  }

  async function loadFleet() {
    try {
      const res = await apiFetch('/tracking/fleet');
      const data = await res.json();
      ambulances = data.ambulances || [];
      hospitals = data.hospitals || [];
      markers = buildMarkers();
    } catch (err) {
      console.error(err);
    }
  }

  async function endTrip() {
    await apiFetch('/accounts/mission/phase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'complete' }),
    });
    await loadMonitor();
    await loadFleet();
  }

  async function loadCorridor() {
    try {
      const res = await apiFetch('/tracking/corridor');
      if (!res.ok) return;
      corridor = await res.json();
      const liveMissions = corridor.missions || [];
      if (liveMissions.length) activeMissions = liveMissions;
      extraRoutes = extraRoutesFor(activeMissions, selectedAmbulanceId || assignedUnit);
      markers = buildMarkers();
    } catch {
      /* ignore */
    }
  }

  async function loadMonitor() {
    try {
      const res = await apiFetch('/accounts/monitor');
      if (!res.ok) return;
      monitor = await res.json();
      const liveList = (monitor.active_missions || []).filter((m: any) => m && m.phase !== 'complete');
      activeMissions = liveList;
      const keep = liveList.find((m: any) => m.ambulance_id === selectedAmbulanceId);
      const latest = monitor?.mission && monitor.mission.phase !== 'complete' ? monitor.mission : null;
      const live = keep || latest || liveList[0] || null;
      if (live) focusMission(live);
      else clearMissionUi();
      markers = buildMarkers();
    } catch {
      /* ignore */
    }
  }

  onMount(() => {
    loadFleet();
    loadMonitor();
    loadCorridor();
    const timer = setInterval(() => {
      loadFleet();
      loadMonitor();
      loadCorridor();
    }, 2500);
    return () => clearInterval(timer);
  });
</script>

<svelte:head><title>{t('dash.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col" style="overflow: hidden;">
  <div class="p-4 grid grid-cols-12 gap-4 h-full overflow-hidden">

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="nb-card nb-yellow p-4 flex-shrink-0">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-[11px] font-black uppercase tracking-widest text-black">System Performance</h3>
          <span class="w-2.5 h-2.5 bg-[#22C55E] blink" style="border:2px solid #111;"></span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-white p-3" style="border:3px solid #111;">
            <div class="text-3xl font-black text-black leading-none">{etaLabel ? etaLabel.split(' ')[0] : '—'}<span class="text-xs text-[#4B4B4B] ml-1">min</span></div>
            <div class="text-[9px] uppercase tracking-widest text-[#4B4B4B] mt-1 font-bold">Hospital ETA</div>
          </div>
          <div class="bg-white p-3" style="border:3px solid #111;">
            <div class="text-3xl font-black text-black leading-none">{availableCount}<span class="text-xs text-[#4B4B4B] ml-1">u</span></div>
            <div class="text-[9px] uppercase tracking-widest text-[#4B4B4B] mt-1 font-bold">Available</div>
          </div>
        </div>
      </section>

      <section class="flex flex-col gap-3 flex-1 min-h-0">
        <div class="flex justify-between items-center flex-wrap gap-1">
          <h3 class="text-[11px] font-black uppercase tracking-widest text-black">{t('dash.fleet')}</h3>
          <span class="nb-chip nb-red" style="color:#fff;">{dispatchStatus || t('dash.waitingSos')}</span>
        </div>

        <p class="text-[10px] text-[#4B4B4B] font-semibold">{t('dash.tapHint')}</p>

        <div class="space-y-2 overflow-y-auto no-sb flex-1 pr-1">
          {#each ambulances as a}
            <button
              type="button"
              onclick={() => selectAmbulance(a.id)}
              class="flex items-center justify-between bg-white px-3 py-2 w-full text-left {assignedIds.has(a.id) ? 'nb-red' : ''} {selectedAmbulanceId === a.id ? 'ring-2 ring-black' : ''}"
              style="border:3px solid #111;box-shadow:3px 3px 0 #111;cursor:pointer;"
            >
              <div>
                <p class="text-[12px] font-black {assignedIds.has(a.id) ? 'text-white' : 'text-black'}">{a.id}</p>
                <p class="text-[9px] {assignedIds.has(a.id) ? 'text-white/80' : 'text-[#4B4B4B]'} uppercase tracking-wide font-bold">{a.label}</p>
              </div>
              <span class="nb-chip {a.status === 'available' ? 'nb-green' : a.status === 'dispatched' ? 'nb-red' : ''}" style="color:{a.status === 'idle' ? '#111' : '#fff'};">{a.status}</span>
            </button>
          {/each}
        </div>
      </section>
    </div>

    <div class="col-span-6 relative overflow-hidden nb-card-lg" style="border:4px solid #111;">
      <MapWidget id="dash-map" {markers} {etaLabel} {pickupRoute} {dropRoute} {extraRoutes} {selectedAmbulanceId} officerCallEnabled showLegend center={[BMSIT.lat, BMSIT.lng]} onSelectAmbulance={selectAmbulance} />
      <div class="absolute inset-0 pointer-events-none z-10" style="padding: 0.9rem;">
        <div class="flex justify-between items-start pointer-events-auto gap-2">
          <div class="glass px-3 py-2">
            <div class="flex items-center gap-2">
              <span class="flex h-2.5 w-2.5 bg-[#FF2D2D] blink" style="border:2px solid #111;"></span>
              <span class="text-[11px] font-black tracking-widest uppercase text-black">{t('dash.liveFeed')}</span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-2">
            {#if monitor?.unread_alerts}
              <a href="/notifications" class="glass px-3 py-1.5 text-[10px] text-black font-black uppercase tracking-widest nb-red" style="color:#fff;">
                {monitor.unread_alerts === 1
                  ? t('dash.staffAlerts', { count: monitor.unread_alerts })
                  : t('dash.staffAlertsPlural', { count: monitor.unread_alerts })}
              </a>
            {/if}
            {#if monitor?.mission && monitor.mission.phase !== 'complete'}
              <button class="btn btn-primary" style="padding:6px 12px;font-size:10px;" onclick={endTrip}>
                {t('dash.endTrip')}
              </button>
            {/if}
            <div class="glass px-3 py-1.5 text-[10px] text-black font-bold uppercase tracking-widest max-w-[220px] text-right nb-yellow">
              📍 {BMSIT.name}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="nb-card nb-blue p-4 flex-shrink-0" style="color:#fff;">
        <div class="flex items-center gap-2 mb-3">
          <span class="material-symbols-outlined">psychology</span>
          <h3 class="text-[11px] font-black uppercase tracking-widest">{t('dash.aiRec')}</h3>
        </div>
        {#if selectedHospital}
          <div class="flex gap-3 mb-3">
            <div class="h-11 w-11 shrink-0 bg-white text-black flex items-center justify-center font-black text-xs" style="border:3px solid #111;">{confidence ?? '—'}%</div>
            <div>
              <p class="text-sm font-black">{selectedHospital.name}</p>
              <p class="text-[10px] text-white/85 mt-1">{reason}</p>
            </div>
          </div>
          {#if pickupMinutes != null}
            <p class="text-[10px] font-semibold">{t('dash.pickupTransport', { pickup: pickupMinutes ?? '—', transport: transportMinutes ?? '—' })}</p>
          {/if}
          {#if constraints}
            <p class="text-[10px] mt-2 uppercase tracking-wide font-bold">
              {constraints.routing === 'emergency-shortest' ? t('dash.corridor') : `${constraints.routing} · ${constraints.traffic} traffic`}
            </p>
            <p class="text-[10px] mt-1 uppercase tracking-wide font-bold">
              Engine: {constraints.engine === 'networkx' ? `NetworkX Dijkstra${constraints.graph_nodes ? ` · ${constraints.graph_nodes} nodes` : ''}` : 'Direct TomTom/OSRM'}
            </p>
            {#if constraints.shortest_km != null && constraints.fastest_min != null}
              <p class="text-[10px] mt-1 font-bold">Shortest {constraints.shortest_km} km · Fastest {constraints.fastest_min} min</p>
            {/if}
          {/if}
          {#if conflictReason}
            <p class="text-[10px] mt-2 font-black" style="background:#FFD23F;color:#111;padding:6px;border:2px solid #111;">{conflictReason}</p>
          {/if}
          {#if assignedUnit}
            <p class="nb-chip mt-2" style="background:#FFD23F;color:#111;">{t('dash.assigned', { unit: assignedUnit })}</p>
          {/if}
          {#if candidates.length}
            <div class="mt-3 space-y-1 bg-white text-black p-2" style="border:3px solid #111;">
              <p class="text-[9px] font-black uppercase tracking-widest text-[#4B4B4B]">{t('dash.ranked')}</p>
              {#each candidates as c, i}
                <div class="flex justify-between gap-2 text-[10px] {i === 0 ? 'font-black' : 'text-[#4B4B4B]'}">
                  <span>{i + 1}. {c.name}</span>
                  <span class="shrink-0">{c.eta_minutes} min</span>
                </div>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="flex gap-3">
            <div class="h-11 w-11 shrink-0 bg-white text-black flex items-center justify-center font-black text-xs" style="border:3px solid #111;">—</div>
            <div>
              <p class="text-sm font-black">{t('dash.waitingPatient')}</p>
              <p class="text-[10px] text-white/85 mt-1">{t('dash.waitingPatientHint')}</p>
            </div>
          </div>
        {/if}
      </section>

      <section class="flex-1 flex flex-col gap-3 min-h-0">
        <h3 class="text-[11px] font-black uppercase tracking-widest text-black">{t('dash.telemetry')}</h3>
        <div class="space-y-3 overflow-y-auto no-sb flex-1 pr-1">
          <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
            <div class="flex justify-between items-center mb-1">
              <span class="nb-chip nb-blue" style="color:#fff;">{t('dash.fleet')}</span>
              <span class="text-[9px] text-[#4B4B4B] font-bold uppercase">{t('dash.live')}</span>
            </div>
            <p class="text-xs text-black font-semibold mt-1">{t('dash.fleetTracked', { count: ambulances.length })}</p>
          </div>
          {#if monitor?.patient}
            <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-green" style="color:#fff;">{t('dash.patient')}</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold">{monitor.patient.vitals?.heart_rate ?? '—'} bpm</span>
              </div>
              <p class="text-xs text-black font-semibold mt-1">{monitor.patient.name || t('dash.unassigned')} · {monitor.patient.address}</p>
              <p class="text-[10px] text-[#4B4B4B] mt-1 font-semibold">
                SpO2 {monitor.patient.vitals?.spo2 ?? '—'}%
                · {t('patient.cardiac')} {monitor.patient.record?.cardiac ? t('dash.yes') : t('dash.no')}
                · {t('patient.diabetes')} {monitor.patient.record?.diabetes ? t('dash.yes') : t('dash.no')}
              </p>
              {#if monitor.driver}
                <p class="text-[10px] text-[#FF2D2D] mt-1 font-black">Driver {monitor.driver.id} at {monitor.driver.lat}, {monitor.driver.lng}</p>
              {/if}
            </div>
          {/if}
          {#if activeMissions.length}
            <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-red" style="color:#fff;">{t('dash.liveCorridors')}</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold uppercase">{activeMissions.length === 1 ? t('dash.unit', { count: activeMissions.length }) : t('dash.units', { count: activeMissions.length })}</span>
              </div>
              {#each activeMissions as m}
                <button type="button" class="block w-full text-left" onclick={() => selectAmbulance(m.ambulance_id)}>
                  <p class="text-[10px] font-semibold mt-1 {selectedAmbulanceId === m.ambulance_id ? 'text-[#FF2D2D] font-black' : 'text-black'}">
                    {m.ambulance_id} · {m.priority_label || 'standard'} · {m.phase} → {m.hospital_name}
                    {#if m.conflict?.status && m.conflict.status !== 'none'}
                      <span class="text-[#b45309]"> · {m.conflict.status}</span>
                    {/if}
                  </p>
                </button>
              {/each}
            </div>
          {/if}
          {#if corridor?.sms?.length}
            <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
              <span class="nb-chip nb-yellow">Corridor SMS</span>
              <p class="text-[10px] text-black font-semibold mt-2">{corridor.sms[0].post_name}: {corridor.sms[0].status}</p>
              <p class="text-[10px] text-[#4B4B4B] mt-1">{corridor.sms[0].body}</p>
            </div>
          {/if}
          {#if selectedHospital}
            <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-red" style="color:#fff;">Route</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold uppercase">Now</span>
              </div>
              <p class="text-xs text-black font-semibold mt-1">{etaLabel} · {selectedHospital.name}</p>
            </div>
          {/if}
          {#if monitor?.mission?.report?.body}
            <div class="bg-white p-3" style="border:3px solid #111;box-shadow:3px 3px 0 #111;">
              <span class="nb-chip nb-red" style="color:#fff;">Trip report</span>
              <pre class="text-[10px] text-black whitespace-pre-wrap font-sans mt-2">{monitor.mission.report.body}</pre>
            </div>
          {/if}
        </div>
      </section>
    </div>

  </div>
</div>
