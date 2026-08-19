<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';
  import { bandColor, bandFromScore, type PriorityBand } from '$lib/priority';

  let mission = $state<any>(null);
  let markers = $state<any[]>([]);
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let etaLabel = $state('');
  let posts = $state<any[]>([]);
  let score = $state(5);
  let saving = $state(false);
  let savedNote = $state('');
  let error = $state('');

  let previewBand = $derived(bandFromScore(score) as PriorityBand);
  let liveBand = $derived((mission?.priority_band as PriorityBand | undefined) || previewBand);

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
    if (typeof m.condition_score === 'number' && !saving) score = m.condition_score;
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

  async function saveCondition() {
    if (!mission || saving) return;
    saving = true;
    error = '';
    savedNote = '';
    try {
      const res = await apiFetch('/accounts/mission/condition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ score: Number(score) }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not update');
      savedNote = t('doctor.saved');
      await loadMission();
    } catch (e: any) {
      error = e?.message || 'Could not update';
    } finally {
      saving = false;
    }
  }

  onMount(() => {
    loadMission();
    loadPosts();
    const timer = setInterval(() => {
      loadMission();
      loadPosts();
    }, 2000);
    return () => clearInterval(timer);
  });
</script>

<svelte:head><title>{t('doctor.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col relative">
  <div class="flex-1 relative">
    <MapWidget
      id="doctor-map"
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
          <p class="nb-chip nb-red mb-2" style="color:#fff;">{t('doctor.standby')}</p>
          <h2 class="text-xl font-black mb-2 uppercase">{t('doctor.noAssignment')}</h2>
          <p class="text-xs text-[#4B4B4B] font-semibold">{t('doctor.alertHint')}</p>
        {:else}
          <p class="nb-chip mb-2" style="color:{liveBand === 'urgent' ? '#111' : '#fff'};background:{bandColor(liveBand)};">
            {mission.phase === 'drop' ? t('doctor.toDrop') : t('doctor.toPickup')}
          </p>
          <h2 class="text-lg font-black mb-1 uppercase">{mission.pickup_person}</h2>
          <p class="text-xs text-[#4B4B4B] font-bold mb-3">{t('navPage.eta')} {mission.eta_minutes ?? '—'} min · {mission.ambulance_id}</p>
          {#if mission.phase === 'drop'}
            <p class="text-xs text-black font-semibold mb-1">{t('doctor.onBoard')}</p>
            <p class="text-sm font-black mb-3">{mission.destination}</p>
          {/if}

          <p class="text-[10px] font-black uppercase tracking-widest mb-1">{t('doctor.condition')}</p>
          <p class="text-[11px] text-[#4B4B4B] font-semibold mb-2">{t('doctor.conditionHint')}</p>
          <div class="flex justify-between text-[10px] font-black uppercase mb-1">
            <span>{t('doctor.good')} · 1</span>
            <span>10 · {t('doctor.bad')}</span>
          </div>
          <input class="w-full mb-2" type="range" min="1" max="10" step="1" bind:value={score} />
          <div class="flex gap-1 mb-2">
            {#each Array.from({ length: 10 }, (_, i) => i + 1) as n}
              <button
                type="button"
                class="flex-1 text-[10px] font-black"
                style="border:2px solid #111;padding:4px 0;background:{score === n ? bandColor(bandFromScore(n)) : '#fff'};color:{score === n && n >= 8 ? '#fff' : '#111'};"
                onclick={() => { score = n; savedNote = ''; }}
              >{n}</button>
            {/each}
          </div>
          <p class="text-xs font-black uppercase mb-3" style="color:{bandColor(previewBand)};">
            {t('doctor.score', { score })} · {previewBand === 'critical' ? t('doctor.critical') : previewBand === 'urgent' ? t('doctor.urgent') : t('doctor.stable')}
          </p>
          <button class="btn btn-primary w-full py-3" disabled={saving} onclick={saveCondition}>
            {saving ? t('doctor.updating') : t('doctor.update')}
          </button>
          {#if savedNote}<p class="text-[11px] font-bold mt-2">{savedNote}</p>{/if}
          {#if error}<p class="text-[11px] font-bold mt-2" style="color:#FF2D2D;">{error}</p>{/if}
        {/if}
      </div>
    </div>
  </div>
</div>
