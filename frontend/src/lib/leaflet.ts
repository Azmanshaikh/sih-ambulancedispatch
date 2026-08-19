/** Leaflet default icons live in node_modules; Vite/Vercel will 404 /marker-icon.png otherwise. */
export function configureLeaflet(L: any) {
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: '/leaflet/marker-icon-2x.png',
    iconUrl: '/leaflet/marker-icon.png',
    shadowUrl: '/leaflet/marker-shadow.png',
  });
}
