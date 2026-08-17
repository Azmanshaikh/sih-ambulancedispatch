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
    <div class="absolute top-5 left-5 space-y-3 z-10 pointer-events-none max-w-[calc(100%-2.5rem)]">
      <div class="glass p-5 w-80 max-w-full pointer-events-auto">
        <p class="nb-chip nb-red mb-2" style="color:#fff;">Target Destination</p>
        <h2 class="text-xl font-black text-black mb-4 uppercase">No Active Mission</h2>
        <div class="flex justify-between mb-1">
          <span class="text-xs text-[#4B4B4B] font-bold uppercase">ETA</span>
          <span class="text-2xl font-black text-black">—</span>
        </div>
        <div class="flex justify-between mb-4">
          <span class="text-xs text-[#4B4B4B] font-bold uppercase">Unit</span>
          <span class="text-sm font-black text-black">—</span>
        </div>
        <div class="w-full h-3 bg-white overflow-hidden" style="border:2px solid #111;">
          <div class="h-full bg-[#FF2D2D] transition-all duration-1000 w-0"></div>
        </div>
      </div>

      <div class="glass p-4 w-80 max-w-full flex items-center gap-3 pointer-events-auto">
        <div class="p-2 nb-blue" style="border:2px solid #111;">
          <span class="material-symbols-outlined text-white">psychology</span>
        </div>
        <div>
          <p class="text-[10px] font-black uppercase tracking-widest text-[#2E5BFF]">AI Routing</p>
          <p class="text-xs text-black leading-snug font-semibold">Dynamic corridor optimization active.</p>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="absolute right-5 top-1/2 -translate-y-1/2 z-10">
      <div class="glass p-1 flex flex-col gap-1">
        <button class="p-2.5 text-black hover:bg-[#FFE8D6]">
          <span class="material-symbols-outlined">add</span>
        </button>
        <button class="p-2.5 text-black hover:bg-[#FFE8D6]">
          <span class="material-symbols-outlined">remove</span>
        </button>
        <div class="h-[2px] bg-[#111] mx-1"></div>
        <button class="p-2.5 text-[#FF2D2D] hover:bg-[#FFE8D6]">
          <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">my_location</span>
        </button>
      </div>
    </div>

    <!-- Bottom bars -->
    <div class="absolute bottom-5 left-5 flex gap-3 z-10 flex-wrap">
      <div class="glass px-4 py-2.5 flex items-center gap-2">
        <span class="material-symbols-outlined text-[#22C55E] text-lg">traffic</span>
        <div>
          <p class="text-[9px] font-black text-[#4B4B4B] uppercase">Traffic</p>
          <p class="text-xs font-black text-black">OPTIMIZED</p>
        </div>
      </div>
      <div class="glass px-4 py-2.5 flex items-center gap-2">
        <span class="text-lg">🌡️</span>
        <div>
          <p class="text-[9px] font-black text-[#4B4B4B] uppercase">Weather</p>
          <p class="text-xs font-black text-black">CLEAR | 28°C</p>
        </div>
      </div>
    </div>
  </div>
</div>
