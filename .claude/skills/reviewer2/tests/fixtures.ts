import type { ConfigRow, ModelCompleteRequest, ModelCompleteResult, On, RenderInput, RenderSurface } from 'claude-code'
import { mock } from 'claude-code/testing'
import type { MockClock } from 'claude-code/testing'

import { avatarSvg } from '../hooks/bubble'

export const ROOT = '/work/rev2agent'
export const SYSTEM_PROMPT = 'Write one aside.'
export const START_MS = 1_000_000
const USAGE = { input_tokens: 10, output_tokens: 5, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 }

export const MANIFEST = {
  default: 'stern',
  avatars: [
    { id: 'stern', file: 'stern.png', label_ko: '기본', tags: ['neutral', 'default'] },
    { id: 'skeptical', file: 'skeptical.png', label_ko: '안경 너머 의심', tags: ['skeptical'] },
    { id: 'cheer', file: 'cheer.png', label_ko: '환호', tags: ['success'] },
    { id: 'thinking', file: 'thinking.png', label_ko: '생각 중', tags: ['hmm'] },
  ],
}

// A 1x1 transparent PNG; the Image element checks for a real PNG header.
const PIXEL_PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='

function crc32(bytes: readonly number[]): number {
  let crc = 0xffffffff
  for (const byte of bytes) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1
  }
  return (crc ^ 0xffffffff) >>> 0
}

const u32 = (n: number) => [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255]

/**
 * What the test's fs answers for an avatar picture: the pixel PNG with a tEXt
 * chunk naming the avatar, so a drawing shows which file it read.
 */
export function pngOf(id: string): string {
  const bytes = [...atob(PIXEL_PNG)].map(char => char.charCodeAt(0))
  const body = [...'tEXt', ...`avatar\0${id}`].map(char => char.charCodeAt(0))
  const chunk = [...u32(body.length - 4), ...body, ...u32(crc32(body))]
  const iend = bytes.length - 12
  return btoa(String.fromCharCode(...bytes.slice(0, iend), ...chunk, ...bytes.slice(iend)))
}
/** The Svg source the desktop band draws for an avatar. */
export const svgOf = (id: string) => avatarSvg(pngOf(id))

export type ModelReply = {
  text?: string
  // Answer without text for this reason instead.
  reason?: 'api-error' | 'empty-reply' | 'aborted'
  // Answer only once the test's clock has moved this far.
  delayMs?: number
}

export type World = {
  clock: MockClock
  store: Map<string, unknown>
  calls: ModelCompleteRequest[]
  replies: ModelReply[]
  logs: string[]
  commands: unknown[]
  env: Map<string, string>
  root: string
  // Files a Rev2Agent checkout has at its root; remove them to make another project.
  markers: Set<string>
  // The avatars' manifest.json; undefined makes reading it fail.
  manifest: unknown
  config: { enabled: boolean; model: string }
  configSets: { key: string; value: unknown }[]
  sessionId: string
}

/**
 * Answers everything beneath the mod: a session opened at a Rev2Agent root, a
 * store, a clock, the plugin's files, its /config rows, and a model that
 * replies from `replies` in order (SKIP once empty).
 */
