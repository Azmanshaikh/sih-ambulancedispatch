<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';

  const BMSIT: [number, number] = [13.1344, 77.5693];

  let ambulances = $state<any[]>([]);
  let hospitals = $state<any[]>([]);
  let corridor = $state<any>(null);
  let monitor = $state<any>(null);
  let activeMissions = $state<any[]>([]);
  let selectedAmbulanceId = $state('');
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let extraRoutes = $state<any[]>([]);
  let markers = $state<any[]>([]);
  let etaLabel = $state('');
  let selected = $state<any>(null);

  let assignedIds = $derived(new Set(activeMissions.map((m) => m.ambulance_id).filter(Boolean)));

  function extraRoutesFor(missions: any[], selectedId: string) {
    const extras: any[] = [];
    for (const m of missions) {
      if (!m || m.ambulance_id === selectedId) continue;
      const pickup = m.pickup_route || [];
      const drop = m.drop_route || m.route || [];
      if (pickup.length > 1) extras.push({ id: `${m.id}-pickup`, points: pickup, color: '#fb7185', kind: 'pickup' });
      if (drop.length > 1) extras.push({ id: `${m.id}-drop`, points: drop, color: '#38bdf8', kind: 'drop' });
    }
    for (const r of corridor?.extra_routes || []) {
      if (r.kind === 'overlap') extras.push(r);
    }
    return extras;
  }

  function buildMarkers() {
    const fleetMarks = ambulances.map((a: any) => ({
      position: [a.lat, a.lng] as [number, number],
      popup: `🚑 ${a.id} · ${a.label}<br/><span style="font-weight:600;color:#6B6B6B">${a.status}${assignedIds.has(a.id) ? ' · assigned' : ''}</span>`,
      type: 'ambulance',
      id: a.id,
      ambulanceId: a.id,
      hasMission: assignedIds.has(a.id),
    }));
    const hospMarks = hospitals.map((h: any) => ({
      position: [h.lat, h.lng] as [number, number],
      popup: `🏥 ${h.name}`,
      type: selected?.hospital?.id === h.id ? 'hospital_selected' : 'hospital',
    }));
    const incident = selected?.pickup
      ? [{ position: [selected.pickup.lat, selected.pickup.lng] as [number, number], popup: `📍 ${selected.pickup.name || selected.patient_name || 'Pickup'}`, type: 'incident' }]
      : [{ position: BMSIT, popup: '📍 BMSIT College, Yelahanka', type: 'incident' }];
    return [
      ...incident,
      ...hospMarks,
      ...fleetMarks,
      ...(corridor?.posts || []).map((p: any) => postToMarker(p, true)),
    ];
  }

  function focusMission(mission: any | null) {
    if (!mission || mission.phase === 'complete') {
      selected = null;
      pickupRoute = [];
      dropRoute = [];
      etaLabel = '';
      extraRoutes = extraRoutesFor(activeMissions, '');
      markers = buildMarkers();
      return;
    }
    selected = mission;
    selectedAmbulanceId = mission.ambulance_id || '';
    pickupRoute = mission.pickup_route || [];
    dropRoute = mission.drop_route || mission.route || [];
    const mins = mission.eta_minutes ?? Math.round((mission.eta_seconds || 0) / 60);
    etaLabel = mins ? `${mins} min` : '';
    extraRoutes = extraRoutesFor(activeMissions, selectedAmbulanceId);
    markers = buildMarkers();
  }

  function selectAmbulance(id: string) {
    selectedAmbulanceId = id;
    const hit = activeMissions.find((m) => m.ambulance_id === id);
    if (hit) focusMission(hit);
    else {
      extraRoutes = extraRoutesFor(activeMissions, id);
      markers = buildMarkers();
    }
  }

  async function loadFleet() {
    try {
      const res = await apiFetch('/tracking/fleet');
      if (!res.ok) return;
      const data = await res.json();
      ambulances = data.ambulances || [];
      hospitals = data.hospitals || [];
      markers = buildMarkers();
    } catch {
      /* ignore */
    }
  }

  async function loadLive() {
    try {
      const [mRes, cRes] = await Promise.all([apiFetch('/accounts/monitor'), apiFetch('/tracking/corridor')]);
      if (cRes.ok) corridor = await cRes.json();
      if (mRes.ok) monitor = await mRes.json();
      const fromMonitor = (monitor?.active_missions || []).filter((m: any) => m && m.phase !== 'complete');
      const fromCorridor = corridor?.missions || [];
      activeMissions = fromMonitor.length ? fromMonitor : fromCorridor;
      const keep = activeMissions.find((m) => m.ambulance_id === selectedAmbulanceId);
      const latest = monitor?.mission && monitor.mission.phase !== 'complete' ? monitor.mission : null;
      focusMission(keep || latest || activeMissions[0] || null);
    } catch (err) {
      console.error(err);
    }
  }

  onMount(() => {
    loadFleet();
    loadLive();
    const timer = setInterval(() => {
      loadFleet();
      loadLive();
    }, 2500);
    return () => clearInterval(timer);
  });
