export const CORRIDOR_CALL_NUMBER = '8147621940';
export const CORRIDOR_TEL_HREF = 'tel:+918147621940';

const FALLBACK_NAMES = [
  'SI Ramesh Kumar',
  'SI Priya Nair',
  'SI Arjun Hegde',
  'SI Kavitha Rao',
  'SI Imran Pasha',
  'SI Deepak Gowda',
];

export function officerNameFor(post: { id?: string; officer_name?: string }) {
  if (post.officer_name) return post.officer_name;
  const id = String(post.id || '');
  let n = 0;
  for (let i = 0; i < id.length; i++) n = (n + id.charCodeAt(i) * (i + 1)) % FALLBACK_NAMES.length;
  return FALLBACK_NAMES[n];
}

export function postToMarker(post: any, canCall: boolean) {
  const rescue = post.kind === 'rescue';
  const kind = rescue ? 'rescue' : 'police';
  const name = officerNameFor(post);
  const phone = post.call_phone || CORRIDOR_CALL_NUMBER;
  const station = `${rescue ? 'Rescue' : 'Traffic'} · ${post.name}${post.alerted ? '<br/>ALERT SENT' : ''}`;
  return {
    position: [post.lat, post.lng] as [number, number],
    popup: station,
    type: post.alerted ? `${kind}_alert` : kind,
    officerName: name,
    phone: canCall ? phone : undefined,
    postId: post.id,
  };
}
