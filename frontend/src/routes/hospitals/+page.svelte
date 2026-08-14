<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';

  interface Hospital {
    id: number;
    name: string;
    available_beds: number;
    total_beds: number;
    specializations: string[];
    phone: string;
    lat?: number;
    lng?: number;
  }

  let hospitals = $state<Hospital[]>([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const response = await apiFetch('/hospitals');
      if (!response.ok) throw new Error('Unable to load hospitals');
      hospitals = await response.json();
    } catch (error) {
      console.error(error);
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>JEEVAN — Hospitals</title></svelte:head>

<div class="flex-col h-full overflow-y-auto">
  <div class="p-8 max-w-5xl mx-auto w-full">
    <div class="mb-7 flex justify-between items-end">
      <div>
        <h1 class="text-4xl font-black tracking-tight uppercase text-white">Medical Facilities</h1>
        <p class="text-slate-500 text-xs font-semibold uppercase tracking-widest mt-1">Live ICU Capacity &amp; Specialization Telemetry</p>
      </div>
      <div class="flex items-center gap-2 bg-green-500/10 px-3 py-1.5 rounded-xl border border-green-500/20">
        <span class="text-green-500 text-sm blink">●</span>
        <span class="text-xs font-bold text-green-500 uppercase tracking-wider">AI Analysis Active</span>
      </div>
    </div>

    <div class="space-y-5">
      {#if loading}
        <div class="text-sm text-slate-600 italic">Fetching hospitals…</div>
      {:else}
        {#each hospitals as h, i}
          <div class="bg-slate-900/50 p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
            <div>
              <h3 class="text-lg font-bold text-white flex items-center gap-2">
                🏥 {h.name}
                {#if i === 0}
                  <span class="text-[10px] bg-red-900/50 text-red-400 px-2 py-0.5 rounded uppercase tracking-widest border border-red-800/50">Top Pick</span>
                {/if}
              </h3>
              <p class="text-xs text-slate-400 mt-1">{h.specializations.join(', ')}</p>
              {#if h.lat != null && h.lng != null}
                <p class="text-[11px] text-slate-500 mt-2 font-mono">{h.lat.toFixed(4)}, {h.lng.toFixed(4)}</p>
              {/if}
            </div>
            <div class="text-right">
              <div class="text-xl font-black text-green-400">{h.available_beds} <span class="text-xs text-slate-500">/ {h.total_beds} Beds</span></div>
              <div class="text-[10px] text-slate-500 font-bold tracking-widest mt-1">📞 {h.phone}</div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>