</script>

<svelte:head><title>{t('navPage.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col">
  <div class="flex-1 relative map-wrap rounded-none">
    <MapWidget
      id="nav-map"
      clazz="absolute inset-0"
      {markers}
      {pickupRoute}
      {dropRoute}
      {extraRoutes}
      {etaLabel}
      {selectedAmbulanceId}
      officerCallEnabled
      showLegend
      center={BMSIT}
      onSelectAmbulance={selectAmbulance}
    />

    <div class="absolute top-5 left-5 space-y-3 z-10 pointer-events-none max-w-[calc(100%-2.5rem)]">
      <div class="glass p-5 w-80 max-w-full pointer-events-auto">
        <p class="nb-chip nb-red mb-2" style="color:#fff;">{selected ? (selected.phase === 'drop' ? t('navPage.toHospital') : t('navPage.toPickup')) : t('navPage.standby')}</p>
        <h2 class="text-xl font-black text-black mb-4 uppercase">
          {selected ? (selected.hospital_name || selected.hospital?.name || t('navPage.activeMission')) : t('navPage.noMission')}
        </h2>
        <div class="flex justify-between mb-1">
          <span class="text-xs text-[#4B4B4B] font-bold uppercase">{t('navPage.eta')}</span>
          <span class="text-2xl font-black text-black">{etaLabel || '—'}</span>
        </div>
        <div class="flex justify-between mb-2">
          <span class="text-xs text-[#4B4B4B] font-bold uppercase">{t('navPage.unit')}</span>
          <span class="text-sm font-black text-black">{selected?.ambulance_id || '—'}</span>
        </div>
        {#if selected?.patient_name}
          <p class="text-xs text-black font-semibold mb-3">{t('navPage.patient', { name: selected.patient_name })}</p>
        {/if}
        <p class="text-[10px] text-[#4B4B4B] font-semibold">{t('navPage.hint')}</p>
      </div>

      {#if activeMissions.length}
        <div class="glass p-3 w-80 max-w-full pointer-events-auto">
          <p class="text-[10px] font-black uppercase tracking-widest text-[#4B4B4B] mb-2">{t('navPage.live')}</p>
          <div class="flex flex-col gap-1">
            {#each activeMissions as m}
              <button
                type="button"
                class="text-left px-2 py-1.5 text-[11px] font-black uppercase"
                style="border:2px solid #111;background:{selectedAmbulanceId === m.ambulance_id ? '#FF2D2D' : '#fff'};color:{selectedAmbulanceId === m.ambulance_id ? '#fff' : '#111'};"
                onclick={() => selectAmbulance(m.ambulance_id)}
              >
                {m.ambulance_id} · {m.phase} → {m.hospital_name || 'hospital'}
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <div class="absolute bottom-5 left-5 flex gap-3 z-10 flex-wrap pointer-events-none">
      <div class="glass px-4 py-2.5 flex items-center gap-2 pointer-events-auto">
        <span class="material-symbols-outlined text-[#22C55E] text-lg">traffic</span>
        <div>
          <p class="text-[9px] font-black text-[#4B4B4B] uppercase">{t('navPage.traffic')}</p>
          <p class="text-xs font-black text-black">{t('navPage.optimized')}</p>
        </div>
      </div>
      <div class="glass px-4 py-2.5 flex items-center gap-2 pointer-events-auto">
        <span class="text-lg">👮</span>
        <div>
          <p class="text-[9px] font-black text-[#4B4B4B] uppercase">{t('navPage.officer')}</p>
          <p class="text-xs font-black text-black">{t('navPage.tapCall')}</p>
        </div>
      </div>
    </div>
  </div>
</div>
