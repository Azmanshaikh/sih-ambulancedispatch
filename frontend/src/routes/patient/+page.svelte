<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { auth, apiFetch } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';

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
    saveMsg = res.ok ? t('patient.saved') : t('patient.saveFailed');
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
    if (data.mission && data.mission.phase !== 'complete') applyLive(data.mission);
    else {
      pickupRoute = [];
      dropRoute = [];
      etaLabel = '';
      markers = [
        { position: [BMSIT.lat, BMSIT.lng], popup: `📍 You · ${BMSIT.name}`, type: 'incident' },
      ];
    }
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
      if (!res.ok) throw new Error(data.detail || t('patient.sosFailed'));
      requestMsg = t('patient.sosSent', {
        unit: data.data?.ambulance_id || '',
        hospital: data.data?.hospital_name || '',
        eta: data.data?.eta_minutes ?? '',
      });
      applyLive(data.data);
    } catch (e: any) {
      requestMsg = e?.message || t('patient.sosError');
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

<svelte:head><title>{t('patient.pageTitle')}</title></svelte:head>

<div class="h-full overflow-hidden p-4 grid grid-cols-1 lg:grid-cols-12 gap-4">
  <div class="lg:col-span-4 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
    <button
      class="btn btn-primary"
      style="width:100%;padding:24px;font-size:20px;letter-spacing:0.2em;box-shadow:6px 6px 0 #111;"
      disabled={requesting}
      onclick={emergencySos}
    >
      {requesting ? t('patient.sending') : t('patient.sos')}
    </button>
    {#if requestMsg}<p class="nb-card p-2 text-xs text-black font-semibold">{requestMsg}</p>{/if}

    <div class="grid grid-cols-2 gap-3">
      <a href="/ai-guide" class="btn btn-secondary" style="padding:16px 10px;flex-direction:column;gap:6px;">
        <span class="material-symbols-outlined" style="font-size:26px;">forum</span>
        <span>{t('patient.chatbot')}</span>
      </a>
      <a href="/ai-call" class="btn btn-blue" style="padding:16px 10px;flex-direction:column;gap:6px;">
        <span class="material-symbols-outlined" style="font-size:26px;">videocam</span>
        <span>{t('patient.videoCall')}</span>
      </a>
    </div>

    <section class="nb-card p-5">
      <h2 class="nb-chip nb-red mb-3" style="color:#fff;">{t('patient.vitals')}</h2>
      <p class="text-[10px] text-[#4B4B4B] uppercase mb-4 font-bold">{t('patient.vitalsHint')}</p>
      <div class="grid grid-cols-2 gap-3">
        <div class="nb-yellow p-3" style="border:3px solid #111;">
          <div class="text-3xl font-black">{vitals.heart_rate}<span class="text-xs ml-1">bpm</span></div>
          <div class="text-[10px] uppercase tracking-widest font-bold">{t('patient.heartRate')}</div>
        </div>
        <div class="nb-yellow p-3" style="border:3px solid #111;">
          <div class="text-3xl font-black">{vitals.spo2}<span class="text-xs ml-1">%</span></div>
          <div class="text-[10px] uppercase tracking-widest font-bold">{t('patient.spo2')}</div>
        </div>
        <div class="nb-yellow p-3" style="border:3px solid #111;">
          <div class="text-2xl font-black">{vitals.bp_sys}/{vitals.bp_dia}</div>
          <div class="text-[10px] uppercase tracking-widest font-bold">{t('patient.bp')}</div>
        </div>
        <div class="nb-yellow p-3" style="border:3px solid #111;">
          <div class="text-2xl font-black">{vitals.temperature_c}<span class="text-xs ml-1">°C</span></div>
          <div class="text-[10px] uppercase tracking-widest font-bold">{t('patient.temp')}</div>
        </div>
        <div class="nb-yellow p-3 col-span-2" style="border:3px solid #111;">
          <div class="text-2xl font-black">{vitals.resp_rate}<span class="text-xs ml-1">/min</span></div>
          <div class="text-[10px] uppercase tracking-widest font-bold">{t('patient.resp')}</div>
        </div>
      </div>
    </section>

    <section class="nb-card p-5">
      <h2 class="nb-chip nb-red mb-2" style="color:#fff;">{t('patient.healthRecords')}</h2>
      <p class="text-[10px] text-[#4B4B4B] uppercase mb-3 font-bold">{t('patient.healthHint')}</p>
      <label class="text-[10px] uppercase tracking-widest text-black font-black">{t('patient.allergies')}</label>
      <textarea class="nb-input text-sm mb-2 mt-1" rows="2" bind:value={health.allergies}></textarea>
      <label class="text-[10px] uppercase tracking-widest text-black font-black">{t('patient.medicines')}</label>
      <textarea class="nb-input text-sm mb-2 mt-1" rows="2" bind:value={health.medicines}></textarea>
      <label class="text-[10px] uppercase tracking-widest text-black font-black">{t('patient.conditions')}</label>
      <textarea class="nb-input text-sm mb-3 mt-1" rows="2" bind:value={health.conditions}></textarea>
      <div class="grid grid-cols-2 gap-2 text-xs font-bold mb-3">
        <label class="flex items-center gap-2"><input type="checkbox" bind:checked={health.cardiac} /> {t('patient.cardiac')}</label>
        <label class="flex items-center gap-2"><input type="checkbox" bind:checked={health.diabetes} /> {t('patient.diabetes')}</label>
        <label class="flex items-center gap-2"><input type="checkbox" bind:checked={health.epilepsy} /> {t('patient.epilepsy')}</label>
        <label class="flex items-center gap-2"><input type="checkbox" bind:checked={health.pregnant} /> {t('patient.pregnant')}</label>
      </div>
      <p class="text-[10px] uppercase tracking-widest text-black font-black mb-1">{t('patient.visits')}</p>
      {#each health.visits as v, i}
        <div class="grid grid-cols-3 gap-1 mb-1">
          <input class="nb-input p-1 text-xs" placeholder={t('patient.hospital')} bind:value={v.hospital} />
          <input class="nb-input p-1 text-xs" placeholder={t('patient.when')} bind:value={v.when} />
          <input class="nb-input p-1 text-xs" placeholder={t('patient.reason')} bind:value={v.reason} />
        </div>
      {/each}
      <button class="btn btn-ghost mb-3 mt-1" style="padding:5px 10px;font-size:10px;" onclick={() => (health.visits = [...health.visits, { hospital: '', when: '', reason: '' }])}>{t('patient.addVisit')}</button>
      <p class="text-[10px] uppercase tracking-widest text-black font-black mb-1">{t('patient.doctors')}</p>
      {#each health.doctors as d}
        <div class="grid grid-cols-3 gap-1 mb-1">
          <input class="nb-input p-1 text-xs" placeholder={t('patient.name')} bind:value={d.name} />
          <input class="nb-input p-1 text-xs" placeholder={t('patient.specialty')} bind:value={d.specialty} />
          <input class="nb-input p-1 text-xs" placeholder={t('patient.notes')} bind:value={d.notes} />
        </div>
      {/each}
      <button class="btn btn-ghost mb-3 mt-1" style="padding:5px 10px;font-size:10px;" onclick={() => (health.doctors = [...health.doctors, { name: '', specialty: '', notes: '' }])}>{t('patient.addDoctor')}</button>
      <label class="text-[10px] uppercase tracking-widest text-black font-black">{t('patient.extraNotes')}</label>
      <textarea class="nb-input text-sm mb-3 mt-1" rows="2" bind:value={health.notes}></textarea>
      <button class="btn btn-primary w-full" onclick={saveHealth}>{t('patient.saveRecords')}</button>
      {#if saveMsg}<p class="text-xs mt-2 font-bold">{saveMsg}</p>{/if}
    </section>

    {#if reports.length}
      <section class="nb-card p-5">
        <h2 class="nb-chip nb-red mb-3" style="color:#fff;">{t('patient.tripReports')}</h2>
        {#each reports as r}
          <article class="mb-3 p-3 bg-[#FFF3E6]" style="border:3px solid #111;">
            <p class="text-[10px] uppercase text-[#4B4B4B] font-bold">{r.hospital_name} · {r.created_at?.slice(0, 16) || ''}</p>
            <pre class="text-xs whitespace-pre-wrap font-sans mt-1">{r.body}</pre>
          </article>
        {/each}
      </section>
    {/if}
  </div>

  <div class="lg:col-span-8 relative min-h-[320px] overflow-hidden nb-card-lg" style="border:4px solid #111;">
    <MapWidget id="patient-map" {markers} {pickupRoute} {dropRoute} {etaLabel} showLegend center={[BMSIT.lat, BMSIT.lng]} />
  </div>
</div>
