<script lang="ts">
  import { goto } from '$app/navigation';

  let description = $state('');
  let narrative = $state('');
  let age = $state('adult');
  let isRaining = $state('false');
  let reportFile = $state<File | null>(null);
  let analysisResult = $state('');
  let isAnalyzing = $state(false);

  async function handleAnalyzeReport() {
    if (!description && !reportFile) {
      alert('Please provide a description or upload a report.');
      return;
    }
    isAnalyzing = true;
    analysisResult = '';
    const formData = new FormData();
    if (description) formData.append('text', description);
    if (reportFile) formData.append('image', reportFile);
    try {
      const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${backendUrl}/ai/analyze-report`, { method: 'POST', body: formData });
      const data = await res.json();
      analysisResult = data.status === 'success' ? data.analysis : `Error: ${data.detail || data.message}`;
    } catch (err) {
      console.error(err);
      analysisResult = 'Failed to connect to the analysis service.';
    } finally {
      isAnalyzing = false;
    }
  }
</script>

<svelte:head><title>JEEVAN — New Request</title></svelte:head>

<div class="flex-col h-full overflow-y-auto">
  <div class="p-8 max-w-5xl mx-auto w-full">
    <div class="mb-8">
      <h1 class="text-4xl font-black tracking-tight uppercase text-white">New Dispatch Request</h1>
      <p class="text-slate-500 text-xs font-semibold uppercase tracking-widest mt-1">AI-Powered Triage &amp; Fleet Assignment</p>
      <div class="mt-3 inline-flex items-center gap-2 bg-yellow-900/20 border border-yellow-700/40 text-yellow-400 text-xs font-bold px-3 py-1.5 rounded-lg">
        🛰️ <span>Detecting your location…</span>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <!-- LEFT: Incident Details + AI -->
      <div class="space-y-4">
        <h3 class="text-sm font-black uppercase tracking-widest text-blue-500">Incident Details</h3>
        <div class="space-y-3">
          <textarea
            class="w-full h-32 bg-slate-900 shadow-inner rounded-xl p-4 text-sm text-slate-300 border border-slate-800 focus:border-blue-500 outline-none transition-all placeholder-slate-600"
            placeholder="Describe the emergency in detail (e.g., 'Severe bleeding from left foot after fall')"
            bind:value={description}
          ></textarea>
        </div>

        <div class="space-y-3 pt-2">
          <h3 class="text-sm font-black uppercase tracking-widest text-red-500">Quick Triage &amp; AI Analysis</h3>
          <div class="bg-slate-900/60 p-4 rounded-xl border border-slate-800/50 space-y-3">
            <label class="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Upload Medical Report (Image)</label>
            <input
              type="file"
              accept="image/*"
              onchange={(e) => reportFile = (e.target as HTMLInputElement).files?.[0] ?? null}
              class="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-600/20 file:text-blue-400 hover:file:bg-blue-600/30 cursor-pointer"
            />
            <button
              onclick={handleAnalyzeReport}
              disabled={isAnalyzing}
              class="w-full py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
            >
              {isAnalyzing ? 'Analyzing with NVIDIA AI...' : 'Analyze Report & Description'}
            </button>
          </div>
          {#if analysisResult}
            <div class="bg-slate-900 shadow-inner rounded-xl p-4 text-sm text-slate-200 border border-blue-500/50 mt-4 max-h-60 overflow-y-auto whitespace-pre-wrap">
              <h4 class="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-2">AI Assessment Result</h4>
              {analysisResult}
            </div>
          {/if}
        </div>
      </div>

      <!-- RIGHT: Context -->
      <div class="space-y-5">
        <h3 class="text-sm font-black uppercase tracking-widest text-blue-400">Incident Context</h3>
        <div class="bg-slate-900/60 p-6 rounded-2xl border border-slate-800/50 space-y-4">
          <label class="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] block">Scene Narrative</label>
          <textarea
            class="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500 min-h-[100px] text-sm resize-none"
            placeholder="Describe the situation…"
            bind:value={narrative}
          ></textarea>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="age-select" class="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Age Group</label>
              <select id="age-select" bind:value={age} class="w-full bg-slate-900 border border-slate-800 rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500">
                <option value="infant">Infant (0-1)</option>
                <option value="child">Child (2-12)</option>
                <option value="teen">Teen (13-17)</option>
                <option value="adult">Adult (18-60)</option>
                <option value="elderly">Elderly (60+)</option>
              </select>
            </div>
            <div>
              <label for="weather-select" class="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Weather</label>
              <select id="weather-select" bind:value={isRaining} class="w-full bg-slate-900 border border-slate-800 rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-red-500">
                <option value="false">Clear</option>
                <option value="true">Raining</option>
              </select>
            </div>
          </div>

          <div class="space-y-2 pt-2 border-t border-slate-800">
            <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest block">Medical History</p>
            <div class="grid grid-cols-2 gap-2">
              <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" class="accent-red-500" /> Cardiac History</label>
              <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" class="accent-red-500" /> Diabetes</label>
              <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" class="accent-red-500" /> Epilepsy</label>
              <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" class="accent-red-500" /> Pregnant</label>
            </div>
          </div>
        </div>

        <div class="flex gap-4 pt-2">
          <button onclick={() => goto('/')} class="flex-1 border border-slate-800 py-4 rounded-xl text-xs font-bold uppercase tracking-widest text-slate-500 hover:text-white hover:bg-slate-900 transition-all">
            Cancel
          </button>
          <button onclick={() => goto('/')} class="flex-[2] bg-red-600 hover:bg-red-700 text-white py-4 rounded-xl text-xs font-bold uppercase tracking-widest transition-all shadow-xl shadow-red-900/30">
            Initiate Dispatch
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
