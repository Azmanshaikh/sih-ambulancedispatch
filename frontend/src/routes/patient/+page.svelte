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
  let saveMsg = $state('');
  let markers = $state<any[]>([
    { position: [BMSIT.lat, BMSIT.lng] as [number, number], popup: `📍 ${BMSIT.name}`, type: 'incident' },
  ]);
  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let etaLabel = $state('');
  let reports = $state<any[]>([]);
  let health = $state({
    allergies: '',
    medicines: '',
    conditions: '',
    cardiac: false,
    diabetes: false,
    epilepsy: false,
    pregnant: false,
    visits: [{ hospital: '', when: '', reason: '' }],
    doctors: [{ name: '', specialty: '', notes: '' }],
    notes: '',
  });

  async function loadVitals() {
    const res = await apiFetch('/accounts/vitals');
    if (!res.ok) return;
    const data = await res.json();
    if (data.vitals) vitals = { ...vitals, ...data.vitals };
  }

  async function loadHealth() {
    const res = await apiFetch('/accounts/health-profile');
    if (!res.ok) return;
    const data = await res.json();
    const p = data.profile || {};
    health = {
      allergies: p.allergies || '',
      medicines: p.medicines || '',
      conditions: p.conditions || '',
      cardiac: !!p.cardiac,
      diabetes: !!p.diabetes,
      epilepsy: !!p.epilepsy,
      pregnant: !!p.pregnant,
      visits: p.visits?.length ? p.visits : [{ hospital: '', when: '', reason: '' }],
      doctors: p.doctors?.length ? p.doctors : [{ name: '', specialty: '', notes: '' }],
      notes: p.notes || '',
    };
  }

  async function loadReports() {
    const res = await apiFetch('/accounts/reports');
    if (!res.ok) return;
    const data = await res.json();
    reports = data.reports || [];
  }

  async function saveHealth() {
    saveMsg = '';
    const res = await apiFetch('/accounts/health-profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(health),
    });
    saveMsg = res.ok ? 'Saved for hospital handover' : 'Could not save';
  }

  function applyLive(payload: any) {
    if (!payload) return;
    pickupRoute = payload.pickup_route || [];
    dropRoute = payload.drop_route || payload.route || [];
    if (payload.eta_minutes != null) etaLabel = `${payload.eta_minutes} min`;
    const pickup = payload.pickup || BMSIT;
    const hosp = payload.hospital;
    const amb = payload.driver_location || payload.ambulance;
    markers = [
      { position: [pickup.lat || BMSIT.lat, pickup.lng || BMSIT.lng], popup: `📍 You · ${pickup.name || BMSIT.name}`, type: 'incident' },
      amb?.lat ? { position: [amb.lat, amb.lng], popup: `🚑 ${payload.ambulance_id}`, type: 'ambulance' } : null,
      hosp?.lat ? { position: [hosp.lat, hosp.lng], popup: `🏥 ${hosp.name}`, type: 'hospital_selected' } : null,
    ].filter(Boolean);
  }

  async function loadMission() {
    const res = await apiFetch('/accounts/mission');
    if (!res.ok) return;
    const data = await res.json();
    if (data.mission) applyLive(data.mission);
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
      requestMsg = `SOS sent · nearest ${data.data?.ambulance_id} → ${data.data?.hospital_name} (${data.data?.eta_minutes} min)`;
      applyLive(data.data);
    } catch (e: any) {
      requestMsg = e?.message || 'Could not send SOS';
    } finally {
      requesting = false;
    }
  }

  onMount(() => {
    loadVitals();
    loadHealth();
    loadReports();
    loadMission();
    const t = setInterval(() => {
      loadVitals();
      loadReports();
      loadMission();
    }, 2500);
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

    <section class="bg-white border-2 border-[#E0E0E0] p-5">
      <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-1">Health records</h2>
      <p class="text-[10px] text-slate-500 uppercase mb-3">Fill this before an emergency so hospitals have allergies, visits, and doctors</p>
      <label class="text-[10px] uppercase tracking-widest text-slate-500">Allergies</label>
      <textarea class="w-full border-2 border-[#E0E0E0] p-2 text-sm mb-2" rows="2" bind:value={health.allergies}></textarea>
      <label class="text-[10px] uppercase tracking-widest text-slate-500">Current medicines</label>
      <textarea class="w-full border-2 border-[#E0E0E0] p-2 text-sm mb-2" rows="2" bind:value={health.medicines}></textarea>
      <label class="text-[10px] uppercase tracking-widest text-slate-500">Other conditions</label>
      <textarea class="w-full border-2 border-[#E0E0E0] p-2 text-sm mb-2" rows="2" bind:value={health.conditions}></textarea>
      <div class="grid grid-cols-2 gap-2 text-xs font-semibold mb-3">
        <label><input type="checkbox" bind:checked={health.cardiac} /> Cardiac</label>
        <label><input type="checkbox" bind:checked={health.diabetes} /> Diabetes</label>
        <label><input type="checkbox" bind:checked={health.epilepsy} /> Epilepsy</label>
        <label><input type="checkbox" bind:checked={health.pregnant} /> Pregnant</label>
      </div>
      <p class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Previous hospital visits</p>
      {#each health.visits as v, i}
        <div class="grid grid-cols-3 gap-1 mb-1">
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="Hospital" bind:value={v.hospital} />
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="When" bind:value={v.when} />
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="Reason" bind:value={v.reason} />
        </div>
      {/each}
      <button class="text-[10px] uppercase mb-3" onclick={() => (health.visits = [...health.visits, { hospital: '', when: '', reason: '' }])}>+ Visit</button>
      <p class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Doctors consulted</p>
      {#each health.doctors as d}
        <div class="grid grid-cols-3 gap-1 mb-1">
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="Name" bind:value={d.name} />
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="Specialty" bind:value={d.specialty} />
          <input class="border-2 border-[#E0E0E0] p-1 text-xs" placeholder="Notes" bind:value={d.notes} />
        </div>
      {/each}
      <button class="text-[10px] uppercase mb-3" onclick={() => (health.doctors = [...health.doctors, { name: '', specialty: '', notes: '' }])}>+ Doctor</button>
      <label class="text-[10px] uppercase tracking-widest text-slate-500">Extra notes</label>
      <textarea class="w-full border-2 border-[#E0E0E0] p-2 text-sm mb-2" rows="2" bind:value={health.notes}></textarea>
      <button class="btn btn-primary w-full" onclick={saveHealth}>Save records</button>
      {#if saveMsg}<p class="text-xs mt-2">{saveMsg}</p>{/if}
    </section>

    {#if reports.length}
      <section class="bg-white border-2 border-[#E0E0E0] p-5">
        <h2 class="text-sm font-black uppercase tracking-widest text-red-600 mb-2">Trip reports</h2>
        {#each reports as r}
          <article class="mb-4 border-t border-[#E0E0E0] pt-3">
            <p class="text-[10px] uppercase text-slate-500">{r.hospital_name} · {r.created_at?.slice(0, 16) || ''}</p>
            <pre class="text-xs whitespace-pre-wrap font-sans mt-1">{r.body}</pre>
          </article>
        {/each}
      </section>
    {/if}
  </div>

  <div class="lg:col-span-8 relative min-h-[320px] border-2 border-[#E0E0E0] overflow-hidden">
    <MapWidget id="patient-map" {markers} {pickupRoute} {dropRoute} {etaLabel} showLegend center={[BMSIT.lat, BMSIT.lng]} />
  </div>
</div>
