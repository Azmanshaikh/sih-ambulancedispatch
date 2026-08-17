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

<div class="flex-col h-full overflow-y-auto no-sb">
  <div class="p-8 max-w-5xl mx-auto w-full">
    <div class="mb-7 flex justify-between items-end flex-wrap gap-3">
      <div>
        <h1 class="text-4xl font-black tracking-tight uppercase text-black">Medical Facilities</h1>
        <p class="text-[#4B4B4B] text-xs font-bold uppercase tracking-widest mt-1">Live ICU Capacity &amp; Specialization Telemetry</p>
      </div>
      <div class="nb-chip nb-green" style="color:#fff;">
        <span class="blink">●</span>
        AI Analysis Active
      </div>
    </div>

    <div class="space-y-5">
      {#if loading}
        <div class="nb-card p-4 text-sm text-black font-bold">Fetching hospitals…</div>
      {:else}
        {#each hospitals as h, i}
          <div class="nb-card p-5 flex items-center justify-between flex-wrap gap-3 {i === 0 ? 'nb-yellow' : ''}">
            <div>
              <h3 class="text-lg font-black text-black flex items-center gap-2 flex-wrap">
                🏥 {h.name}
                {#if i === 0}
                  <span class="nb-chip nb-red" style="color:#fff;">Top Pick</span>
                {/if}
              </h3>
              <p class="text-xs text-[#4B4B4B] mt-1 font-semibold">{h.specializations.join(', ')}</p>
              {#if h.lat != null && h.lng != null}
                <p class="text-[11px] text-[#4B4B4B] mt-2 font-mono-tech">{h.lat.toFixed(4)}, {h.lng.toFixed(4)}</p>
              {/if}
            </div>
            <div class="text-right">
              <div class="text-xl font-black text-black">{h.available_beds} <span class="text-xs text-[#4B4B4B]">/ {h.total_beds} Beds</span></div>
              <div class="text-[10px] text-[#4B4B4B] font-bold tracking-widest mt-1">📞 {h.phone}</div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>
