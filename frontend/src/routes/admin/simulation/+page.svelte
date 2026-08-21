<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiFetch, auth, isMainAdmin } from '$lib/auth.svelte';
  import MapWidget from '$lib/components/MapWidget.svelte';
  import { lookupAddress, lookupCoords } from '$lib/geocode';

  const BMSIT = { lat: 13.1344, lng: 77.5693, name: 'BMSIT College, Avalahalli, Yelahanka' };
  const PUTTENA = { lat: 13.12, lng: 77.575, name: 'Puttenahalli Junction, Yelahanka' };
  const A2_PICKUP_COLOR = '#ea580c';
  const A2_DROP_COLOR = '#0f766e';

  type PinMode = 'pickup' | 'destination' | 'ambulance' | 'traffic';
  type MissionSlot = 1 | 2;

  type TrafficHotspot = {
    key: string;
    lat: number;
    lng: number;
    taps: number;
    onRoute?: boolean;
    status?: string;
  };

  const TRAFFIC_DEG = 40 / 111_000;
  const TRAFFIC_MERGE_M = 90;

  function trafficLevel(taps: number) {
    if (taps <= 1) return 1;
    if (taps === 2) return 2;
    if (taps === 3) return 3;
    return 4;
  }

  function trafficLabel(taps: number) {
    return (['', 'Low', 'Moderate', 'High', 'Severe'] as const)[trafficLevel(taps)];
  }

  function haversineM(aLat: number, aLng: number, bLat: number, bLng: number) {
    const r = 6371000;
    const dLat = ((bLat - aLat) * Math.PI) / 180;
    const dLng = ((bLng - aLng) * Math.PI) / 180;
    const lat1 = (aLat * Math.PI) / 180;
    const lat2 = (bLat * Math.PI) / 180;
    const h =
      Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return 2 * r * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function snapTrafficCell(lat: number, lng: number) {
    const i = Math.round(lat / TRAFFIC_DEG);
    const j = Math.round(lng / TRAFFIC_DEG);
    return { key: `${i}:${j}`, lat: i * TRAFFIC_DEG, lng: j * TRAFFIC_DEG };
  }

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
  let trafficPoints = $state<TrafficHotspot[]>([]);
  let rerouteNotice = $state(false);
  let previousDropRoute = $state<[number, number][] | null>(null);
  let trafficTimer: ReturnType<typeof setTimeout> | null = null;
  let altTimer: ReturnType<typeof setTimeout> | null = null;
  let panelTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let hospitals = $state<any[]>([]);
  let assignedHospitalId = $state<number | null>(1);
  let emergencyCategory = $state('general_medical');
  let showAltCompare = $state(false);
  let showDecisionPanel = $state(false);
  let emergencyNotice = $state<any>(null);

  let showMission2 = $state(false);
  let activeMission = $state<MissionSlot>(1);
  let selectedAmbulanceId2 = $state('');
  let pickupLat2 = $state(PUTTENA.lat);
  let pickupLng2 = $state(PUTTENA.lng);
  let pickupAddress2 = $state(PUTTENA.name);
  let destLat2 = $state(13.0995);
  let destLng2 = $state(77.5963);
  let destAddress2 = $state('Sparsh Hospital, Yelahanka');
  let ambLat2 = $state<number | null>(null);
  let ambLng2 = $state<number | null>(null);
  let ambAddress2 = $state('');
  let assignedHospitalId2 = $state<number | null>(2);
  let emergencyCategory2 = $state('general_medical');
  let dangerRating = $state(5);
  let dangerRating2 = $state(5);

  const CATEGORIES = [
    { id: 'general_medical', label: 'General medical' },
    { id: 'cardiac', label: 'Cardiac' },
    { id: 'trauma', label: 'Trauma' },
    { id: 'pediatric', label: 'Pediatric' },
    { id: 'neurological', label: 'Neurological' },
    { id: 'respiratory', label: 'Respiratory' },
    { id: 'obstetric', label: 'Obstetric' },
  ];

  let pickupRoute = $derived(result?.pickup_route?.length ? result.pickup_route : null);
  let dropRoute = $derived(result?.route?.length ? result.route : null);
  let mission2 = $derived(result?.mission2 || null);
  let dual = $derived(result?.dual || null);

  let selectedAmbulance = $derived(ambulances.find((a) => a.id === selectedAmbulanceId));
  let selectedAmbulance2 = $derived(ambulances.find((a) => a.id === selectedAmbulanceId2));

  let markers = $derived.by(() => {
    const list: any[] = [];
    if (pickupLat && pickupLng) {
      list.push({
        position: [pickupLat, pickupLng] as [number, number],
        type: 'pickup',
        popup: `A1 pickup: ${pickupAddress}`,
      });
    }
    if (destLat && destLng && !assignedHospitalId) {
      list.push({
        position: [destLat, destLng] as [number, number],
        type: 'destination',
        popup: `A1 destination: ${destAddress}`,
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
        popup: `A1 ${selectedAmbulance?.label || selectedAmbulanceId} · ${ambAddress || 'Custom position'}`,
      });
    }
    if (showMission2) {
      if (pickupLat2 && pickupLng2) {
        list.push({
          position: [pickupLat2, pickupLng2] as [number, number],
          type: 'pickup',
          popup: `A2 pickup: ${pickupAddress2}`,
        });
      }
      if (destLat2 && destLng2 && !assignedHospitalId2) {
        list.push({
          position: [destLat2, destLng2] as [number, number],
          type: 'destination',
          popup: `A2 destination: ${destAddress2}`,
        });
      }
      const lat2 = ambLat2 ?? selectedAmbulance2?.lat;
      const lng2 = ambLng2 ?? selectedAmbulance2?.lng;
      if (lat2 != null && lng2 != null && selectedAmbulanceId2) {
        list.push({
          position: [lat2, lng2] as [number, number],
          type: 'ambulance',
          id: selectedAmbulanceId2,
          ambulanceId: selectedAmbulanceId2,
          popup: `A2 ${selectedAmbulance2?.label || selectedAmbulanceId2} · ${ambAddress2 || 'Custom position'}`,
        });
      }
    }
    for (const h of hospitals) {
      const selected = assignedHospitalId === h.id || (showMission2 && assignedHospitalId2 === h.id);
      if (pinMode !== 'destination' && !selected) continue;
      const specs = (h.specializations || []).join(', ');
      const sim = h.simulation ? 'Simulation · ' : '';
      const tag =
        assignedHospitalId === h.id && showMission2 && assignedHospitalId2 === h.id
          ? 'A1+A2 · '
          : assignedHospitalId === h.id
            ? 'A1 · '
            : showMission2 && assignedHospitalId2 === h.id
              ? 'A2 · '
              : '';
      list.push({
        position: [h.lat, h.lng] as [number, number],
        type: selected ? 'hospital_selected' : 'hospital',
        popup: `${tag}${sim}${h.name}<br>${specs || 'General'}<br>Beds ${h.available_beds}/${h.total_beds}${h.icu_available ? ` · ICU ${h.icu_beds}` : ''}<br>ER ${h.emergency_available ? 'open' : 'no'} · ${h.status || 'operational'}`,
      });
    }
    for (const p of trafficPoints) {
      const level = trafficLevel(p.taps);
      const affected =
        p.onRoute || p.status === 'on_route'
          ? 'Affects current route'
          : p.status === 'avoided'
            ? 'Congested corridor — avoided'
            : 'Nearby road cell';
      list.push({
        position: [p.lat, p.lng] as [number, number],
        type: 'traffic',
        trafficLevel: level,
        taps: p.taps,
        popup: `Simulation traffic · ${trafficLabel(p.taps)} (${p.taps} tap${p.taps === 1 ? '' : 's'}) · ${affected}`,
      });
    }
    return list;
  });

  let extraRoutes = $derived.by(() => {
    const list: any[] = [];
    if (mission2?.pickup_route?.length > 1) {
      list.push({
        points: mission2.pickup_route,
        color: A2_PICKUP_COLOR,
        kind: 'mission2-pickup',
      });
    }
    if (mission2?.route?.length > 1) {
      list.push({
        points: mission2.route,
        color: A2_DROP_COLOR,
        kind: 'mission2-drop',
      });
    }
    if (showAltCompare && result?.candidate_routes) {
      for (const alt of result.candidate_routes) {
        const rank = Number(alt.rank || 0);
        if (rank === 1 || !alt.coords?.length) continue;
        list.push({
          points: alt.coords,
          color: '#64748b',
          kind: 'compare',
        });
      }
    }
    if (showAltCompare && mission2?.candidate_routes) {
      for (const alt of mission2.candidate_routes) {
        const rank = Number(alt.rank || 0);
        if (rank === 1 || !alt.coords?.length) continue;
        list.push({
          points: alt.coords,
          color: '#94a3b8',
          kind: 'compare',
        });
      }
    }
    return list;
  });

  let etaLabel = $derived(
    dual?.active
      ? `A1 ${dual.a1_eta_minutes ?? '—'}m · A2 ${dual.a2_eta_minutes ?? '—'}m`
      : result?.eta_minutes != null
        ? `ETA ${result.eta_minutes} min`
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
      result.constraints?.traffic === 'simulated'
        ? result.constraints?.road_conditions ||
          'Simulated traffic raised road cost on affected NetworkX edges.'
        : result.constraints?.traffic === 'waived'
          ? 'Emergency corridor active — live delays waived unless simulation traffic is applied.'
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

  function syncAmbulance2FromFleet() {
    const amb = ambulances.find((a) => a.id === selectedAmbulanceId2);
    if (!amb) return;
    ambLat2 = amb.lat;
    ambLng2 = amb.lng;
    ambAddress2 = amb.label ? `${amb.label} (${amb.id})` : amb.id;
  }

  function selectAmbulance(id: string) {
    if (showMission2 && id === selectedAmbulanceId2) {
      error = 'Ambulance 1 must be a different unit from Ambulance 2.';
      return;
    }
    selectedAmbulanceId = id;
    error = '';
    syncAmbulanceFromFleet();
  }

  function selectAmbulance2(id: string) {
    if (id === selectedAmbulanceId) {
      error = 'Ambulance 2 must be a different unit from Ambulance 1.';
      return;
    }
    selectedAmbulanceId2 = id;
    error = '';
    syncAmbulance2FromFleet();
  }

  function selectHospital(id: number | null) {
    assignedHospitalId = id;
    const h = hospitals.find((row) => row.id === id);
    if (!h) return;
    destLat = h.lat;
    destLng = h.lng;
    destAddress = h.name;
  }

  function selectHospital2(id: number | null) {
    assignedHospitalId2 = id;
    const h = hospitals.find((row) => row.id === id);
    if (!h) return;
    destLat2 = h.lat;
    destLng2 = h.lng;
    destAddress2 = h.name;
  }

  function addSecondAmbulance() {
    showMission2 = true;
    activeMission = 2;
    error = '';
    const other =
      ambulances.find((a) => a.id !== selectedAmbulanceId && a.status === 'available') ||
      ambulances.find((a) => a.id !== selectedAmbulanceId);
    if (other) selectAmbulance2(other.id);
    if (assignedHospitalId2 && hospitals.some((h) => h.id === assignedHospitalId2)) {
      selectHospital2(assignedHospitalId2);
    }
  }

  function removeSecondAmbulance() {
    showMission2 = false;
    activeMission = 1;
    if (result?.dual) {
      result = null;
    }
  }

  function clearTimers() {
    if (trafficTimer) clearTimeout(trafficTimer);
    if (altTimer) clearTimeout(altTimer);
    if (panelTimer) clearTimeout(panelTimer);
    trafficTimer = null;
    altTimer = null;
    panelTimer = null;
  }

  function startCompareAndPanel() {
    if (altTimer) clearTimeout(altTimer);
    if (panelTimer) clearTimeout(panelTimer);
    const alts = [...(result?.candidate_routes || []), ...(result?.mission2?.candidate_routes || [])];
    showAltCompare = alts.filter((a: any) => a?.coords?.length > 1 && Number(a.rank || 0) !== 1).length > 0;
    showDecisionPanel = false;
    if (showAltCompare) {
      altTimer = setTimeout(() => {
        showAltCompare = false;
        showDecisionPanel = true;
        panelTimer = setTimeout(() => {
          showDecisionPanel = false;
        }, 15000);
      }, 3000);
    } else {
      showDecisionPanel = true;
      panelTimer = setTimeout(() => {
        showDecisionPanel = false;
      }, 15000);
    }
  }

  onMount(() => {
    void loadFleet();
    void loadHospitals();
    pollTimer = setInterval(() => {
      void pollMission();
    }, 2000);
  });

  onDestroy(() => {
    clearTimers();
    if (pollTimer) clearInterval(pollTimer);
  });

  $effect(() => {
    if (!auth.ready) return;
    if (!isMainAdmin()) goto('/', { replaceState: true });
  });

  async function loadHospitals() {
    try {
      const res = await apiFetch('/hospitals');
      if (!res.ok) return;
      hospitals = await res.json();
      if (assignedHospitalId && hospitals.some((h) => h.id === assignedHospitalId)) {
        selectHospital(assignedHospitalId);
      }
      if (assignedHospitalId2 && hospitals.some((h) => h.id === assignedHospitalId2)) {
        selectHospital2(assignedHospitalId2);
      }
    } catch {
      /* ignore */
    }
  }

  async function pollMission() {
    if (!selectedAmbulanceId || !result) return;
    try {
      const res = await apiFetch('/accounts/mission');
      if (!res.ok) return;
      const data = await res.json();
      const mission = data.mission;
      if (!mission || mission.ambulance_id !== selectedAmbulanceId) return;
      const reroute = mission.emergency_reroute;
      if (reroute?.changed && reroute.new_hospital_id && reroute.new_hospital_id !== assignedHospitalId) {
        assignedHospitalId = reroute.new_hospital_id;
        destAddress = reroute.new_hospital || destAddress;
        const h = hospitals.find((row) => row.id === assignedHospitalId);
        if (h) {
          destLat = h.lat;
          destLng = h.lng;
        } else if (mission.hospital?.lat) {
          destLat = mission.hospital.lat;
          destLng = mission.hospital.lng;
        }
        if (mission.drop_route?.length) {
          previousDropRoute = result?.route ? [...result.route] : previousDropRoute;
          result = {
            ...result,
            route: mission.drop_route,
            pickup_route: mission.pickup_route || result.pickup_route,
            eta_minutes: mission.eta_total_minutes ?? mission.eta_minutes ?? result.eta_minutes,
            hospital: mission.hospital,
            hospital_id: mission.hospital_id,
            hospital_name: mission.destination,
            reason: mission.reason || result.reason,
            decision: mission.decision || result.decision,
            candidate_routes: mission.candidate_routes || result.candidate_routes,
            hospital_rerouted: true,
          };
        }
        emergencyNotice = reroute;
        rerouteNotice = false;
        startCompareAndPanel();
      }
    } catch {
      /* ignore */
    }
  }

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
      if (showMission2) {
        if (!selectedAmbulanceId2) {
          const other =
            ambulances.find((a) => a.id !== selectedAmbulanceId && a.status === 'available') ||
            ambulances.find((a) => a.id !== selectedAmbulanceId);
          if (other) selectAmbulance2(other.id);
        } else {
          syncAmbulance2FromFleet();
        }
      }
    } catch {
      error = 'Could not load the fleet.';
    }
  }

  async function geocodePickup() {
    const is2 = activeMission === 2 && showMission2;
    const q = (is2 ? pickupAddress2 : pickupAddress).trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Pickup address not found.';
      return;
    }
    if (is2) {
      pickupLat2 = hit.lat;
      pickupLng2 = hit.lng;
      if (hit.address) pickupAddress2 = hit.address;
    } else {
      pickupLat = hit.lat;
      pickupLng = hit.lng;
      if (hit.address) pickupAddress = hit.address;
    }
    error = '';
  }

  async function geocodeDest() {
    const is2 = activeMission === 2 && showMission2;
    const q = (is2 ? destAddress2 : destAddress).trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Destination address not found.';
      return;
    }
    if (is2) {
      destLat2 = hit.lat;
      destLng2 = hit.lng;
      if (hit.address) destAddress2 = hit.address;
      assignedHospitalId2 = null;
    } else {
      destLat = hit.lat;
      destLng = hit.lng;
      if (hit.address) destAddress = hit.address;
      assignedHospitalId = null;
    }
    error = '';
  }

  async function geocodeAmbulance() {
    const is2 = activeMission === 2 && showMission2;
    const q = (is2 ? ambAddress2 : ambAddress).trim();
    if (!q) return;
    const hit = await lookupAddress(q);
    if (!hit) {
      error = 'Ambulance address not found.';
      return;
    }
    if (is2) {
      ambLat2 = hit.lat;
      ambLng2 = hit.lng;
      if (hit.address) ambAddress2 = hit.address;
    } else {
      ambLat = hit.lat;
      ambLng = hit.lng;
      if (hit.address) ambAddress = hit.address;
    }
    error = '';
  }

  async function onMapClick(lat: number, lng: number) {
    error = '';
    if (pinMode === 'traffic') {
      addTrafficTap(lat, lng);
      return;
    }
    if (pinMode === 'pickup') {
      if (activeMission === 2 && showMission2) {
        pickupLat2 = lat;
        pickupLng2 = lng;
        try {
          const hit = await lookupCoords(lat, lng);
          pickupAddress2 = hit.address;
        } catch {
          pickupAddress2 = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
      } else {
        pickupLat = lat;
        pickupLng = lng;
        try {
          const hit = await lookupCoords(lat, lng);
          pickupAddress = hit.address;
        } catch {
          pickupAddress = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
      }
    } else if (pinMode === 'destination') {
      const near = hospitals.find((h) => haversineM(lat, lng, h.lat, h.lng) <= 180);
      if (near) {
        if (activeMission === 2 && showMission2) selectHospital2(near.id);
        else selectHospital(near.id);
        return;
      }
      if (activeMission === 2 && showMission2) {
        assignedHospitalId2 = null;
        destLat2 = lat;
        destLng2 = lng;
        try {
          const hit = await lookupCoords(lat, lng);
          destAddress2 = hit.address;
        } catch {
          destAddress2 = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
      } else {
        assignedHospitalId = null;
        destLat = lat;
        destLng = lng;
        try {
          const hit = await lookupCoords(lat, lng);
          destAddress = hit.address;
        } catch {
          destAddress = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
      }
    } else if (activeMission === 2 && showMission2) {
      ambLat2 = lat;
      ambLng2 = lng;
      try {
        const hit = await lookupCoords(lat, lng);
        ambAddress2 = hit.address;
      } catch {
        ambAddress2 = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
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

  function nearAnyRoute(lat: number, lng: number) {
    const routes = [
      result?.pickup_route,
      result?.route,
      mission2?.pickup_route,
      mission2?.route,
    ].filter(Boolean) as [number, number][][];
    for (const route of routes) {
      for (const pt of route) {
        if (pt && haversineM(lat, lng, Number(pt[0]), Number(pt[1])) <= 120) return true;
      }
    }
    return false;
  }

  function addTrafficTap(lat: number, lng: number) {
    const snapped = snapTrafficCell(lat, lng);
    const existing = trafficPoints.find(
      (p) => p.key === snapped.key || haversineM(p.lat, p.lng, snapped.lat, snapped.lng) <= TRAFFIC_MERGE_M
    );
    if (existing) {
      existing.taps += 1;
      trafficPoints = [...trafficPoints];
    } else {
      trafficPoints = [...trafficPoints, { ...snapped, taps: 1 }];
    }
    rerouteNotice = false;
    if (result && nearAnyRoute(snapped.lat, snapped.lng)) {
      scheduleTrafficRecalc();
    }
  }

  function clearTraffic() {
    trafficPoints = [];
    previousDropRoute = null;
    rerouteNotice = false;
    pinMode = 'pickup';
    if (result) scheduleTrafficRecalc(true);
  }

  function scheduleTrafficRecalc(immediate = false) {
    if (!result) return;
    if (trafficTimer) clearTimeout(trafficTimer);
    if (immediate) {
      void calculateRoute({ fromTraffic: true });
      return;
    }
    trafficTimer = setTimeout(() => {
      void calculateRoute({ fromTraffic: true });
    }, 450);
  }

  async function calculateRoute(opts?: { fromTraffic?: boolean }) {
    if (!selectedAmbulanceId) {
      error = 'Select an ambulance from the fleet.';
      return;
    }
    if (ambLat == null || ambLng == null) {
      error = 'Set the ambulance location on the map or enter an address.';
      return;
    }
    if (showMission2) {
      if (!selectedAmbulanceId2) {
        error = 'Select a second ambulance, or remove Mission 2.';
        return;
      }
      if (selectedAmbulanceId2 === selectedAmbulanceId) {
        error = 'Ambulance 2 must be a different unit from Ambulance 1.';
        return;
      }
      if (ambLat2 == null || ambLng2 == null) {
        error = 'Set Ambulance 2 location on the map or enter an address.';
        return;
      }
    }
    calculating = true;
    error = '';
    const previousDrop = result?.route ? [...result.route] : null;
    const previousDropSig = result?.path_sig_drop || null;
    const previousPickupSig = result?.path_sig_pickup || null;
    const previousDropSig2 = mission2?.path_sig_drop || null;
    const previousPickupSig2 = mission2?.path_sig_pickup || null;
    if (!opts?.fromTraffic) {
      result = null;
      rerouteNotice = false;
      previousDropRoute = null;
    }
    try {
      const body: Record<string, unknown> = {
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
        traffic_points: trafficPoints.map((p) => ({ lat: p.lat, lng: p.lng, taps: p.taps })),
        previous_drop_sig: previousDropSig,
        previous_pickup_sig: previousPickupSig,
        hospital_id: assignedHospitalId,
        emergency_category: emergencyCategory,
        cardiac: emergencyCategory === 'cardiac',
        danger_rating: dangerRating,
      };
      if (showMission2) {
        body.mission2 = {
          pickup_lat: pickupLat2,
          pickup_lng: pickupLng2,
          pickup_address: pickupAddress2,
          dest_lat: destLat2,
          dest_lng: destLng2,
          dest_address: destAddress2,
          ambulance_id: selectedAmbulanceId2,
          ambulance_lat: ambLat2,
          ambulance_lng: ambLng2,
          ambulance_address: ambAddress2,
          hospital_id: assignedHospitalId2,
          emergency_category: emergencyCategory2,
          cardiac: emergencyCategory2 === 'cardiac',
          previous_drop_sig: previousDropSig2,
          previous_pickup_sig: previousPickupSig2,
          danger_rating: dangerRating2,
        };
      }
      const res = await apiFetch('/tracking/admin/simulate-route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || 'Route calculation failed.';
        return;
      }
      const next = data.data;
      const dualRerouted = Boolean(next?.dual?.rerouted || next?.rerouted || next?.mission2?.rerouted);
      if (opts?.fromTraffic && dualRerouted && previousDrop) {
        previousDropRoute = previousDrop;
        rerouteNotice = true;
      } else if (opts?.fromTraffic && !dualRerouted) {
        rerouteNotice = false;
      }
      result = next;
      if (next?.hospital_id) assignedHospitalId = next.hospital_id;
      if (next?.destination?.lat) {
        destLat = next.destination.lat;
        destLng = next.destination.lng;
        destAddress = next.destination.address || destAddress;
      }
      if (next?.mission2?.hospital_id) assignedHospitalId2 = next.mission2.hospital_id;
      if (next?.mission2?.destination?.lat) {
        destLat2 = next.mission2.destination.lat;
        destLng2 = next.mission2.destination.lng;
        destAddress2 = next.mission2.destination.address || destAddress2;
      }
      emergencyNotice =
        next?.emergency_reroute?.changed
          ? next.emergency_reroute
          : next?.mission2?.emergency_reroute?.changed
            ? next.mission2.emergency_reroute
            : emergencyNotice;
      startCompareAndPanel();
      const snapped = [...(next?.sim_traffic || []), ...(next?.mission2?.sim_traffic || [])];
      if (Array.isArray(snapped) && snapped.length) {
        trafficPoints = trafficPoints.map((p) => {
          const hit = snapped.find(
            (s: any) => haversineM(p.lat, p.lng, s.lat, s.lng) <= TRAFFIC_MERGE_M
          );
          return hit
            ? { ...p, onRoute: Boolean(hit.on_route), status: hit.status || (hit.on_route ? 'on_route' : 'nearby') }
            : p;
        });
      }
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
      <span><strong>Simulation</strong> — Main Admin route lab. Does not change live SOS dispatch. Calculating also sends the job to the driver of the selected unit(s).</span>
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
        <button class="btn traffic-mode-btn" class:btn-primary={pinMode === 'traffic'} onclick={() => (pinMode = 'traffic')}>
          Traffic
        </button>
      </div>
      <p class="hint">
        {#if pinMode === 'pickup'}
          Click the map to set {showMission2 ? `Mission ${activeMission} ` : ''}pickup, or enter an address below.
        {:else if pinMode === 'destination'}
          Click the map to set {showMission2 ? `Mission ${activeMission} ` : ''}destination, or enter an address below.
        {:else if pinMode === 'traffic'}
          Simulation: tap the map (or the current route) to add traffic. Repeat taps on the same road cell raise density — Low → Moderate → High → Severe. Both missions are re-optimized together.
        {:else}
          Click the map to place {showMission2 ? `Mission ${activeMission} ` : ''}the ambulance, or enter an address below.
        {/if}
      </p>
      {#if showMission2 && pinMode !== 'traffic'}
        <div class="mode-toggle">
          <button class="btn" class:btn-primary={activeMission === 1} onclick={() => (activeMission = 1)}>Pin Mission 1</button>
          <button class="btn" class:btn-primary={activeMission === 2} onclick={() => (activeMission = 2)}>Pin Mission 2</button>
        </div>
      {/if}
    </section>

    {#if !showMission2}
      <button class="btn btn-secondary" type="button" onclick={addSecondAmbulance}>+ Add Second Ambulance</button>
    {:else}
      <button class="btn" type="button" onclick={removeSecondAmbulance}>Remove Mission 2</button>
    {/if}

    <section class="sim-section mission-card" class:mission-active={activeMission === 1}>
      <p class="med-section-title">Mission 1 · Pickup → Ambulance → Hospital</p>
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
        <button class="btn btn-secondary" onclick={() => { activeMission = 1; void geocodeAmbulance(); }}>Locate</button>
      </div>
      {#if ambLat != null && ambLng != null}
        <p class="coords-hint">{ambLat.toFixed(5)}, {ambLng.toFixed(5)}</p>
      {/if}
      <p class="med-section-title">Pickup</p>
      <div class="field-row">
        <input class="nb-input" bind:value={pickupAddress} placeholder="Pickup address" />
        <button class="btn btn-secondary" onclick={() => { activeMission = 1; void geocodePickup(); }}>Locate</button>
      </div>
      <p class="med-section-title">Hospital / drop</p>
      <p class="hint">The ambulance routes to this assigned hospital. It is not replaced just because another site is closer.</p>
      <select class="nb-input" value={assignedHospitalId == null ? '' : String(assignedHospitalId)} onchange={(e) => {
        const v = (e.currentTarget as HTMLSelectElement).value;
        selectHospital(v ? Number(v) : null);
      }}>
        <option value="">Custom destination</option>
        {#each hospitals as h}
          <option value={String(h.id)}>{h.simulation ? 'SIM · ' : ''}{h.name}</option>
        {/each}
      </select>
      <div class="field-row">
        <input class="nb-input" bind:value={destAddress} placeholder="Drop / hospital address" />
        <button class="btn btn-secondary" onclick={() => { activeMission = 1; void geocodeDest(); }}>Locate</button>
      </div>
      <p class="med-section-title">Emergency type</p>
      <select class="nb-input" bind:value={emergencyCategory}>
        {#each CATEGORIES as c}
          <option value={c.id}>{c.label}</option>
        {/each}
      </select>
      <p class="med-section-title">Danger rating · {dangerRating}/10</p>
      <input
        class="rating-slider"
        type="range"
        min="1"
        max="10"
        step="1"
        bind:value={dangerRating}
        onchange={() => { if (result) scheduleTrafficRecalc(); }}
      />
      <p class="hint">At 8–10 the drop switches to the nearest eligible hospital and the route is recalculated.</p>
    </section>

    {#if showMission2}
    <section class="sim-section mission-card mission-card-2" class:mission-active={activeMission === 2}>
      <p class="med-section-title">Mission 2 · Pickup → Ambulance → Hospital</p>
      {#if ambulances.length}
        <div class="fleet-picker">
          {#each ambulances as amb}
            <button
              type="button"
              class="fleet-pick"
              class:active={selectedAmbulanceId2 === amb.id}
              onclick={() => selectAmbulance2(amb.id)}
            >
              <span class="fleet-pick-id">{amb.id}</span>
              <span class="fleet-pick-meta">{amb.label || amb.type_label || amb.ambulance_type}</span>
              <span class="fleet-pick-status">{amb.status}</span>
            </button>
          {/each}
        </div>
      {/if}
      <div class="field-row">
        <input class="nb-input" bind:value={ambAddress2} placeholder="Ambulance 2 location address" />
        <button class="btn btn-secondary" onclick={() => { activeMission = 2; void geocodeAmbulance(); }}>Locate</button>
      </div>
      {#if ambLat2 != null && ambLng2 != null}
        <p class="coords-hint">{ambLat2.toFixed(5)}, {ambLng2.toFixed(5)}</p>
      {/if}
      <p class="med-section-title">Pickup</p>
      <div class="field-row">
        <input class="nb-input" bind:value={pickupAddress2} placeholder="Second pickup address" />
        <button class="btn btn-secondary" onclick={() => { activeMission = 2; void geocodePickup(); }}>Locate</button>
      </div>
      <p class="med-section-title">Hospital / drop</p>
      <select class="nb-input" value={assignedHospitalId2 == null ? '' : String(assignedHospitalId2)} onchange={(e) => {
        const v = (e.currentTarget as HTMLSelectElement).value;
        selectHospital2(v ? Number(v) : null);
      }}>
        <option value="">Custom destination</option>
        {#each hospitals as h}
          <option value={String(h.id)}>{h.simulation ? 'SIM · ' : ''}{h.name}</option>
        {/each}
      </select>
      <div class="field-row">
        <input class="nb-input" bind:value={destAddress2} placeholder="Second drop / hospital address" />
        <button class="btn btn-secondary" onclick={() => { activeMission = 2; void geocodeDest(); }}>Locate</button>
      </div>
      <p class="med-section-title">Emergency type</p>
      <select class="nb-input" bind:value={emergencyCategory2}>
        {#each CATEGORIES as c}
          <option value={c.id}>{c.label}</option>
        {/each}
      </select>
      <p class="med-section-title">Danger rating · {dangerRating2}/10</p>
      <input
        class="rating-slider"
        type="range"
        min="1"
        max="10"
        step="1"
        bind:value={dangerRating2}
        onchange={() => { if (result) scheduleTrafficRecalc(); }}
      />
      <p class="hint">At 8–10 Ambulance 2 reroutes to the nearest eligible hospital.</p>
    </section>
    {/if}

    <section class="sim-section">
      <p class="med-section-title">Simulation traffic</p>
      <p class="hint">Taps snap to the nearest 40 m road cell. Density raises NetworkX travel cost and can reroute one or both ambulances after combined re-optimization.</p>
      <div class="mode-toggle">
        <button class="btn" class:btn-primary={pinMode === 'traffic'} onclick={() => (pinMode = 'traffic')}>
          Place traffic
        </button>
        <button class="btn btn-secondary" disabled={!trafficPoints.length} onclick={clearTraffic}>
          Clear traffic
        </button>
      </div>
      {#if trafficPoints.length}
        <ul class="traffic-list">
          {#each trafficPoints as p}
            <li>
              <span class="traffic-swatch lv-{trafficLevel(p.taps)}"></span>
              <span>
                {trafficLabel(p.taps)} · {p.taps} tap{p.taps === 1 ? '' : 's'}
                {#if p.onRoute || p.status === 'on_route'}<em> · on route</em>
                {:else if p.status === 'avoided'}<em> · avoided</em>{/if}
              </span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="coords-hint">No simulated hotspots yet.</p>
      {/if}
    </section>

    <button class="btn btn-primary calc-btn" disabled={calculating} onclick={() => calculateRoute()}>
      {calculating ? 'Calculating…' : showMission2 ? 'Calculate Combined Routes' : 'Calculate Fastest Route'}
    </button>

    {#if error}
      <p class="error-msg">{error}</p>
    {/if}

    {#if result}
      <section class="sim-section results">
        <p class="med-section-title">{dual?.active ? 'Combined simulation results' : 'Route results'}</p>
        {#if dual?.active}
          <div class="dual-summary">
            <p>A1 {dual.a1_eta_minutes} min · A2 {dual.a2_eta_minutes} min</p>
            <p class="hint" style="margin-top:4px;">Combined · starvation {dual.traffic_starvation === 'prevented' ? 'prevented' : dual.traffic_starvation} · corridor {dual.corridor_conflict}</p>
          </div>
        {/if}
        <div class="med-stat-grid">
          <div class="med-stat">
            <div class="label">{dual?.active ? 'A1 ETA' : 'Total ETA'}</div>
            <div class="value">{result.eta_minutes} min</div>
          </div>
          {#if dual?.active}
          <div class="med-stat">
            <div class="label">A2 ETA</div>
            <div class="value">{dual.a2_eta_minutes} min</div>
          </div>
          {/if}
          <div class="med-stat">
            <div class="label">{dual?.active ? 'A1 distance' : 'Distance'}</div>
            <div class="value">{result.total_distance_km} km</div>
          </div>
          {#if !dual?.active}
          <div class="med-stat">
            <div class="label">Pickup leg</div>
            <div class="value">{result.pickup_minutes} min</div>
          </div>
          <div class="med-stat">
            <div class="label">Transport leg</div>
            <div class="value">{result.transport_minutes} min</div>
          </div>
          {/if}
        </div>

        <div class="constraint-list">
          <span class="nb-chip chip-info">{result.constraints?.engine || 'routing'}</span>
          {#if result.is_raining}
            <span class="nb-chip chip-warning">Rain — ETA adjusted</span>
          {:else}
            <span class="nb-chip chip-success">Clear weather</span>
          {/if}
          <span class="nb-chip">{result.constraints?.road_conditions || 'Traffic assessed'}</span>
          {#if result.constraints?.traffic === 'simulated'}
            <span class="nb-chip chip-warning">Simulation traffic</span>
          {/if}
          {#if result.rerouted}
            <span class="nb-chip chip-info">Route updated</span>
          {/if}
          {#if result.emergency_reroute?.changed || result.hospital_rerouted}
            <span class="nb-chip chip-warning">Nearest hospital (rating {result.emergency_reroute?.danger_rating ?? dangerRating})</span>
          {/if}
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
        extraRoutes={extraRoutes}
        {etaLabel}
        selectedAmbulanceId={selectedAmbulanceId}
        showLegend={false}
        allowDrive={false}
        fitRoute={true}
        onMapClick={onMapClick}
      />
      {#if pickupRoute || dropRoute || extraRoutes.length}
        <div class="sim-legend" aria-hidden="true">
          <p><span class="lg-a1p"></span> A1 pickup</p>
          <p><span class="lg-a1d"></span> A1 hospital</p>
          {#if showMission2}
            <p><span class="lg-a2p"></span> A2 pickup</p>
            <p><span class="lg-a2d"></span> A2 hospital</p>
          {/if}
        </div>
      {/if}
      {#if rerouteNotice}
        <div class="reroute-banner" role="status">
          <strong>Route Updated</strong>
          {#if dual?.active}
            Simulated traffic changed corridor cost. Combined optimization reassigned one or both ambulances.
          {:else}
            Traffic detected ahead. A faster alternative route has been selected.
          {/if}
        </div>
      {/if}
      {#if emergencyNotice?.changed}
        <div class="emergency-banner" role="status">
          <strong>Emergency Reroute</strong>
          Danger Rating: {emergencyNotice.danger_rating}/10<br />
          Previous Hospital: {emergencyNotice.previous_hospital}<br />
          New Hospital: {emergencyNotice.new_hospital}<br />
          Reason: {emergencyNotice.reason}
        </div>
      {/if}
      {#if showAltCompare}
        <div class="compare-chip" role="status">Comparing alternatives</div>
      {/if}
      {#if showDecisionPanel && result?.decision}
        <aside class="decision-panel" role="dialog" aria-label="Route decision">
          <button type="button" class="decision-close" onclick={() => { showDecisionPanel = false; if (panelTimer) clearTimeout(panelTimer); }}>×</button>
          {#if dual?.active && result.decision?.a1}
            <p class="decision-kicker">Multi-ambulance route decision · Simulation</p>
            <p class="decision-pair">🚑 Ambulance 1: {result.decision.a1.route} — {result.decision.a1.eta_minutes} min</p>
            <p class="decision-pair">🚑 Ambulance 2: {result.decision.a2.route} — {result.decision.a2.eta_minutes} min</p>
            <p class="decision-kicker">Why this combination?</p>
            <ul>
              {#each result.decision.why || result.decision.conditions_met || [] as item}
                <li>{item}</li>
              {/each}
            </ul>
            <dl>
              <div><dt>Traffic starvation</dt><dd>{result.decision.traffic_starvation}</dd></div>
              <div><dt>Shared corridor</dt><dd>{result.decision.corridor_conflict}</dd></div>
              <div><dt>Combined strategy</dt><dd>{result.decision.combined_strategy}</dd></div>
            </dl>
            {#if dual.combinations?.length}
              <p class="decision-kicker">Combinations scored</p>
              <ul class="combo-list">
                {#each dual.combinations as combo}
                  <li class:combo-win={combo.selected}>
                    {combo.selected ? 'Selected · ' : ''}{combo.label}
                    · A1 {combo.eta1_minutes} min / A2 {combo.eta2_minutes} min
                    · overlap {combo.overlap_km} km
                    {#if combo.lost_reason}<span class="combo-lost">{combo.lost_reason}</span>{/if}
                  </li>
                {/each}
              </ul>
            {/if}
            <p class="decision-final">{result.decision.decision}</p>
          {:else}
            <p class="decision-kicker">Route decision</p>
            <dl>
              <div><dt>Selected Route</dt><dd>{result.decision.selected_route}</dd></div>
              <div><dt>Algorithm</dt><dd>{result.decision.algorithm}</dd></div>
              <div><dt>ETA</dt><dd>{result.decision.eta_minutes} min</dd></div>
              <div><dt>Distance</dt><dd>{result.decision.distance_km} km</dd></div>
              <div><dt>Traffic</dt><dd>{result.decision.traffic}</dd></div>
              <div><dt>Road conditions</dt><dd>{result.decision.road_conditions}</dd></div>
            </dl>
            <p class="decision-kicker">Conditions met</p>
            <ul>
              {#each result.decision.conditions_met || [] as item}
                <li>{item}</li>
              {/each}
            </ul>
            <p class="decision-final">{result.decision.decision}</p>
          {/if}
        </aside>
      {/if}
    </div>
    {#if result}
      <div class="map-reasoning nb-card">
        <div class="map-reasoning-head">
          <span class="material-symbols-outlined">route</span>
          <h3>Why this route?</h3>
        </div>
        <p class="map-reasoning-text">{result.reason || routeSummary}</p>
        {#if dual?.active}
          <p class="map-reasoning-text dual-why-head">Why this combination?</p>
          <ul class="dual-why">
            {#each dual.why || [] as item}
              <li>{item}</li>
            {/each}
          </ul>
        {/if}
      </div>
    {:else}
      <div class="map-reasoning map-reasoning--empty nb-card">
        <span class="material-symbols-outlined">info</span>
        <p>Set pickup, ambulance, and assigned hospital, then calculate to see the top routes and why Route 1 wins. Optionally add a second ambulance to jointly optimize both missions.</p>
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
  .mission-card {
    padding: 10px;
    border: 2px solid #111;
    background: #fff;
    box-shadow: 3px 3px 0 #111;
  }
  .mission-card-2 {
    box-shadow: 3px 3px 0 #0f766e;
  }
  .mission-active {
    outline: 3px solid var(--clr-primary);
  }
  .rating-slider {
    width: 100%;
    accent-color: #dc2626;
  }
  .sim-legend {
    position: absolute;
    bottom: 12px;
    left: 12px;
    z-index: 500;
    background: #fff;
    border: 2px solid #111;
    padding: 6px 8px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    line-height: 1.45;
  }
  .sim-legend p {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .sim-legend span {
    width: 16px;
    height: 3px;
    display: inline-block;
  }
  .lg-a1p { background: #dc2626; }
  .lg-a1d { background: #2563eb; }
  .lg-a2p { background: #ea580c; }
  .lg-a2d { background: #0f766e; }
  .dual-summary {
    margin: 0;
    padding: 8px 10px;
    background: #fff7ed;
    border: 2px solid #111;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.45;
  }
  .dual-summary p {
    margin: 0;
  }
  .dual-map-chip {
    position: absolute;
    bottom: 48px;
    left: 12px;
    z-index: 600;
    max-width: min(420px, calc(100% - 24px));
    background: #fff;
    color: #0F172A;
    font-size: 11px;
    font-weight: 800;
    line-height: 1.35;
    padding: 8px 10px;
    border: 3px solid #111;
    box-shadow: 3px 3px 0 #0f766e;
  }
  .decision-pair {
    margin: 0 0 6px;
    font-weight: 700;
  }
  .combo-list {
    list-style: none;
    padding: 0;
    margin: 0 0 10px;
  }
  .combo-list li {
    margin-bottom: 6px;
    font-size: 11px;
  }
  .combo-win {
    font-weight: 800;
  }
  .combo-lost {
    display: block;
    color: #64748b;
    font-weight: 600;
  }
  .dual-why {
    margin: 0;
    padding-left: 18px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--clr-muted);
  }
  .dual-why-head {
    margin: 10px 0 6px !important;
    font-weight: 800;
    color: var(--clr-ink) !important;
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
  .traffic-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .traffic-list li {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--clr-ink);
  }
  .traffic-list em {
    font-style: normal;
    color: var(--clr-muted);
  }
  .traffic-swatch {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid #111;
    flex-shrink: 0;
  }
  .traffic-swatch.lv-1 { background: #86efac; }
  .traffic-swatch.lv-2 { background: #fde047; }
  .traffic-swatch.lv-3 { background: #fb923c; }
  .traffic-swatch.lv-4 { background: #ef4444; }
  .reroute-banner {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 600;
    width: min(420px, calc(100% - 24px));
    padding: 10px 14px;
    background: #fff7ed;
    color: #0F172A;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
    font-size: 13px;
    line-height: 1.4;
  }
  .reroute-banner strong {
    display: block;
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 2px;
  }
  .emergency-banner {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 610;
    width: min(340px, calc(100% - 24px));
    padding: 10px 14px;
    background: #fee2e2;
    color: #0F172A;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
    font-size: 12px;
    line-height: 1.45;
  }
  .emergency-banner strong {
    display: block;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .compare-chip {
    position: absolute;
    bottom: 14px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 600;
    background: #111;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 8px 12px;
    border: 3px solid #111;
    box-shadow: 3px 3px 0 #2563eb;
  }
  .decision-panel {
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 620;
    width: min(340px, calc(100% - 24px));
    max-height: calc(100% - 24px);
    overflow-y: auto;
    background: #fff;
    color: #0F172A;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
    padding: 12px 14px 14px;
    font-size: 12px;
    line-height: 1.4;
  }
  .decision-close {
    position: absolute;
    top: 6px;
    right: 8px;
    border: 2px solid #111;
    background: #fff;
    width: 24px;
    height: 24px;
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
  }
  .decision-kicker {
    margin: 0 0 8px;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .decision-panel dl {
    margin: 0 0 10px;
  }
  .decision-panel dl div {
    display: grid;
    grid-template-columns: 92px 1fr;
    gap: 6px;
    margin-bottom: 4px;
  }
  .decision-panel dt {
    font-weight: 800;
    color: #64748b;
  }
  .decision-panel dd {
    margin: 0;
    font-weight: 600;
  }
  .decision-panel ul {
    margin: 0 0 10px;
    padding-left: 16px;
  }
  .decision-final {
    margin: 0;
    font-weight: 700;
  }
  .fleet-picker {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 220px;
    overflow-y: auto;
    padding-bottom: 4px;
  }
  .mission-card .fleet-picker {
    max-height: 132px;
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
