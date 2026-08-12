<script lang="ts">
  import MapWidget from '$lib/components/MapWidget.svelte';
</script>

<svelte:head><title>JEEVAN — Notifications</title></svelte:head>

<div class="flex-col h-full overflow-y-auto">
  <div class="p-5 grid grid-cols-12 gap-5 content-start">
    
    <!-- Left: Mini map + incoming -->
    <div class="col-span-12 lg:col-span-4 flex flex-col gap-4">
      <div class="relative rounded-xl overflow-hidden border border-slate-800 map-wrap" style="height: 220px;">
        <MapWidget id="notif-map" clazz="absolute inset-0" />
        <div class="absolute top-3 left-3 glass px-3 py-1.5 rounded-lg border border-slate-700/50 z-10">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 bg-red-500 rounded-full blink"></div>
            <span class="text-[10px] font-bold tracking-widest uppercase text-slate-200">STANDBY</span>
          </div>
        </div>
      </div>
      
      <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800/50">
        <div class="flex justify-between items-end mb-4">
          <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Incoming Assets</h3>
          <span class="text-2xl font-black text-slate-200">00</span>
        </div>
        <div class="space-y-3">
          <p class="text-xs text-slate-600 italic">No incoming emergency units.</p>
        </div>
      </div>
    </div>

    <!-- Middle: Vitals -->
    <div class="col-span-12 lg:col-span-5 flex flex-col gap-4">
      <div class="bg-slate-900 rounded-xl p-6 flex justify-between items-start border border-slate-800/50">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <span class="material-symbols-outlined text-red-500">emergency</span>
            <h2 class="text-2xl font-black text-white tracking-tight uppercase">AWAITING DISPATCH</h2>
          </div>
          <p class="text-slate-500 font-medium tracking-wide uppercase text-xs">System monitoring all sectors</p>
        </div>
        <div class="text-right">
          <p class="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Assigned Bay</p>
          <span class="text-2xl font-black text-red-500">TRAUMA 1</span>
        </div>
      </div>

      <div class="flex flex-col items-center justify-center py-10 gap-3 bg-slate-900/40 border border-slate-800/40 rounded-2xl">
        <span class="material-symbols-outlined text-4xl text-slate-700" style="font-variation-settings: 'FILL' 1;">monitor_heart</span>
        <p class="text-sm font-bold text-slate-600 uppercase tracking-widest">No Active Dispatch</p>
        <p class="text-xs text-slate-700">Vitals will appear when a patient is en route.</p>
      </div>
    </div>

    <!-- Right: Timeline -->
    <div class="col-span-12 lg:col-span-3 flex flex-col gap-4">
      <div class="bg-slate-900/40 rounded-xl p-5 border border-slate-800/30 flex flex-col items-center justify-center gap-2 py-8">
        <span class="material-symbols-outlined text-3xl text-slate-700">timeline</span>
        <p class="text-xs text-slate-600 font-bold uppercase tracking-widest">No Mission Yet</p>
      </div>
    </div>

  </div>
</div>
