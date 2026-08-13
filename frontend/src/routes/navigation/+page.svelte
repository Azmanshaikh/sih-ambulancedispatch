<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { apiFetch } from '$lib/auth.svelte';

  const BMSIT: [number, number] = [13.1344, 77.5693];
  let markers = $state<any[]>([
    { position: BMSIT, popup: '📍 BMSIT College, Yelahanka', type: 'incident' },
  ]);

  onMount(async () => {
    try {
      const res = await apiFetch('/tracking/fleet');
      const data = await res.json();
      const fleet = (data.ambulances || []).map((a: any) => ({
        position: [a.lat, a.lng],
        popup: `🚑 ${a.id} · ${a.label}`,
        type: 'ambulance',
      }));
      const hospitals = (data.hospitals || []).map((h: any) => ({
        position: [h.lat, h.lng],
        popup: `🏥 ${h.name}`,
        type: 'hospital',
      }));
      markers = [
        { position: BMSIT, popup: '📍 BMSIT College, Yelahanka', type: 'incident' },
        ...hospitals,
        ...fleet,
      ];
    } catch (err) {
      console.error(err);
    }
  });
</script>

<svelte:head><title>JEEVAN — Navigation</title></svelte:head>

<div class="h-full flex flex-col">
  <div class="flex-1 relative map-wrap rounded-none">
    <MapWidget id="nav-map" clazz="absolute inset-0" {markers} center={BMSIT} />

    <!-- HUD overlay -->
    <div class="absolute top-5 left-5 space-y-3 z-10 pointer-events-none">
      <div class="glass p-5 rounded-xl border border-slate-800/60 shadow-2xl w-80 pointer-events-auto">
        <p class="text-[10px] font-bold uppercase tracking-widest text-red-500 mb-0.5">Target Destination</p>
        <h2 class="text-xl font-bold text-white mb-4">No Active Mission</h2>
        <div class="flex justify-between mb-1">
          <span class="text-xs text-slate-400">ETA</span>
          <span class="text-2xl font-black text-white">—</span>
        </div>
        <div class="flex justify-between mb-4">
          <span class="text-xs text-slate-400">Unit</span>
          <span class="text-sm font-bold text-slate-200">—</span>
        </div>
        <div class="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full bg-red-600 transition-all duration-1000 w-0 shadow-[0_0_8px_rgba(220,38,38,0.6)]"></div>
        </div>
      </div>

      <div class="glass p-4 rounded-xl border border-slate-800/50 shadow-xl w-80 flex items-center gap-3 pointer-events-auto">
        <div class="p-2 bg-blue-600/20 rounded-lg">
          <span class="material-symbols-outlined text-blue-400">psychology</span>
        </div>
        <div>
          <p class="text-[10px] font-bold uppercase tracking-widest text-blue-400">AI Routing</p>
          <p class="text-xs text-slate-300 leading-snug">Dynamic corridor optimization active.</p>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="absolute right-5 top-1/2 -translate-y-1/2 z-10">
      <div class="glass rounded-xl border border-slate-800/60 p-1 flex flex-col gap-1">
        <button class="p-2.5 text-slate-300 hover:bg-slate-700/50 rounded-lg">
          <span class="material-symbols-outlined">add</span>
        </button>
        <button class="p-2.5 text-slate-300 hover:bg-slate-700/50 rounded-lg">
          <span class="material-symbols-outlined">remove</span>
        </button>
        <div class="h-px bg-slate-800 mx-2"></div>
        <button class="p-2.5 text-yellow-500 hover:bg-slate-700/50 rounded-lg">
          <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">my_location</span>
        </button>
      </div>
    </div>

    <!-- Bottom bars -->
    <div class="absolute bottom-5 left-5 flex gap-3 z-10">
      <div class="glass px-4 py-2.5 rounded-xl border border-slate-800/50 flex items-center gap-2">
        <span class="material-symbols-outlined text-green-500 text-lg">traffic</span>
        <div>
          <p class="text-[9px] font-bold text-slate-500 uppercase">Traffic</p>
          <p class="text-xs font-bold">OPTIMIZED</p>
        </div>
      </div>
      <div class="glass px-4 py-2.5 rounded-xl border border-slate-800/50 flex items-center gap-2">
        <span class="text-lg">🌡️</span>
        <div>
          <p class="text-[9px] font-bold text-slate-500 uppercase">Weather</p>
          <p class="text-xs font-bold">CLEAR | 28°C</p>
        </div>
      </div>
    </div>
  </div>
</div>
