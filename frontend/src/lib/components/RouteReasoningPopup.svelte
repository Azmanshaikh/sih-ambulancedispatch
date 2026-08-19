<script lang="ts">
  import { onDestroy } from 'svelte';

  interface Props {
    decision?: any;
    visible?: boolean;
    onDismiss?: () => void;
  }

  let { decision = null, visible = true, onDismiss }: Props = $props();

  let isDismissed = $state(false);
  let remainingMs = $state(10000);
  const DURATION_MS = 10000;
  let timerId: any = null;
  let lastDecisionKey = $state('');

  // Extract a unique identifier for this decision to detect new dispatches
  let currentKey = $derived.by(() => {
    if (!decision) return '';
    const amb = decision.ambulance_id || decision.ambulance?.id || '';
    const hosp = decision.hospital_name || decision.hospital?.name || decision.hospital?.id || '';
    const eta = decision.eta_minutes ?? decision.eta_seconds ?? '';
    const phase = decision.phase || '';
    const priority = decision.priority ?? '';
    const reason = decision.reason || '';
    return `${amb}|${hosp}|${eta}|${phase}|${priority}|${reason.slice(0, 30)}`;
  });

  // Check if we have valid route decision data
  let hasValidRoute = $derived.by(() => {
    if (!decision) return false;
    const hasAmb = Boolean(decision.ambulance_id || decision.ambulance);
    const hasHosp = Boolean(decision.hospital_name || decision.hospital);
    const hasRoute = Boolean(
      (decision.pickup_route && decision.pickup_route.length > 1) ||
      (decision.drop_route && decision.drop_route.length > 1) ||
      (decision.route && decision.route.length > 1)
    );
    const notComplete = decision.phase !== 'complete';
    return (hasAmb || hasHosp || hasRoute) && notComplete;
  });

  function startCountdown() {
    stopCountdown();
    remainingMs = DURATION_MS;
    const interval = 100;
    timerId = setInterval(() => {
      remainingMs = Math.max(0, remainingMs - interval);
      if (remainingMs <= 0) {
        stopCountdown();
        isDismissed = true;
        onDismiss?.();
      }
    }, interval);
  }

  function stopCountdown() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function dismissManual() {
    stopCountdown();
    isDismissed = true;
    onDismiss?.();
  }

  // React to new decision changes
  $effect(() => {
    if (currentKey && currentKey !== lastDecisionKey && hasValidRoute) {
      lastDecisionKey = currentKey;
      isDismissed = false;
      startCountdown();
    } else if (!hasValidRoute) {
      stopCountdown();
      isDismissed = true;
    }
  });

  onDestroy(() => {
    stopCountdown();
  });

  // Format decision factors from actual data
  let ambulanceLabel = $derived.by(() => {
    const amb = decision?.ambulance;
    const id = decision?.ambulance_id || amb?.id || 'Unit';
    const type = decision?.assigned_ambulance_type_label || amb?.type_label || decision?.assigned_ambulance_type || amb?.ambulance_type || 'ALS';
    return { id, type };
  });

  let ambulanceEligibility = $derived.by(() => {
    const status = decision?.match_status;
    const fallback = decision?.fallback_reason;
    if (fallback) return `Safest available unit · ${fallback}`;
    if (status === 'exact') return 'Nearest eligible unit with exact capability match';
    if (status === 'fallback') return 'Nearest available unit (capability fallback)';
    return 'Nearest available eligible unit';
  });

  let hospitalInfo = $derived.by(() => {
    const hosp = decision?.hospital;
    const name = decision?.hospital_name || hosp?.name || 'Assigned Hospital';
    const specs = Array.isArray(hosp?.specializations) && hosp.specializations.length
      ? hosp.specializations.slice(0, 3).join(', ')
      : 'Emergency Department';
    const beds = hosp?.available_beds != null ? `${hosp.available_beds} beds available` : null;
    return { name, specs, beds };
  });

  let etaInfo = $derived.by(() => {
    const total = decision?.eta_minutes ?? (decision?.eta_seconds ? Math.round(decision.eta_seconds / 60) : null);
    const pickup = decision?.pickup_minutes ?? null;
    const transport = decision?.transport_minutes ?? null;
    return { total, pickup, transport };
  });

  let trafficInfo = $derived.by(() => {
    const constraints = decision?.constraints;
    if (constraints?.traffic === 'waived' || constraints?.routing === 'emergency-shortest') {
      return 'Emergency Green Corridor (signals prioritized)';
    }
    if (constraints?.traffic) {
      return `${constraints.traffic} traffic model`;
    }
    return 'Signal-preempted green corridor';
  });

  let roadInfo = $derived.by(() => {
    const conflict = decision?.conflict?.reason || decision?.conflictReason;
    if (conflict) return `Conflict resolved: ${conflict}`;
    return 'No major road blockage · clear corridor';
  });

  let weatherInfo = $derived.by(() => {
    if (decision?.is_raining) return 'Rain active (+8% safety margin)';
    return null;
  });

  let priorityInfo = $derived.by(() => {
    const p = decision?.priority ?? 1;
    const label = decision?.priority_label || 'Standard';
    const cat = decision?.emergency_category;
    return { p, label, cat };
  });

  let progressPercent = $derived(Math.max(0, Math.min(100, (remainingMs / DURATION_MS) * 100)));
  let secondsRemaining = $derived(Math.ceil(remainingMs / 1000));
</script>

