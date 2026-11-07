<script lang="ts">
  import { onMount } from 'svelte'
  import Button from './lib/components/Button.svelte'
  import Card from './lib/components/Card.svelte'
  import Modal from './lib/components/Modal.svelte'
  import {
    createSession,
    deleteSession,
    fetchHealth,
    fetchModels,
    sendOffer,
    stopSession,
    summarizeSession,
    warmupModels,
    wsUrl,
    type SttModel,
  } from './lib/api'
  import { Download, Eye, Mic, MicOff, Sparkles, Cpu, RotateCcw } from 'lucide-svelte'

  const PREVIEW_LINES = 3

  let models = $state<SttModel[]>([])
  let selectedModel = $state('small')
  let language = $state('vi')
  let health = $state<any>(null)
  let status = $state('idle')
  let error = $state('')
  let sessionId = $state<string | null>(null)
  let partial = $state('')
  let finals = $state<string[]>([])
  let summary = $state('')
  let recording = $state(false)
  let warming = $state(false)
  let showTranscriptModal = $state(false)
  let showSummaryModal = $state(false)

  let pc: RTCPeerConnection | null = null
  let localStream: MediaStream | null = null
  let eventsWs: WebSocket | null = null

  let previewFinals = $derived(finals.slice(-PREVIEW_LINES))
  let hasTranscript = $derived(finals.length > 0 || !!partial.trim())
  let hasSummary = $derived(!!summary.trim())
  let loadedModels = $derived<string[]>(health?.agent?.models_loaded || [])
  let selectedLoaded = $derived(loadedModels.includes(selectedModel))

  async function refreshHealth() {
    health = await fetchHealth()
  }

  onMount(async () => {
    try {
      await refreshHealth()
      models = await fetchModels()
      if (models.length && !models.find((m) => m.id === selectedModel)) {
        selectedModel = models[0].id
      }
    } catch (e: any) {
      error = e?.message || String(e)
    }
  })

  async function loadSelectedModel() {
    error = ''
    warming = true
    status = 'loading-model'
    try {
      const result = await warmupModels([selectedModel])
      await refreshHealth()
      status = result.all_loaded?.includes(selectedModel) ? 'model-ready' : 'idle'
    } catch (e: any) {
      error = e?.message || String(e)
      status = 'error'
    } finally {
      warming = false
    }
  }

  function pushEvent(event: any) {
    if (event.type === 'transcript.partial') {
      partial = event.text || ''
    } else if (event.type === 'transcript.final') {
      if (event.text) finals = [...finals, event.text]
      partial = ''
    } else if (event.type === 'summary.done') {
      summary = event.summary || ''
      if (event.transcript && !finals.length) {
        finals = String(event.transcript).split('\n').filter(Boolean)
      }
      status = 'summarized'
    } else if (event.type === 'error') {
      error = event.message || 'unknown error'
    } else if (event.type === 'status') {
      status = event.state || status
    }
  }

  function downloadText(filename: string, content: string) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function fullTranscriptText() {
    return finals.join('\n\n').trim()
  }

  function downloadSummary() {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    downloadText(`summary-${stamp}.md`, summary)
  }

  function downloadTranscript() {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    downloadText(`transcript-${stamp}.md`, fullTranscriptText())
  }

  async function startRecording() {
    error = ''
    summary = ''
    finals = []
    partial = ''
    showTranscriptModal = false
    showSummaryModal = false
    // Nếu model chưa trên GPU → session.open sẽ load (có thể mất vài chục giây)
    status = selectedLoaded ? 'starting' : 'loading-model'
    try {
      const session = await createSession(selectedModel, language || undefined)
      sessionId = session.session_id
      status = session.state
      await refreshHealth()

      eventsWs = new WebSocket(wsUrl(`/api/sessions/${sessionId}/events`))
      eventsWs.onmessage = (msg) => {
        try {
          pushEvent(JSON.parse(msg.data))
        } catch {
          /* ignore */
        }
      }

      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          'Trình duyệt chặn mic trên HTTP. Mở bằng HTTPS: https://new-home-server.tailae2496.ts.net:5180 (hoặc localhost).',
        )
      }

      localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
        video: false,
      })

      pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
      for (const track of localStream.getAudioTracks()) {
        pc.addTrack(track, localStream)
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      await waitIceComplete(pc)
      const answer = await sendOffer(sessionId, pc.localDescription!.toJSON())
      await pc.setRemoteDescription(answer)

      recording = true
      status = 'recording'
    } catch (e: any) {
      error = e?.message || String(e)
      status = 'error'
      await cleanupMedia()
    }
  }

  function waitIceComplete(peer: RTCPeerConnection) {
    if (peer.iceGatheringState === 'complete') return Promise.resolve()
    return new Promise<void>((resolve) => {
      const check = () => {
        if (peer.iceGatheringState === 'complete') {
          peer.removeEventListener('icegatheringstatechange', check)
          resolve()
        }
      }
      peer.addEventListener('icegatheringstatechange', check)
      setTimeout(() => resolve(), 2000)
    })
  }

  function applyTranscriptResult(result: { finals?: string[]; transcript?: string }) {
    if (result.finals?.length) finals = result.finals
    else if (result.transcript) {
      finals = String(result.transcript)
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
    }
  }

  async function haltLocalMedia() {
    if (localStream) {
      localStream.getTracks().forEach((t) => t.stop())
      localStream = null
    }
    if (pc) {
      pc.close()
      pc = null
    }
  }

  async function stopRecording() {
    if (!sessionId) return
    status = 'stopping'
    recording = false
    try {
      await haltLocalMedia()
      const result = await stopSession(sessionId, false)
      applyTranscriptResult(result)
      if (partial.trim() && !finals.includes(partial.trim())) {
        finals = [...finals, partial.trim()]
      }
      partial = ''
      status = 'stopped'
    } catch (e: any) {
      error = e?.message || String(e)
      status = 'error'
    }
  }

  async function runSummarize() {
    if (!sessionId) return
    error = ''
    status = 'summarizing'
    try {
      if (recording) {
        recording = false
        await haltLocalMedia()
        await stopSession(sessionId, false)
      }
      const result = await summarizeSession(sessionId)
      summary = result.summary || ''
      applyTranscriptResult(result)
      status = 'summarized'
    } catch (e: any) {
      error = e?.message || String(e)
      status = 'error'
    }
  }

  async function resetAll() {
    error = ''
    recording = false
    await cleanupMedia(true)
    finals = []
    partial = ''
    summary = ''
    showTranscriptModal = false
    showSummaryModal = false
    status = 'idle'
  }

  async function cleanupMedia(closeSession = true) {
    await haltLocalMedia()
    if (eventsWs) {
      eventsWs.close()
      eventsWs = null
    }
    if (closeSession && sessionId) {
      try {
        await deleteSession(sessionId)
      } catch {
        /* ignore */
      }
      sessionId = null
    }
  }
