<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch, auth, refreshProfile } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';

  let mission = $state<any>(null);
  let markers = $state<any[]>([]);
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let etaLabel = $state('');
  let alertBanner = $state<any>(null);
  let lastAlertId = $state('');
  let posts = $state<any[]>([]);
  let fleet = $state<any[]>([]);
  let switching = $state(false);
  let unitId = $derived(auth.profile?.ambulance_id || '');

  async function loadFleet() {
    try {
      const res = await apiFetch('/accounts/fleet-units');
      if (!res.ok) return;
      const data = await res.json();
      fleet = data.ambulances || [];
    } catch {
      /* ignore */
    }
  }

  async function switchUnit(id: string) {
    if (!id || id === unitId || switching) return;
    switching = true;
    try {
      const res = await apiFetch('/accounts/me/ambulance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ambulance_id: id }),
      });
      if (!res.ok) return;
      await refreshProfile();
      await loadMission();
    } finally {
      switching = false;
    }
  }

  function applyMission(m: any) {
    if (!m || m.phase === 'complete') {
      mission = null;
      pickupRoute = [];
      dropRoute = [];
      etaLabel = '';
      markers = posts.map((p) => postToMarker(p, true));
      return;
    }
    mission = m;
    const pickup = m.pickup || {};
    const hosp = m.hospital || {};
    const drv = m.driver_location || {};
    const pts: any[] = [];
    if (drv.lat) {
      pts.push({
        position: [drv.lat, drv.lng],
        popup: `Unit ${m.ambulance_id}`,
        type: 'ambulance',
        id: m.ambulance_id,
        ambulanceId: m.ambulance_id,
        hasMission: true,
        priorityBand: m.priority_band,
      });
    }
    if (pickup.lat) pts.push({ position: [pickup.lat, pickup.lng], popup: `Pickup · ${m.pickup_person}`, type: 'incident' });
    if (hosp.lat) pts.push({ position: [hosp.lat, hosp.lng], popup: `Hospital · ${m.destination}`, type: 'hospital_selected' });
    markers = [...pts, ...posts.map((p) => postToMarker(p, true))];
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

  async function loadPosts() {
    try {
      const res = await apiFetch('/tracking/corridor');
      if (!res.ok) return;
      const data = await res.json();
      posts = data.posts || [];
      if (mission) applyMission(mission);
      else markers = posts.map((p) => postToMarker(p, true));
    } catch {
      /* ignore */
    }
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
    loadPosts();
    loadFleet();
    const t = setInterval(() => {
      loadMission();
      loadAlerts();
      loadPosts();
    }, 2000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>{t('driver.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col relative">
  {#if alertBanner}
    <div class="absolute inset-0 z-30 flex items-center justify-center p-4" style="background:rgba(17,17,17,0.82);">
      <div class="nb-card-lg bg-white p-8 max-w-md w-[90%] text-center" style="border:4px solid #111;">
        <p class="nb-chip nb-red mx-auto mb-3" style="color:#fff;">{alertBanner.title}</p>
        <h2 class="text-2xl font-black mb-3 uppercase">{t('driver.assigned')}</h2>
        <p class="text-sm text-black mb-2 font-semibold">{alertBanner.body}</p>
        {#if alertBanner.pickup}
          <p class="text-xs uppercase tracking-widest text-[#4B4B4B] mt-3 font-bold">{t('driver.pickup')}</p>
          <p class="font-black">{alertBanner.pickup}</p>
        {/if}
        {#if alertBanner.drop}
          <p class="text-xs uppercase tracking-widest text-[#4B4B4B] mt-3 font-bold">{t('driver.drop')}</p>
          <p class="font-black">{alertBanner.drop}</p>
        {/if}
        <button class="btn btn-primary mt-6 w-full py-3" onclick={ackAlert}>{t('driver.acknowledge')}</button>
      </div>
    </div>
  {/if}

  <div class="flex-1 relative">
    <MapWidget
      id="driver-map"
      clazz="absolute inset-0"
      {markers}
      {pickupRoute}
      {dropRoute}
      {etaLabel}
      selectedAmbulanceId={mission?.ambulance_id || ''}
      officerCallEnabled
      showLegend
    />
    <div class="absolute top-5 left-5 z-10 w-80 max-w-[calc(100%-2.5rem)] pointer-events-none">
      <div class="glass p-5 pointer-events-auto">
        {#if !mission}
          <p class="nb-chip nb-red mb-2" style="color:#fff;">{t('driver.standby')}</p>
          <h2 class="text-xl font-black mb-2 uppercase">{t('driver.noAssignment')}</h2>
          <p class="text-xs text-[#4B4B4B] font-semibold mb-3">{t('driver.alertHint')}</p>
          {#if unitId}
            <p class="text-xs font-black uppercase tracking-widest mb-2">{t('driver.yourUnit', { id: unitId })}</p>
          {/if}
          {#if fleet.length}
            <label class="text-[10px] font-black uppercase tracking-widest">{t('driver.pickUnit')}</label>
            <select
              class="nb-input w-full mt-1"
              disabled={switching}
              value={unitId}
              onchange={(e) => switchUnit((e.currentTarget as HTMLSelectElement).value)}
            >
              {#each fleet as a}
                <option value={a.id}>{a.id} · {a.label || a.type_label || a.status}</option>
              {/each}
            </select>
          {/if}
        {:else}
          <p class="nb-chip nb-red mb-2" style="color:#fff;">
            {mission.phase === 'complete' ? t('driver.tripComplete') : mission.phase === 'drop' ? t('driver.toDrop') : t('driver.toPickup')}
          </p>
          <h2 class="text-lg font-black mb-2 uppercase">{mission.pickup_person}</h2>
          {#if mission.phase === 'complete'}
            <p class="text-xs text-black font-semibold">{t('driver.handover')}</p>
          {:else}
            {#if mission.phase !== 'drop'}
              <p class="text-xs text-black font-semibold mb-3">{t('driver.goTo', { name: mission.pickup_name })}</p>
              <button class="btn btn-primary w-full mb-2" onclick={arrivedPickup}>{t('driver.arrivedPickup')}</button>
            {:else}
              <p class="text-xs text-black font-semibold mb-1">{t('driver.onBoard')}</p>
              <p class="nb-chip nb-blue mt-3 mb-1" style="color:#fff;">{t('driver.destination')}</p>
              <p class="text-sm font-black mb-3">{mission.destination}</p>
            {/if}
            <button class="btn btn-secondary w-full py-3" onclick={endTrip}>
              {t('driver.endTrip')}
            </button>
            <p class="text-[10px] text-[#4B4B4B] mt-2 font-semibold">{t('driver.autoComplete')}</p>
          {/if}
          <p class="text-xs text-[#4B4B4B] mt-2 font-bold">{t('navPage.eta')} {mission.eta_minutes ?? '—'} min · {mission.ambulance_id}</p>
          <p class="text-[10px] text-[#4B4B4B] mt-2 font-semibold">{t('driver.callHint')}</p>
        {/if}
      </div>
    </div>
  </div>
</div>
