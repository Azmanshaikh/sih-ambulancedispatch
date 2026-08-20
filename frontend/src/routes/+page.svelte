<script lang="ts">
  import { onMount } from 'svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import RouteReasoningPopup from '$lib/components/RouteReasoningPopup.svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { postToMarker } from '$lib/officers';
  import { t } from '$lib/i18n.svelte';
  import { bandForAmbulance } from '$lib/priority';

  const BMSIT = {
    name: 'BMSIT College, Avalahalli, Yelahanka',
    lat: 13.1344,
    lng: 77.5693,
  };

  let pickupRoute = $state<[number, number][]>([]);
  let dropRoute = $state<[number, number][]>([]);
  let markers = $state<any[]>([]);
  let dispatchStatus = $state('');
  let etaLabel = $state('');
  let ambulances = $state<any[]>([]);
  let hospitals = $state<any[]>([]);
  let selectedHospital = $state<any>(null);
  let assignedUnit = $state('');
  let constraints = $state<any>(null);
  let confidence = $state<number | null>(null);
  let reason = $state('');
  let candidates = $state<any[]>([]);
  let pickupMinutes = $state<number | null>(null);
  let transportMinutes = $state<number | null>(null);
  let assignedAmbulanceType = $state('');
  let fallbackReason = $state('');
  let monitor = $state<any>(null);
  let extraRoutes = $state<any[]>([]);
  let corridor = $state<any>(null);
  let activeMissions = $state<any[]>([]);
  let selectedAmbulanceId = $state('');
  let assignedIds = $derived(new Set([assignedUnit, ...activeMissions.map((m) => m.ambulance_id)].filter(Boolean)));
  let availableCount = $derived(ambulances.filter((a) => a.status === 'available').length);
  let conflictReason = $derived(
    monitor?.mission?.conflict?.reason ||
      activeMissions.find((m) => m.conflict?.reason)?.conflict?.reason ||
      ''
  );

  let currentDecision = $derived.by(() => {
    if (!assignedUnit && !selectedHospital && !pickupRoute.length && !dropRoute.length) {
      return null;
    }
    const matchingMission = activeMissions.find((m) => m.ambulance_id === (selectedAmbulanceId || assignedUnit))
      || (monitor?.mission?.ambulance_id === (selectedAmbulanceId || assignedUnit) ? monitor.mission : null)
      || monitor?.mission
      || null;

    return {
      id: matchingMission?.id || `${assignedUnit || 'unit'}-${selectedHospital?.id || 'hosp'}`,
      ambulance_id: assignedUnit || matchingMission?.ambulance_id || selectedAmbulanceId,
      ambulance: matchingMission?.ambulance || ambulances.find((a) => a.id === (assignedUnit || selectedAmbulanceId)),
      assigned_ambulance_type_label: assignedAmbulanceType || matchingMission?.assigned_ambulance_type_label,
      assigned_ambulance_type: matchingMission?.assigned_ambulance_type,
      match_status: matchingMission?.match_status || (fallbackReason ? 'fallback' : 'exact'),
      fallback_reason: fallbackReason || matchingMission?.fallback_reason,
      hospital: selectedHospital || matchingMission?.hospital,
      hospital_name: selectedHospital?.name || matchingMission?.hospital_name,
      eta_minutes: etaLabel ? parseInt(etaLabel) : matchingMission?.eta_minutes,
      pickup_minutes: pickupMinutes ?? matchingMission?.pickup_minutes,
      transport_minutes: transportMinutes ?? matchingMission?.transport_minutes,
      pickup_route: pickupRoute,
      drop_route: dropRoute,
      route: dropRoute,
      constraints: constraints || matchingMission?.constraints,
      confidence: confidence ?? matchingMission?.confidence,
      reason: reason || matchingMission?.reason,
      priority: matchingMission?.priority ?? 1,
      priority_label: matchingMission?.priority_label,
      emergency_category: matchingMission?.emergency_category,
      is_raining: matchingMission?.is_raining,
      conflict: matchingMission?.conflict,
      conflictReason: conflictReason || matchingMission?.conflict?.reason,
      phase: matchingMission?.phase || 'pickup',
    };
  });

  function applyPayload(payload: any) {
    if (!payload) return;
    pickupRoute = payload.pickup_route || [];
    dropRoute = payload.drop_route || payload.route || [];
    selectedHospital = payload.hospital;
    assignedUnit = payload.ambulance_id || '';
    constraints = payload.constraints;
    confidence = payload.confidence ?? null;
    reason = payload.reason || '';
    candidates = payload.candidates || [];
    pickupMinutes = payload.pickup_minutes ?? null;
    transportMinutes = payload.transport_minutes ?? null;
    assignedAmbulanceType = payload.assigned_ambulance_type_label || payload.ambulance?.type_label || '';
    fallbackReason = payload.fallback_reason || '';
    const mins = payload.eta_minutes ?? Math.round((payload.eta_seconds || 0) / 60);
    if (mins) etaLabel = `${mins} min`;
    if (payload.hospital_name) {
      const phase = payload.phase || 'pickup';
      dispatchStatus =
        phase === 'complete'
          ? `Trip complete · ${payload.hospital_name}`
          : `Nearest 🚑 ${assignedUnit || 'unit'} → ${payload.hospital_name}`;
    }
    markers = buildMarkers();
  }

  function postMarkers(posts: any[] = []) {
    return posts.map((p) => postToMarker(p, true));
  }

  function extraRoutesFor(missions: any[], selectedId: string) {
    const extras: any[] = [];
    for (const m of missions) {
      if (!m || m.ambulance_id === selectedId) continue;
      const pickup = m.pickup_route || [];
      const drop = m.drop_route || m.route || [];
      if (pickup.length > 1) {
        extras.push({ id: `${m.id}-pickup`, points: pickup, color: '#fb7185', kind: 'pickup', label: `${m.ambulance_id} pickup` });
      }
      if (drop.length > 1) {
        extras.push({
          id: `${m.id}-drop`,
          points: drop,
          color: m.conflict?.status === 'rerouted' ? '#a855f7' : '#38bdf8',
          kind: 'drop',
          label: `${m.ambulance_id} → ${m.hospital_name || 'hospital'}`,
        });
      }
    }
    for (const r of corridor?.extra_routes || []) {
      if (r.kind === 'overlap') extras.push(r);
    }
    return extras;
  }

  function focusMission(mission: any | null) {
    if (!mission || mission.phase === 'complete') return;
    selectedAmbulanceId = mission.ambulance_id || selectedAmbulanceId;
    applyPayload(mission);
    extraRoutes = extraRoutesFor(activeMissions, selectedAmbulanceId);
  }

  function selectAmbulance(id: string) {
    selectedAmbulanceId = id;
    const hit =
      activeMissions.find((m) => m.ambulance_id === id) ||
      (monitor?.mission?.ambulance_id === id ? monitor.mission : null);
    if (hit && hit.phase !== 'complete') focusMission(hit);
    else extraRoutes = extraRoutesFor(activeMissions, id);
    markers = buildMarkers();
  }

  function buildMarkers(fleet = ambulances, hosp = hospitals, extra: any[] = []) {
    const hospitalId = selectedHospital?.id;
    const assigned = new Set(activeMissions.map((m) => m.ambulance_id).filter(Boolean));
    if (assignedUnit) assigned.add(assignedUnit);
    const allMissions = [
      ...activeMissions,
      ...(monitor?.mission && !activeMissions.some((m) => m.ambulance_id === monitor.mission.ambulance_id)
        ? [monitor.mission]
        : []),
    ];
    const fleetMarks = fleet.map((a: any) => ({
      position: [a.lat, a.lng] as [number, number],
      popup: `🚑 ${a.id} · ${a.label}<br/><span style="font-weight:600;color:#6B6B6B">${a.status}${assigned.has(a.id) ? ' · assigned' : ''}</span>`,
      type: 'ambulance',
      id: a.id,
      ambulanceId: a.id,
      hasMission: assigned.has(a.id),
      priorityBand: bandForAmbulance(a.id, allMissions),
    }));
    const hospMarks = hosp.map((h: any) => ({
      position: [h.lat, h.lng] as [number, number],
      popup: `🏥 ${h.name}<br/>Beds ${h.available_beds}/${h.total_beds}`,
      type: hospitalId === h.id ? 'hospital_selected' : 'hospital',
    }));
    return [
      { position: [BMSIT.lat, BMSIT.lng] as [number, number], popup: `📍 ${BMSIT.name}`, type: 'incident' },
      ...hospMarks,
      ...fleetMarks,
      ...(monitor?.patient?.lat
        ? [{ position: [monitor.patient.lat, monitor.patient.lng] as [number, number], popup: `Patient · ${monitor.patient.name || 'unknown'}`, type: 'incident' }]
        : []),
      ...postMarkers(corridor?.posts || []),
      ...extra,
    ];
  }

  function clearMissionUi() {
    pickupRoute = [];
    dropRoute = [];
    extraRoutes = [];
    etaLabel = '';
    selectedHospital = null;
    assignedUnit = '';
    constraints = null;
    confidence = null;
    reason = '';
    candidates = [];
    pickupMinutes = null;
    transportMinutes = null;
    assignedAmbulanceType = '';
    fallbackReason = '';
    dispatchStatus = '';
    selectedAmbulanceId = '';
    extraRoutes = extraRoutesFor(activeMissions, '');
    markers = buildMarkers();
  }

  async function loadFleet() {
    try {
      const res = await apiFetch('/tracking/fleet');
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        console.error('Fleet load failed', data);
        return;
      }
      ambulances = data.ambulances || [];
      hospitals = data.hospitals || [];
      markers = buildMarkers();
    } catch (err) {
      console.error(err);
    }
  }

  async function endTrip() {
    await apiFetch('/accounts/mission/phase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase: 'complete' }),
    });
    await loadMonitor();
    await loadFleet();
  }

  async function loadCorridor() {
    try {
      const res = await apiFetch('/tracking/corridor');
      if (!res.ok) return;
      corridor = await res.json();
      const liveMissions = corridor.missions || [];
      if (liveMissions.length) activeMissions = liveMissions;
      extraRoutes = extraRoutesFor(activeMissions, selectedAmbulanceId || assignedUnit);
      markers = buildMarkers();
    } catch {
      /* ignore */
    }
  }

  async function loadMonitor() {
    try {
      const res = await apiFetch('/accounts/monitor');
      if (!res.ok) return;
      monitor = await res.json();
      const liveList = (monitor.active_missions || []).filter((m: any) => m && m.phase !== 'complete');
      activeMissions = liveList;
      const keep = liveList.find((m: any) => m.ambulance_id === selectedAmbulanceId);
      const latest = monitor?.mission && monitor.mission.phase !== 'complete' ? monitor.mission : null;
      const live = keep || latest || liveList[0] || null;
      if (live) focusMission(live);
      else clearMissionUi();
      markers = buildMarkers();
    } catch {
      /* ignore */
    }
  }

  onMount(() => {
    loadFleet();
    loadMonitor();
    loadCorridor();
    const timer = setInterval(() => {
      loadFleet();
      loadMonitor();
      loadCorridor();
    }, 2500);
    return () => clearInterval(timer);
  });
