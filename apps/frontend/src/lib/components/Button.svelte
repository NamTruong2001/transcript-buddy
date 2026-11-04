<script lang="ts">
  import { cn } from '../cn'
  import type { Snippet } from 'svelte'
  import type { HTMLButtonAttributes } from 'svelte/elements'

  type Props = HTMLButtonAttributes & {
    variant?: 'default' | 'secondary' | 'danger' | 'ghost'
    children?: Snippet
  }

  let { variant = 'default', class: className = '', children, ...rest }: Props = $props()

  const variants: Record<string, string> = {
    default: 'bg-[var(--accent)] text-white hover:brightness-110',
    secondary: 'bg-[var(--panel)] border border-[var(--border)] text-[var(--text)] hover:bg-[#243040]',
    danger: 'bg-[var(--danger)] text-white hover:brightness-110',
    ghost: 'bg-transparent text-[var(--muted)] hover:text-[var(--text)]',
  }
</script>

<button
  class={cn(
    'inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-50',
    variants[variant],
    className,
  )}
  {...rest}
>
  {@render children?.()}
</button>
