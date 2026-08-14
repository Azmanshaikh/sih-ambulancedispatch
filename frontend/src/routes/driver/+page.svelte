<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let mission = $state<any>(null);
  let markers = $state<any[]>([]);
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let etaLabel = $state('');
  let alertBanner = $state<any>(null);
  let lastAlertId = $state('');

  function applyMission(m: any) {
    mission = m;
    if (!m) {
      markers = [];
      pickupRoute = [];
      dropRoute = [];
      etaLabel = '';
      return;
    }
    const pickup = m.pickup || {};
    const hosp = m.hospital || {};
    const drv = m.driver_location || {};
    const pts: any[] = [];
    if (drv.lat) pts.push({ position: [drv.lat, drv.lng], popup: `Unit ${m.ambulance_id}`, type: 'ambulance' });
    if (pickup.lat) pts.push({ position: [pickup.lat, pickup.lng], popup: `Pickup · ${m.pickup_person}`, type: 'incident' });
    if (hosp.lat) pts.push({ position: [hosp.lat, hosp.lng], popup: `Hospital · ${m.destination}`, type: 'hospital_selected' });
    markers = pts;
    pickupRoute = m.pickup_route || [];
    dropRoute = m.drop_route || [];
    etaLabel = m.eta_label || '';
  }

  async function loadMission() {
    const res = await apiFetch('/accounts/mission');
    if (!res.ok) return;
    const data = await res.json();
    applyMission(data.mission);
  }

  async function loadAlerts() {
    const res = await apiFetch('/accounts/alerts');
    if (!res.ok) return;
    const data = await res.json();
    const unread = (data.alerts || []).find((a: any) => !a.read);
    if (unread && unread.id !== lastAlertId) {
      alertBanner = unread;
      lastAlertId = unread.id;
    }
  }

  async function ackAlert() {
    if (!alertBanner) return;
    await apiFetch(`/accounts/alerts/${alertBanner.id}/ack`, { method: 'POST' });
    alertBanner = null;
  }

  async function arrivedPickup() {
    await apiFetch('/accounts/mission/phase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'drop' }),
    });
    await loadMission();
  }

  async function endTrip() {
    await apiFetch('/accounts/mission/phase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'complete' }),
    });
    await loadMission();
  }

  onMount(() => {
    loadMission();
    loadAlerts();
    const t = setInterval(() => {
      loadMission();
      loadAlerts();
    }, 2000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>JEEVAN — Driver mission</title></svelte:head>

<div class="h-full flex flex-col relative">
  {#if alertBanner}
    <div class="absolute inset-0 z-30 flex items-center justify-center" style="background:rgba(127,29,29,0.88);">
      <div class="bg-white p-8 max-w-md w-[90%] border-4 border-[#DC2626] text-center">
        <p class="text-[11px] font-black uppercase tracking-[0.3em] text-red-600 mb-2">{alertBanner.title}</p>
        <h2 class="text-2xl font-black mb-3">You are assigned this job</h2>
        <p class="text-sm text-slate-700 mb-2">{alertBanner.body}</p>
        {#if alertBanner.pickup}
          <p class="text-xs uppercase tracking-widest text-slate-500 mt-3">Pickup</p>
          <p class="font-bold">{alertBanner.pickup}</p>
        {/if}
        {#if alertBanner.drop}
          <p class="text-xs uppercase tracking-widest text-slate-500 mt-3">Drop</p>
          <p class="font-bold">{alertBanner.drop}</p>
        {/if}
        <button class="btn btn-primary mt-6 w-full py-3" onclick={ackAlert}>Acknowledge</button>
      </div>
    </div>
  {/if}

  <div class="flex-1 relative">
    <MapWidget id="driver-map" clazz="absolute inset-0" {markers} {pickupRoute} {dropRoute} {etaLabel} showLegend />
    <div class="absolute top-5 left-5 z-10 w-80 pointer-events-none">
      <div class="glass p-5 rounded-xl border border-slate-800/60 shadow-2xl pointer-events-auto" style="background:rgba(255,255,255,0.95);">
        {#if !mission}
          <p class="text-[10px] font-bold uppercase tracking-widest text-red-500">Standby</p>
          <h2 class="text-xl font-bold mb-2">No assignment</h2>
          <p class="text-xs text-slate-500">You will be alerted when a patient requests dispatch.</p>
        {:else}
          <p class="text-[10px] font-bold uppercase tracking-widest text-red-500">
            {mission.phase === 'complete' ? 'Trip complete' : mission.phase === 'drop' ? 'Heading to drop' : 'Heading to pickup'}
          </p>
          <h2 class="text-lg font-bold mb-2">{mission.pickup_person}</h2>
          {#if mission.phase === 'complete'}
            <p class="text-xs text-slate-600">Patient handed over. A trip report was generated for staff and the patient.</p>
          {:else}
            {#if mission.phase !== 'drop'}
              <p class="text-xs text-slate-600 mb-3">Go to {mission.pickup_name}</p>
              <button class="btn btn-primary w-full mb-2" onclick={arrivedPickup}>Arrived at pickup</button>
            {:else}
              <p class="text-xs text-slate-600 mb-1">Patient on board</p>
              <p class="text-[10px] font-bold uppercase tracking-widest text-red-500 mt-3">Final destination</p>
              <p class="text-sm font-bold mb-3">{mission.destination}</p>
            {/if}
            <button class="btn w-full border-2 border-[#DC2626] text-[#DC2626] font-black uppercase tracking-widest py-3" onclick={endTrip}>
              End trip / Trip complete
            </button>
            <p class="text-[10px] text-slate-500 mt-2">Auto-completes when the unit reaches hospital if you do not tap this.</p>
          {/if}
          <p class="text-xs text-slate-500 mt-2">ETA {mission.eta_minutes ?? '—'} min · {mission.ambulance_id}</p>
        {/if}
      </div>
    </div>
  </div>
</div>
