<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';

  const BMSIT = {
    name: 'BMSIT College, Avalahalli, Yelahanka',
    lat: 13.1344,
    lng: 77.5693,
  };

  let route = $state<[number, number][]>([]);
  let markers = $state<any[]>([]);
  let dispatchStatus = $state('Waiting for SOS');
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
  let availableCount = $derived(ambulances.filter((a) => a.status === 'available').length);

  function applyPayload(payload: any) {
    if (!payload) return;
    const routeCoords: [number, number][] = payload.route || payload.pickup_route || [];
    route = routeCoords.length > 1 ? routeCoords : [];
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
      dispatchStatus = `Auto → ${payload.hospital_name} · ${assignedUnit || 'unit'}`;
    }
    markers = buildMarkers();
  }

  function buildMarkers(fleet = ambulances, hosp = hospitals, extra: any[] = []) {
    const hospitalId = selectedHospital?.id;
    const fleetMarks = fleet.map((a: any) => ({
      position: [a.lat, a.lng] as [number, number],
      popup: `🚑 ${a.id} · ${a.label}<br/><span style="font-weight:600;color:#6B6B6B">${a.status}</span>`,
      type: 'ambulance',
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
      ...extra,
    ];
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

  async function loadMonitor() {
    try {
      const res = await apiFetch('/accounts/monitor');
      if (!res.ok) return;
      monitor = await res.json();
      if (monitor?.mission) applyPayload(monitor.mission);
    } catch {
      /* ignore */
    }
  }

  onMount(() => {
    loadFleet();
    loadMonitor();
    const timer = setInterval(() => {
      loadFleet();
      loadMonitor();
    }, 2500);
    return () => clearInterval(timer);
  });
</script>

<svelte:head><title>JEEVAN — Dispatch</title></svelte:head>

<div class="h-full flex flex-col" style="overflow: hidden;">
  <div class="p-5 grid grid-cols-12 gap-5 h-full overflow-hidden">

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="bg-slate-900/60 p-5 rounded-xl border border-slate-800/60 flex-shrink-0">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500">System Performance</h3>
          <span class="w-2 h-2 rounded-full bg-green-500 blink"></span>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <div class="text-2xl font-black text-white">{etaLabel ? etaLabel.split(' ')[0] : '—'}<span class="text-xs text-slate-500 ml-1">min</span></div>
            <div class="text-[9px] uppercase tracking-wide text-slate-400 mt-0.5">Hospital ETA</div>
          </div>
          <div>
            <div class="text-2xl font-black text-white">{availableCount}<span class="text-xs text-slate-500 ml-1">units</span></div>
            <div class="text-[9px] uppercase tracking-wide text-slate-400 mt-0.5">Available</div>
          </div>
        </div>
      </section>

      <section class="flex flex-col gap-3 flex-1 min-h-0">
        <div class="flex justify-between items-center">
          <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500">Yelahanka Fleet</h3>
          <span class="text-[10px] text-red-500 font-bold">{dispatchStatus}</span>
        </div>

        <p class="text-[10px] text-slate-400">Fastest unit and hospital are assigned automatically from patient SOS using traffic routing. Staff does not pick a hospital.</p>

        <div class="space-y-1.5 overflow-y-auto no-sb flex-1">
          {#each ambulances as a}
            <div class="flex items-center justify-between bg-slate-900/40 border border-slate-800/60 px-3 py-1.5 rounded-lg">
              <div>
                <p class="text-[11px] font-bold text-white">{a.id}</p>
                <p class="text-[9px] text-slate-500 uppercase tracking-wide">{a.label}</p>
              </div>
              <span class="text-[9px] font-bold uppercase tracking-wider {a.status === 'available' ? 'text-green-400' : a.status === 'dispatched' ? 'text-red-400' : 'text-yellow-400'}">{a.status}</span>
            </div>
          {/each}
        </div>
      </section>
    </div>

    <div class="col-span-6 relative rounded-2xl overflow-hidden shadow-2xl border border-slate-800">
      <MapWidget id="dash-map" {route} {markers} {etaLabel} center={[BMSIT.lat, BMSIT.lng]} />
      <div class="absolute inset-0 pointer-events-none z-10" style="padding: 1rem;">
        <div class="flex justify-between items-start pointer-events-auto">
          <div class="glass px-4 py-2 rounded-xl border border-slate-700/50 shadow">
            <div class="flex items-center gap-2">
              <span class="flex h-2 w-2 rounded-full bg-red-600 blink"></span>
              <span class="text-xs font-bold tracking-widest uppercase text-white">Yelahanka Live Feed</span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-2">
            {#if monitor?.unread_alerts}
              <a href="/notifications" class="glass px-3 py-1.5 rounded-xl border border-red-500/50 text-[10px] text-red-400 font-bold uppercase tracking-widest">
                {monitor.unread_alerts} staff alert{monitor.unread_alerts === 1 ? '' : 's'}
              </a>
            {/if}
            <div class="glass px-3 py-1.5 rounded-xl border border-yellow-500/30 text-[10px] text-yellow-400 font-bold uppercase tracking-widest max-w-[220px] text-right">
              📍 {BMSIT.name}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="bg-gradient-to-br from-slate-900 to-blue-900/20 p-5 rounded-2xl border border-blue-500/20 shadow-xl flex-shrink-0">
        <div class="flex items-center gap-2 mb-4">
          <span class="material-symbols-outlined text-blue-400">psychology</span>
          <h3 class="text-[10px] font-black uppercase tracking-widest text-blue-400">AI Recommendation</h3>
        </div>
        {#if selectedHospital}
          <div class="flex gap-3 mb-3">
            <div class="h-9 w-9 shrink-0 bg-blue-600/20 rounded-lg flex items-center justify-center border border-blue-500/30 text-blue-400 font-bold text-xs">{confidence ?? '—'}%</div>
            <div>
              <p class="text-xs font-bold text-white">{selectedHospital.name}</p>
              <p class="text-[10px] text-slate-400 mt-1">{reason}</p>
            </div>
          </div>
          {#if pickupMinutes != null}
            <p class="text-[10px] text-slate-300">Pickup {pickupMinutes} min · Transport {transportMinutes} min</p>
          {/if}
          {#if constraints}
            <p class="text-[10px] text-blue-300 mt-2 uppercase tracking-wide">
              {constraints.routing} · {constraints.traffic} traffic
            </p>
          {/if}
          {#if assignedUnit}
            <p class="text-[10px] text-red-400 mt-1 font-bold">Assigned {assignedUnit}</p>
          {/if}
          {#if candidates.length}
            <div class="mt-3 space-y-1.5">
              <p class="text-[9px] font-black uppercase tracking-widest text-slate-500">Ranked hospitals</p>
              {#each candidates as c, i}
                <div class="flex justify-between gap-2 text-[10px] {i === 0 ? 'text-white font-bold' : 'text-slate-400'}">
                  <span>{i + 1}. {c.name}</span>
                  <span class="shrink-0">{c.eta_minutes} min</span>
                </div>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="flex gap-3">
            <div class="h-9 w-9 shrink-0 bg-blue-600/20 rounded-lg flex items-center justify-center border border-blue-500/30 text-blue-400 font-bold text-xs">—</div>
            <div>
              <p class="text-xs font-bold text-white">Waiting for patient SOS</p>
              <p class="text-[10px] text-slate-400 mt-1">The fastest ambulance and hospital are assigned automatically from traffic.</p>
            </div>
          </div>
        {/if}
      </section>

      <section class="flex-1 flex flex-col gap-3 min-h-0">
        <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500">Telemetry Stream</h3>
        <div class="relative space-y-3 overflow-y-auto no-sb flex-1" style="padding-left: 1.75rem;">
          <div class="absolute left-2 top-0 bottom-0 w-px bg-slate-800"></div>
          <div class="relative">
            <span class="absolute -left-[1.35rem] top-1 w-2 h-2 rounded-full bg-blue-500 ring-4 ring-slate-950"></span>
            <div class="bg-slate-900/40 p-3 rounded-xl border border-slate-800/50">
              <div class="flex justify-between items-center mb-1">
                <span class="text-[10px] font-bold text-blue-500 uppercase">Fleet</span>
                <span class="text-[9px] text-slate-500">Live</span>
              </div>
              <p class="text-xs text-slate-200">{ambulances.length} ambulances tracked across Yelahanka.</p>
            </div>
          </div>
          {#if monitor?.patient}
            <div class="relative">
              <span class="absolute -left-[1.35rem] top-1 w-2 h-2 rounded-full bg-green-500 ring-4 ring-slate-950"></span>
              <div class="bg-slate-900/40 p-3 rounded-xl border border-slate-800/50">
                <div class="flex justify-between items-center mb-1">
                  <span class="text-[10px] font-bold text-green-500 uppercase">Patient</span>
                  <span class="text-[9px] text-slate-500">{monitor.patient.vitals?.heart_rate ?? '—'} bpm</span>
                </div>
                <p class="text-xs text-slate-200">{monitor.patient.name || 'Unassigned'} · {monitor.patient.address}</p>
                <p class="text-[10px] text-slate-400 mt-1">
                  SpO2 {monitor.patient.vitals?.spo2 ?? '—'}%
                  · Cardiac {monitor.patient.record?.cardiac ? 'yes' : 'no'}
                  · Diabetes {monitor.patient.record?.diabetes ? 'yes' : 'no'}
                </p>
                {#if monitor.driver}
                  <p class="text-[10px] text-red-300 mt-1">Driver {monitor.driver.id} at {monitor.driver.lat}, {monitor.driver.lng}</p>
                {/if}
              </div>
            </div>
          {/if}
          {#if selectedHospital}
            <div class="relative">
              <span class="absolute -left-[1.35rem] top-1 w-2 h-2 rounded-full bg-red-500 ring-4 ring-slate-950"></span>
              <div class="bg-slate-900/40 p-3 rounded-xl border border-slate-800/50">
                <div class="flex justify-between items-center mb-1">
                  <span class="text-[10px] font-bold text-red-500 uppercase">Route</span>
                  <span class="text-[9px] text-slate-500">Now</span>
                </div>
                <p class="text-xs text-slate-200">{etaLabel} · {selectedHospital.name}</p>
              </div>
            </div>
          {/if}
        </div>
      </section>
    </div>

  </div>
</div>
