<svelte:head><title>JEEVAN — AI Guide</title></svelte:head>

<div class="flex-col h-full overflow-y-auto">
  <div class="p-8 max-w-5xl mx-auto w-full">
    <div class="mb-7 flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-black tracking-tight uppercase flex items-center gap-3">
          <span class="material-symbols-outlined text-blue-500" style="font-variation-settings: 'FILL' 1;">psychology</span>
          JEEVAN AI GUIDE
        </h2>
        <p class="text-slate-500 text-xs font-semibold uppercase tracking-widest mt-1">Live Trauma Assessment Protocol</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div class="space-y-6">
        <div class="flex gap-4">
          <div class="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-900/50 flex items-center justify-center shrink-0">
            <span class="material-symbols-outlined text-blue-400">medical_services</span>
          </div>
          <div class="bg-slate-900/60 p-6 rounded-3xl rounded-tl-none border border-slate-800/50 flex-1">
            <h4 class="text-blue-400 font-bold uppercase tracking-widest text-xs mb-3">Priority Instruction #1</h4>
            <p class="text-xl font-bold text-white mb-4">Check for life-threatening bleeding immediately.</p>
            <div class="bg-slate-950/60 rounded-xl p-4 flex items-center gap-4 border border-slate-800">
              <span class="material-symbols-outlined text-red-500" style="font-variation-settings: 'FILL' 1;">emergency_share</span>
              <p class="text-sm text-slate-400 leading-relaxed italic">Assess airway, breathing, and circulation. Control major bleeding with direct pressure or tourniquet.</p>
            </div>
          </div>
        </div>

        <div class="ml-14 space-y-5 border-l-2 border-slate-900 pl-8 py-2">
          <div class="relative">
            <div class="absolute -left-[35px] top-1 w-3 h-3 rounded-full bg-blue-500 border-4 border-slate-950"></div>
            <h5 class="font-bold text-white mb-1">1. Check Airway Patency</h5>
            <p class="text-sm text-slate-400">Ensure patient is breathing. Remove any obstructions.</p>
          </div>
          <div class="relative opacity-60">
            <div class="absolute -left-[35px] top-1 w-3 h-3 rounded-full bg-slate-700 border-4 border-slate-950"></div>
            <h5 class="font-bold text-slate-400 mb-1">2. Secondary Trauma Scan</h5>
            <p class="text-sm text-slate-500">Search for occult injuries once primary bleed is managed.</p>
          </div>
          <div class="relative opacity-40">
            <div class="absolute -left-[35px] top-1 w-3 h-3 rounded-full bg-slate-700 border-4 border-slate-950"></div>
            <h5 class="font-bold text-slate-400 mb-1">3. Continuous Vitals Monitoring</h5>
            <p class="text-sm text-slate-500">Record pulse and respiratory rate every 2 minutes.</p>
          </div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="bg-gradient-to-br from-slate-900/60 to-slate-950 p-6 rounded-3xl border border-slate-800/50">
          <div class="flex justify-between items-center mb-5">
            <p class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Trauma Assessment Map</p>
            <span class="px-2 py-1 bg-red-950 text-red-500 text-[10px] font-black rounded uppercase">Live Feed</span>
          </div>
          <div class="flex gap-8 items-center">
            <div class="relative w-28 h-44 bg-slate-900/80 rounded-2xl border border-slate-800 flex items-center justify-center overflow-hidden">
              <span class="material-symbols-outlined text-slate-800" style="font-size: 4.5rem;">accessibility_new</span>
              <div class="absolute top-12 left-14 w-4 h-4 bg-red-500/30 rounded-full flex items-center justify-center">
                <div class="w-1.5 h-1.5 bg-red-500 rounded-full blink"></div>
              </div>
            </div>
            <div class="flex-1 space-y-4">
              <div>
                <div class="flex justify-between text-sm mb-1"><span class="text-slate-400">Airway</span><span class="text-white font-bold">95%</span></div>
                <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden"><div class="h-full bg-green-500" style="width: 95%;"></div></div>
              </div>
              <div>
                <div class="flex justify-between text-sm mb-1"><span class="text-slate-400">Circulation</span><span class="text-red-400 font-bold">40%</span></div>
                <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden"><div class="h-full bg-red-500" style="width: 40%;"></div></div>
              </div>
              <div>
                <div class="flex justify-between text-sm mb-1"><span class="text-slate-400">Neurological</span><span class="text-blue-400 font-bold">75%</span></div>
                <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden"><div class="h-full bg-blue-500" style="width: 75%;"></div></div>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <button class="bg-slate-900/80 hover:bg-slate-800 p-5 rounded-2xl flex flex-col items-center gap-2.5 border border-slate-800 transition-all group">
            <span class="material-symbols-outlined text-slate-500 group-hover:text-blue-400">history_edu</span>
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest text-center">Protocol Log</span>
          </button>
          <button class="bg-slate-900/80 hover:bg-slate-800 p-5 rounded-2xl flex flex-col items-center gap-2.5 border border-slate-800 transition-all group">
            <span class="material-symbols-outlined text-slate-500 group-hover:text-green-400">medical_information</span>
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest text-center">Patient Records</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
