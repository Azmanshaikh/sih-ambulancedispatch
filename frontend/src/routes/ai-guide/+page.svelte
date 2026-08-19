<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { i18n, t } from '$lib/i18n.svelte';

  let messages = $state<{ role: string; content: string }[]>([]);
  let draft = $state('');
  let sending = $state(false);
  let error = $state('');
  let recording = $state(false);
  let transcribing = $state(false);
  let threadEl: HTMLDivElement | undefined;

  let mediaRecorder: MediaRecorder | null = null;
  let mediaStream: MediaStream | null = null;
  let chunks: Blob[] = [];
  let stopTimer: ReturnType<typeof setTimeout> | undefined;

  const MAX_SECONDS = 45;

  async function loadHistory() {
    const res = await apiFetch('/ai/chat/history');
    if (!res.ok) return;
    const data = await res.json();
    messages = (data.messages || []).map((m: any) => ({ role: m.role, content: m.content }));
    await scrollToEnd();
  }

  async function scrollToEnd() {
    await tick();
    if (threadEl) threadEl.scrollTop = threadEl.scrollHeight;
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending || recording || transcribing) return;
    sending = true;
    error = '';
    draft = '';
    messages = [...messages, { role: 'user', content: text }];
    await scrollToEnd();
    try {
      const res = await apiFetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Chat failed');
      messages = [...messages, { role: 'assistant', content: data.reply }];
      await scrollToEnd();
    } catch (e: any) {
      error = e?.message || 'Chat failed';
    } finally {
      sending = false;
    }
  }

  function stopTracks() {
    mediaStream?.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }

  function wavFromPcm(samples: Float32Array, sampleRate: number) {
    const n = samples.length;
    const buffer = new ArrayBuffer(44 + n * 2);
    const view = new DataView(buffer);
    const ascii = (offset: number, s: string) => {
      for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
    };
    ascii(0, 'RIFF');
    view.setUint32(4, 36 + n * 2, true);
    ascii(8, 'WAVE');
    ascii(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    ascii(36, 'data');
    view.setUint32(40, n * 2, true);
    let off = 44;
    for (let i = 0; i < n; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      off += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }

  async function blobToWav(blob: Blob) {
    const AudioCtx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) throw new Error(t('chat.micUnsupported'));
    const ctx = new AudioCtx();
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    await ctx.close();
    const targetRate = 16000;
    const frames = Math.max(1, Math.round(decoded.duration * targetRate));
    const offline = new OfflineAudioContext(1, frames, targetRate);
    const mixed = offline.createBuffer(1, decoded.length, decoded.sampleRate);
    const out = mixed.getChannelData(0);
    const channels = decoded.numberOfChannels;
    for (let i = 0; i < decoded.length; i++) {
      let sum = 0;
      for (let c = 0; c < channels; c++) sum += decoded.getChannelData(c)[i];
      out[i] = sum / channels;
    }
    const src = offline.createBufferSource();
    src.buffer = mixed;
    src.connect(offline.destination);
    src.start(0);
    const rendered = await offline.startRendering();
    return wavFromPcm(rendered.getChannelData(0), targetRate);
  }

  async function sendVoice(blob: Blob) {
    if (blob.size < 800) {
      error = t('chat.voiceEmpty');
      return;
    }
    transcribing = true;
    sending = true;
    error = '';
    try {
      const wav = await blobToWav(blob);
      const body = new FormData();
      body.append('audio', wav, 'speech.wav');
      body.append('language', i18n.lang);
      const res = await apiFetch('/ai/chat/voice', { method: 'POST', body });
      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Voice chat failed';
        if (res.status === 400 && /no speech/i.test(detail)) throw new Error(t('chat.voiceEmpty'));
        throw new Error(detail);
      }
      messages = [
        ...messages,
        { role: 'user', content: data.transcript },
        { role: 'assistant', content: data.reply },
      ];
      await scrollToEnd();
    } catch (e: any) {
      error = e?.message || 'Voice chat failed';
    } finally {
      transcribing = false;
      sending = false;
    }
  }

  async function toggleMic() {
    if (sending && !recording) return;
    if (recording) {
      if (stopTimer) clearTimeout(stopTimer);
      stopTimer = undefined;
      mediaRecorder?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      error = t('chat.micUnsupported');
      return;
    }
    error = '';
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      error = t('chat.micDenied');
      return;
    }
    chunks = [];
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/mp4')
        ? 'audio/mp4'
        : '';
    mediaRecorder = mime ? new MediaRecorder(mediaStream, { mimeType: mime }) : new MediaRecorder(mediaStream);
    mediaRecorder.ondataavailable = (ev) => {
      if (ev.data.size) chunks.push(ev.data);
    };
    mediaRecorder.onstop = async () => {
      recording = false;
      const type = mediaRecorder?.mimeType || chunks[0]?.type || 'audio/webm';
      mediaRecorder = null;
      stopTracks();
      const blob = new Blob(chunks, { type });
      chunks = [];
      await sendVoice(blob);
    };
    mediaRecorder.start();
    recording = true;
    stopTimer = setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
    }, MAX_SECONDS * 1000);
  }

  onMount(loadHistory);
  onDestroy(() => {
    if (stopTimer) clearTimeout(stopTimer);
    if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
    stopTracks();
  });
