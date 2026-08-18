<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { t } from '$lib/i18n.svelte';

  interface MapMarker {
    position: [number, number];
    popup?: string;
    type?: string;
    id?: string;
    ambulanceId?: string;
    hasMission?: boolean;
    officerName?: string;
    phone?: string;
    postId?: string;
  }

  interface ExtraRoute {
    points: [number, number][];
    color?: string;
    halo?: string;
    kind?: string;
    label?: string;
  }

  interface Props {
    id?: string;
    clazz?: string;
    markers?: MapMarker[];
    route?: [number, number][] | null;
    pickupRoute?: [number, number][] | null;
    dropRoute?: [number, number][] | null;
    extraRoutes?: ExtraRoute[];
    etaLabel?: string;
    center?: [number, number];
    zoom?: number;
    fitRoute?: boolean;
    showLegend?: boolean;
    selectedAmbulanceId?: string;
    officerCallEnabled?: boolean;
    onSelectAmbulance?: (id: string) => void;
  }

  const BMSIT: [number, number] = [13.1344, 77.5693];

  let {
    id = 'map',
    clazz = '',
    markers = [],
    route = null,
    pickupRoute = null,
    dropRoute = null,
    extraRoutes = [],
    etaLabel = '',
    center = BMSIT,
    zoom = 13,
    fitRoute = true,
    showLegend = false,
    selectedAmbulanceId = '',
    officerCallEnabled = false,
    onSelectAmbulance,
  }: Props = $props();

  let mapElement: HTMLElement;
  let map: any;
  let L: any;
  let mapMarkers: any[] = [];
  let mapPolylines: any[] = [];
  let etaMarker: any = null;
  let lastRouteKey = '';
  let overview: { center: any; zoom: number } | null = null;
  let pendingNav = false;

  let navMode = $state(false);
  let heading = $state(0);
  let headingSmoothed = 0;
  /** Screen Y of the vehicle / map yaw pivot (0–1). Must match --nav-pivot. */
  const NAV_PIVOT = 0.68;
  let navHint = $state({
    icon: 'navigation',
    dist: '',
    text: 'Start drive',
    remain: '',
    eta: '',
    arrive: '',
  });

  function cardinal(deg: number) {
    const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const n = ((deg % 360) + 360) % 360;
    return dirs[Math.round(n / 45) % 8];
  }

  /** Bearing to a point ~look-ahead meters along the remaining path. */
  function headingAlong(path: [number, number][]) {
    if (!path || path.length < 2) return ((headingSmoothed % 360) + 360) % 360;
    const lookAhead = 40;
    let acc = 0;
    let i = 0;
    for (; i < path.length - 1; i++) {
      acc += meters(path[i], path[i + 1]);
      if (acc >= lookAhead) break;
    }
    return bearingDeg(path[0], path[Math.min(i + 1, path.length - 1)]);
  }

  const HOSPITAL_SVG = `
    <div class="hosp-building">
      <svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="8" width="22" height="17" rx="1.5" fill="#1d4ed8" stroke="#fff" stroke-width="1.4"/>
        <rect x="10" y="3" width="8" height="6" fill="#1d4ed8" stroke="#fff" stroke-width="1.2"/>
        <rect x="12.2" y="12" width="3.6" height="11" fill="#fff"/>
        <rect x="8.5" y="15.4" width="11" height="3.6" fill="#fff"/>
      </svg>
    </div>`;

  function makeIcon(html: string, size = 28, className = '') {
    return L.divIcon({
      html,
      className,
      iconSize: [size, size],
      iconAnchor: [size / 2, size],
      popupAnchor: [0, -size],
    });
  }

  function routeKey(r: [number, number][] | null | undefined) {
    if (!r || r.length < 2) return '';
    const a = r[0];
    const b = r[r.length - 1];
    return `${r.length}:${a[0]},${a[1]}:${b[0]},${b[1]}`;
  }

  function dist2(a: [number, number], b: [number, number]) {
    const dlat = a[0] - b[0];
    const dlng = a[1] - b[1];
    return dlat * dlat + dlng * dlng;
  }

  function meters(a: [number, number], b: [number, number]) {
    const R = 6371000;
    const dLat = ((b[0] - a[0]) * Math.PI) / 180;
    const dLng = ((b[1] - a[1]) * Math.PI) / 180;
    const lat1 = (a[0] * Math.PI) / 180;
    const lat2 = (b[0] * Math.PI) / 180;
    const h =
      Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function bearingDeg(a: [number, number], b: [number, number]) {
    const lat1 = (a[0] * Math.PI) / 180;
    const lat2 = (b[0] * Math.PI) / 180;
    const dLng = ((b[1] - a[1]) * Math.PI) / 180;
    const y = Math.sin(dLng) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
    return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  }

  function pathLength(path: [number, number][]) {
    let s = 0;
    for (let i = 0; i < path.length - 1; i++) s += meters(path[i], path[i + 1]);
    return s;
  }

  function formatDist(m: number) {
    if (m >= 1000) return `${(m / 1000).toFixed(1)} km`;
    return `${Math.max(10, Math.round(m / 10) * 10)} m`;
  }

  function closestOnPath(path: [number, number][], pos: [number, number]) {
    let best = { dist2: Infinity, idx: 0, point: path[0] as [number, number], t: 0 };
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i];
      const b = path[i + 1];
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const len2 = dx * dx + dy * dy || 1e-12;
      let t = ((pos[0] - a[0]) * dx + (pos[1] - a[1]) * dy) / len2;
      t = Math.max(0, Math.min(1, t));
      const point: [number, number] = [a[0] + t * dx, a[1] + t * dy];
      const d = dist2(pos, point);
      if (d < best.dist2) best = { dist2: d, idx: i, point, t };
    }
    return best;
  }

  function ambulancePositions() {
    return markers
      .filter((m) => m.type === 'ambulance' && m.position)
      .map((m) => m.position as [number, number]);
  }

  function markerAmbulanceId(m: MapMarker) {
    return m.ambulanceId || m.id || '';
  }

  function ambulancePosById(id: string | undefined) {
    if (!id) return null;
    const hit = markers.find((m) => m.type === 'ambulance' && markerAmbulanceId(m) === id);
    return hit?.position ? (hit.position as [number, number]) : null;
  }

  function popupHtml(marker: MapMarker) {
    const isOfficer = Boolean(marker.type && (marker.type.startsWith('police') || marker.type.startsWith('rescue')));
    if (officerCallEnabled && isOfficer && marker.phone) {
      const tel = marker.phone.replace(/\D/g, '');
      const href = tel.length === 10 ? `tel:+91${tel}` : `tel:${tel}`;
      const name = marker.officerName || 'SI Duty Officer';
      return `<div class="officer-card">
        <p class="officer-name">${name}</p>
        <p class="officer-station">${marker.popup || ''}</p>
        <a class="officer-call" href="${href}">Call ${marker.phone}</a>
      </div>`;
    }
    return `<span style="font-weight:700;font-size:13px">${marker.popup || ''}</span>`;
  }

  function nearestAmbulance(path: [number, number][] | null | undefined) {
    const ambs = ambulancePositions();
    if (!ambs.length || !path || path.length < 2) return null;
    let bestPos: [number, number] | null = null;
    let bestD = Infinity;
    for (const pos of ambs) {
      const hit = closestOnPath(path, pos);
      if (hit.dist2 < bestD) {
        bestD = hit.dist2;
        bestPos = pos;
      }
    }
    return bestPos;
  }

  /** Keep only the road still ahead of the unit so traveled red/blue vanishes. */
  function remainingPath(
    path: [number, number][] | null | undefined,
    from: [number, number] | null
  ): [number, number][] {
    if (!path || path.length < 2) return [];
    if (!from) return path;
    const hit = closestOnPath(path, from);
    if (hit.dist2 > 0.0025 * 0.0025) return path;
    const rest = path.slice(hit.idx + 1);
    if (!rest.length) return [];
    const last = path[path.length - 1];
    if (dist2(from, last) < 0.00018 * 0.00018) return [];
    if (dist2(from, rest[0]) < 1e-14) return rest;
    return [from, ...rest];
  }

  function traveledPath(full: [number, number][] | null | undefined, remaining: [number, number][]) {
    if (!full || full.length < 2 || !remaining.length) return [];
    const hit = closestOnPath(full, remaining[0]);
    const done = full.slice(0, hit.idx + 1);
    if (!done.length) return [];
    if (dist2(done[done.length - 1], remaining[0]) < 1e-14) return done;
    return [...done, remaining[0]];
  }

  function setHeading(target: number) {
    let d = target - headingSmoothed;
    while (d > 180) d -= 360;
    while (d < -180) d += 360;
    headingSmoothed += d;
    heading = headingSmoothed;
  }

  function guidance(path: [number, number][], dest: string) {
    if (!path || path.length < 2) {
      return { icon: 'navigation', dist: '', text: 'Waiting for route', remain: '', heading: headingAlong(path) };
    }
    const remainM = pathLength(path);
    const startBear = headingAlong(path);
    let toTurn = 0;
    for (let i = 0; i < path.length - 1; i++) {
      toTurn += meters(path[i], path[i + 1]);
      const b = bearingDeg(path[i], path[i + 1]);
      let delta = b - startBear;
      while (delta > 180) delta -= 360;
      while (delta < -180) delta += 360;
      if (Math.abs(delta) > 38 && toTurn > 28) {
        const sharp = Math.abs(delta) > 120 ? 'sharp ' : Math.abs(delta) < 55 ? 'slight ' : '';
        const left = delta < 0;
        return {
          icon: Math.abs(delta) > 120 ? (left ? 'u_turn_left' : 'u_turn_right') : left ? 'turn_left' : 'turn_right',
          dist: formatDist(toTurn),
          text: `Turn ${sharp}${left ? 'left' : 'right'}`,
          remain: formatDist(remainM),
          heading: startBear,
        };
      }
      if (toTurn > 450) break;
    }
    return {
      icon: remainM < 80 ? 'flag' : 'straight',
      dist: formatDist(remainM),
      text: remainM < 80 ? `Arriving · ${dest}` : `Continue to ${dest}`,
      remain: formatDist(remainM),
      heading: startBear,
    };
  }

  function clipRoutes() {
    const redFull = pickupRoute && pickupRoute.length > 1 ? pickupRoute : route;
    const blueFull = dropRoute && dropRoute.length > 1 ? dropRoute : null;
    const selectedPos = ambulancePosById(selectedAmbulanceId);
    const ambOnRed = selectedPos || nearestAmbulance(redFull);
    const ambOnBlue = selectedPos || nearestAmbulance(blueFull);
    let red = remainingPath(redFull, ambOnRed);
    let blue = remainingPath(blueFull, ambOnBlue);
    let onDrop = false;
    if (redFull && redFull.length > 1 && blueFull && blueFull.length > 1 && ambOnRed) {
      const dPickup = closestOnPath(redFull, ambOnRed).dist2;
      const dDrop = closestOnPath(blueFull, ambOnBlue || ambOnRed).dist2;
      if (dDrop < dPickup) {
        red = [];
        onDrop = true;
      } else {
        blue = blueFull;
      }
    }
    const follow = selectedPos || ambOnRed || ambOnBlue || ambulancePositions()[0] || null;
    const remaining = red.length > 1 ? red : blue.length > 1 ? blue : [];
    return { redFull, blueFull, red, blue, follow, remaining, onDrop, dest: onDrop || !red.length ? 'hospital' : 'patient' };
  }

  function drawLine(points: [number, number][], color: string, halo: string, drive = false) {
    const casing = L.polyline(points, {
      color: drive ? '#fff' : halo,
      weight: drive ? 16 : 10,
      opacity: drive ? 0.95 : 0.28,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    const main = L.polyline(points, {
      color,
      weight: drive ? 9 : 5,
      opacity: 1,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    mapPolylines.push(casing, main);
  }

  function applyNavCamera(latlng: [number, number]) {
    if (!map || !L) return;
    const z = 17;
    const p = map.project(L.latLng(latlng[0], latlng[1]), z);
    // Place the unit at NAV_PIVOT (below screen center) so the road stays under the vehicle.
    p.y -= map.getSize().y * (NAV_PIVOT - 0.5);
    map.setView(map.unproject(p, z), z, { animate: true, duration: 0.45 });
  }

  function updateHint(drive: ReturnType<typeof clipRoutes>) {
    const g = guidance(drive.remaining, drive.dest);
    const mins = Number.parseInt(String(etaLabel).replace(/[^\d]/g, ''), 10);
    const eta = etaLabel || (Number.isFinite(mins) ? `${mins} min` : '—');
    let arrive = '';
    if (Number.isFinite(mins) && mins > 0) {
      const t = new Date(Date.now() + mins * 60000);
      arrive = t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }
    navHint = {
      icon: g.icon,
      dist: g.dist,
      text: g.text,
      remain: g.remain,
      eta,
      arrive,
    };
    if (drive.remaining.length > 1) setHeading(g.heading);
  }

  function updateMap() {
    if (!map || !L) return;

    mapMarkers.forEach((m) => m.remove());
    mapMarkers = [];
    mapPolylines.forEach((p) => p.remove());
    mapPolylines = [];
    if (etaMarker) {
      etaMarker.remove();
      etaMarker = null;
    }

    const ICONS: Record<string, any> = {
      incident: makeIcon(
        `<span class="user-icon" style="font-size:28px;line-height:1">📍</span>`,
        28
      ),
      ambulance: makeIcon(
        `<span class="amb-icon" style="font-size:22px;line-height:1">🚑</span>`,
        22,
        'amb-marker'
      ),
      ambulance_selected: makeIcon(
        `<span class="amb-icon" style="font-size:26px;line-height:1">🚑</span>`,
        26,
        'amb-marker amb-selected'
      ),
      hospital: makeIcon(HOSPITAL_SVG, 28, 'hosp-marker'),
      hospital_selected: makeIcon(HOSPITAL_SVG, 34, 'hosp-marker hosp-selected'),
      police: makeIcon(
        `<span style="font-size:18px;line-height:1;filter:grayscale(0.2)">👮</span>`,
        18,
        'officer-marker'
      ),
      police_alert: makeIcon(
        `<span style="font-size:20px;line-height:1">👮</span>`,
        20,
        'amb-marker officer-marker'
      ),
      rescue: makeIcon(
        `<span style="font-size:18px;line-height:1">🛟</span>`,
        18,
        'officer-marker'
      ),
      rescue_alert: makeIcon(
        `<span style="font-size:20px;line-height:1">🛟</span>`,
        20,
        'amb-marker officer-marker'
      ),
      default: makeIcon(`<span style="font-size:22px">📍</span>`, 22),
    };

    const drive = clipRoutes();
    const shown = navMode
      ? markers.filter((m) => {
          const t = m.type || '';
          if (t === 'incident' || t === 'hospital_selected') return true;
          if (t.startsWith('police') || t.startsWith('rescue')) return true;
          if (t === 'ambulance' && drive.follow) {
            return dist2(m.position, drive.follow) < 1e-12;
          }
          return false;
        })
      : markers;

    shown.forEach((marker) => {
      if (navMode && marker.type === 'ambulance') return;
      const ambId = markerAmbulanceId(marker);
      const selectedAmb = marker.type === 'ambulance' && ambId && ambId === selectedAmbulanceId;
      const iconKey = selectedAmb ? 'ambulance_selected' : marker.type || 'default';
      const m = L.marker(marker.position, {
        icon: ICONS[iconKey] || ICONS.default,
        zIndexOffset:
          selectedAmb
            ? 900
            : marker.type === 'hospital_selected'
              ? 600
              : marker.type === 'incident'
                ? 500
                : marker.type === 'ambulance'
                  ? 700
                  : marker.type?.includes('alert')
                    ? 800
                    : 0,
      }).addTo(map);
      const isOfficer = Boolean(marker.type && (marker.type.startsWith('police') || marker.type.startsWith('rescue')));
      if (marker.hasMission && ambId) {
        m.on('click', () => {
          pendingNav = true;
          onSelectAmbulance?.(ambId);
        });
      } else if (marker.popup || (officerCallEnabled && isOfficer && marker.phone)) {
        m.bindPopup(popupHtml(marker), { className: 'custom-popup', maxWidth: 260 });
      }
      if (marker.type === 'ambulance' && ambId && !marker.hasMission) {
        m.on('click', () => onSelectAmbulance?.(ambId));
      }
      mapMarkers.push(m);
    });

    if (navMode) {
      const doneRed = traveledPath(drive.redFull, drive.red);
      const doneBlue = traveledPath(drive.blueFull, drive.blue);
      if (doneRed.length > 1) drawLine(doneRed, '#94a3b8', '#cbd5e1', true);
      if (doneBlue.length > 1) drawLine(doneBlue, '#94a3b8', '#cbd5e1', true);
    }

    if (drive.red.length > 1) drawLine(drive.red, '#dc2626', '#7f1d1d', navMode);
    if (drive.blue.length > 1) drawLine(drive.blue, navMode ? '#1a73e8' : '#2563eb', '#1e3a8a', navMode);

    if (!navMode) {
      extraRoutes.forEach((r) => {
        if (r.points && r.points.length > 1) {
          const color = r.color || '#38bdf8';
          const clip = r.kind === 'pickup' || r.kind === 'drop';
          const pts = clip ? remainingPath(r.points, nearestAmbulance(r.points)) : r.points;
          if (pts.length > 1) drawLine(pts, color, r.halo || color);
        }
      });
    }

    const etaOn = (drive.blue.length > 1 ? drive.blue : drive.red) || [];
    if (!navMode && etaLabel && etaOn.length > 1) {
      const mid = etaOn[Math.floor(etaOn.length / 2)];
      etaMarker = L.marker(mid, {
        icon: L.divIcon({
          className: 'eta-badge-wrap',
          html: `<div class="eta-badge">⏱ ${etaLabel}</div>`,
          iconSize: [120, 28],
          iconAnchor: [60, 14],
        }),
        interactive: false,
        zIndexOffset: 1000,
      }).addTo(map);
    }

    const key = `${routeKey(drive.redFull)}|${routeKey(drive.blueFull)}|${extraRoutes.length}`;
    if (fitRoute && !navMode && key !== '||0' && key !== lastRouteKey) {
      lastRouteKey = key;
      try {
        const boundsPts = [
          ...(drive.redFull || []),
          ...(drive.blueFull || []),
          ...extraRoutes.flatMap((r) => r.points || []),
        ];
        if (boundsPts.length) map.fitBounds(boundsPts, { padding: [56, 56], maxZoom: 14 });
      } catch {
        /* ignore */
      }
    }

    updateHint(drive);
    if (navMode && drive.follow) applyNavCamera(drive.follow);
    else if (navMode && drive.remaining.length) applyNavCamera(drive.remaining[0]);
  }

  function setMapInteractive(on: boolean) {
    if (!map) return;
    if (on) {
      map.dragging.enable();
      map.scrollWheelZoom.enable();
      map.touchZoom.enable();
      map.doubleClickZoom.enable();
    } else {
      map.dragging.disable();
      map.scrollWheelZoom.disable();
      map.touchZoom.disable();
      map.doubleClickZoom.disable();
    }
  }

  function startNav() {
    if (!map) return;
    overview = { center: map.getCenter(), zoom: map.getZoom() };
    navMode = true;
    setMapInteractive(false);
    updateMap();
  }

  function stopNav() {
    navMode = false;
    setMapInteractive(true);
    headingSmoothed = 0;
    heading = 0;
    lastRouteKey = '';
    if (overview) {
      map.setView(overview.center, overview.zoom, { animate: true });
      overview = null;
    }
    updateMap();
  }

  function toggleNav() {
    if (navMode) stopNav();
    else startNav();
  }

  onMount(async () => {
    if (!browser) return;
    L = (await import('leaflet')).default;
    await import('leaflet/dist/leaflet.css');

    map = L.map(mapElement, { zoomControl: false }).setView(center, zoom);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '',
    }).addTo(map);
    updateMap();

    return () => map?.remove();
  });

  $effect(() => {
    const _m = markers;
    const _r = route;
    const _p = pickupRoute;
    const _d = dropRoute;
    const _x = extraRoutes;
    const _e = etaLabel;
    const _n = navMode;
    const _s = selectedAmbulanceId;
    if (map && L) {
      updateMap();
      const ready =
        (pickupRoute && pickupRoute.length > 1) ||
        (dropRoute && dropRoute.length > 1) ||
        (route && route.length > 1);
      if (pendingNav && ready) {
        pendingNav = false;
        if (!navMode) queueMicrotask(() => startNav());
      }
    }
  });

  let hasRoute = $derived(
    (pickupRoute && pickupRoute.length > 1) ||
      (dropRoute && dropRoute.length > 1) ||
      (route && route.length > 1)
  );
</script>

<div
  class="map-wrap {clazz}"
  class:is-nav={navMode}
  style="width: 100%; height: 100%; position: relative; --nav-pivot: {NAV_PIVOT * 100}%;"
>
  <div class="nav-stage">
    <div class="nav-yaw" style={navMode ? `transform: rotate(${-heading}deg)` : ''}>
      <div bind:this={mapElement} {id} style="width: 100%; height: 100%; border-radius: inherit; z-index: 0;"></div>
    </div>
    {#if navMode}
      <div class="nav-vehicle" aria-hidden="true">
        <svg class="nav-beam" viewBox="0 0 80 90" width="86" height="96">
          <polygon points="40,78 8,2 72,2" fill="#1a73e8" opacity="0.28" />
        </svg>
        <svg class="nav-amb" viewBox="0 0 72 96" width="52" height="70">
          <ellipse cx="36" cy="82" rx="18" ry="7" fill="#000" opacity="0.32" />
          <rect x="16" y="40" width="6" height="13" rx="2" fill="#111" />
          <rect x="50" y="40" width="6" height="13" rx="2" fill="#111" />
          <rect x="16" y="64" width="6" height="13" rx="2" fill="#111" />
          <rect x="50" y="64" width="6" height="13" rx="2" fill="#111" />
          <rect x="20" y="34" width="32" height="48" rx="8" fill="#f8fafc" stroke="#111" stroke-width="2.4" />
          <path d="M24 38h24v11c0 2.2-1.8 4-4 4H28c-2.2 0-4-1.8-4-4V38Z" fill="#1e3a5f" />
          <rect x="26" y="35.5" width="10" height="3.4" rx="1" fill="#dc2626" />
          <rect x="36" y="35.5" width="10" height="3.4" rx="1" fill="#2563eb" />
          <rect x="20" y="56" width="32" height="7" fill="#dc2626" />
          <rect x="33.5" y="65" width="5" height="12" fill="#dc2626" />
          <rect x="30" y="68.2" width="12" height="5" fill="#dc2626" />
          <rect x="24" y="74" width="24" height="5" rx="1.4" fill="#334155" />
        </svg>
      </div>
    {/if}
  </div>

  {#if navMode}
    <div class="nav-sky"></div>
    <div class="nav-banner">
      <span class="material-symbols-outlined nav-turn">{navHint.icon}</span>
      <div>
        <p class="nav-dist">{navHint.dist || '—'}</p>
        <p class="nav-text">{navHint.text}</p>
      </div>
    </div>
    <div class="nav-compass" title="Heading {cardinal(heading)}">
      <div class="nav-compass-disc" style="transform: rotate({-heading}deg)">
        <span class="nav-compass-n">N</span>
        <span class="nav-compass-needle"></span>
      </div>
      <span class="nav-compass-label">{cardinal(heading)}</span>
    </div>
    <div class="nav-sheet">
      <div class="nav-stat">
        <strong>{navHint.eta || '—'}</strong>
        <span>{t('map.eta')}</span>
      </div>
      <div class="nav-stat">
        <strong>{navHint.remain || '—'}</strong>
        <span>{t('map.left')}</span>
      </div>
      <div class="nav-stat">
        <strong>{navHint.arrive || '—'}</strong>
        <span>{t('map.arrive')}</span>
      </div>
      <button type="button" class="nav-exit" onclick={stopNav}>{t('map.exit')}</button>
    </div>
  {/if}

  {#if showLegend && !navMode && ((pickupRoute && pickupRoute.length > 1) || (dropRoute && dropRoute.length > 1) || (route && route.length > 1) || extraRoutes.length)}
    <div class="absolute bottom-3 left-3 z-[500] px-3 py-2 text-[10px] font-black uppercase tracking-widest" style="background:#fff;color:#111;border:3px solid #111;box-shadow:3px 3px 0 #111;">
      <p><span style="color:#FF2D2D">━</span> {t('map.ambPatient')}</p>
      <p><span style="color:#2E5BFF">━</span> {t('map.patientHospital')}</p>
      <p><span style="color:#38bdf8">━</span> {t('map.otherCorridor')}</p>
      <p><span style="color:#f59e0b">━</span> {t('map.shared')}</p>
      <p><span style="color:#a855f7">━</span> {t('map.rerouted')}</p>
    </div>
  {/if}

  {#if !navMode && hasRoute}
    <button
      type="button"
      class="nav-go"
      class:ready={hasRoute}
      onclick={toggleNav}
      aria-label={t('map.drive')}
    >
      <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1;">navigation</span>
      <span>{t('map.drive')}</span>
    </button>
  {/if}
</div>

<style>
  .map-wrap {
    overflow: hidden;
  }
  .nav-stage,
  .nav-yaw {
    width: 100%;
    height: 100%;
    transform-origin: 50% var(--nav-pivot, 68%);
  }
  .nav-stage {
    position: relative;
  }
  .is-nav .nav-stage {
    transform: perspective(1100px) rotateX(42deg) scale(1.28);
    transform-origin: 50% 86%;
    will-change: transform;
    z-index: 1;
  }
  .is-nav .nav-yaw {
    transition: transform 0.45s ease-out;
    will-change: transform;
  }
  .is-nav :global(.leaflet-container) {
    background: #cfdcc8;
  }
  .nav-sky {
    pointer-events: none;
    position: absolute;
    inset: 0 0 58%;
    z-index: 420;
    background: linear-gradient(180deg, rgba(135, 186, 230, 0.5), transparent);
  }
  .nav-banner {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 620;
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: min(78%, 340px);
    max-width: calc(100% - 24px);
    padding: 10px 16px;
    background: #1a73e8;
    color: #fff;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
  }
  .nav-turn {
    font-size: 36px;
    line-height: 1;
  }
  .nav-dist {
    font-family: 'Rajdhani', sans-serif;
    font-weight: 800;
    font-size: 22px;
    letter-spacing: 0.04em;
    line-height: 1;
  }
  .nav-text {
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.92;
    margin-top: 2px;
  }
  .nav-vehicle {
    position: absolute;
    left: 50%;
    top: var(--nav-pivot, 68%);
    z-index: 610;
    width: 86px;
    height: 96px;
    transform: translate(-50%, -58%);
    pointer-events: none;
    filter: drop-shadow(0 3px 0 #111);
  }
  .nav-beam {
    position: absolute;
    left: 50%;
    bottom: 28px;
    transform: translateX(-50%);
    mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.85), transparent);
  }
  .nav-amb {
    position: absolute;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
  }
  .nav-compass {
    position: absolute;
    top: 86px;
    right: 12px;
    z-index: 620;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    pointer-events: none;
  }
  .nav-compass-disc {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: #fff;
    border: 3px solid #111;
    box-shadow: 3px 3px 0 #111;
    position: relative;
    transition: transform 0.45s ease-out;
  }
  .nav-compass-n {
    position: absolute;
    top: 3px;
    left: 50%;
    transform: translateX(-50%);
    font-family: 'Rajdhani', sans-serif;
    font-size: 11px;
    font-weight: 800;
    color: #dc2626;
    line-height: 1;
  }
  .nav-compass-needle {
    position: absolute;
    left: 50%;
    top: 14px;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 14px solid #dc2626;
    transform: translateX(-50%);
  }
  .nav-compass-label {
    font-family: 'Rajdhani', sans-serif;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #111;
    background: #fff;
    border: 2px solid #111;
    padding: 1px 6px;
    box-shadow: 2px 2px 0 #111;
  }
  .nav-sheet {
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 12px;
    z-index: 620;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: #fff;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
  }
  .nav-stat {
    flex: 1;
    min-width: 0;
  }
  .nav-stat strong {
    display: block;
    font-family: 'Rajdhani', sans-serif;
    font-size: 16px;
    font-weight: 800;
    line-height: 1.1;
  }
  .nav-stat span {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #4B4B4B;
  }
  .nav-exit {
    border: 3px solid #111;
    background: #FF2D2D;
    color: #fff;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 8px 12px;
    cursor: pointer;
    box-shadow: 3px 3px 0 #111;
  }
  .nav-go {
    position: absolute;
    right: 12px;
    bottom: 12px;
    z-index: 620;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    width: 64px;
    height: 64px;
    background: #1a73e8;
    color: #fff;
    border: 3px solid #111;
    box-shadow: 4px 4px 0 #111;
    cursor: pointer;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 800;
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }
  .nav-go:hover {
    transform: translate(-2px, -2px);
    box-shadow: 6px 6px 0 #111;
  }
  .nav-go:active {
    transform: translate(3px, 3px);
    box-shadow: 0 0 0 #111;
  }
  .nav-go :global(.material-symbols-outlined) {
    font-size: 26px;
    line-height: 1;
  }
  .nav-go:not(.ready) {
    background: #2E5BFF;
  }
  :global(.amb-marker) {
    cursor: pointer;
  }
  :global(.officer-marker) {
    cursor: pointer;
  }
  :global(.amb-selected .amb-icon) {
    filter: drop-shadow(0 0 6px #FF2D2D) drop-shadow(0 0 2px #111);
  }
  :global(.custom-popup .officer-card) {
    min-width: 160px;
  }
  :global(.custom-popup .officer-name) {
    margin: 0;
    font-weight: 800;
    font-size: 14px;
    color: #111;
  }
  :global(.custom-popup .officer-station) {
    margin: 4px 0 8px;
    font-size: 11px;
    font-weight: 600;
    color: #4B4B4B;
    line-height: 1.35;
  }
  :global(.custom-popup .officer-call) {
    display: block;
    padding: 8px 10px;
    background: #FF2D2D;
    color: #fff !important;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    text-decoration: none;
    text-align: center;
    border: 3px solid #111;
    box-shadow: 2px 2px 0 #111;
  }
</style>
