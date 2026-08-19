import { apiFetch } from '$lib/auth.svelte';

export type PlaceHit = {
  lat: number;
  lng: number;
  address: string;
  source?: string;
};

const BIAS_LAT = 13.1344;
const BIAS_LNG = 77.5693;

function photonAddress(props: Record<string, unknown>, fallback: string) {
  const parts = [
    props.name,
    [props.housenumber, props.street].filter(Boolean).join(' '),
    props.locality || props.city || props.district,
    props.county || props.state,
    props.postcode,
    props.country,
  ].filter((p): p is string => typeof p === 'string' && p.length > 0);
  return [...new Set(parts)].join(', ') || fallback;
}

async function photonForward(query: string): Promise<PlaceHit | null> {
  const url =
    `https://photon.komoot.io/api/?q=${encodeURIComponent(query)}` +
    `&limit=1&lat=${BIAS_LAT}&lon=${BIAS_LNG}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = await res.json();
  const feat = data?.features?.[0];
  if (!feat) return null;
  const [lng, lat] = feat.geometry.coordinates;
  return {
    lat,
    lng,
    address: photonAddress(feat.properties || {}, query),
    source: 'photon',
  };
}

async function photonReverse(lat: number, lng: number): Promise<PlaceHit | null> {
  const res = await fetch(`https://photon.komoot.io/reverse?lat=${lat}&lon=${lng}`);
  if (!res.ok) return null;
  const data = await res.json();
  const feat = data?.features?.[0];
  const fallback = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  if (!feat) return { lat, lng, address: fallback, source: 'coords' };
  return {
    lat,
    lng,
    address: photonAddress(feat.properties || {}, fallback),
    source: 'photon',
  };
}

async function backendGeocode(body: Record<string, unknown>): Promise<PlaceHit | null> {
  try {
    const res = await apiFetch('/tracking/geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data?.lat == null || data?.lng == null) return null;
    return {
      lat: Number(data.lat),
      lng: Number(data.lng),
      address: String(data.address || ''),
      source: data.source,
    };
  } catch {
    return null;
  }
}

export async function lookupAddress(query: string): Promise<PlaceHit | null> {
  const q = query.trim();
  if (!q) return null;
  return (await backendGeocode({ query: q })) || (await photonForward(q));
}

export async function lookupCoords(lat: number, lng: number): Promise<PlaceHit> {
  const fallback = { lat, lng, address: `${lat.toFixed(5)}, ${lng.toFixed(5)}`, source: 'coords' };
  return (await backendGeocode({ lat, lng })) || (await photonReverse(lat, lng)) || fallback;
}
