<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiFetch, isMainAdmin } from '$lib/auth.svelte';
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

  function syncAmbulanceFromFleet() {
    const amb = ambulances.find((a) => a.id === selectedAmbulanceId);
    if (!amb) return;
    ambLat = amb.lat;
    ambLng = amb.lng;
    ambAddress = amb.label ? `${amb.label} (${amb.id})` : amb.id;
  }

  $effect(() => {
    if (selectedAmbulanceId && ambulances.length) syncAmbulanceFromFleet();
  });

  onMount(async () => {
    if (!isMainAdmin()) {
      goto('/', { replaceState: true });
      return;
    }
    await loadFleet();
  });

  async function loadFleet() {
    try {
      const res = await apiFetch('/tracking/fleet');
      if (!res.ok) return;
      const data = await res.json();
      ambulances = data.ambulances || [];
      if (!selectedAmbulanceId && ambulances.length) {
        const available = ambulances.find((a) => a.status === 'available') || ambulances[0];
        selectedAmbulanceId = available.id;
      }
      syncAmbulanceFromFleet();
    } catch {
      /* ignore */
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
      <span><strong>Admin Simulation</strong> — test routes only. No real dispatch.</span>
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
      <select class="nb-input" bind:value={selectedAmbulanceId}>
        {#each ambulances as amb}
          <option value={amb.id}>
            {amb.label || amb.id} · {amb.type_label || amb.ambulance_type} · {amb.status}
          </option>
        {/each}
      </select>
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

        <p class="reason">{result.reason}</p>
      </section>
    {/if}
  </aside>

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
  .sim-map {
    position: relative;
    min-height: 0;
    border-radius: 0;
    overflow: hidden;
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