</script>

<main class="mx-auto flex min-h-screen w-full max-w-5xl min-w-0 flex-col gap-6 px-4 py-8">
  <header class="space-y-2">
    <p class="text-xs tracking-[0.2em] text-[var(--accent)] uppercase">transcript-buddy</p>
    <h1 class="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Realtime ASR</h1>
    <p class="max-w-2xl text-[var(--muted)]">
      Mic → WebRTC → faster-whisper GPU → tóm tắt qwen3.5:4b khi Stop.
    </p>
  </header>

  <div class="grid min-w-0 gap-4 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
    <Card title="Controls" class="min-w-0">
      <div class="min-w-0 space-y-4">
        <label class="block min-w-0 space-y-1 text-sm">
          <span class="text-[var(--muted)]">STT model</span>
          <select
            class="w-full max-w-full rounded-md border border-[var(--border)] bg-[#121820] px-3 py-2"
            bind:value={selectedModel}
            disabled={recording}
          >
            {#each models as m}
              <option value={m.id}>{m.id} ({m.size_mb} MB)</option>
            {/each}
          </select>
        </label>

        <label class="block space-y-1 text-sm">
          <span class="text-[var(--muted)]">Language</span>
          <input
            class="w-full rounded-md border border-[var(--border)] bg-[#121820] px-3 py-2"
            bind:value={language}
            placeholder="vi / en / auto"
            disabled={recording}
          />
        </label>

        <div class="flex flex-wrap gap-2">
          {#if !recording}
            <Button
              onclick={startRecording}
              disabled={
                warming ||
                status === 'starting' ||
                status === 'loading-model' ||
                status === 'summarizing' ||
                status === 'stopping'
              }
            >
              <Mic size={16} /> Start
            </Button>
            <Button
              variant="secondary"
              onclick={loadSelectedModel}
              disabled={recording || warming || selectedLoaded || status === 'starting' || status === 'loading-model'}
            >
              <Cpu size={16} />
              {warming ? 'Đang load…' : selectedLoaded ? 'Đã load' : 'Load model'}
            </Button>
            <Button
              variant="secondary"
              onclick={runSummarize}
              disabled={!sessionId || !hasTranscript || status === 'summarizing' || status === 'stopping'}
            >
              <Sparkles size={16} /> Tóm tắt
            </Button>
            <Button
              variant="ghost"
              onclick={resetAll}
              disabled={status === 'summarizing' || status === 'stopping' || (!sessionId && !hasTranscript && !hasSummary)}
            >
              <RotateCcw size={16} /> Reset
            </Button>
          {:else}
            <Button variant="danger" onclick={stopRecording} disabled={status === 'stopping'}>
              <MicOff size={16} /> Dừng
            </Button>
            <Button variant="secondary" onclick={runSummarize} disabled={status === 'stopping'}>
              <Sparkles size={16} /> Tóm tắt
            </Button>
            <Button variant="ghost" onclick={resetAll} disabled={status === 'stopping'}>
              <RotateCcw size={16} /> Reset
            </Button>
          {/if}
        </div>

        <div class="min-w-0 overflow-hidden rounded-md border border-[var(--border)] bg-[#121820] p-3 text-xs text-[var(--muted)]">
          <div>Status: <span class="text-[var(--text)]">{status}</span></div>
          <div class="break-all">
            Session: <span class="text-[var(--text)]">{sessionId || '—'}</span>
          </div>
          <div>
            Agent:
            {#if health?.ok}
              <span class="text-[var(--accent)]">ok</span>
            {:else if health}
              <span class="text-[var(--danger)]">degraded</span>
            {:else}
              …
            {/if}
          </div>
          <div class="break-words">
            GPU loaded:
            <span class="text-[var(--text)]">{loadedModels.length ? loadedModels.join(', ') : '—'}</span>
          </div>
        </div>

        {#if error}
          <p class="break-words text-sm text-[var(--danger)]">{error}</p>
        {/if}
      </div>
    </Card>

    <div class="min-w-0 space-y-4">
      <Card title="Live preview" class="min-w-0">
        <div
          class="max-h-[12rem] min-h-[7.5rem] min-w-0 overflow-y-auto overflow-x-hidden rounded-md border border-[var(--border)] bg-[#121820] px-3 py-2 sm:max-h-[14rem]"
        >
          {#if partial}
            <p class="break-words text-sm whitespace-pre-wrap text-[var(--live)]">{partial}</p>
          {:else if previewFinals.length}
            <ul class="min-w-0 space-y-2 text-sm">
              {#each previewFinals as line}
                <li class="break-words whitespace-pre-wrap text-[var(--text)]/90">{line}</li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm text-[var(--muted)]">Đang chờ giọng nói…</p>
          {/if}
        </div>
        <div class="mt-3 flex min-w-0 flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            disabled={!hasTranscript}
            onclick={() => (showTranscriptModal = true)}
          >
            <Eye size={16} /> Xem lại transcript
          </Button>
          <Button variant="ghost" disabled={!finals.length} onclick={downloadTranscript}>
            <Download size={16} /> Tải transcript
          </Button>
          {#if finals.length}
            <span class="self-center text-xs text-[var(--muted)]">{finals.length} câu</span>
          {/if}
        </div>
      </Card>

      <Card title="Summary" class="min-w-0">
        {#if status === 'summarizing'}
          <p class="text-sm text-[var(--muted)]">Đang tóm tắt bằng qwen3.5:4b…</p>
        {:else if hasSummary}
          <div class="flex min-w-0 flex-col gap-3">
            <div class="flex min-w-0 flex-wrap items-center gap-2">
              <Sparkles size={16} class="shrink-0 text-[var(--accent-2)]" />
              <span class="text-sm text-[var(--text)]">Đã có bản tóm tắt</span>
              <div class="flex flex-wrap gap-2">
                <Button variant="secondary" onclick={() => (showSummaryModal = true)}>
                  <Eye size={16} /> Xem tóm tắt
                </Button>
                <Button variant="ghost" onclick={downloadSummary}>
                  <Download size={16} /> Tải tóm tắt
                </Button>
              </div>
            </div>
            <div
              class="max-h-[10rem] min-w-0 overflow-y-auto rounded-md border border-[var(--border)] bg-[#121820] px-3 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap text-[var(--text)]/90 sm:max-h-[12rem]"
            >
              {summary}
            </div>
          </div>
        {:else}
          <p class="text-sm text-[var(--muted)]">
            Bấm <strong>Dừng</strong> để kết thúc ghi, rồi <strong>Tóm tắt</strong> khi cần. Reset để xóa hết.
          </p>
        {/if}
      </Card>
    </div>
  </div>
</main>

<Modal bind:open={showTranscriptModal} title="Transcript đầy đủ">
  {#if finals.length}
    <ol class="list-decimal space-y-3 break-words pl-5">
      {#each finals as line, i}
        <li class="min-w-0">
          <span class="mr-2 text-xs text-[var(--muted)]">#{i + 1}</span>
          <span class="break-words whitespace-pre-wrap">{line}</span>
        </li>
      {/each}
    </ol>
  {:else if partial}
    <p class="break-words whitespace-pre-wrap text-[var(--live)]">{partial}</p>
  {:else}
    <p class="text-[var(--muted)]">Chưa có transcript.</p>
  {/if}
</Modal>

<Modal bind:open={showSummaryModal} title="Tóm tắt (qwen3.5:4b)">
  <div class="mb-4 flex justify-end">
    <Button variant="secondary" onclick={downloadSummary}>
      <Download size={16} /> Tải về
    </Button>
  </div>
  <div class="break-words whitespace-pre-wrap leading-relaxed">{summary}</div>
</Modal>
