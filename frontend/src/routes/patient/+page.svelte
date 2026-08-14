<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { auth, apiFetch } from '$lib/auth.svelte';

  const BMSIT = { name: 'BMSIT College, Avalahalli, Yelahanka', lat: 13.1344, lng: 77.5693 };

  let vitals = $state({
    heart_rate: 72,
    spo2: 98,
    bp_sys: 118,
    bp_dia: 76,
    temperature_c: 36.8,
    resp_rate: 16,
  });
  let requesting = $state(false);
  let requestMsg = $state('');
  let markers = $state<any[]>([
    { position: [BMSIT.lat, BMSIT.lng] as [number, number], popup: `📍 ${BMSIT.name}`, type: 'incident' },
  ]);
  let route = $state<[number, number][]>([]);
  let etaLabel = $state('');

  async function loadVitals() {
    const res = await apiFetch('/accounts/vitals');
    if (!res.ok) return;
    const data = await res.json();
    if (data.vitals) vitals = { ...vitals, ...data.vitals };
  }

  async function emergencySos() {
    requesting = true;
    requestMsg = '';
    try {
      const res = await apiFetch('/tracking/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_lat: BMSIT.lat,
          incident_lng: BMSIT.lng,
          address: BMSIT.name,
          patient_name: auth.profile?.full_name || auth.profile?.email,
          patient_email: auth.profile?.email,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'SOS failed');
      requestMsg = `SOS sent · ${data.data?.ambulance_id} → ${data.data?.hospital_name} (${data.data?.eta_minutes} min)`;
      const payload = data.data;
      if (payload?.route?.length) route = payload.route;
      if (payload?.eta_minutes != null) etaLabel = `${payload.eta_minutes} min`;
      const hosp = payload?.hospital;
      markers = [
        { position: [BMSIT.lat, BMSIT.lng], popup: `📍 You · ${BMSIT.name}`, type: 'incident' },
        hosp?.lat ? { position: [hosp.lat, hosp.lng], popup: `🏥 ${hosp.name}`, type: 'hospital_selected' } : null,
      ].filter(Boolean);
    } catch (e: any) {
      requestMsg = e?.message || 'Could not send SOS';
    } finally {
      requesting = false;
    }
  }

  onMount(() => {
    loadVitals();
    const t = setInterval(loadVitals, 2000);
    return () => clearInterval(t);
  });
</script>

<svelte:head><title>JEEVAN — Patient</title></svelte:head>

<div class="h-full overflow-hidden p-4 grid grid-cols-1 lg:grid-cols-12 gap-4" style="background:#F5F5F5;">
  <div class="lg:col-span-4 flex flex-col gap-4 overflow-y-auto">
    <button
      class="btn btn-primary"
      style="width:100%;padding:22px;font-size:18px;letter-spacing:0.2em;"
      disabled={requesting}
      onclick={emergencySos}
    >
      {requesting ? 'SENDING SOS…' : 'EMERGENCY SOS'}
    </button>
    {#if requestMsg}<p class="text-xs text-slate-700">{requestMsg}</p>{/if}

    <section class="bg-white border-2 border-[#E0E0E0] p-5">
      <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-1">Vitals</h2>
      <p class="text-[10px] text-slate-500 uppercase mb-4">Mock sensor · random live values</p>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="text-3xl font-black">{vitals.heart_rate}<span class="text-xs text-slate-500 ml-1">bpm</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">Heart rate</div>
        </div>
        <div>
          <div class="text-3xl font-black">{vitals.spo2}<span class="text-xs text-slate-500 ml-1">%</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">SpO2</div>
        </div>
        <div>
          <div class="text-2xl font-black">{vitals.bp_sys}/{vitals.bp_dia}</div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">Blood pressure</div>
        </div>
        <div>
          <div class="text-2xl font-black">{vitals.temperature_c}<span class="text-xs text-slate-500 ml-1">°C</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">Temperature</div>
        </div>
        <div>
          <div class="text-2xl font-black">{vitals.resp_rate}<span class="text-xs text-slate-500 ml-1">/min</span></div>
          <div class="text-[10px] uppercase tracking-widest text-slate-500">Respiration</div>
        </div>
      </div>
    </section>
  </div>

  <div class="lg:col-span-8 relative min-h-[320px] border-2 border-[#E0E0E0] overflow-hidden">
    <MapWidget id="patient-map" {markers} {route} {etaLabel} center={[BMSIT.lat, BMSIT.lng]} />
  </div>
</div>
