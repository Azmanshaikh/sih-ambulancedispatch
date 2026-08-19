export type PriorityBand = 'critical' | 'urgent' | 'stable';

const BANDS: PriorityBand[] = ['critical', 'urgent', 'stable'];

export function bandForMission(mission: any): PriorityBand | undefined {
  const band = mission?.priority_band;
  if (BANDS.includes(band)) return band;
  return undefined;
}

export function bandForAmbulance(id: string | undefined, missions: any[]): PriorityBand | undefined {
  if (!id) return undefined;
  const hit = missions.find((m) => m && m.ambulance_id === id);
  return bandForMission(hit);
}

export function bandColor(band?: PriorityBand | string | null) {
  if (band === 'critical') return '#FF2D2D';
  if (band === 'urgent') return '#FFD23F';
  if (band === 'stable') return '#22C55E';
  return '#111111';
}

export function bandFromScore(score: number): PriorityBand {
  if (score >= 8) return 'critical';
  if (score >= 4) return 'urgent';
  return 'stable';
}
