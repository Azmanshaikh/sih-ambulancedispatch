<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { apiFetch } from '$lib/auth.svelte';
  import { t } from '$lib/i18n.svelte';

  type Intake = {
    name: string;
    date_of_birth: string;
    issue: string;
    recap: string;
    confirmed?: boolean;
  };

  let conversationUrl = $state('');
  let conversationId = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let confirming = $state(false);
  let error = $state('');
  let savedNote = $state('');
  let stageEl = $state<HTMLDivElement | null>(null);
  let dailyCall = $state<any>(null);
  let verifyOpen = $state(false);
  let verifyLive = $state(false);
  let intake = $state<Intake>({ name: '', date_of_birth: '', issue: '', recap: '' });
  let lastConversationId = $state('');

  let expectNext: 'name' | 'dob' | 'issue' | null = null;
  let canvasTool: { id: string; component: string } | null = null;
  let ending = false;
  let useIframe = $state(false);

  function emptyIntake(): Intake {
    return { name: '', date_of_birth: '', issue: '', recap: '' };
  }

  function unwrapMessage(event: any) {
    let msg = event?.data ?? event?.payload ?? event;
    if (msg?.data && (msg.data.event_type || msg.data.message_type)) msg = msg.data;
    return msg;
  }

  function parseArgs(raw: unknown): Record<string, any> {
    if (!raw) return {};
    if (typeof raw === 'object') return raw as Record<string, any>;
    if (typeof raw !== 'string') return {};
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }

  function toolNameOf(msg: any): string {
    const props = msg?.properties || msg;
    return String(
      props?.name || props?.tool_name || props?.function_name || props?.tool || ''
    ).toLowerCase();
  }

  function toolCallIdOf(msg: any): string {
    const props = msg?.properties || msg;
    return String(props?.tool_call_id || props?.id || props?.call_id || '');
  }

  function utteranceText(msg: any): { role: string; text: string } | null {
    const props = msg?.properties || msg;
    const text = String(props?.speech || props?.text || props?.content || props?.transcript || '').trim();
    if (!text) return null;
    let role = String(props?.role || props?.speaker || '').toLowerCase();
    if (role in { replica: 1, model: 1, pal: 1, persona: 1, assistant: 1 }) role = 'assistant';
    if (role !== 'user' && role !== 'assistant') {
      const event = String(msg?.event_type || '');
      role = event.includes('user') ? 'user' : 'assistant';
    }
    return { role, text };
  }

  function noteAssistant(text: string) {
    const t = text.toLowerCase();
    if (/full name|your name|what(?:'s| is) your name|who am i speaking/.test(t)) expectNext = 'name';
    else if (/date of birth|\bdob\b|birthday|when were you born|year you were born/.test(t)) expectNext = 'dob';
    else if (/what.*(issue|problem|symptom|wrong|bring you)|how can i help|what is bothering/.test(t)) expectNext = 'issue';
    if (
      /please verify|look at (the|this) (box|card|screen)|on (the|this) (box|card|screen)|confirm (these|this|the) (details|information)/i.test(
        text
      )
    ) {
      openVerify(true);
    }
  }

  function noteUser(text: string) {
    if (expectNext === 'name') intake = { ...intake, name: text };
    else if (expectNext === 'dob') intake = { ...intake, date_of_birth: text };
    else if (expectNext === 'issue') intake = { ...intake, issue: text };
    expectNext = null;
  }

  function applyRecapBody(title: string, body: string) {
    const next = { ...intake };
    const grab = (re: RegExp) => {
      const m = body.match(re);
      return m?.[1]?.split('\n')[0]?.trim() || '';
    };
    next.name = grab(/name\s*[:\-]\s*(.+)/i) || next.name;
    next.date_of_birth =
      grab(/(?:date of birth|d\.?o\.?b\.?|birthday)\s*[:\-]\s*(.+)/i) || next.date_of_birth;
    next.issue = grab(/(?:issue|complaint|problem|symptom)\s*[:\-]\s*(.+)/i) || next.issue;
    next.recap = [title, body].filter(Boolean).join('\n').trim() || next.recap;
    intake = next;
  }

  function openVerify(live: boolean) {
    if (!intake.recap) {
      const bits = [
        intake.name && `Name: ${intake.name}`,
        intake.date_of_birth && `Date of birth: ${intake.date_of_birth}`,
        intake.issue && `Issue: ${intake.issue}`,
      ].filter(Boolean);
      if (bits.length) intake = { ...intake, recap: bits.join('\n') };
    }
    verifyLive = live;
    verifyOpen = true;
  }

  async function postCanvasInteraction(type: string, value: Record<string, unknown> = {}) {
    if (!conversationId || !canvasTool?.id) return;
    try {
      await fetch(`https://tavusapi.com/v2/conversations/${conversationId}/canvas/interactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interaction_id: `ci_${canvasTool.id}_${type}_${crypto.randomUUID().slice(0, 8)}`,
          tool_call_id: canvasTool.id,
          component: canvasTool.component,
          component_version: 'v1',
          type,
          value,
        }),
      });
    } catch {
      /* card may already be gone */
    }
  }

  function sendToolResult(msg: any, output: string) {
    const id = toolCallIdOf(msg);
    if (!dailyCall || !id || !conversationId) return;
    dailyCall.sendAppMessage(
      {
        message_type: 'conversation',
        event_type: 'conversation.tool_result',
        conversation_id: conversationId,
        properties: { tool_call_id: id, name: toolNameOf(msg), output, status: 'success' },
      },
      '*'
    );
  }

  function handleToolCall(msg: any) {
    const name = toolNameOf(msg);
    const args = parseArgs((msg?.properties || msg)?.arguments || (msg?.properties || msg)?.args);
    const id = toolCallIdOf(msg);

    if (name.includes('canvas_show_input') || name.includes('canvas_show_calendar') || name.includes('canvas_show_question')) {
      canvasTool = { id, component: name.includes('calendar') ? 'canvas.calendar' : name.includes('question') ? 'canvas.question' : 'canvas.input' };
      sendToolResult(
        msg,
        'The patient will answer this out loud. Do not wait for typing. Ask them to speak their name or date of birth.'
      );
      postCanvasInteraction('skip', { input_type: 'text', value: null, skipped: true });
      canvasTool = null;
      return;
    }

    if (name.includes('canvas_show_text') || name.includes('canvas_show_alert')) {
      canvasTool = { id, component: name.includes('alert') ? 'canvas.alert' : 'canvas.text' };
      applyRecapBody(String(args.title || args.heading || 'Please verify'), String(args.body || args.message || args.text || ''));
      openVerify(true);
      return;
    }

    if (name.includes('canvas_clear')) {
      if (verifyLive) verifyOpen = false;
    }
  }

  function onAppMessage(event: any) {
    const msg = unwrapMessage(event);
    if (!msg || typeof msg !== 'object') return;
    const eventType = String(msg.event_type || msg.event || '').toLowerCase();
    if (eventType.includes('tool_call') || eventType.includes('toolcall')) {
      handleToolCall(msg);
      return;
    }
    if (eventType.includes('utterance')) {
      const u = utteranceText(msg);
      if (!u) return;
      if (u.role === 'assistant') noteAssistant(u.text);
      else noteUser(u.text);
    }
  }

  async function destroyCall() {
    const call = dailyCall;
    dailyCall = null;
    if (!call) return;
    try {
      await call.leave();
    } catch {
      /* already left */
    }
    try {
      call.destroy();
    } catch {
      /* ignore */
    }
  }

  async function waitForStage() {
    for (let i = 0; i < 20; i++) {
      if (stageEl) return stageEl;
      await tick();
      await new Promise((r) => setTimeout(r, 40));
    }
    return stageEl;
  }

  async function joinDaily(url: string) {
    useIframe = false;
    const el = await waitForStage();
    if (!el) {
      useIframe = true;
      return;
    }
    await destroyCall();
    try {
      const Daily = (await import('@daily-co/daily-js')).default;
      const call = Daily.createFrame(el, {
        showLeaveButton: false,
        showFullscreenButton: true,
        iframeStyle: {
          width: '100%',
          height: '100%',
          border: '0',
          position: 'absolute',
          inset: '0',
        },
      });
      call.on('app-message', onAppMessage);
      call.on('left-meeting', () => {
        if (!ending && conversationId) endCall();
      });
      dailyCall = call;
      await call.join({ url });
    } catch {
      useIframe = true;
    }
  }

  async function startCall() {
    loading = true;
    error = '';
    savedNote = '';
    verifyOpen = false;
    intake = emptyIntake();
    expectNext = null;
    canvasTool = null;
    ending = false;
    useIframe = false;
    try {
      const res = await apiFetch('/ai/tavus/start', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not start Tavus call');
      conversationUrl = data.conversation_url;
      conversationId = data.conversation_id || '';
      lastConversationId = conversationId;
      await joinDaily(conversationUrl);
    } catch (e: any) {
      error = e?.message || 'Could not start Tavus call. Add TAVUS_API_KEY to .env.';
      conversationUrl = '';
      conversationId = '';
    } finally {
      loading = false;
    }
  }

  async function endCall() {
    if (ending) return;
    ending = true;
    const id = conversationId || lastConversationId;
    conversationUrl = '';
    conversationId = '';
    await destroyCall();
    if (!id) {
      ending = false;
      return;
    }
    saving = true;
    try {
      const res = await apiFetch(`/ai/tavus/${id}/end`, { method: 'POST' });
      const data = await res.json();
      const next = data.intake || {};
      intake = {
        name: next.name || intake.name,
        date_of_birth: next.date_of_birth || intake.date_of_birth,
        issue: next.issue || intake.issue,
        recap: next.recap || intake.recap,
      };
      lastConversationId = id;
      verifyLive = false;
      verifyOpen = true;
      const n = data.saved || 0;
      savedNote = n
        ? `Saved ${n} spoken turns. Please verify the recap below.`
        : 'Call ended. Please verify the recap below.';
    } catch {
      savedNote = 'Call ended.';
      verifyLive = false;
      verifyOpen = true;
    } finally {
      saving = false;
      ending = false;
    }
  }

  async function confirmIntake() {
    const id = lastConversationId || conversationId;
    if (!id) return;
    confirming = true;
    try {
      if (verifyLive && dailyCall && conversationId) {
        dailyCall.sendAppMessage(
          {
            message_type: 'conversation',
            event_type: 'conversation.respond',
            conversation_id: conversationId,
            properties: { text: 'Yes, that is correct.' },
          },
          '*'
        );
        await postCanvasInteraction('dismiss', {});
      }
      const res = await apiFetch(`/ai/tavus/${id}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intake),
      });
      if (!res.ok) throw new Error('Could not save verification');
      savedNote = 'Verified. Name, date of birth, and issue are saved for your trip report.';
      verifyOpen = false;
    } catch (e: any) {
      error = e?.message || 'Could not save verification';
    } finally {
      confirming = false;
    }
  }

  onDestroy(() => {
    const id = conversationId;
    destroyCall();
    if (id) apiFetch(`/ai/tavus/${id}/end`, { method: 'POST' });
  });
