export type SttModel = {
  id: string
  path: string
  size_mb: number
}

const EDGE = (import.meta.env.VITE_EDGE_URL as string | undefined) || ''

export function apiUrl(path: string): string {
  return `${EDGE}${path}`
}

export function wsUrl(path: string): string {
  if (EDGE) {
    const u = new URL(EDGE)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    u.pathname = path
    u.search = ''
    return u.toString()
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}${path}`
}

export async function fetchModels(): Promise<SttModel[]> {
  const res = await fetch(apiUrl('/api/models'))
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return data.models || []
}

export async function fetchHealth() {
  const res = await fetch(apiUrl('/api/health'))
  return res.json()
}

export async function createSession(model: string, language?: string) {
  const res = await fetch(apiUrl('/api/sessions'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, language: language || null }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ session_id: string; model: string; state: string }>
}

export async function sendOffer(sessionId: string, offer: RTCSessionDescriptionInit) {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/webrtc/offer`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(offer),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<RTCSessionDescriptionInit>
}

export async function stopSession(sessionId: string) {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/stop`), { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ transcript: string; summary: string; finals: string[] }>
}

export async function deleteSession(sessionId: string) {
  await fetch(apiUrl(`/api/sessions/${sessionId}`), { method: 'DELETE' })
}
