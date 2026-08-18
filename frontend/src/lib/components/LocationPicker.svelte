<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    lat?: number;
    lng?: number;
    onPin?: (lat: number, lng: number) => void;
  }

  let { lat = 13.1344, lng = 77.5693, onPin }: Props = $props();

  let mapElement: HTMLElement;
  let map: any;
  let marker: any;
  let L: any;

  function syncPin(nextLat: number, nextLng: number, fly = false) {
    if (!map || !L) return;
    const here = L.latLng(nextLat, nextLng);
    if (marker) marker.setLatLng(here);
    else {
      marker = L.marker(here, { draggable: true }).addTo(map);
      marker.on('dragend', () => {
        const p = marker.getLatLng();
        onPin?.(p.lat, p.lng);
      });
    }
    if (fly) map.flyTo(here, Math.max(map.getZoom(), 15), { duration: 0.6 });
  }

  onMount(async () => {
    if (!browser) return;
    L = (await import('leaflet')).default;
    await import('leaflet/dist/leaflet.css');
    map = L.map(mapElement, { zoomControl: true }).setView([lat, lng], 14);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '' }).addTo(map);
    syncPin(lat, lng);
    map.on('click', (e: any) => {
      onPin?.(e.latlng.lat, e.latlng.lng);
    });
    setTimeout(() => map?.invalidateSize(), 80);
    return () => map?.remove();
  });

  $effect(() => {
    const a = lat;
    const b = lng;
    if (!map || !L) return;
    const cur = marker?.getLatLng();
    const far = !cur || Math.hypot(cur.lat - a, cur.lng - b) > 0.002;
    syncPin(a, b, far);
  });
</script>

<div class="picker">
  <div bind:this={mapElement} class="picker-map"></div>
  <p class="hint">{t('request.pinHint')}</p>
</div>

<style>
  .picker {
    position: relative;
    width: 100%;
    border: 3px solid #111;
    background: #fff;
  }
  .picker-map {
    width: 100%;
    height: 260px;
  }
  .hint {
    margin: 0;
    padding: 8px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4B4B4B;
    border-top: 2px solid #111;
  }
</style>