</script>

<svelte:head><title>{t('call.pageTitle')}</title></svelte:head>

<div class="h-full flex flex-col">
  {#if conversationUrl}
    <div class="flex items-center justify-between px-4 py-2" style="background:#2E5BFF;border-bottom:4px solid #111;">
      <p class="nb-chip nb-yellow">{t('call.body')}</p>
      <button class="btn btn-primary px-4 py-2" disabled={saving} onclick={endCall}>
        {saving ? t('call.saving') : t('map.exit')}
      </button>
    </div>
    <div class="relative flex-1 min-h-0">
      {#if useIframe}
        <iframe
          title="JEEVAN Tavus call"
          src={conversationUrl}
          allow="camera; microphone; fullscreen; display-capture; autoplay"
          class="absolute inset-0 w-full h-full border-0"
        ></iframe>
      {:else}
        <div bind:this={stageEl} class="absolute inset-0"></div>
      {/if}
      {#if verifyOpen && verifyLive}
        <aside class="verify-card">
          <p class="nb-chip nb-yellow mb-2">{t('call.verify')}</p>
          <h2 class="text-lg font-black uppercase mb-2">{t('call.recap')}</h2>
          <p class="text-sm font-semibold mb-3">{t('call.verifyHint')}</p>
          <dl class="text-sm font-bold space-y-2 mb-4">
            <div><dt class="text-[10px] uppercase tracking-widest text-[#4B4B4B]">{t('call.name')}</dt><dd>{intake.name || '—'}</dd></div>
            <div><dt class="text-[10px] uppercase tracking-widest text-[#4B4B4B]">{t('call.dob')}</dt><dd>{intake.date_of_birth || '—'}</dd></div>
            <div><dt class="text-[10px] uppercase tracking-widest text-[#4B4B4B]">{t('call.issue')}</dt><dd>{intake.issue || intake.recap || '—'}</dd></div>
          </dl>
          <button class="btn btn-primary w-full" disabled={confirming} onclick={confirmIntake}>
            {confirming ? t('call.saving') : t('call.confirm')}
          </button>
        </aside>
      {/if}
    </div>
  {:else}
    <div class="flex-1 flex flex-col items-center justify-center p-8 text-center overflow-y-auto">
      <div class="nb-card nb-blue p-8 max-w-md w-full" style="color:#fff;">
        <div class="inline-flex items-center justify-center mb-4 bg-white text-black" style="width:64px;height:64px;border:3px solid #111;box-shadow:4px 4px 0 #111;">
          <span class="material-symbols-outlined" style="font-size:36px;">videocam</span>
        </div>
        <p class="nb-chip nb-yellow mb-3">{t('call.chip')}</p>
        <h1 class="text-3xl font-black mb-3 uppercase tracking-tight">{t('call.title')}</h1>
        <p class="text-sm text-white/90 max-w-md mb-6 font-semibold">
          {t('call.body')}
        </p>
        {#if error}<p class="nb-card p-2 text-xs text-black mb-4 max-w-lg font-bold">{error}</p>{/if}
        {#if savedNote}<p class="nb-card nb-green p-2 text-xs mb-4 font-bold" style="color:#fff;">{savedNote}</p>{/if}
        <button class="btn btn-primary px-10 py-3 w-full" disabled={loading || saving} onclick={startCall}>
          {loading ? t('call.connecting') : t('call.start')}
        </button>
      </div>
      {#if verifyOpen && !verifyLive}
        <div class="nb-card nb-yellow p-6 max-w-md w-full mt-6 text-left">
          <p class="nb-chip mb-3">{t('call.verify')}</p>
          <h2 class="text-xl font-black uppercase mb-2">{t('call.recap')}</h2>
          <p class="text-xs font-semibold mb-4">{t('call.verifyHint')}</p>
          <label class="block text-[10px] font-black uppercase tracking-widest mb-1">{t('call.name')}</label>
          <input class="nb-input mb-3" bind:value={intake.name} placeholder={t('call.spokenName')} />
          <label class="block text-[10px] font-black uppercase tracking-widest mb-1">{t('call.dob')}</label>
          <input class="nb-input mb-3" bind:value={intake.date_of_birth} placeholder={t('call.spokenDob')} />
          <label class="block text-[10px] font-black uppercase tracking-widest mb-1">{t('call.issue')}</label>
          <input class="nb-input mb-3" bind:value={intake.issue} placeholder={t('call.spokenIssue')} />
          {#if intake.recap}
            <p class="text-sm font-semibold mb-4 whitespace-pre-wrap">{intake.recap}</p>
          {/if}
          <button class="btn btn-primary w-full" disabled={confirming} onclick={confirmIntake}>
            {confirming ? t('call.saving') : t('call.confirm')}
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .verify-card {
    position: absolute;
    top: 16px;
    right: 16px;
    width: min(340px, calc(100% - 32px));
    z-index: 20;
    background: #ffd23f;
    color: #111;
    border: 3px solid #111;
    box-shadow: 6px 6px 0 #111;
    padding: 16px;
    text-align: left;
  }
</style>
