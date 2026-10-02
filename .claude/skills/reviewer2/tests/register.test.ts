import type { Engine } from 'claude-code/testing'
import { describe, expect, test } from 'claude-code/testing'

import { buildPayload, formatInstruction, parseCatalog } from '../hooks/bubble'
import {
  bandOf,
  command,
  completed,
  imagesOf,
  MANIFEST,
  pngOf,
  ROOT,
  START_MS,
  svgOf,
  svgsOf,
  SYSTEM_PROMPT,
  textOf,
  worldOf,
} from './fixtures'

const SESSION = { surface: 'desktop', isInteractive: true, cwd: ROOT } as const
const PROMPT = '실험 결과 어때?'
const ANSWER = '정확도가 기준선보다 0.4%p 올랐습니다. 시드 3개 평균입니다.'
const ASIDE = '시드 셋으로 0.4%p라. 신뢰구간은 기도로 구했나?'
const REPLY = `[skeptical]\n${ASIDE}`
const SHOWN = `${ASIDE}[×]`
const PENDING = 'Reviewer 2 is drafting comments…'
const INSTRUCTION = formatInstruction(parseCatalog(MANIFEST)!)

/** Raises the settings hook event Claude Code fires after `/clear`, `/resume` or `/branch`. */
async function sessionStartsOver($: Engine, source: 'resume' | 'clear' | 'fork'): Promise<void> {
  const classic = ($ as unknown as { classic: { SessionStart: (e: object) => Promise<unknown> } }).classic
  await classic.SessionStart({ source })
}

