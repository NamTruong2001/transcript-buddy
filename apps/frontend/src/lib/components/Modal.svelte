<script lang="ts">
  import type { Snippet } from 'svelte'
  import { X } from 'lucide-svelte'
  import Button from './Button.svelte'

  let {
    open = $bindable(false),
    title = '',
    children,
  }: {
    open?: boolean
    title?: string
    children?: Snippet
  } = $props()

  function close() {
    open = false
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') close()
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <button
      class="absolute inset-0 bg-black/60 backdrop-blur-sm"
      aria-label="Close overlay"
      onclick={close}
    ></button>
    <div
      class="relative z-10 flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--panel)] shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div class="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <h3 class="text-sm font-semibold tracking-wide text-[var(--muted)] uppercase">{title}</h3>
        <Button variant="ghost" class="!px-2 !py-1" onclick={close} aria-label="Close">
          <X size={16} />
        </Button>
      </div>
      <div class="overflow-y-auto px-4 py-4 text-sm leading-relaxed">
        {@render children?.()}
      </div>
    </div>
  </div>
{/if}
