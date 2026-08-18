<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';

  let alerts = $state<any[]>([]);
  let monitor = $state<any>(null);
  let markers = $state<any[]>([]);
  let cases = $state<any[]>([]);
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let extraRoutes = $state<any[]>([]);
  let reports = $state<any[]>([]);
  let corridor = $state<any>(null);

  function flagList(rec: any) {
    if (!rec) return t('notif.noneFlags');
    const flags = [];
    if (rec.cardiac) flags.push(t('patient.cardiac'));
    if (rec.diabetes) flags.push(t('patient.diabetes'));
    if (rec.epilepsy) flags.push(t('patient.epilepsy'));
    if (rec.pregnant) flags.push(t('patient.pregnant'));
    if (rec.notes) flags.push(rec.notes);
    return flags.length ? flags.join(', ') : t('notif.noneFlags');
  }

  async function load() {
    const [aRes, mRes, cRes] = await Promise.all([
      apiFetch('/accounts/alerts'),
      apiFetch('/accounts/monitor'),
      apiFetch('/tracking/corridor'),
    ]);
    if (aRes.ok) {
      const data = await aRes.json();
      alerts = data.alerts || [];
    }
    if (cRes.ok) {
      corridor = await cRes.json();
    }
    if (mRes.ok) {
      monitor = await mRes.json();
      cases = monitor.cases || [];
      const live = monitor.mission && monitor.mission.phase !== 'complete' ? monitor.mission : null;
      const p = live ? monitor.patient || {} : {};
      const d = live ? monitor.driver || {} : {};
      const h = live?.hospital || {};
      pickupRoute = live?.pickup_route || [];
      dropRoute = live?.drop_route || live?.route || [];
      reports = monitor.reports || [];
      const posts = (corridor?.posts || []).map((post: any) => postToMarker(post, true));
      markers = [
        p.lat ? { position: [p.lat, p.lng], popup: `Patient · ${p.name || ''}`, type: 'incident' } : null,
        d.lat
          ? {
              position: [d.lat, d.lng],
              popup: `Driver · ${d.id}`,
              type: 'ambulance',
              id: live?.ambulance_id,
              ambulanceId: live?.ambulance_id,
              hasMission: true,
            }
          : null,
        h.lat ? { position: [h.lat, h.lng], popup: `Hospital · ${h.name}`, type: 'hospital_selected' } : null,
        ...posts,
      ].filter(Boolean);
      const latestId = monitor.mission?.id;
      extraRoutes = (corridor?.extra_routes || []).filter((r: any) => {
        if (r.kind === 'overlap') return true;
        if (latestId && String(r.id || '').startsWith(String(latestId))) return false;
        return true;
      });
    }
  }

  async function ack(id: string) {
    await apiFetch(`/accounts/alerts/${id}/ack`, { method: 'POST' });
    await load();
  }

  async function endTrip() {
    await apiFetch('/accounts/mission/phase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'complete' }),
    });
    await load();
  }

  onMount(() => {
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  });

  let unread = $derived(alerts.filter((a) => !a.read));
  let latest = $derived(unread[0] || alerts[0]);
  let history = $derived(
    monitor?.patient?.history?.length
      ? monitor.patient.history
      : (cases[0]?.medical?.history || [])
  );
</script>

<svelte:head><title>{t('notif.pageTitle')}</title></svelte:head>