export function worldOf(on: On, options: { store?: Record<string, unknown>; sessionId?: string } = {}): World {
  const world: World = {
    clock: mock.clock(on, { now: START_MS }),
    store: new Map(Object.entries(options.store ?? {})),
    calls: [],
    replies: [],
    logs: [],
    commands: [],
    env: new Map([['TERM', 'xterm-256color']]),
    root: ROOT,
    markers: new Set([`${ROOT}/prompts/agent_workflow.md`, `${ROOT}/prompts/conventions.md`]),
    manifest: MANIFEST,
    config: { enabled: true, model: 'haiku' },
    configSets: [],
    sessionId: options.sessionId ?? 'session-1',
  }
  on('env.get', ($, e) => ({ value: world.env.get(e.name) }))
  on('store.get', ($, e) => ({ value: world.store.get(e.key) }))
  on('store.set', ($, e) => {
    world.store.set(e.key, e.value)
    return { value: undefined }
  })
  on('store.delete', ($, e) => {
    world.store.delete(e.key)
    return { value: undefined }
  })
  on('store.keys', () => ({ value: [...world.store.keys()] }))
  on('session.id', () => ({ value: world.sessionId }))
  on('session.root', () => ({ value: world.root }))
  on('fs.exists', ($, e) => ({ value: world.markers.has(e.path) }))
  on('fs.read', ($, e) => {
    if (e.as === 'bytes') {
      const file = /\/avatars\/([a-z0-9-]+)\.png$/.exec(e.path)
      return file === null ? { deny: `ENOENT: ${e.path}` } : { value: { base64: pngOf(file[1]!) } }
    }
    if (e.path.endsWith('/avatars/manifest.json')) {
      return world.manifest === undefined ? { deny: `ENOENT: ${e.path}` } : { value: JSON.stringify(world.manifest) }
    }
    if (e.path.endsWith('/prompts/system.txt')) return { value: `${SYSTEM_PROMPT}\n` }
    return { deny: `ENOENT: ${e.path}` }
  })
  on('model.complete', async ($, e) => {
    world.calls.push(e)
    const reply = world.replies.shift() ?? { text: 'SKIP' }
    if (reply.delayMs !== undefined) await world.clock.sleep(reply.delayMs)
    let value: ModelCompleteResult
    if (reply.reason === 'api-error') {
      value = { isAnswered: false, reason: 'api-error', status: 529, error: 'overloaded', usage: USAGE }
    } else if (reply.reason !== undefined) {
      value = { isAnswered: false, reason: reply.reason, usage: USAGE }
    } else {
      value = { isAnswered: true, text: reply.text ?? '', usage: USAGE }
    }
    return { value }
  })
  on('config.list', () => {
    const provider = { plugin: 'reviewer2', tier: 'user' } as const
    const rows: ConfigRow[] = [
      { key: 'theme', label: 'Theme', kind: 'choice', value: 'dark', provider: { plugin: 'engine', tier: 'core' }, isLocked: false },
      { key: 'reviewer2.enabled', label: 'Reviewer 2 bubble', kind: 'boolean', value: world.config.enabled, provider, isLocked: false },
      { key: 'reviewer2.model', label: 'Reviewer 2 model', kind: 'choice', value: world.config.model, provider, isLocked: false },
    ]
    return { value: rows }
  })
  on('config.set', ($, e) => {
    world.configSets.push({ key: e.key, value: e.value })
    if (e.key === 'reviewer2.enabled' && typeof e.value === 'boolean') world.config.enabled = e.value
    return { value: e.value }
  })
  on('command.register', ($, e) => {
    world.commands.push(e)
    return { value: { command: e.name } }
  })
  on('ui.log', ($, e) => {
    world.logs.push(e.text)
    return { value: undefined }
  })
  on('session.start', () => ({ cwd: ROOT }))
  on('classic.SessionStart', () => ({}))
  on('prompt.submit', ($, e) => ({ text: e.text }))
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Box', props: {}, children: [] }))
  return world
}

export function bandOf(
  surface: Extract<RenderSurface, 'terminal' | 'desktop' | 'vscode'> = 'desktop',
  props: Partial<RenderInput<'AbovePrompt', 'desktop'>['props']> = {},
): RenderInput<'AbovePrompt'> {
  return {
    component: 'AbovePrompt',
    surface,
    requestId: 'band',
    viewport: { columns: 100, rows: 40 },
    props: {
      hasSurvey: false,
      isWorking: false,
      maxRows: 10,
      bodyColumns: 96,
      scroll: { offset: 0, bodyRows: 10 },
      view: {},
      ...props,
    },
  }
}

type Node = { type?: unknown; props?: Record<string, unknown>; children?: unknown }

function nodesOf(node: unknown): Node[] {
  if (Array.isArray(node)) return node.flatMap(nodesOf)
  if (node === null || typeof node !== 'object') return []
  const element = node as Node
  return [element, ...nodesOf(element.children ?? [])]
}

/** Every string a drawing shows: Text children and Button labels in brackets. */
export function textOf(node: unknown): string {
  if (typeof node === 'string') return node
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (node === null || typeof node !== 'object') return ''
  const { type, props, children } = node as Node
  const own = type === 'Button' && typeof props?.label === 'string' ? `[${props.label}]` : ''
  return own + textOf(children ?? [])
}

/** The sources of the Svg elements in a drawing, in order. */
export function svgsOf(node: unknown): unknown[] {
  return nodesOf(node)
    .filter(element => element.type === 'Svg')
    .map(element => element.props?.source)
}

/** The sources of the Image elements in a drawing, in order. */
export function imagesOf(node: unknown): unknown[] {
  return nodesOf(node)
    .filter(element => element.type === 'Image')
    .map(element => element.props?.source)
}

export const completed = (turnId: string, answer: string) =>
  ({ answer, durationMs: 1200, isAborted: false, turnId, reason: 'answer' }) as const

/** `/reviewer2 <args>` as the user types it. */
export const command = (args: string) =>
  ({
    command: 'reviewer2',
    args,
    origin: { kind: 'composer' },
    presentation: { isFullscreen: false, columns: 100 },
  }) as const
