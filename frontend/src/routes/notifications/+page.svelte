<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';

  let alerts = $state<any[]>([]);
  let monitor = $state<any>(null);
  let markers = $state<any[]>([]);
  let route = $state<[number, number][]>([]);

  function flagList(rec: any) {
    if (!rec) return 'None noted';
    const flags = [];
    if (rec.cardiac) flags.push('Cardiac');
    if (rec.diabetes) flags.push('Diabetes');
    if (rec.epilepsy) flags.push('Epilepsy');
    if (rec.pregnant) flags.push('Pregnant');
    if (rec.notes) flags.push(rec.notes);
    return flags.length ? flags.join(', ') : 'None noted';
  }

  async function load() {
    const [aRes, mRes] = await Promise.all([apiFetch('/accounts/alerts'), apiFetch('/accounts/monitor')]);
    if (aRes.ok) {
      const data = await aRes.json();
      alerts = data.alerts || [];
    }
    if (mRes.ok) {
      monitor = await mRes.json();
      const p = monitor.patient || {};
      const d = monitor.driver || {};
      const h = monitor.mission?.hospital || {};
      markers = [
        p.lat ? { position: [p.lat, p.lng], popup: `Patient · ${p.name || ''}`, type: 'incident' } : null,
        d.lat ? { position: [d.lat, d.lng], popup: `Driver · ${d.id}`, type: 'ambulance' } : null,
        h.lat ? { position: [h.lat, h.lng], popup: `Hospital · ${h.name}`, type: 'hospital_selected' } : null,
      ].filter(Boolean);
      route = monitor.mission?.drop_route || monitor.mission?.route || [];
    }
  }

  async function ack(id: string) {
    await apiFetch(`/accounts/alerts/${id}/ack`, { method: 'POST' });
    await load();
  }

  onMount(() => {
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  });

  let unread = $derived(alerts.filter((a) => !a.read));
  let latest = $derived(unread[0] || alerts[0]);
  let history = $derived(monitor?.patient?.history || []);
</script>

<svelte:head><title>JEEVAN — Notifications</title></svelte:head>

<div class="flex-col h-full overflow-y-auto">
  <div class="p-5 grid grid-cols-12 gap-5 content-start">

    <div class="col-span-12 lg:col-span-4 flex flex-col gap-4">
      <div class="relative rounded-xl overflow-hidden border border-slate-800 map-wrap" style="height: 220px;">
        <MapWidget id="notif-map" clazz="absolute inset-0" {markers} {route} />
        <div class="absolute top-3 left-3 glass px-3 py-1.5 rounded-lg border border-slate-700/50 z-10">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 bg-red-500 rounded-full blink"></div>
            <span class="text-[10px] font-bold tracking-widest uppercase text-slate-200">{unread.length ? 'ALERT' : 'STANDBY'}</span>
          </div>
        </div>
      </div>

      <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800/50">
        <div class="flex justify-between items-end mb-4">
          <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Staff alerts</h3>
          <span class="text-2xl font-black text-slate-200">{String(unread.length).padStart(2, '0')}</span>
        </div>
        <div class="space-y-3 max-h-64 overflow-y-auto">
          {#if alerts.length === 0}
            <p class="text-xs text-slate-600 italic">No incoming emergency units.</p>
          {:else}
            {#each alerts as a}
              <div class="border border-slate-700 p-3 {a.read ? 'opacity-60' : ''}">
                <p class="text-[10px] font-black uppercase tracking-widest text-red-400">{a.title}</p>
                <p class="text-xs text-slate-200 mt-1">{a.body}</p>
                {#if !a.read}
                  <button class="btn btn-primary mt-2 text-[10px]" onclick={() => ack(a.id)}>Acknowledge</button>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>

    <div class="col-span-12 lg:col-span-5 flex flex-col gap-4">
      <div class="bg-slate-900 rounded-xl p-6 border border-slate-800/50">
        {#if latest}
          <div class="flex items-center gap-3 mb-1">
            <span class="material-symbols-outlined text-red-500">emergency</span>
            <h2 class="text-xl font-black text-white tracking-tight uppercase">Patient en route</h2>
          </div>
          <p class="text-slate-300 text-sm mt-2">
            {latest.patient_name || monitor?.patient?.name || 'Patient'}
            is going to
            <strong>{latest.hospital_name || monitor?.mission?.hospital_name || 'hospital'}</strong>
          </p>
        {:else}
          <h2 class="text-2xl font-black text-white tracking-tight uppercase">Awaiting dispatch</h2>
          <p class="text-slate-500 font-medium tracking-wide uppercase text-xs mt-1">Alerts appear when a patient requests an ambulance</p>
        {/if}
      </div>

      <div class="bg-slate-900/40 border border-slate-800/40 rounded-2xl p-5">
        <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3">Patient details</h3>
        {#if monitor?.patient?.name || monitor?.patient?.email}
          <p class="text-lg font-bold text-white">{monitor.patient.name || '—'}</p>
          <p class="text-xs text-slate-400">{monitor.patient.email || 'no email'}</p>
          <p class="text-xs text-slate-300 mt-3">HR {monitor.patient.vitals?.heart_rate ?? '—'} bpm · SpO2 {monitor.patient.vitals?.spo2 ?? '—'}%</p>
          <p class="text-xs text-slate-400 mt-1">Current: {flagList(monitor.patient.record)}</p>
        {:else}
          <p class="text-sm text-slate-600">No active patient.</p>
        {/if}
      </div>
    </div>

    <div class="col-span-12 lg:col-span-3 flex flex-col gap-4">
      <div class="bg-slate-900/40 rounded-xl p-5 border border-slate-800/30">
        <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3">Past records</h3>
        {#if history.length === 0}
          <p class="text-xs text-slate-600">No prior records.</p>
        {:else}
          <div class="space-y-2 max-h-80 overflow-y-auto">
            {#each history.slice().reverse() as h}
              <div class="text-[11px] text-slate-300 border border-slate-800 p-2">
                <p class="text-[9px] text-slate-500">{h.at?.slice(0, 19)?.replace('T', ' ')}</p>
                <p>{flagList(h)}</p>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

  </div>
</div>
