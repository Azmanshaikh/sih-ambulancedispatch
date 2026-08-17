<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';

  interface MapMarker {
    position: [number, number];
    popup?: string;
    type?: string;
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
  }: Props = $props();

  let mapElement: HTMLElement;
  let map: any;
  let L: any;
  let mapMarkers: any[] = [];
  let mapPolylines: any[] = [];
  let etaMarker: any = null;
  let lastRouteKey = '';

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

  function drawLine(points: [number, number][], color: string, halo: string) {
    const h = L.polyline(points, { color: halo, weight: 10, opacity: 0.28 }).addTo(map);
    const main = L.polyline(points, {
      color,
      weight: 5,
      opacity: 1,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    mapPolylines.push(h, main);
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
      hospital: makeIcon(HOSPITAL_SVG, 28, 'hosp-marker'),
      hospital_selected: makeIcon(HOSPITAL_SVG, 34, 'hosp-marker hosp-selected'),
      police: makeIcon(
        `<span style="font-size:18px;line-height:1;filter:grayscale(0.2)">👮</span>`,
        18
      ),
      police_alert: makeIcon(
        `<span style="font-size:20px;line-height:1">👮</span>`,
        20,
        'amb-marker'
      ),
      rescue: makeIcon(
        `<span style="font-size:18px;line-height:1">🛟</span>`,
        18
      ),
      rescue_alert: makeIcon(
        `<span style="font-size:20px;line-height:1">🛟</span>`,
        20,
        'amb-marker'
      ),
      default: makeIcon(`<span style="font-size:22px">📍</span>`, 22),
    };

    markers.forEach((marker) => {
      const m = L.marker(marker.position, {
        icon: ICONS[marker.type || 'default'] || ICONS.default,
        zIndexOffset: marker.type === 'hospital_selected' ? 600 : marker.type === 'incident' ? 500 : marker.type === 'ambulance' ? 700 : marker.type?.includes('alert') ? 800 : 0,
      }).addTo(map);
      if (marker.popup) {
        m.bindPopup(`<span style="font-weight:700;font-size:13px">${marker.popup}</span>`, {
          className: 'custom-popup',
        });
      }
      mapMarkers.push(m);
    });

    const red = pickupRoute && pickupRoute.length > 1 ? pickupRoute : route;
    const blue = dropRoute && dropRoute.length > 1 ? dropRoute : null;
    if (red && red.length > 1) drawLine(red, '#dc2626', '#7f1d1d');
    if (blue && blue.length > 1) drawLine(blue, '#2563eb', '#1e3a8a');
    extraRoutes.forEach((r) => {
      if (r.points && r.points.length > 1) {
        const color = r.color || '#38bdf8';
        drawLine(r.points, color, r.halo || color);
      }
    });

    const etaOn = (blue && blue.length > 1 ? blue : red) || [];
    if (etaLabel && etaOn.length > 1) {
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

    const key = `${routeKey(red)}|${routeKey(blue)}|${extraRoutes.length}`;
    if (fitRoute && key !== '||0' && key !== lastRouteKey) {
      lastRouteKey = key;
      try {
        const boundsPts = [
          ...(red || []),
          ...(blue || []),
          ...extraRoutes.flatMap((r) => r.points || []),
        ];
        if (boundsPts.length) map.fitBounds(boundsPts, { padding: [56, 56], maxZoom: 14 });
      } catch {
        /* ignore */
      }
    }
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
    if (map && L) updateMap();
  });
</script>

<div class="map-wrap {clazz}" style="width: 100%; height: 100%; position: relative;">
  <div bind:this={mapElement} {id} style="width: 100%; height: 100%; border-radius: inherit; z-index: 0;"></div>
  {#if showLegend && ((pickupRoute && pickupRoute.length > 1) || (dropRoute && dropRoute.length > 1) || (route && route.length > 1) || extraRoutes.length)}
    <div class="absolute bottom-3 left-3 z-[500] px-3 py-2 text-[10px] font-black uppercase tracking-widest" style="background:#fff;color:#111;border:3px solid #111;box-shadow:3px 3px 0 #111;">
      <p><span style="color:#FF2D2D">━</span> Ambulance → patient</p>
      <p><span style="color:#2E5BFF">━</span> Patient → hospital</p>
      <p><span style="color:#38bdf8">━</span> Other active corridor</p>
      <p><span style="color:#f59e0b">━</span> Shared / conflict</p>
      <p><span style="color:#a855f7">━</span> Rerouted unit</p>
    </div>
  {/if}
</div>