</script>

<svelte:head><title>{t('chat.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col p-4">
  <div class="max-w-3xl mx-auto w-full flex flex-col h-full">
    <div class="nb-card nb-yellow p-4 mb-3 flex items-center gap-3">
      <span class="material-symbols-outlined" style="font-size:32px;">forum</span>
      <div>
        <h1 class="text-xl font-black uppercase tracking-tight leading-none">{t('chat.title')}</h1>
        <p class="text-[11px] text-black font-semibold mt-1">{t('chat.subtitle')}</p>
      </div>
    </div>
    <div bind:this={threadEl} class="flex-1 overflow-y-auto no-sb nb-card p-4 space-y-3">
      {#if messages.length === 0}
        <p class="text-sm text-[#4B4B4B] font-semibold">{t('chat.empty')}</p>
      {/if}
      {#each messages as m}
        <div class="text-sm {m.role === 'user' ? 'text-right' : ''}">
          <span class="inline-block max-w-[85%] p-3 font-semibold {m.role === 'user' ? 'nb-red' : 'nb-flat'}" style="{m.role === 'user' ? 'color:#fff;' : ''}box-shadow:3px 3px 0 #111;">{m.content}</span>
        </div>
      {/each}
      {#if transcribing}
        <p class="text-xs font-black uppercase tracking-wide">{t('chat.transcribing')}</p>
      {/if}
    </div>
    {#if error}<p class="text-xs text-[#FF2D2D] font-black mt-2">{error}</p>{/if}
    <p class="text-[11px] font-semibold text-[#4B4B4B] mt-2">{t('chat.voiceHint')}</p>
    <form class="mt-2 flex gap-2" onsubmit={(e) => { e.preventDefault(); send(); }}>
      <button
        type="button"
        class="btn px-3 {recording ? 'btn-primary rec-pulse' : 'btn-ghost'}"
        disabled={transcribing || (sending && !recording)}
        onclick={toggleMic}
        aria-label={recording ? t('chat.listening') : t('chat.mic')}
        title={recording ? t('chat.listening') : t('chat.mic')}
      >
        <span class="material-symbols-outlined" style="font-size:22px;">{recording ? 'stop' : 'mic'}</span>
      </button>
      <input
        class="nb-input flex-1"
        bind:value={draft}
        placeholder={recording ? t('chat.speakNow') : transcribing ? t('chat.transcribing') : t('chat.placeholder')}
        disabled={sending || recording}
      />
      <button class="btn btn-primary px-5" disabled={sending || recording}>{sending ? '…' : t('chat.send')}</button>
    </form>
  </div>
</div>

<style>
  .rec-pulse {
    animation: recpulse 1s ease-in-out infinite;
  }
  @keyframes recpulse {
    0%, 100% { box-shadow: 3px 3px 0 #111; }
    50% { box-shadow: 0 0 0 4px #ff2d2d, 3px 3px 0 #111; }
  }
</style>
