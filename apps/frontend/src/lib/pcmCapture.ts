/** Capture mic → PCM s16le mono 16 kHz (gửi qua WebSocket, tránh WebRTC ICE fail trong Docker). */

export type PcmHandler = (pcm: ArrayBuffer) => void

const TARGET_RATE = 16000

function downsampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === TARGET_RATE) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]))
      out[i] = s < 0 ? (s * 0x8000) | 0 : (s * 0x7fff) | 0
    }
    return out
  }
  const ratio = inputRate / TARGET_RATE
  const outLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(outLen)
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(input.length, Math.floor((i + 1) * ratio))
    let sum = 0
    let n = 0
    for (let j = start; j < end; j++) {
      sum += input[j]
      n++
    }
    const s = Math.max(-1, Math.min(1, n ? sum / n : 0))
    out[i] = s < 0 ? (s * 0x8000) | 0 : (s * 0x7fff) | 0
  }
  return out
}

export class PcmCapture {
  private ctx: AudioContext | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private processor: ScriptProcessorNode | null = null
  private stream: MediaStream | null = null

  async start(onPcm: PcmHandler, existingStream?: MediaStream): Promise<void> {
    await this.stop()
    this.stream =
      existingStream ??
      (await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
        video: false,
      }))
    this.ctx = new AudioContext()
    if (this.ctx.state === 'suspended') {
      await this.ctx.resume()
    }
    this.source = this.ctx.createMediaStreamSource(this.stream)
    // 4096 ~ ổn định trên mobile; downsample về 16 kHz trước khi gửi
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1)
    const inputRate = this.ctx.sampleRate
    this.processor.onaudioprocess = (ev) => {
      const input = ev.inputBuffer.getChannelData(0)
      const pcm = downsampleTo16k(input, inputRate)
      if (pcm.length) {
        onPcm(pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength))
      }
    }
    // ScriptProcessor cần nằm trong graph; gain=0 để không phát mic ra loa
    const mute = this.ctx.createGain()
    mute.gain.value = 0
    this.source.connect(this.processor)
    this.processor.connect(mute)
    mute.connect(this.ctx.destination)
  }

  async stop(): Promise<void> {
    try {
      this.processor?.disconnect()
    } catch {
      /* ignore */
    }
    try {
      this.source?.disconnect()
    } catch {
      /* ignore */
    }
    this.processor = null
    this.source = null
    if (this.ctx) {
      try {
        await this.ctx.close()
      } catch {
        /* ignore */
      }
      this.ctx = null
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop())
      this.stream = null
    }
  }

  /** Dừng graph nhưng giữ MediaStream (để chuyển WebRTC → WS). */
  async detachKeepingStream(): Promise<MediaStream | null> {
    const kept = this.stream
    this.stream = null
    try {
      this.processor?.disconnect()
    } catch {
      /* ignore */
    }
    try {
      this.source?.disconnect()
    } catch {
      /* ignore */
    }
    this.processor = null
    this.source = null
    if (this.ctx) {
      try {
        await this.ctx.close()
      } catch {
        /* ignore */
      }
      this.ctx = null
    }
    return kept
  }
}