</script>

<svelte:head><title>{t('dash.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col" style="overflow: hidden;">
  <div class="p-4 grid grid-cols-12 gap-4 h-full overflow-hidden">

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="nb-card p-4 flex-shrink-0 dash-panel">
        <div class="flex justify-between items-center mb-3">
          <h3 class="dash-heading">System Performance</h3>
          <span class="status-dot status-dot--live blink"></span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="med-stat">
            <div class="text-3xl font-bold text-[var(--clr-ink)] leading-none">{etaLabel ? etaLabel.split(' ')[0] : '—'}<span class="text-xs text-[var(--clr-muted)] ml-1">min</span></div>
            <div class="text-[10px] uppercase tracking-wide text-[var(--clr-muted)] mt-1 font-semibold">Hospital ETA</div>
          </div>
          <div class="med-stat">
            <div class="text-3xl font-bold text-[var(--clr-success)] leading-none">{availableCount}<span class="text-xs text-[var(--clr-muted)] ml-1">u</span></div>
            <div class="text-[10px] uppercase tracking-wide text-[var(--clr-muted)] mt-1 font-semibold">Available</div>
          </div>
        </div>
      </section>

      <section class="flex flex-col gap-3 flex-1 min-h-0">
        <div class="flex justify-between items-center flex-wrap gap-1">
          <h3 class="dash-heading">{t('dash.fleet')}</h3>
          <span class="nb-chip chip-danger">{dispatchStatus || t('dash.waitingSos')}</span>
        </div>

        <p class="text-[11px] text-[var(--clr-muted)] font-medium">{t('dash.tapHint')}</p>

        <div class="space-y-2 overflow-y-auto no-sb flex-1 pr-1">
          {#each ambulances as a}
            <button
              type="button"
              onclick={() => selectAmbulance(a.id)}
              class="fleet-row flex items-center justify-between px-3 py-2 w-full text-left {assignedIds.has(a.id) ? 'fleet-row--assigned' : a.status === 'available' ? 'fleet-row--available' : ''} {selectedAmbulanceId === a.id ? 'fleet-row--selected' : ''}"
            >
              <div>
                <p class="text-[12px] font-bold">{a.id}</p>
                <p class="text-[10px] text-[var(--clr-muted)] uppercase tracking-wide font-semibold">{a.label}</p>
                <p class="text-[10px] text-[var(--clr-primary)] uppercase tracking-wide font-semibold">{a.type_label || a.ambulance_type || 'BLS'}</p>
              </div>
              <span class="nb-chip {a.status === 'available' ? 'chip-success' : a.status === 'dispatched' ? 'chip-danger' : ''}">{a.status}</span>
            </button>
          {/each}
        </div>
      </section>
    </div>

    <div class="col-span-6 relative overflow-hidden nb-card-lg map-panel">
      <MapWidget id="dash-map" {markers} {etaLabel} {pickupRoute} {dropRoute} {extraRoutes} {selectedAmbulanceId} officerCallEnabled showLegend center={[BMSIT.lat, BMSIT.lng]} onSelectAmbulance={selectAmbulance} />
      <div class="absolute inset-0 pointer-events-none z-10" style="padding: 0.9rem;">
        <div class="flex justify-between items-start pointer-events-auto gap-2">
          <div class="glass px-3 py-2">
            <div class="flex items-center gap-2">
              <span class="status-dot status-dot--alert blink"></span>
              <span class="text-[11px] font-bold tracking-wide uppercase text-[var(--clr-ink)]">{t('dash.liveFeed')}</span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-2">
            {#if monitor?.unread_alerts}
              <a href="/notifications" class="glass px-3 py-1.5 text-[10px] text-black font-black uppercase tracking-widest nb-red" style="color:#fff;">
                {monitor.unread_alerts === 1
                  ? t('dash.staffAlerts', { count: monitor.unread_alerts })
                  : t('dash.staffAlertsPlural', { count: monitor.unread_alerts })}
              </a>
            {/if}
            {#if monitor?.mission && monitor.mission.phase !== 'complete'}
              <button class="btn btn-primary" style="padding:6px 12px;font-size:10px;" onclick={endTrip}>
                {t('dash.endTrip')}
              </button>
            {/if}
            <div class="glass px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide max-w-[220px] text-right">
              📍 {BMSIT.name}
            </div>
          </div>
        </div>
      </div>
      <RouteReasoningPopup decision={currentDecision} />
    </div>

    <div class="col-span-3 flex flex-col gap-4 overflow-y-auto no-sb pb-3">
      <section class="nb-card nb-blue p-4 flex-shrink-0 ai-panel">
        <div class="flex items-center gap-2 mb-3">
          <span class="material-symbols-outlined">psychology</span>
          <h3 class="text-[11px] font-black uppercase tracking-widest">{t('dash.aiRec')}</h3>
        </div>
        {#if selectedHospital}
          <div class="flex gap-3 mb-3">
            <div class="h-11 w-11 shrink-0 bg-white text-[var(--clr-ink)] flex items-center justify-center font-bold text-xs rounded-lg border border-[var(--clr-border)]">{confidence ?? '—'}%</div>
            <div>
              <p class="text-sm font-black">{selectedHospital.name}</p>
              <p class="text-[10px] text-white/85 mt-1">{reason}</p>
            </div>
          </div>
          {#if pickupMinutes != null}
            <p class="text-[10px] font-semibold">{t('dash.pickupTransport', { pickup: pickupMinutes ?? '—', transport: transportMinutes ?? '—' })}</p>
          {/if}
          {#if constraints}
            <p class="text-[10px] mt-2 uppercase tracking-wide font-bold">
              {constraints.routing === 'emergency-shortest' ? t('dash.corridor') : `${constraints.routing} · ${constraints.traffic} traffic`}
            </p>
            <p class="text-[10px] mt-1 uppercase tracking-wide font-bold">
              Engine: {constraints.engine === 'networkx' ? `NetworkX Dijkstra${constraints.graph_nodes ? ` · ${constraints.graph_nodes} nodes` : ''}` : 'Direct TomTom/OSRM'}
            </p>
            {#if constraints.shortest_km != null && constraints.fastest_min != null}
              <p class="text-[10px] mt-1 font-bold">Shortest {constraints.shortest_km} km · Fastest {constraints.fastest_min} min</p>
            {/if}
          {/if}
          {#if conflictReason}
            <p class="text-[10px] mt-2 font-semibold alert-banner">{conflictReason}</p>
          {/if}
          {#if assignedUnit}
            <p class="nb-chip chip-warning mt-2">{t('dash.assigned', { unit: assignedUnit })}{assignedAmbulanceType ? ` · ${assignedAmbulanceType}` : ''}</p>
          {/if}
          {#if fallbackReason}
            <p class="text-[10px] mt-2 font-semibold alert-banner">Capability fallback: {fallbackReason}</p>
          {/if}
          {#if candidates.length}
            <div class="mt-3 space-y-1 nb-card p-2">
              <p class="text-[9px] font-black uppercase tracking-widest text-[var(--clr-ink)]">{t('dash.ranked')}</p>
              {#each candidates as c, i}
                <div class="flex justify-between gap-2 text-[10px] text-[var(--clr-ink)] {i === 0 ? 'font-black' : 'font-semibold'}">
                  <span>{i + 1}. {c.name}</span>
                  <span class="shrink-0">{c.eta_minutes} min</span>
                </div>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="flex gap-3">
            <div class="h-11 w-11 shrink-0 bg-white text-[var(--clr-ink)] flex items-center justify-center font-bold text-xs rounded-lg border border-[var(--clr-border)]">—</div>
            <div>
              <p class="text-sm font-black">{t('dash.waitingPatient')}</p>
              <p class="text-[10px] text-white/85 mt-1">{t('dash.waitingPatientHint')}</p>
            </div>
          </div>
        {/if}
      </section>

      <section class="flex-1 flex flex-col gap-3 min-h-0">
        <h3 class="dash-heading">{t('dash.telemetry')}</h3>
        <div class="space-y-3 overflow-y-auto no-sb flex-1 pr-1">
          <div class="telemetry-card">
            <div class="flex justify-between items-center mb-1">
              <span class="nb-chip nb-green" style="color:#fff;">{t('dash.fleet')}</span>
              <span class="text-[9px] text-[var(--clr-success)] font-bold uppercase">{t('dash.live')}</span>
            </div>
            <p class="text-xs text-black font-semibold mt-1">{t('dash.fleetTracked', { count: ambulances.length })}</p>
          </div>
          {#if monitor?.patient}
            <div class="telemetry-card">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-green" style="color:#fff;">{t('dash.patient')}</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold">{monitor.patient.vitals?.heart_rate ?? '—'} bpm</span>
              </div>
              <p class="text-xs text-black font-semibold mt-1">{monitor.patient.name || t('dash.unassigned')} · {monitor.patient.address}</p>
              <p class="text-[10px] text-[#4B4B4B] mt-1 font-semibold">
                SpO2 {monitor.patient.vitals?.spo2 ?? '—'}%
                · {t('patient.cardiac')} {monitor.patient.record?.cardiac ? t('dash.yes') : t('dash.no')}
                · {t('patient.diabetes')} {monitor.patient.record?.diabetes ? t('dash.yes') : t('dash.no')}
              </p>
              {#if monitor.driver}
                <p class="text-[10px] text-[#FF2D2D] mt-1 font-black">Driver {monitor.driver.id} at {monitor.driver.lat}, {monitor.driver.lng}</p>
              {/if}
            </div>
          {/if}
          {#if activeMissions.length}
            <div class="telemetry-card">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-red" style="color:#fff;">{t('dash.liveCorridors')}</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold uppercase">{activeMissions.length === 1 ? t('dash.unit', { count: activeMissions.length }) : t('dash.units', { count: activeMissions.length })}</span>
              </div>
              {#each activeMissions as m}
                <button type="button" class="block w-full text-left" onclick={() => selectAmbulance(m.ambulance_id)}>
                  <p class="text-[10px] font-semibold mt-1 {selectedAmbulanceId === m.ambulance_id ? 'text-[#FF2D2D] font-black' : 'text-black'}">
                    {m.ambulance_id} · {m.priority_label || 'standard'} · {m.phase} → {m.hospital_name}
                    {#if m.conflict?.status && m.conflict.status !== 'none'}
                      <span class="text-[#b45309]"> · {m.conflict.status}</span>
                    {/if}
                  </p>
                </button>
              {/each}
            </div>
          {/if}
          {#if corridor?.sms?.length}
            <div class="telemetry-card">
              <span class="nb-chip nb-yellow">Corridor SMS</span>
              <p class="text-[10px] text-black font-semibold mt-2">{corridor.sms[0].post_name}: {corridor.sms[0].status}</p>
              <p class="text-[10px] text-[#4B4B4B] mt-1">{corridor.sms[0].body}</p>
            </div>
          {/if}
          {#if selectedHospital}
            <div class="telemetry-card">
              <div class="flex justify-between items-center mb-1">
                <span class="nb-chip nb-red" style="color:#fff;">Route</span>
                <span class="text-[9px] text-[#4B4B4B] font-bold uppercase">Now</span>
              </div>
              <p class="text-xs text-black font-semibold mt-1">{etaLabel} · {selectedHospital.name}</p>
            </div>
          {/if}
          {#if monitor?.mission?.report?.body}
            <div class="telemetry-card">
              <span class="nb-chip nb-red" style="color:#fff;">Trip report</span>
              <pre class="text-[10px] text-black whitespace-pre-wrap font-sans mt-2">{monitor.mission.report.body}</pre>
            </div>
          {/if}
        </div>
      </section>
    </div>

  </div>
</div>

<style>
  .dash-heading {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--clr-muted);
    margin: 0;
  }
  .dash-panel {
    background: var(--clr-surface);
  }
  .map-panel {
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  .ai-panel {
    color: #fff;
    background: linear-gradient(135deg, #0F766E 0%, #166534 100%);
    border: none;
  }
  .ai-panel :global(.nb-card) {
    color: var(--clr-ink);
  }
  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    display: inline-block;
  }
  .status-dot--live {
    background: var(--clr-success);
    box-shadow: 0 0 0 2px #BBF7D0;
  }
  .status-dot--alert {
    background: var(--clr-danger);
    box-shadow: 0 0 0 2px #FECACA;
  }
  .fleet-row {
    background: var(--clr-surface);
    border: 1px solid var(--clr-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: border-color 0.12s, box-shadow 0.12s;
  }
  .fleet-row:hover {
    border-color: var(--clr-primary);
  }
  .fleet-row--selected {
    border-color: var(--clr-primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }
  .fleet-row--assigned {
    background: var(--clr-danger-bg);
    border-color: #FECACA;
  }
  .fleet-row--available {
    border-color: #86EFAC;
    background: var(--clr-success-bg);
  }
  .alert-banner {
    background: var(--clr-warning-bg);
    color: var(--clr-warning);
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid #FDE68A;
  }
  .telemetry-card {
    background: var(--clr-surface);
    color: var(--clr-ink);
    padding: 12px;
    border: 1px solid var(--clr-border);
    border-radius: var(--radius-sm);
    box-shadow: var(--sh-sm);
  }
</style>
