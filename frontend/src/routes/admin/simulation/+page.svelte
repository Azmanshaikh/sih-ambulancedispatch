<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiFetch, auth, isMainAdmin } from '$lib/auth.svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { lookupAddress, lookupCoords } from '$lib/geocode';

  const BMSIT = { lat: 13.1344, lng: 77.5693, name: 'BMSIT College, Avalahalli, Yelahanka' };

  type PinMode = 'pickup' | 'destination' | 'ambulance';

  let ambulances = $state<any[]>([]);
  let selectedAmbulanceId = $state('');
  let pinMode = $state<PinMode>('pickup');

  let pickupLat = $state(BMSIT.lat);
  let pickupLng = $state(BMSIT.lng);
  let pickupAddress = $state(BMSIT.name);
  let destLat = $state(13.1168);
  let destLng = $state(77.5819);
  let destAddress = $state('Cytecare Hospital, Yelahanka');

  let ambLat = $state<number | null>(null);
  let ambLng = $state<number | null>(null);
  let ambAddress = $state('');

  let calculating = $state(false);
  let error = $state('');
  let result = $state<any>(null);

  let pickupRoute = $derived(result?.pickup_route?.length ? result.pickup_route : null);
  let dropRoute = $derived(result?.route?.length ? result.route : null);

  let selectedAmbulance = $derived(ambulances.find((a) => a.id === selectedAmbulanceId));

  let markers = $derived.by(() => {
    const list: any[] = [];
    if (pickupLat && pickupLng) {
      list.push({
        position: [pickupLat, pickupLng] as [number, number],
        type: 'pickup',
        popup: `Pickup: ${pickupAddress}`,
      });
    }
    if (destLat && destLng) {
      list.push({
        position: [destLat, destLng] as [number, number],
        type: 'destination',
        popup: `Destination: ${destAddress}`,
      });
    }
    const lat = ambLat ?? selectedAmbulance?.lat;
    const lng = ambLng ?? selectedAmbulance?.lng;
    if (lat != null && lng != null && selectedAmbulanceId) {
      list.push({
        position: [lat, lng] as [number, number],
        type: 'ambulance',
        id: selectedAmbulanceId,
        ambulanceId: selectedAmbulanceId,
        popup: `${selectedAmbulance?.label || selectedAmbulanceId} · ${ambAddress || 'Custom position'}`,
      });
    }
    return list;
  });

  let etaLabel = $derived(
    result?.eta_minutes != null
      ? `ETA ${result.eta_minutes} min · ${result.total_distance_km ?? '—'} km`
      : ''
  );

  let routeSummary = $derived.by(() => {
    if (!result) return '';
    const unit = result.ambulance?.label || result.ambulance_id || 'Selected unit';
    const engine =
      result.constraints?.engine === 'networkx'
        ? 'NetworkX over live road data'
        : result.constraints?.provider || result.constraints?.engine || 'routing engine';
    const traffic =
      result.constraints?.traffic === 'waived'
        ? 'Emergency corridor active — traffic signals waived for fastest arrival.'
        : 'Standard traffic considered.';
    const weather = result.is_raining
      ? 'Rain detected; ETA includes a small weather adjustment.'
      : 'Clear weather at pickup.';
    return `${unit} was chosen for this simulation. Fastest path: ${result.pickup_minutes} min to pickup (${result.pickup_distance_km ?? '—'} km), then ${result.transport_minutes} min to destination (${result.transport_distance_km ?? '—'} km) — ${result.total_distance_km ?? '—'} km total, ~${result.eta_minutes} min ETA. Calculated via ${engine}. ${traffic} ${weather}`;
  });

  function syncAmbulanceFromFleet() {
    const amb = ambulances.find((a) => a.id === selectedAmbulanceId);
    if (!amb) return;
    ambLat = amb.lat;
    ambLng = amb.lng;
    ambAddress = amb.label ? `${amb.label} (${amb.id})` : amb.id;
  }

  function selectAmbulance(id: string) {
    selectedAmbulanceId = id;
    error = '';
    syncAmbulanceFromFleet();
  }

  onMount(() => {
    void loadFleet();
  });

  $effect(() => {
    if (!auth.ready) return;
    if (!isMainAdmin()) goto('/', { replaceState: true });
  });

  async function loadFleet() {
    try {
      const res = await apiFetch('/tracking/fleet');
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        error = typeof data.detail === 'string' ? data.detail : 'Could not load the fleet.';
        return;
      }
      ambulances = data.ambulances || [];
      if (!ambulances.length) {
        error = 'No ambulances in the fleet yet.';
        return;
      }
      if (!selectedAmbulanceId) {
        const available = ambulances.find((a) => a.status === 'available') || ambulances[0];
        selectAmbulance(available.id);
      } else {
        syncAmbulanceFromFleet();
      }
    } catch {
      error = 'Could not load the fleet.';
    }
  }

  async function geocodePickup() {
    const q = pickupAddress.trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Pickup address not found.';
      return;
    }
    pickupLat = hit.lat;
    pickupLng = hit.lng;
    if (hit.address) pickupAddress = hit.address;
    error = '';
  }

  async function geocodeDest() {
    const q = destAddress.trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Destination address not found.';
      return;
    }
    destLat = hit.lat;
    destLng = hit.lng;
    if (hit.address) destAddress = hit.address;
    error = '';
  }

  async function geocodeAmbulance() {
    const q = ambAddress.trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Ambulance address not found.';
      return;
    }
    ambLat = hit.lat;
    ambLng = hit.lng;
    if (hit.address) ambAddress = hit.address;
    error = '';
  }

  async function onMapClick(lat: number, lng: number) {
    error = '';
    if (pinMode === 'pickup') {
      pickupLat = lat;
      pickupLng = lng;
      try {
        const hit = await lookupCoords(lat, lng);
        pickupAddress = hit.address;
      } catch {
        pickupAddress = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      }
    } else if (pinMode === 'destination') {
      destLat = lat;
      destLng = lng;
      try {
        const hit = await lookupCoords(lat, lng);
        destAddress = hit.address;
      } catch {
        destAddress = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      }
    } else {
      ambLat = lat;
      ambLng = lng;
      try {
        const hit = await lookupCoords(lat, lng);
        ambAddress = hit.address;
      } catch {
        ambAddress = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      }
    }
  }

  async function calculateRoute() {
    if (!selectedAmbulanceId) {
      error = 'Select an ambulance from the fleet.';
      return;
    }
    if (ambLat == null || ambLng == null) {
      error = 'Set the ambulance location on the map or enter an address.';
      return;
    }
    calculating = true;
    error = '';
    result = null;
    try {
      const res = await apiFetch('/tracking/admin/simulate-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pickup_lat: pickupLat,
          pickup_lng: pickupLng,
          pickup_address: pickupAddress,
          dest_lat: destLat,
          dest_lng: destLng,
          dest_address: destAddress,
          ambulance_id: selectedAmbulanceId,
          ambulance_lat: ambLat,
          ambulance_lng: ambLng,
          ambulance_address: ambAddress,
          push_to_driver: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || 'Route calculation failed.';
        return;
      }
      result = data.data;
    } catch {
      error = 'Could not reach the routing service.';
    } finally {
      calculating = false;
    }
  }