describe('register', () => {
  test('the module loads, registers /reviewer2, and a fresh session reports its state', async ($, on) => {
    const world = worldOf(on)

    await $.session.start(SESSION)

    expect(world.commands).toEqual([
      {
        name: 'reviewer2',
        description: 'Reviewer 2 bubble: status, on/off, or comment on the last answer again',
        argumentHint: '[status|on|off|again]',
        immediate: true,
      },
    ])
    expect((await $.command.run(command(''))).text).toBe('on · this session is served · model haiku · last: none yet')
  })

  test('a finished answer shows the aside in a bubble beside the avatar the model named', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: `${REPLY}\n` })

    await $.session.start(SESSION)
    await $.turn.start({ text: PROMPT, turnId: 't1' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    expect(world.calls).toEqual([
      {
        model: 'haiku',
        system: `${SYSTEM_PROMPT}\n\n${INSTRUCTION}`,
        prompt: buildPayload(PROMPT, ANSWER),
        maxTokens: 300,
        effort: 'low',
        timeoutMs: 30_000,
      },
    ])
    for (const surface of ['desktop', 'vscode'] as const) {
      const drawing = await $.ui.render(bandOf(surface))
      expect(textOf(drawing)).toBe(SHOWN)
      expect(svgsOf(drawing)).toEqual([svgOf('skeptical')])
    }
    // A terminal without the kitty graphics protocol shows the bubble alone.
    const terminal = await $.ui.render(bandOf('terminal'))
    expect(textOf(terminal)).toBe(SHOWN)
    expect(imagesOf(terminal)).toEqual([])
    expect(world.store.get('bubble:session-1')).toEqual({ text: ASIDE, avatarId: 'skeptical', turnId: 't1', at: START_MS })
    expect(world.store.get('bubbles')).toMatchObject([{ id: 'session-1', t: START_MS }])
  })

  test('a terminal that draws pictures shows the avatar beside the bubble', async ($, on) => {
    const world = worldOf(on)
    world.env.set('TERM', 'xterm-kitty')
    world.replies.push({ text: REPLY })

    await $.session.start({ ...SESSION, surface: 'terminal' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    const terminal = await $.ui.render(bandOf('terminal'))
    expect(textOf(terminal)).toBe(SHOWN)
    expect(imagesOf(terminal)).toEqual([{ png: pngOf('skeptical') }])
  })

  test('turn.complete returns before the model answers, and the thinking avatar waits in the band', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY, delayMs: 5_000 })

    await $.session.start(SESSION)
    await $.turn.start({ text: PROMPT, turnId: 't1' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    expect(world.calls.length).toBe(1)
    const waiting = await $.ui.render(bandOf())
    expect(textOf(waiting)).toBe('…')
    expect(svgsOf(waiting)).toEqual([svgOf('thinking')])
    expect(textOf(await $.ui.render(bandOf('terminal')))).toBe(PENDING)
    expect(textOf(await $.ui.render(bandOf('desktop', { isWorking: true })))).toBe('')

    await world.clock.advance(5_000)
    expect(textOf(await $.ui.render(bandOf()))).toBe(SHOWN)
  })

  test("a turn a notification started reads the person's last own prompt, not the notification", async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY }, { text: REPLY })
    const NOTE = 'survey agent finished: 10 papers, all BibTeX verified.'

    await $.session.start(SESSION)
    // The test kit leaves origin unset unless given: unset reads as the person's own.
    const submit = $.prompt.submit as (input: object) => Promise<unknown>
    await submit({ text: PROMPT })
    await $.turn.start({ text: PROMPT, turnId: 't1' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    await submit({ text: NOTE, origin: { kind: 'task-notification' } })
    await $.turn.start({ text: NOTE, turnId: 't2' })
    await $.turn.complete(completed('t2', '서베이 에이전트도 끝났습니다.'))
    await world.clock.settle()

    expect(world.calls.map(call => call.prompt)).toEqual([
      buildPayload(PROMPT, ANSWER),
      buildPayload(PROMPT, '서베이 에이전트도 끝났습니다.'),
    ])
  })

  test('the next prompt takes the bubble down, and an aside that finishes after it stays unsaid', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY }, { text: '[cheer]\n늦은 한마디', delayMs: 5_000 })

    await $.session.start(SESSION)
    await $.turn.start({ text: PROMPT, turnId: 't1' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(textOf(await $.ui.render(bandOf()))).toBe(SHOWN)

    await $.turn.start({ text: '다음 질문', turnId: 't2' })
    expect(textOf(await $.ui.render(bandOf()))).toBe('')
    expect(world.store.has('bubble:session-1')).toBe(false)

    await $.turn.complete(completed('t2', '두 번째 답'))
    await $.turn.start({ text: '세 번째 질문', turnId: 't3' })
    await world.clock.advance(5_000)
    expect(textOf(await $.ui.render(bandOf()))).toBe('')
    expect((await $.command.run(command('status'))).text).toContain('the next turn started first')
  })

  test('the × takes the bubble down and forgets it', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY })

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    const ui = await $.ui.mount({ ...bandOf('desktop'), plugin: 'reviewer2' })
    expect(await ui.find({ type: 'Svg' })).toBeDefined()
    await ui.press({ key: 'reviewer2-dismiss' })
    await ui.unmount()
    await world.clock.settle()

    expect(textOf(await $.ui.render(bandOf()))).toBe('')
    expect(world.store.has('bubble:session-1')).toBe(false)
  })

  test('a missing or unknown avatar id falls back to the default, and a trailing one counts', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: '태그 없는 한마디' }, { text: '[nope]\n모르는 표정' }, { text: '끝에 붙인 표정 [cheer]' })
    const band = async () => {
      const drawing = await $.ui.render(bandOf())
      return { text: textOf(drawing), svgs: svgsOf(drawing) }
    }

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(await band()).toEqual({ text: '태그 없는 한마디[×]', svgs: [svgOf('stern')] })

    await $.turn.start({ text: PROMPT, turnId: 't2' })
    await $.turn.complete(completed('t2', ANSWER))
    await world.clock.settle()
    expect(await band()).toEqual({ text: '모르는 표정[×]', svgs: [svgOf('stern')] })

    await $.turn.start({ text: PROMPT, turnId: 't3' })
    await $.turn.complete(completed('t3', ANSWER))
    await world.clock.settle()
    expect(await band()).toEqual({ text: '끝에 붙인 표정[×]', svgs: [svgOf('cheer')] })
  })

  test('other projects, subagents, interruptions, refusals and errors get no aside', async ($, on) => {
    const world = worldOf(on)

    await $.session.start(SESSION)
    await $.turn.complete({ ...completed('t1', ANSWER), agentId: 'agent-1' })
    await $.turn.complete({ ...completed('t2', ANSWER), reason: 'aborted', isAborted: true })
    await $.turn.complete({ ...completed('t3', ANSWER), reason: 'error' })
    await $.turn.complete(completed('t4', '   '))
    await world.clock.settle()
    expect(world.calls).toEqual([])

    world.markers.clear()
    world.root = '/work/other-project'
    await $.turn.complete(completed('t5', ANSWER))
    await world.clock.settle()
    expect(world.calls).toEqual([])
    expect((await $.command.run(command('status'))).text).toContain('this session is not served (Rev2Agent root only)')
  })

  test('SKIP, a reply out of format, an API error and a timeout show no bubble and show in /reviewer2', async ($, on) => {
    const world = worldOf(on)
    world.replies.push(
      { text: '[stern]\nSKIP' },
      { text: '사용자가 말풍선 문제를 보고했습니다.\n\n제 역할은 뭔가요?\n- 원인을 명확' },
      { reason: 'api-error' },
      { reason: 'aborted' },
    )
    const status = async () => (await $.command.run(command('status'))).text

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(textOf(await $.ui.render(bandOf()))).toBe('')
    expect(await status()).toContain('last: skipped by Reviewer 2 (0s ago)')

    await $.turn.complete(completed('t2', ANSWER))
    await world.clock.settle()
    expect(textOf(await $.ui.render(bandOf()))).toBe('')
    expect(await status()).toContain(
      'last: not shown, the reply was not in the format: 사용자가 말풍선 문제를 보고했습니다. (0s ago)',
    )

    await $.turn.complete(completed('t3', ANSWER))
    await world.clock.settle()
    expect(await status()).toContain('last: failed: API error 529 overloaded (0s ago)')

    await $.turn.complete(completed('t4', ANSWER))
    await world.clock.settle()
    expect(await status()).toContain('last: timed out (0s ago)')
    expect(textOf(await $.ui.render(bandOf()))).toBe('')
  })

  test('turned off in /config, no aside is drafted, and /reviewer2 on flips the /config row', { options: { enabled: false } }, async ($, on) => {
    const world = worldOf(on)
    world.config.enabled = false

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(world.calls).toEqual([])
    expect((await $.command.run(command('status'))).text).toMatch(/^off · /)

    expect((await $.command.run(command('on'))).text).toBe(
      'Reviewer 2 bubble on. An aside appears above the prompt after each answer.',
    )
    expect((await $.command.run(command('off'))).text).toBe(
      'Reviewer 2 bubble off. /reviewer2 on or /config turns it back on.',
    )
    expect(world.configSets).toEqual([
      { key: 'reviewer2.enabled', value: true },
      { key: 'reviewer2.enabled', value: false },
    ])
  })

  test('the model named in /config writes the aside', { options: { model: 'sonnet' } }, async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY })

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(world.calls.map(call => call.model)).toEqual(['sonnet'])
    expect((await $.command.run(command('status'))).text).toContain('model sonnet')
  })

  test('/reviewer2 again asks once more for the last answer, even when off', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: '[stern]\nSKIP' }, { text: REPLY })

    await $.session.start(SESSION)
    expect((await $.command.run(command('again'))).text).toBe('No answer to comment on yet.')
    await $.turn.start({ text: PROMPT, turnId: 't1' })
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()
    expect(textOf(await $.ui.render(bandOf()))).toBe('')

    expect((await $.command.run(command('again'))).text).toBe('Reviewer 2 is re-reading the last answer.')
    await world.clock.settle()
    expect(world.calls.length).toBe(2)
    expect(world.calls[1]!.prompt).toBe(buildPayload(PROMPT, ANSWER))
    expect(textOf(await $.ui.render(bandOf()))).toBe(SHOWN)
    expect((await $.command.run(command('loudly'))).text).toBe('Usage: /reviewer2 [status|on|off|again]')
  })

  test('a saved bubble comes back at start and after a resume', async ($, on) => {
    const saved = (text: string, avatarId: string) => ({ text, avatarId, turnId: 't0', at: START_MS - 10 })
    const world = worldOf(on, {
      store: { 'bubble:session-1': saved(ASIDE, 'skeptical'), 'bubble:session-2': saved('예전 한마디', 'cheer') },
    })

    await $.session.start(SESSION)
    const first = await $.ui.render(bandOf())
    expect(textOf(first)).toBe(SHOWN)
    expect(svgsOf(first)).toEqual([svgOf('skeptical')])

    world.sessionId = 'session-2'
    await sessionStartsOver($, 'resume')

    const second = await $.ui.render(bandOf())
    expect(textOf(second)).toBe('예전 한마디[×]')
    expect(svgsOf(second)).toEqual([svgOf('cheer')])
  })

  test('without the avatars the bubble shows alone and the model gets no format', async ($, on) => {
    const world = worldOf(on)
    world.manifest = undefined
    world.replies.push({ text: REPLY })

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    expect(world.calls[0]!.system).toBe(SYSTEM_PROMPT)
    const drawing = await $.ui.render(bandOf())
    expect(textOf(drawing)).toBe(SHOWN)
    expect(svgsOf(drawing)).toEqual([])
  })

  test('the band yields to a survey and to a subagent transcript', async ($, on) => {
    const world = worldOf(on)
    world.replies.push({ text: REPLY })

    await $.session.start(SESSION)
    await $.turn.complete(completed('t1', ANSWER))
    await world.clock.settle()

    expect(textOf(await $.ui.render(bandOf('desktop', { hasSurvey: true })))).toBe('')
    expect(textOf(await $.ui.render(bandOf('desktop', { view: { agentId: 'agent-1' } })))).toBe('')
  })
})
