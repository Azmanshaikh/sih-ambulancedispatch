<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let mission = $state<any>(null);
  let markers = $state<any[]>([]);
  let route = $state<[number, number][]>([]);
  let etaLabel = $state('');

  async function loadMission() {
    const res = await apiFetch('/accounts/mission');
    if (!res.ok) return;
    const data = await res.json();
    mission = data.mission;
    if (!mission) {
      markers = [];
      route = [];
      etaLabel = '';
      return;
    }
    const pickup = mission.pickup || {};
    const hosp = mission.hospital || {};
    const drv = mission.driver_location || {};
    markers = [
      pickup.lat ? { position: [pickup.lat, pickup.lng], popup: `Pickup · ${mission.pickup_person}`, type: 'incident' } : null,
      hosp.lat ? { position: [hosp.lat, hosp.lng], popup: `Hospital · ${mission.destination}`, type: 'hospital_selected' } : null,
      drv.lat ? { position: [drv.lat, drv.lng], popup: `Unit ${mission.ambulance_id}`, type: 'ambulance' } : null,
    ].filter(Boolean);
    route = mission.route || [];
    etaLabel = mission.eta_label || '';
  }

  onMount(() => {
    loadMission();
    const t = setInterval(loadMission, 4000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>JEEVAN — Driver mission</title></svelte:head>

<div class="h-full flex flex-col">
  <div class="flex-1 relative">
    <MapWidget id="driver-map" clazz="absolute inset-0" {markers} {route} {etaLabel} />
    <div class="absolute top-5 left-5 z-10 w-80 pointer-events-none">
      <div class="glass p-5 rounded-xl border border-slate-800/60 shadow-2xl pointer-events-auto" style="background:rgba(255,255,255,0.95);">
        {#if !mission}
          <p class="text-[10px] font-bold uppercase tracking-widest text-red-500">Standby</p>
          <h2 class="text-xl font-bold mb-2">No assignment</h2>
          <p class="text-xs text-slate-500">You will see pickup, heading, and hospital here when staff dispatches a job.</p>
        {:else}
          <p class="text-[10px] font-bold uppercase tracking-widest text-red-500">Pickup</p>
          <h2 class="text-lg font-bold mb-2">{mission.pickup_person}</h2>
          <p class="text-xs text-slate-600 mb-3">Heading to {mission.heading}</p>
          <p class="text-[10px] font-bold uppercase tracking-widest text-red-500">Final destination</p>
          <p class="text-sm font-bold">{mission.destination}</p>
          <p class="text-xs text-slate-500 mt-2">ETA {mission.eta_minutes ?? '—'} min · {mission.ambulance_id}</p>
        {/if}
      </div>
    </div>
  </div>
</div>