</script>

<svelte:head><title>Admin Simulation — JEEVAN</title></svelte:head>

<div class="sim-page">
  <aside class="sim-panel no-sb">
    <div class="sim-banner">
      <span class="material-symbols-outlined">science</span>
      <span><strong>Admin Simulation</strong> — calculating also sends the job to the driver of this unit.</span>
    </div>

    <section class="sim-section">
      <p class="med-section-title">Map pin mode</p>
      <div class="mode-toggle">
        <button class="btn" class:btn-primary={pinMode === 'pickup'} onclick={() => (pinMode = 'pickup')}>
          Set pickup
        </button>
        <button class="btn" class:btn-primary={pinMode === 'destination'} onclick={() => (pinMode = 'destination')}>
          Set destination
        </button>
        <button class="btn" class:btn-primary={pinMode === 'ambulance'} onclick={() => (pinMode = 'ambulance')}>
          Set ambulance
        </button>
      </div>
      <p class="hint">
        {#if pinMode === 'pickup'}
          Click the map to set pickup, or enter an address below.
        {:else if pinMode === 'destination'}
          Click the map to set destination, or enter an address below.
        {:else}
          Click the map to place the ambulance, or enter an address below.
        {/if}
      </p>
    </section>

    <section class="sim-section">
      <p class="med-section-title">Ambulance</p>
      {#if ambulances.length}
        <div class="fleet-picker">
          {#each ambulances as amb}
            <button
              type="button"
              class="fleet-pick"
              class:active={selectedAmbulanceId === amb.id}
              onclick={() => selectAmbulance(amb.id)}
            >
              <span class="fleet-pick-id">{amb.id}</span>
              <span class="fleet-pick-meta">{amb.label || amb.type_label || amb.ambulance_type}</span>
              <span class="fleet-pick-status">{amb.status}</span>
            </button>
          {/each}
        </div>
      {:else}
        <p class="hint">Fleet list is empty. Check that you are signed in as Main Admin and the backend is running.</p>
      {/if}
      <div class="field-row">
        <input class="nb-input" bind:value={ambAddress} placeholder="Ambulance location address" />
        <button class="btn btn-secondary" onclick={geocodeAmbulance}>Locate</button>
      </div>
      {#if ambLat != null && ambLng != null}
        <p class="coords-hint">{ambLat.toFixed(5)}, {ambLng.toFixed(5)}</p>
      {/if}
    </section>

    <section class="sim-section">
      <p class="med-section-title">Pickup location</p>
      <div class="field-row">
        <input class="nb-input" bind:value={pickupAddress} placeholder="Pickup address" />
        <button class="btn btn-secondary" onclick={geocodePickup}>Locate</button>
      </div>
    </section>

    <section class="sim-section">
      <p class="med-section-title">Destination</p>
      <div class="field-row">
        <input class="nb-input" bind:value={destAddress} placeholder="Drop / hospital address" />
        <button class="btn btn-secondary" onclick={geocodeDest}>Locate</button>
      </div>
    </section>

    <button class="btn btn-primary calc-btn" disabled={calculating} onclick={calculateRoute}>
      {calculating ? 'Calculating…' : 'Calculate Fastest Route'}
    </button>

    {#if error}
      <p class="error-msg">{error}</p>
    {/if}

    {#if result}
      <section class="sim-section results">
        <p class="med-section-title">Route results</p>
        <div class="med-stat-grid">
          <div class="med-stat">
            <div class="label">Total ETA</div>
            <div class="value">{result.eta_minutes} min</div>
          </div>
          <div class="med-stat">
            <div class="label">Distance</div>
            <div class="value">{result.total_distance_km} km</div>
          </div>
          <div class="med-stat">
            <div class="label">Pickup leg</div>
            <div class="value">{result.pickup_minutes} min</div>
          </div>
          <div class="med-stat">
            <div class="label">Transport leg</div>
            <div class="value">{result.transport_minutes} min</div>
          </div>
        </div>

        <div class="constraint-list">
          <span class="nb-chip chip-info">{result.constraints?.engine || 'routing'}</span>
          {#if result.is_raining}
            <span class="nb-chip chip-warning">Rain — ETA adjusted</span>
          {:else}
            <span class="nb-chip chip-success">Clear weather</span>
          {/if}
          <span class="nb-chip">{result.constraints?.road_conditions || 'Traffic assessed'}</span>
          <span class="nb-chip chip-info">{result.constraints?.routing || 'emergency-shortest'}</span>
        </div>
      </section>
    {/if}
  </aside>

  <div class="sim-map-col">
    <div class="sim-map">
      <MapWidget
        markers={markers}
        {pickupRoute}
        dropRoute={dropRoute}
        {etaLabel}
        selectedAmbulanceId={selectedAmbulanceId}
        showLegend={true}
        fitRoute={true}
        onMapClick={onMapClick}
      />
    </div>
    {#if result}
      <div class="map-reasoning nb-card">
        <div class="map-reasoning-head">
          <span class="material-symbols-outlined">route</span>
          <h3>Why this route?</h3>
        </div>
        <p class="map-reasoning-text">{routeSummary}</p>
      </div>
    {:else}
      <div class="map-reasoning map-reasoning--empty nb-card">
        <span class="material-symbols-outlined">info</span>
        <p>Set pickup, destination, and ambulance, then calculate to see why JEEVAN picks this route.</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .sim-page {
    display: grid;
    grid-template-columns: minmax(280px, 360px) 1fr;
    height: 100%;
    gap: 0;
    background: var(--clr-bg);
  }
  .sim-panel {
    overflow-y: auto;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    border-right: 1px solid var(--clr-border);
    background: var(--clr-surface);
  }
  .sim-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .mode-toggle {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .mode-toggle .btn {
    flex: 1 1 calc(33% - 8px);
    min-width: 90px;
    font-size: 11px;
    padding: 8px 8px;
  }
  .fleet-picker {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 220px;
    overflow-y: auto;
    padding-bottom: 4px;
  }
  .fleet-pick {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 8px;
    width: 100%;
    text-align: left;
    padding: 8px 10px;
    background: #fff;
    color: var(--clr-ink);
    border: 2px solid #111;
    border-radius: 0;
    box-shadow: 3px 3px 0 #111;
    cursor: pointer;
    font-family: inherit;
    transition: transform 0.1s ease, box-shadow 0.1s ease;
  }
  .fleet-pick:hover {
    transform: translate(-2px, -2px);
    box-shadow: 5px 5px 0 #111;
  }
  .fleet-pick:active,
  .fleet-pick.active {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 #111;
    background: var(--clr-primary);
    color: #fff;
  }
  .fleet-pick-id {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.04em;
  }
  .fleet-pick-meta {
    font-size: 11px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fleet-pick-status {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .hint {
    margin: 0;
    font-size: 11px;
    color: var(--clr-muted);
    line-height: 1.4;
  }
  .coords-hint {
    margin: 0;
    font-size: 10px;
    color: var(--clr-muted);
    font-family: var(--font-mono);
  }
  .field-row {
    display: flex;
    gap: 8px;
  }
  .field-row .nb-input {
    flex: 1;
  }
  .calc-btn {
    width: 100%;
    padding: 12px;
    font-size: 14px;
  }
  .error-msg {
    margin: 0;
    padding: 10px 12px;
    background: var(--clr-danger-bg);
    border: 1px solid #FECACA;
    border-radius: var(--radius-sm);
    color: var(--clr-danger);
    font-size: 13px;
    font-weight: 600;
  }
  .results {
    animation: fadeUp 0.25s ease;
  }
  .constraint-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .reason {
    margin: 0;
    font-size: 12px;
    line-height: 1.5;
    color: var(--clr-muted);
    padding: 10px 12px;
    background: var(--clr-surface2);
    border-radius: var(--radius-sm);
    border: 1px solid var(--clr-border);
  }
  .sim-map-col {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
  .sim-map {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .map-reasoning {
    flex-shrink: 0;
    margin: 0;
    padding: 14px 16px;
    border-top: 1px solid var(--clr-border);
    border-radius: 0;
    border-left: none;
    border-right: none;
    border-bottom: none;
    box-shadow: none;
  }
  .map-reasoning-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .map-reasoning-head h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--clr-ink);
  }
  .map-reasoning-head .material-symbols-outlined {
    font-size: 20px;
    color: var(--clr-primary);
  }
  .map-reasoning-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--clr-muted);
  }
  .map-reasoning--empty {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--clr-muted);
    font-size: 12px;
    line-height: 1.45;
  }
  .map-reasoning--empty p {
    margin: 0;
  }
  .map-reasoning--empty .material-symbols-outlined {
    font-size: 22px;
    color: var(--clr-subtle);
    flex-shrink: 0;
  }
  @media (max-width: 900px) {
    .sim-page {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
    }
    .sim-panel {
      max-height: 42vh;
      border-right: none;
      border-bottom: 1px solid var(--clr-border);
    }
  }
</style>
