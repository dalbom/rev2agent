// reviewer2: after the assistant answers in a session opened at a Rev2Agent
// checkout's root, asks a small model for Reviewer 2's one-line aside and shows
// it in a speech bubble above the right end of the prompt, beside an avatar
// whose expression the model picks for the line.
//
// Flow: turn.start keeps the prompt and takes the bubble down, turn.complete
// starts the model call in the background and returns at once, and the
// finished line becomes the bubble unless a newer turn has begun. The bubble is
// saved per session, so a resume or a reload shows it again until the next
// prompt. The aside is drawn only: it never enters the conversation, so the
// assistant never reads it and it cannot steer the research.

import type { EngineInterface, On, PluginOptions, RenderElement, RenderInput } from 'claude-code'

import type { Catalog, Outcome, Reply } from './bubble'
import {
  avatarFor,
  avatarSvg,
  buildPayload,
  describeOutcome,
  firstLineOf,
  formatInstruction,
  isFromPerson,
  parseCatalog,
  parseIndex,
  parseReply,
  parseStoredBubble,
  planIndex,
  terminalDrawsImages,
} from './bubble'

// A session is served when its project root holds these: the root of a
// Rev2Agent checkout. The plugin ships in that checkout's .claude/skills, so
// Claude Code loads it only for sessions opened there; the check also holds a
// copy installed anywhere else to Rev2Agent sessions.
const ROOT_MARKERS = ['prompts/agent_workflow.md', 'prompts/conventions.md']
const DEFAULT_MODEL = 'haiku'
const MODEL_TIMEOUT_MS = 30_000
const MODEL_EFFORT = 'low'
const MAX_REPLY_TOKENS = 300
// Asides that may generate at once; a turn that finds this many gets none.
const MAX_IN_FLIGHT = 2
const MAX_STORED_SESSIONS = 20
const MAX_STORED_BYTES = 200_000
const MAX_TRACKED_TURNS = 32
// The avatar's side on the desktop, in CSS pixels, and its box in a terminal
// that draws pictures (cells are about twice as tall as wide).
const AVATAR_SIZE = 56
const IMAGE_COLUMNS = 6
const IMAGE_ROWS = 3
const ACCENT = '#C8232A'
const THINKING_AVATAR = 'thinking'
const PENDING_TEXT = 'Reviewer 2 is drafting comments…'
const COMMAND = 'reviewer2'
const USAGE = `Usage: /${COMMAND} [status|on|off|again]`

const STORE_INDEX = 'bubbles'
const BUBBLE_PREFIX = 'bubble:'

type Engine = EngineInterface
type Settings = { enabled: boolean; model: string }
type Job = { turnId: string; prompt: string; answer: string }
type Bubble = { text: string; avatarId: string; turnId: string; at: number; picture: string | null }

let settings: Settings = { enabled: true, model: DEFAULT_MODEL }
let bubble: Bubble | null = null
// Bumped whenever the bubble is set or taken down, so a slow restore that
// started before cannot bring an old one back.
let bubbleEpoch = 0
let pendingPicture: string | null = null
let catalog: Catalog | null | undefined
const pictures = new Map<string, string>()
const promptsByTurn = new Map<string, string>()
const pendingTurns = new Set<string>()
let checkedRoot: { root: string; isServed: boolean } | null = null
let drawsImages = false
let loadedSessionId: string | null = null
let lastPrompt = ''
// The person's own latest words, kept by prompt.submit; null until it has seen them.
let lastPersonPrompt: string | null = null
let latestTurnId: string | null = null
let lastJob: Job | null = null
let lastOutcome: Outcome | null = null

