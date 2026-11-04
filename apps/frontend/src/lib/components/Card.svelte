<script lang="ts">
  import { cn } from '../cn'
  import type { Snippet } from 'svelte'

  let {
    title,
    class: className = '',
    children,
  }: { title?: string; class?: string; children?: Snippet } = $props()
</script>

<section
  class={cn(
    'rounded-xl border border-[var(--border)] bg-[var(--panel)]/90 p-4 shadow-[0_10px_40px_rgba(0,0,0,0.25)] backdrop-blur',
    className,
  )}
>
  {#if title}
    <h2 class="mb-3 text-sm font-semibold tracking-wide text-[var(--muted)] uppercase">{title}</h2>
  {/if}
  {@render children?.()}
</section>