{#if visible && hasValidRoute && !isDismissed}
  <div
    class="route-reasoning-popup absolute bottom-4 right-4 z-30 max-w-[340px] w-[calc(100%-2rem)] sm:w-[340px] bg-white text-black pointer-events-auto animate-fade-slide-up"
    style="border: 3px solid #111; box-shadow: 5px 5px 0 #111;"
    role="region"
    aria-label="Route Decision Reasoning"
  >
    <!-- Header -->
    <div class="bg-[#FFD23F] px-3 py-2 border-b-[3px] border-black flex items-center justify-between gap-2 select-none">
      <div class="flex items-center gap-1.5 min-w-0">
        <span class="w-2.5 h-2.5 bg-[#FF2D2D] rounded-full border border-black animate-pulse shrink-0"></span>
        <span class="font-['Orbitron',sans-serif] font-black text-[11px] tracking-wider uppercase text-black truncate">
          Why This Route?
        </span>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span class="text-[9px] font-mono font-black bg-black/10 px-1.5 py-0.5 rounded border border-black/30">
          {secondsRemaining}s
        </span>
        <button
          type="button"
          onclick={dismissManual}
          class="w-6 h-6 bg-black text-white hover:bg-[#FF2D2D] hover:text-white flex items-center justify-center font-black text-sm transition-colors border border-black rounded-none cursor-pointer"
          title="Dismiss (or auto-closes in 10s)"
          aria-label="Dismiss route reasoning popup"
        >
          ×
        </button>
      </div>
    </div>

    <!-- Content Body -->
    <div class="p-3 space-y-2 text-[11px] leading-snug">
      <!-- Tagline -->
      <div class="bg-[#FFE8D6] px-2 py-1.5 border-[2px] border-black text-[10px] font-black text-black uppercase tracking-wide flex items-center gap-1.5">
        <span class="text-[#DC2626]">⚡</span>
        <span class="truncate">Decision: Fastest Eligible Emergency Route</span>
      </div>

      <!-- Factors List -->
      <div class="space-y-1.5 pt-0.5">
        <!-- Ambulance -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">🚑</span>
          <div class="min-w-0 flex-1">
            <div class="font-black text-black">
              {ambulanceLabel.id}
              <span class="font-bold text-[#DC2626] ml-1">· {ambulanceLabel.type}</span>
            </div>
            <div class="text-[10px] text-[#4B4B4B] font-semibold truncate">
              {ambulanceEligibility}
            </div>
          </div>
        </div>

        <!-- Hospital -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">🏥</span>
          <div class="min-w-0 flex-1">
            <div class="font-black text-black truncate">{hospitalInfo.name}</div>
            <div class="text-[10px] text-[#4B4B4B] font-semibold truncate">
              {hospitalInfo.specs}{hospitalInfo.beds ? ` · ${hospitalInfo.beds}` : ''}
            </div>
          </div>
        </div>

        <!-- ETA -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">⏱</span>
          <div class="min-w-0 flex-1">
            <span class="font-black text-black">ETA: {etaInfo.total != null ? `${etaInfo.total} min` : 'Calculating...'}</span>
            {#if etaInfo.pickup != null || etaInfo.transport != null}
              <span class="text-[10px] text-[#4B4B4B] ml-1 font-semibold">
                ({etaInfo.pickup ?? '—'}m pickup + {etaInfo.transport ?? '—'}m transit)
              </span>
            {/if}
          </div>
        </div>

        <!-- Traffic & Signal Preemption -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">🚦</span>
          <div class="min-w-0 flex-1 text-[10px] text-[#374151] font-semibold truncate">
            {trafficInfo}
          </div>
        </div>

        <!-- Road & Conflicts -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">🚧</span>
          <div class="min-w-0 flex-1 text-[10px] text-[#374151] font-semibold truncate">
            {roadInfo}
          </div>
        </div>

        <!-- Weather if applicable -->
        {#if weatherInfo}
          <div class="flex items-start gap-2">
            <span class="text-sm shrink-0 leading-none mt-0.5">🌧️</span>
            <div class="min-w-0 flex-1 text-[10px] text-[#2563EB] font-bold truncate">
              {weatherInfo}
            </div>
          </div>
        {/if}

        <!-- Priority -->
        <div class="flex items-start gap-2">
          <span class="text-sm shrink-0 leading-none mt-0.5">❤️</span>
          <div class="min-w-0 flex-1 font-black text-black text-[10px]">
            Priority: Level {priorityInfo.p} ({priorityInfo.label})
            {#if priorityInfo.cat && priorityInfo.cat !== 'general_medical'}
              <span class="text-[#DC2626] font-bold"> · {priorityInfo.cat}</span>
            {/if}
          </div>
        </div>
      </div>

      <!-- Why Summary Callout -->
      <div class="mt-2 bg-[#F3F4F6] p-2 border-[2px] border-black text-[10px] text-[#1F2937] leading-relaxed">
        <strong class="font-black text-black">Why:</strong>
        {#if decision?.reason}
          <span class="ml-1 text-[#374151]">{decision.reason}</span>
        {:else}
          <span class="ml-1 text-[#374151]">Lowest expected response time while satisfying clinical capabilities and corridor constraints.</span>
        {/if}
      </div>
    </div>

    <!-- Progress Timer Bar -->
    <div class="w-full bg-gray-200 h-1 border-t border-black overflow-hidden">
      <div
        class="bg-[#FF2D2D] h-full transition-[width] duration-100 ease-linear"
        style="width: {progressPercent}%;"
      ></div>
    </div>
  </div>
{/if}

<style>
  @keyframes fadeSlideUp {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .animate-fade-slide-up {
    animation: fadeSlideUp 0.22s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }
</style>
