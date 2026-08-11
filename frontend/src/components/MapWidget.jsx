import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';

// Setup custom Leaflet icons using Material Symbols or SVGs if required
// For now, we'll use default Leaflet markers or divIcons
const createCustomIcon = (iconClass) => L.divIcon({
  html: `<span class="material-symbols-outlined ${iconClass}" style="color: red;">local_hospital</span>`,
  className: 'custom-leaflet-icon',
  iconSize: [24, 24],
});

export default function MapWidget({ id, className, markers = [], route = null }) {
  // Fix for React Leaflet missing default icon
  useEffect(() => {
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    });
  }, []);

  return (
    <div className={`map-wrap ${className || ''}`} style={{ width: '100%', height: '100%' }}>
      <MapContainer
        id={id}
        center={[28.6139, 77.2090]} // Default center (New Delhi)
        zoom={13}
        style={{ width: '100%', height: '100%', borderRadius: 'inherit', zIndex: 0 }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution=""
        />
        {markers.map((marker, index) => (
          <Marker key={index} position={marker.position}>
            {marker.popup && <Popup>{marker.popup}</Popup>}
          </Marker>
        ))}
        {route && route.length > 0 && (
          <Polyline positions={route} pathOptions={{ color: '#3b82f6', weight: 5, opacity: 0.8 }} />
        )}
      </MapContainer>
    </div>
  );
}
