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
    <div class="absolute inset-0 z-30 flex items-center justify-center p-4" style="background:rgba(17,17,17,0.82);">
      <div class="nb-card-lg bg-white p-8 max-w-md w-[90%] text-center" style="border:4px solid #111;">
        <p class="nb-chip nb-red mx-auto mb-3" style="color:#fff;">{alertBanner.title}</p>
        <h2 class="text-2xl font-black mb-3 uppercase">You are assigned this job</h2>
        <p class="text-sm text-black mb-2 font-semibold">{alertBanner.body}</p>
        {#if alertBanner.pickup}
          <p class="text-xs uppercase tracking-widest text-[#4B4B4B] mt-3 font-bold">Pickup</p>
          <p class="font-black">{alertBanner.pickup}</p>
        {/if}
        {#if alertBanner.drop}
          <p class="text-xs uppercase tracking-widest text-[#4B4B4B] mt-3 font-bold">Drop</p>
          <p class="font-black">{alertBanner.drop}</p>
        {/if}
        <button class="btn btn-primary mt-6 w-full py-3" onclick={ackAlert}>Acknowledge</button>
      </div>
    </div>
  {/if}

  <div class="flex-1 relative">
    <MapWidget id="driver-map" clazz="absolute inset-0" {markers} {pickupRoute} {dropRoute} {etaLabel} showLegend />
    <div class="absolute top-5 left-5 z-10 w-80 max-w-[calc(100%-2.5rem)] pointer-events-none">
      <div class="glass p-5 pointer-events-auto">
        {#if !mission}
          <p class="nb-chip nb-red mb-2" style="color:#fff;">Standby</p>
          <h2 class="text-xl font-black mb-2 uppercase">No assignment</h2>
          <p class="text-xs text-[#4B4B4B] font-semibold">You will be alerted when a patient requests dispatch.</p>
        {:else}
          <p class="nb-chip nb-red mb-2" style="color:#fff;">
            {mission.phase === 'complete' ? 'Trip complete' : mission.phase === 'drop' ? 'Heading to drop' : 'Heading to pickup'}
          </p>
          <h2 class="text-lg font-black mb-2 uppercase">{mission.pickup_person}</h2>
          {#if mission.phase === 'complete'}
            <p class="text-xs text-black font-semibold">Patient handed over. A trip report was generated for staff and the patient.</p>
          {:else}
            {#if mission.phase !== 'drop'}
              <p class="text-xs text-black font-semibold mb-3">Go to {mission.pickup_name}</p>
              <button class="btn btn-primary w-full mb-2" onclick={arrivedPickup}>Arrived at pickup</button>
            {:else}
              <p class="text-xs text-black font-semibold mb-1">Patient on board</p>
              <p class="nb-chip nb-blue mt-3 mb-1" style="color:#fff;">Final destination</p>
              <p class="text-sm font-black mb-3">{mission.destination}</p>
            {/if}
            <button class="btn btn-secondary w-full py-3" onclick={endTrip}>
              End trip / Trip complete
            </button>
            <p class="text-[10px] text-[#4B4B4B] mt-2 font-semibold">Auto-completes when the unit reaches hospital if you do not tap this.</p>
          {/if}
          <p class="text-xs text-[#4B4B4B] mt-2 font-bold">ETA {mission.eta_minutes ?? '—'} min · {mission.ambulance_id}</p>
        {/if}
      </div>
    </div>
  </div>
</div>
