import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';

// ── Auto-fit map bounds to route + markers ───────────────────────────────────
function FitBounds({ route, markers }) {
  const map = useMap();
  useEffect(() => {
    const pts = [
      ...(route || []),
      ...(markers || []).map(m => m.position),
    ];
    if (pts.length > 1) {
      try { map.fitBounds(pts, { padding: [48, 48], maxZoom: 15 }); }
      catch (_) {}
    }
  }, [route, markers, map]);
  return null;
}

// ── Custom divIcon factory ────────────────────────────────────────────────────
const makeIcon = (emoji, size = 32) => L.divIcon({
  html: `<span style="font-size:${size}px;line-height:1;filter:drop-shadow(0 2px 6px rgba(0,0,0,.7))">${emoji}</span>`,
  className: '',
  iconSize: [size, size],
  iconAnchor: [size / 2, size / 2],
  popupAnchor: [0, -(size / 2) - 4],
});

const ICONS = {
  incident:  makeIcon('🚨', 34),
  ambulance: makeIcon('🚑', 32),
  default:   makeIcon('📍', 28),
};

export default function MapWidget({ id, className, markers = [], route = null }) {
  return (
    <div className={`map-wrap ${className || ''}`} style={{ width: '100%', height: '100%' }}>
      <MapContainer
        id={id}
        center={[28.6139, 77.2090]}
        zoom={13}
        style={{ width: '100%', height: '100%', borderRadius: 'inherit', zIndex: 0 }}
        zoomControl={false}
      >
        {/* ── Vibrant colorful tile layer (OpenStreetMap Bright) ── */}
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution=""
          maxZoom={19}
        />

        {/* ── Markers ── */}
        {markers.map((marker, index) => (
          <Marker
            key={index}
            position={marker.position}
            icon={ICONS[marker.type] || ICONS.default}
          >
            {marker.popup && (
              <Popup className="custom-popup">
                <span style={{ fontWeight: 700, fontSize: 13 }}>{marker.popup}</span>
              </Popup>
            )}
          </Marker>
        ))}

        {/* ── Route: glowing animated dashed line ── */}
        {route && route.length > 1 && (
          <>
            {/* Glow halo */}
            <Polyline
              positions={route}
              pathOptions={{ color: '#f97316', weight: 12, opacity: 0.25 }}
            />
            {/* Main route */}
            <Polyline
              positions={route}
              pathOptions={{
                color: '#ef4444',
                weight: 5,
                opacity: 0.95,
                dashArray: '14 8',
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          </>
        )}

        {/* ── Auto-fit bounds when route/markers change ── */}
        <FitBounds route={route} markers={markers} />
      </MapContainer>
    </div>
  );
}