<div class="flex-col h-full overflow-y-auto no-sb">
  <div class="p-5 grid grid-cols-12 gap-5 content-start">

    <div class="col-span-12 lg:col-span-4 flex flex-col gap-4">
      <div class="relative overflow-hidden nb-card-lg map-wrap" style="height: 220px;border:4px solid #111;">
        <MapWidget id="notif-map" clazz="absolute inset-0" {markers} {pickupRoute} {dropRoute} {extraRoutes} officerCallEnabled showLegend />
        <div class="absolute top-3 left-3 glass px-3 py-1.5 z-10">
          <div class="flex items-center gap-2">
            <div class="w-2.5 h-2.5 bg-[#FF2D2D] blink" style="border:2px solid #111;"></div>
            <span class="text-[10px] font-black tracking-widest uppercase text-black">{unread.length ? t('notif.alert') : t('notif.standby')}</span>
          </div>
        </div>
      </div>

      <div class="nb-card p-5">
        <div class="flex justify-between items-end mb-4">
          <h3 class="text-xs font-black uppercase tracking-[0.2em] text-[#4B4B4B]">{t('notif.staffAlerts')}</h3>
          <span class="text-2xl font-black text-black">{String(unread.length).padStart(2, '0')}</span>
        </div>
        <div class="space-y-3 max-h-64 overflow-y-auto no-sb">
          {#if alerts.length === 0}
            <p class="text-xs text-[#4B4B4B] font-semibold">{t('notif.none')}</p>
          {:else}
            {#each alerts as a}
              <div class="p-3 bg-[#FFF3E6] {a.read ? 'opacity-60' : ''}" style="border:3px solid #111;">
                <p class="nb-chip nb-red" style="color:#fff;">{a.title}</p>
                <p class="text-xs text-black mt-2 font-semibold">{a.body}</p>
                {#if !a.read}
                  <button class="btn btn-primary mt-2 text-[10px]" style="padding:6px 12px;" onclick={() => ack(a.id)}>{t('notif.acknowledge')}</button>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      </div>

      <div class="nb-card p-5">
        <div class="flex justify-between items-end mb-4">
          <h3 class="text-xs font-black uppercase tracking-[0.2em] text-[#4B4B4B]">{t('notif.sms')}</h3>
          <span class="text-2xl font-black text-black">{String((corridor?.sms || []).length).padStart(2, '0')}</span>
        </div>
        <div class="space-y-3 max-h-64 overflow-y-auto no-sb">
          {#if !(corridor?.sms || []).length}
            <p class="text-xs text-[#4B4B4B] font-semibold">{t('notif.smsHint')}</p>
          {:else}
            {#each corridor.sms as s}
              <div class="p-3 bg-[#FFF3E6]" style="border:3px solid #111;">
                <p class="nb-chip {s.status === 'demo' ? 'nb-yellow' : 'nb-green'}">{s.status} · {s.provider}</p>
                <p class="text-xs text-black mt-2 font-black">{s.post_name}</p>
                <p class="text-[10px] text-[#4B4B4B] font-semibold">{s.phone}</p>
                <p class="text-xs text-black mt-2 font-semibold">{s.body}</p>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>

    <div class="col-span-12 lg:col-span-5 flex flex-col gap-4">
      <div class="nb-card nb-red p-6" style="color:#fff;">
        {#if latest}
          <div class="flex items-center gap-3 mb-1">
            <span class="material-symbols-outlined">emergency</span>
            <h2 class="text-xl font-black tracking-tight uppercase">{t('notif.enRoute')}</h2>
          </div>
          <p class="text-white/90 text-sm mt-2 font-semibold">
            {t('notif.goingTo', {
              name: latest.patient_name || monitor?.patient?.name || t('dash.patient'),
              hospital: latest.hospital_name || monitor?.mission?.hospital_name || t('patient.hospital'),
            })}
          </p>
          {#if monitor?.mission?.conflict?.reason}
            <p class="text-[11px] text-white mt-3 font-black" style="background:#111;padding:8px;">{monitor.mission.conflict.reason}</p>
          {/if}
          {#if monitor?.mission && monitor.mission.phase !== 'complete'}
            <button class="btn btn-secondary mt-4 w-full" onclick={endTrip}>{t('notif.endTrip')}</button>
            <p class="text-[10px] text-white/80 mt-2 uppercase tracking-widest font-bold">{t('notif.autoComplete')}</p>
          {/if}
        {:else}
          <h2 class="text-2xl font-black tracking-tight uppercase">{t('notif.awaiting')}</h2>
          <p class="text-white/80 font-bold tracking-wide uppercase text-xs mt-1">{t('notif.awaitingHint')}</p>
        {/if}
      </div>

      <div class="nb-card p-5">
        <h3 class="nb-chip nb-blue mb-3" style="color:#fff;">{t('notif.patientDetails')}</h3>
        {#if monitor?.patient?.name || monitor?.patient?.email}
          <p class="text-lg font-black text-black">{monitor.patient.name || '—'}</p>
          <p class="text-xs text-[#4B4B4B] font-semibold">{monitor.patient.email || t('notif.noEmail')}</p>
          <p class="text-xs text-black mt-3 font-semibold">HR {monitor.patient.vitals?.heart_rate ?? '—'} bpm · SpO2 {monitor.patient.vitals?.spo2 ?? '—'}%</p>
          <p class="text-xs text-[#4B4B4B] mt-1 font-semibold">{t('notif.current', { flags: flagList(monitor.patient.record) })}</p>
          {#if monitor.health_profile}
            <p class="text-xs text-black mt-3 font-semibold">{t('patient.allergies')}: {monitor.health_profile.allergies || t('notif.noneNoted')}</p>
            <p class="text-xs text-black font-semibold">{t('patient.medicines')}: {monitor.health_profile.medicines || t('notif.noneNoted')}</p>
          {/if}
        {:else}
          <p class="text-sm text-[#4B4B4B] font-semibold">{t('notif.noPatient')}</p>
        {/if}
      </div>
    </div>

    <div class="col-span-12 lg:col-span-3 flex flex-col gap-4">
      <div class="nb-card p-5">
        <h3 class="nb-chip nb-red mb-3" style="color:#fff;">{t('notif.tripReports')}</h3>
        {#if reports.length === 0}
          <p class="text-xs text-[#4B4B4B] mb-4 font-semibold">{t('notif.reportsHint')}</p>
        {:else}
          <div class="space-y-3 max-h-64 overflow-y-auto no-sb mb-4">
            {#each reports as r}
              <div class="text-[11px] text-black p-2 bg-[#FFF3E6]" style="border:3px solid #111;">
                <p class="font-black">{r.patient_name || 'Patient'} → {r.hospital_name}</p>
                <pre class="whitespace-pre-wrap font-sans mt-1 text-[#4B4B4B]">{r.body}</pre>
              </div>
            {/each}
          </div>
        {/if}
        <h3 class="nb-chip nb-yellow mb-3">{t('notif.stored')}</h3>
        {#if cases.length === 0}
          <p class="text-xs text-[#4B4B4B] mb-4 font-semibold">{t('notif.noCases')}</p>
        {:else}
          <div class="space-y-2 max-h-40 overflow-y-auto no-sb mb-4">
            {#each cases as c}
              <div class="text-[11px] text-black p-2 bg-[#FFF3E6]" style="border:3px solid #111;">
                <p class="font-black">{c.patient_name || c.patient_email || 'Patient'}</p>
                <p class="text-[#4B4B4B]">{c.patient_email}</p>
                <p>→ {c.hospital_name} · {c.ambulance_id}</p>
              </div>
            {/each}
          </div>
        {/if}
        <h3 class="nb-chip mb-3">{t('notif.past')}</h3>
        {#if history.length === 0}
          <p class="text-xs text-[#4B4B4B] font-semibold">{t('notif.noRecords')}</p>
        {:else}
          <div class="space-y-2 max-h-80 overflow-y-auto no-sb">
            {#each history.slice().reverse() as h}
              <div class="text-[11px] text-black p-2 bg-[#FFF3E6]" style="border:3px solid #111;">
                <p class="text-[9px] text-[#4B4B4B]">{h.at?.slice(0, 19)?.replace('T', ' ')}</p>
                <p>{flagList(h)}</p>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

  </div>
</div>
