<script lang="ts">
  import { i18n, LANGUAGES, setLang, t, type Lang } from '$lib/i18n.svelte';

  interface Props {
    compact?: boolean;
  }

  let { compact = false }: Props = $props();
  let open = $state(false);

  function pick(lang: Lang) {
    setLang(lang);
    open = false;
  }

  function onWindowClick(e: MouseEvent) {
    const target = e.target as HTMLElement | null;
    if (!target?.closest('.lang-settings')) open = false;
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="lang-settings" style="position:relative;">
  <button
    type="button"
    class="btn btn-ghost"
    style="padding:{compact ? '6px 8px' : '8px 10px'};font-size:10px;box-shadow:3px 3px 0 #111;min-width:36px;"
    aria-label={t('nav.settings')}
    title={t('nav.settings')}
    onclick={(e) => {
      e.stopPropagation();
      open = !open;
    }}
  >
    <span class="material-symbols-outlined" style="font-size:18px;">settings</span>
  </button>

  {#if open}
    <div
      class="nb-card"
      style="
        position:absolute;right:0;top:calc(100% + 8px);z-index:80;
        width:min(280px, calc(100vw - 24px));padding:14px;background:#fff;
      "
    >
      <p style="margin:0 0 4px;font-size:11px;font-weight:900;letter-spacing:0.12em;text-transform:uppercase;">{t('nav.settings')}</p>
      <p style="margin:0 0 10px;font-size:12px;font-weight:800;">{t('nav.language')}</p>
      <p style="margin:0 0 12px;font-size:11px;color:#4B4B4B;font-weight:600;line-height:1.4;">{t('nav.languageHint')}</p>
      <div style="display:flex;flex-direction:column;gap:8px;">
        {#each LANGUAGES as lang}
          <label
            class="nb-card"
            style="
              display:flex;align-items:center;gap:10px;padding:10px;cursor:pointer;
              background:{i18n.lang === lang.id ? '#FFD23F' : '#fff'};
            "
          >
            <input
              type="radio"
              name="jeevan-lang"
              checked={i18n.lang === lang.id}
              onchange={() => pick(lang.id)}
              style="accent-color:#111;width:16px;height:16px;"
            />
            <span style="display:flex;flex-direction:column;line-height:1.2;">
              <strong style="font-size:13px;">{lang.native}</strong>
              <span style="font-size:10px;color:#4B4B4B;font-weight:700;">{lang.name}</span>
            </span>
          </label>
        {/each}
      </div>
    </div>
  {/if}
</div>