function settingsOf(options: PluginOptions): Settings {
  const model = typeof options.model === 'string' && options.model.trim() !== '' ? options.model : DEFAULT_MODEL
  return { enabled: options.enabled !== false, model }
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function logDebug($: Engine, text: string): void {
  $.ui.log(text, { to: 'debug' })
}

/** Whether this session's project root is a Rev2Agent checkout. */
async function isServed($: Engine): Promise<boolean> {
  const root = await $.session.root()
  if (checkedRoot?.root === root) return checkedRoot.isServed
  let served = true
  for (const marker of ROOT_MARKERS) {
    if (!(await $.fs.exists(`${root}/${marker}`))) {
      served = false
      break
    }
  }
  checkedRoot = { root, isServed: served }
  return served
}

/** The avatars this plugin ships, read once per load; null when unusable. */
async function catalogOf($: Engine): Promise<Catalog | null> {
  if (catalog !== undefined) return catalog
  try {
    catalog = parseCatalog(JSON.parse(String(await $.fs.read(`${$.plugin.root}/avatars/manifest.json`))))
    if (catalog === null) logDebug($, 'avatars/manifest.json lists no usable avatar')
  } catch (error) {
    logDebug($, `avatars unavailable: ${messageOf(error)}`)
    catalog = null
  }
  return catalog
}

/** The PNG (base64) of the avatar `id` names, else the default; null when there is none to show. */
async function pictureOf($: Engine, id: string | null): Promise<string | null> {
  const known = await catalogOf($)
  if (known === null) return null
  const avatar = avatarFor(known, id)
  const cached = pictures.get(avatar.id)
  if (cached !== undefined) return cached
  try {
    const { base64 } = await $.fs.read(`${$.plugin.root}/avatars/${avatar.file}`, { as: 'bytes' })
    pictures.set(avatar.id, base64)
    return base64
  } catch (error) {
    logDebug($, `avatar ${avatar.id} unavailable: ${messageOf(error)}`)
    return null
  }
}

async function systemPromptOf($: Engine, known: Catalog | null): Promise<string> {
  const base = String(await $.fs.read(`${$.plugin.root}/prompts/system.txt`)).trim()
  if (!base) throw new Error('prompts/system.txt is empty')
  return known === null ? base : `${base}\n\n${formatInstruction(known)}`
}

/** Asks the model for the aside; null when it skips or fails, with the reason in lastOutcome. */
async function generate($: Engine, job: Job): Promise<Reply | null> {
  let kind: Outcome['kind'] = 'error'
  let detail = ''
  let reply: Reply | null = null
  try {
    const result = await $.model.complete({
      model: settings.model,
      system: await systemPromptOf($, await catalogOf($)),
      prompt: buildPayload(job.prompt, job.answer),
      maxTokens: MAX_REPLY_TOKENS,
      effort: MODEL_EFFORT,
      timeoutMs: MODEL_TIMEOUT_MS,
    })
    if (result.isAnswered) {
      const parsed = parseReply(result.text)
      kind = parsed.kind === 'aside' ? 'ok' : parsed.kind
      if (parsed.kind === 'aside') reply = { avatarId: parsed.avatarId, text: parsed.text }
      if (parsed.kind === 'malformed') detail = firstLineOf(result.text, 60)
    } else if (result.reason === 'aborted') {
      kind = 'timeout'
    } else if (result.reason === 'api-error') {
      detail = `API error ${result.status ?? '(no response)'} ${result.error}`
    } else {
      detail = result.reason
    }
  } catch (error) {
    detail = firstLineOf(messageOf(error))
  }
  lastOutcome = detail ? { kind, at: await $.clock.now(), detail } : { kind, at: await $.clock.now() }
  if (kind === 'error' || kind === 'timeout' || kind === 'malformed') {
    logDebug($, `no aside for turn ${job.turnId}: ${kind}${detail ? `: ${detail}` : ''}`)
  }
  return reply
}

async function loadSession($: Engine, id: string): Promise<void> {
  if (loadedSessionId === id) return
  loadedSessionId = id
  bubble = null
  bubbleEpoch += 1
  const epoch = bubbleEpoch
  const saved = parseStoredBubble(await $.store.get(BUBBLE_PREFIX + id))
  if (saved === null || loadedSessionId !== id || bubbleEpoch !== epoch) return
  const picture = await pictureOf($, saved.avatarId)
  if (loadedSessionId !== id || bubbleEpoch !== epoch) return
  bubble = { ...saved, picture }
  $.ui.invalidate('ui.render')
}

async function saveBubble($: Engine, id: string, shown: Bubble): Promise<void> {
  const stored = { text: shown.text, avatarId: shown.avatarId, turnId: shown.turnId, at: shown.at }
  await $.store.set(BUBBLE_PREFIX + id, stored)
  const bytes = new TextEncoder().encode(JSON.stringify(stored)).length
  const storedIds = (await $.store.keys())
    .filter(key => key.startsWith(BUBBLE_PREFIX))
    .map(key => key.slice(BUBBLE_PREFIX.length))
  const plan = planIndex(
    parseIndex(await $.store.get(STORE_INDEX)),
    { id, t: await $.clock.now(), n: bytes },
    storedIds,
    MAX_STORED_SESSIONS,
    MAX_STORED_BYTES,
  )
  for (const evicted of plan.evict) await $.store.delete(BUBBLE_PREFIX + evicted)
  await $.store.set(STORE_INDEX, plan.index)
}

/** Takes the bubble down and forgets it, so neither a resume nor a reload brings it back. */
function clearBubble($: Engine): void {
  bubbleEpoch += 1
  if (bubble === null) return
  bubble = null
  $.ui.invalidate('ui.render')
  const id = loadedSessionId
  if (id === null) return
  void $.store.delete(BUBBLE_PREFIX + id).catch(error => logDebug($, `forgetting the bubble failed: ${messageOf(error)}`))
}

async function startJob($: Engine, job: Job, isRequested: boolean): Promise<void> {
  if (pendingTurns.has(job.turnId)) return
  if (!isRequested && !settings.enabled) return
  if (!(await isServed($))) return
  if (pendingTurns.size >= MAX_IN_FLIGHT) {
    lastOutcome = { kind: 'busy', at: await $.clock.now() }
    return
  }
  const id = await $.session.id()
  pendingTurns.add(job.turnId)
  $.ui.invalidate('ui.render')
  try {
    await loadSession($, id)
    pendingPicture = await pictureOf($, THINKING_AVATAR)
    $.ui.invalidate('ui.render')
    const reply = await generate($, job)
    if (reply === null || loadedSessionId !== id) return
    const known = await catalogOf($)
    const avatarId = known === null ? (reply.avatarId ?? '') : avatarFor(known, reply.avatarId).id
    const picture = await pictureOf($, avatarId)
    if (loadedSessionId !== id) return
    // An aside about an answer the person has already moved past stays unsaid.
    if (latestTurnId !== null && latestTurnId !== job.turnId) {
      lastOutcome = { kind: 'stale', at: await $.clock.now() }
      return
    }
    const shown: Bubble = { text: reply.text, avatarId, turnId: job.turnId, at: await $.clock.now(), picture }
    bubbleEpoch += 1
    bubble = shown
    $.ui.invalidate('ui.render')
    await saveBubble($, id, shown).catch(error => logDebug($, `saving the bubble failed: ${messageOf(error)}`))
  } finally {
    pendingTurns.delete(job.turnId)
    $.ui.invalidate('ui.render')
  }
}

/** Turns the bubble on or off through its `/config` row, which reloads this module with the new value. */
async function setEnabled($: Engine, enabled: boolean): Promise<string> {
  const rows = await $.config.list()
  const row = rows.find(candidate => candidate.provider.plugin === $.plugin.name && candidate.key.endsWith('.enabled'))
  if (row === undefined) return 'The Reviewer 2 bubble row is missing from /config.'
  const { deny } = await $.config.set({ key: row.key, value: enabled })
  if (deny !== undefined) return `Could not change it: ${deny}`
  return enabled
    ? 'Reviewer 2 bubble on. An aside appears above the prompt after each answer.'
    : `Reviewer 2 bubble off. /${COMMAND} on or /config turns it back on.`
}

async function statusText($: Engine): Promise<string> {
  const parts = [
    settings.enabled ? 'on' : 'off',
    (await isServed($)) ? 'this session is served' : 'this session is not served (Rev2Agent root only)',
    `model ${settings.model}`,
  ]
  if (pendingTurns.size > 0) parts.push(`${pendingTurns.size} drafting`)
  parts.push(`last: ${describeOutcome(lastOutcome, await $.clock.now())}`)
  return parts.join(' · ')
}

async function runCommand($: Engine, args: string): Promise<string> {
  const words = args.trim().toLowerCase().split(/\s+/).filter(word => word !== '')
  const [word = ''] = words
  if (words.length === 0 || (word === 'status' && words.length === 1)) return statusText($)
  if ((word === 'on' || word === 'off') && words.length === 1) return setEnabled($, word === 'on')
  if (word === 'again' && words.length === 1) {
    const job = lastJob
    if (job === null) return 'No answer to comment on yet.'
    if (pendingTurns.has(job.turnId)) return 'Reviewer 2 is already drafting that one.'
    if (!(await isServed($))) return 'This session is not served (Rev2Agent root only).'
    void startJob($, job, true).catch(error => logDebug($, `again failed: ${messageOf(error)}`))
    return 'Reviewer 2 is re-reading the last answer.'
  }
  return USAGE
}

function balloonOf(
  Box: (props: Record<string, unknown>) => RenderElement,
  inside: RenderElement[],
): RenderElement {
  return Box({
    key: 'reviewer2-bubble',
    flexDirection: 'row',
    columnGap: 1,
    flexShrink: 1,
    borderStyle: 'round',
    borderColor: ACCENT,
    paddingX: 1,
    children: inside,
  })
}

/** The bubble, or the waiting dots while the model drafts, with the avatar to its right. */
function drawDesktop($: Engine, e: RenderInput<'AbovePrompt', 'desktop'>, shown: Bubble | null): RenderElement {
  const { Box, Button, Svg, Text } = $.ui.resolve(e)
  const picture = shown === null ? pendingPicture : shown.picture
  const inside: RenderElement[] = [
    Box({
      flexShrink: 1,
      children: [
        shown === null ? Text({ dimColor: true, italic: true, children: ['…'] }) : Text({ children: [shown.text] }),
      ],
    }),
  ]
  if (shown !== null) {
    inside.push(Button({ key: 'reviewer2-dismiss', label: '×', plain: true, dimColor: true, onPress: () => clearBubble($) }))
  }
  const balloon = balloonOf(Box, inside)
  const alt = shown === null ? 'Reviewer 2 · thinking' : `Reviewer 2 · ${shown.avatarId}`
  return Box({
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'flex-end',
    columnGap: 1,
    children:
      picture === null
        ? [balloon]
        : [balloon, Svg({ source: avatarSvg(picture), alt, width: AVATAR_SIZE, height: AVATAR_SIZE })],
  })
}

/** The terminal draws the avatar only where it speaks the kitty graphics protocol. */
function drawTerminal($: Engine, e: RenderInput<'AbovePrompt', 'terminal'>, shown: Bubble | null): RenderElement {
  const { Box, Button, Image, Text } = $.ui.resolve(e)
  if (shown === null) return Text({ dimColor: true, italic: true, children: [PENDING_TEXT] })
  const balloon = balloonOf(Box, [
    Box({ flexShrink: 1, children: [Text({ children: [shown.text] })] }),
    Button({ key: 'reviewer2-dismiss', label: '×', plain: true, dimColor: true, onPress: () => clearBubble($) }),
  ])
  const children = [balloon]
  if (drawsImages && shown.picture !== null) {
    children.push(
      Image({
        key: 'reviewer2-avatar',
        source: { png: shown.picture },
        columns: IMAGE_COLUMNS,
        rows: IMAGE_ROWS,
        alt: 'Reviewer 2',
      }),
    )
  }
  return Box({ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'flex-end', columnGap: 1, children })
}

export function register(on: On, options: PluginOptions): void {
  settings = settingsOf(options)

  on('session.start', async ($, e, next) => {
    try {
      drawsImages = terminalDrawsImages({
        term: await $.env.get('TERM'),
        termProgram: await $.env.get('TERM_PROGRAM'),
        kittyWindow: await $.env.get('KITTY_WINDOW_ID'),
      })
    } catch (error) {
      logDebug($, `could not read the terminal's name: ${messageOf(error)}`)
    }
    try {
      await loadSession($, await $.session.id())
    } catch (error) {
      logDebug($, `loading the saved bubble failed: ${messageOf(error)}`)
    }
    try {
      await $.command.register({
        name: COMMAND,
        description: 'Reviewer 2 bubble: status, on/off, or comment on the last answer again',
        argumentHint: '[status|on|off|again]',
        immediate: true,
      })
    } catch (error) {
      logDebug($, `/${COMMAND} was not registered: ${messageOf(error)}`)
    }
    return next(e)
  })

  // /clear, /resume and /branch move the process to another session id
  // without a new session.start.
  on('classic.SessionStart', { source: ['resume', 'clear', 'fork'] }, async ($, e, next) => {
    promptsByTurn.clear()
    lastJob = null
    latestTurnId = null
    lastPersonPrompt = null
    try {
      await loadSession($, await $.session.id())
    } catch (error) {
      logDebug($, `loading the saved bubble failed: ${messageOf(error)}`)
    }
    $.ui.invalidate('ui.render')
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    if (isFromPerson(e.origin) && e.text.trim() !== '') lastPersonPrompt = e.text
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.text.trim() !== '') lastPrompt = e.text
    // A turn a task notification or a peer's message started carries that
    // text, not the person's: the aside reads the person's last own words.
    promptsByTurn.set(e.turnId, lastPersonPrompt ?? lastPrompt)
    while (promptsByTurn.size > MAX_TRACKED_TURNS) {
      const oldest = promptsByTurn.keys().next().value
      if (oldest === undefined) break
      promptsByTurn.delete(oldest)
    }
    latestTurnId = e.turnId
    clearBubble($)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const prompt = promptsByTurn.get(e.turnId) ?? lastPrompt
    promptsByTurn.delete(e.turnId)
    // Main-loop answers only: no subagent turns, interruptions, refusals or errors.
    if (e.agentId === undefined && e.reason === 'answer' && e.answer.trim() !== '') {
      const job: Job = { turnId: e.turnId, prompt, answer: e.answer }
      lastJob = job
      void startJob($, job, false).catch(error => logDebug($, `aside failed: ${messageOf(error)}`))
    }
    return next(e)
  })

  on('command.run', { command: COMMAND }, async ($, e) => ({ text: await runCommand($, e.args) }))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const shown = bubble
    const isPending = shown === null && pendingTurns.size > 0 && !e.props.isWorking
    if ((shown === null && !isPending) || e.props.hasSurvey || e.props.view?.agentId !== undefined) {
      return next(e)
    }
    let mine: RenderElement
    if (e.surface === 'terminal') mine = drawTerminal($, e, shown)
    else if (e.surface === 'desktop' || e.surface === 'vscode') mine = drawDesktop($, e as RenderInput<'AbovePrompt', 'desktop'>, shown)
    else return next(e)
    const { Box } = $.ui.resolve(e)
    const below = await next(e)
    return below ? Box({ flexDirection: 'column', children: [mine, below] }) : mine
  })
}
