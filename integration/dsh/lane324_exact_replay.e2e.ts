/**
 * Phase 3.2.4: capture exact AgentLoop llm/stream request and replay it.
 * Uses real exported markAgentLoopRequest / isAgentLoopRequest / SessionId / toolHistory.
 * Sanitized structural fingerprint only — no full prompt/messages/tools/secrets.
 */
import { it, expect } from 'vitest'
import { createHash } from 'node:crypto'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

const MODEL = 'deepseek-v4-flash'
const PROVIDER = 'deepseek-official'
const PROMPT = 'Reply with exactly PONG.'

function structuralFingerprint(opts: any, extra: Record<string, unknown> = {}) {
  const msgs = opts?.messages ?? []
  const tools = opts?.tools ?? []
  const roleSeq = msgs.map((m: any) => m.role)
  const blockSeq = msgs.map((m: any) => (m.content ?? []).map((b: any) => b.type).join(','))
  const toolNameHash = createHash('sha256')
    .update(tools.map((t: any) => t.name).sort().join('|'))
    .digest('hex')
    .slice(0, 16)
  const structural = JSON.stringify({
    provider: opts?.provider,
    model: opts?.model,
    reasoningEffort: opts?.reasoningEffort ?? null,
    maxTokens: opts?.maxTokens ?? null,
    sessionId: opts?.sessionId != null ? String(opts.sessionId) : null,
    frozen: Object.isFrozen(opts),
    messagesFrozen: Object.isFrozen(msgs),
    msgCount: msgs.length,
    roleSeq,
    blockSeq,
    toolsCount: tools.length,
    toolNameHash,
    hasToolHistory: opts?.toolHistory != null,
    hasPurpose: opts?.purpose != null,
    topKeys: Object.keys(opts ?? {}).sort(),
  })
  return {
    ...extra,
    provider: opts?.provider,
    model: opts?.model,
    reasoningEffort: opts?.reasoningEffort ?? null,
    maxTokens: opts?.maxTokens ?? null,
    session_present: opts?.sessionId != null,
    isAgentLoop: null as boolean | null,
    request_frozen: Object.isFrozen(opts),
    messages_frozen: Object.isFrozen(msgs),
    msg_count: msgs.length,
    role_seq: roleSeq,
    block_seq: blockSeq,
    tools_count: tools.length,
    tool_name_hash: toolNameHash,
    toolHistory_present: opts?.toolHistory != null,
    purpose_present: opts?.purpose != null,
    top_keys: Object.keys(opts ?? {}).sort(),
    structural_sha256: createHash('sha256').update(structural).digest('hex'),
  }
}

it('exact captured AgentLoop request replay', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const llm = await import('@deepseek-ai/dsh-llm')
  const sessMod = await import('@deepseek-ai/dsh-session').catch(() => ({} as any))
  const markAgentLoopRequest = llm.markAgentLoopRequest
  const isAgentLoopRequest = llm.isAgentLoopRequest
  const SessionId = (sessMod as any).SessionId ?? llm.SessionId
  if (typeof markAgentLoopRequest !== 'function' || typeof isAgentLoopRequest !== 'function') {
    throw new Error('markAgentLoopRequest/isAgentLoopRequest not exported from dsh-llm')
  }

  const web = await launchWebScaffold({})
  const report: any = { probes: {}, capture: null, exact_replay: null, bisect: {} }
  let captured: any = null
  let allStreamCount = 0
  const allStreamMarkers: boolean[] = []
  let capturedFingerprint: any = null
  try {
    const ctx: any = web.ctx

    // Register prepend observer to capture exact AgentLoop request
    const dispose = ctx.on('llm/stream', (options: any, next: any) => {
      try {
        allStreamCount++
        allStreamMarkers.push(isAgentLoopRequest(options))
        const marked = isAgentLoopRequest(options)
        if (marked && captured === null) {
          captured = options
          try { capturedFingerprint = structuralFingerprint(options, { isAgentLoop: true }) } catch { capturedFingerprint = { error: 'fingerprint_failed' } }
        }
      } catch { /* observer must not break stream */ }
      return next()
    }, { prepend: true })

    // --- real minimal Agent to reproduce failure ---
    const targetSessionId = `cap-${Date.now()}`
    const handle = await ctx.agents.create({
      sessionId: SessionId ? SessionId(targetSessionId) : targetSessionId,
      meta: { cwd: web.workspaceCwd, agentPreset: 'minimal' },
      agentOptions: { provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 },
      setup: async (agentCtx: any) => { await ctx.agentPresets.mount(agentCtx, 'minimal') },
    })
    const createUserMessage = (llm as any).createUserMessage
    handle.agent.followup(createUserMessage({
      content: [{ type: 'text', text: PROMPT }],
      source: { kind: 'user' },
    }))
    await handle.agent.whenIdle()

    const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
    report.minimal_agent_retries = events.filter((e: any) => e.type === 'llm/retry').length
    report.minimal_agent_failed = report.minimal_agent_retries > 0
    report.event_types = [...new Set(events.map((e: any) => e.type))]
    report.event_count = events.length
    report.has_request_header = events.some((e: any) => e.type === 'request/header')
    // capture ALL llm/stream calls (not just agent-loop marked)
    report.all_stream_count = allStreamCount
    report.all_stream_markers = allStreamMarkers
    const asst = events.filter((e: any) => e.type === 'assistant/message')
    report.assistant_text = asst.map((e: any) => (e.data?.content ?? []).map((b: any) => b.text ?? '').join('')).join('|').slice(0, 80)
    report.capture_debug = captured ? 'set' : 'null'

    // --- exact captured replay BEFORE dispose ---
    if (captured) {
      report.capture = capturedFingerprint
      try {
        const prepared = await ctx.llm.prepareCall({
          provider: captured.provider ?? PROVIDER,
          model: captured.model ?? MODEL,
          reasoningEffort: captured.reasoningEffort ?? 'off',
          maxTokens: captured.maxTokens ?? 50,
        })
        let text = ''
        for await (const chunk of prepared.stream(captured)) {
          if (chunk?.text) text += chunk.text
          if (chunk?.delta?.text) text += chunk.delta.text
        }
        report.exact_replay = {
          status: text.includes('PONG') ? 'PASS' : 'FAILED',
          text_len: text.length,
          marker_still: isAgentLoopRequest(captured),
        }
      } catch (e) {
        report.exact_replay = {
          status: 'FAILED',
          error: String(e).slice(0, 250),
          marker_still: (() => { try { return isAgentLoopRequest(captured) } catch { return null } })(),
        }
      }

      // --- clone-and-bisect if exact replay FAIL ---
      if (report.exact_replay.status === 'FAILED') {
        const variants: Array<[string, (o: any) => any]> = [
          ['A_no_marker', (o) => { const c = { ...o }; delete (c as any)[Symbol.for('dsh.agentLoop')]; return c }],
          ['B_with_marker', (o) => markAgentLoopRequest({ ...o })],
          ['C_no_session', (o) => { const c = { ...o }; delete c.sessionId; return c }],
          ['D_no_toolHistory', (o) => { const c = { ...o }; delete c.toolHistory; return c }],
          ['E_no_tools', (o) => ({ ...o, tools: [] })],
          ['F_single_pong_user', (o) => ({ ...o, messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }] })],
          ['G_no_system', (o) => ({ ...o, messages: (o.messages ?? []).filter((m: any) => m.role !== 'system') })],
        ]
        for (const [name, mutate] of variants) {
          try {
            const prepared = await ctx.llm.prepareCall({
              provider: captured.provider ?? PROVIDER,
              model: captured.model ?? MODEL,
              reasoningEffort: 'off',
              maxTokens: 50,
            })
            const variant = mutate({ ...captured })
            let text = ''
            for await (const chunk of prepared.stream(variant)) {
              if (chunk?.text) text += chunk.text
              if (chunk?.delta?.text) text += chunk.delta.text
            }
            report.bisect[name] = text.includes('PONG') ? 'PASS' : 'FAILED'
          } catch (e) {
            report.bisect[name] = 'FAILED'
            report.bisect[name + '_err'] = String(e).slice(0, 120)
          }
        }
      }
    } else {
      report.capture = null
      report.exact_replay = { status: 'NOT_RUN', error: 'no captured AgentLoop request' }
    }

    // --- real P2/P3/P4 with real APIs ---
    try {
      const realSid = SessionId ? SessionId(`real-p2-${Date.now()}`) : `real-p2-${Date.now()}`
      // P2: direct stream + real sessionId (from session create if available)
      let sessObj: any = null
      try {
        sessObj = await ctx.sessions?.create?.(realSid)
      } catch { /* session create may not exist */ }
      const sidValue = sessObj?.id ?? realSid
      const prepared2 = await ctx.llm.prepareCall({ provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 })
      let t2 = ''
      for await (const chunk of prepared2.stream({
        ...prepared2.config,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
        sessionId: sidValue,
      })) { if (chunk?.text) t2 += chunk.text; if (chunk?.delta?.text) t2 += chunk.delta.text }
      report.probes.P2_real_session = t2.includes('PONG') ? 'PASS' : 'FAILED'

      // P4: real toolHistory from session if available
      let toolHistory: any = undefined
      try {
        toolHistory = sessObj?.toolHistory?.() ?? handle.agent.session?.toolHistory?.()
      } catch { /* */ }
      report.probes.P4_toolHistory_present = toolHistory != null
      const prepared4 = await ctx.llm.prepareCall({ provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 })
      const req4 = {
        ...prepared4.config,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
        sessionId: sidValue,
        ...(toolHistory ? { toolHistory } : {}),
      }
      markAgentLoopRequest(req4)
      report.probes.P4_marker = isAgentLoopRequest(req4) === true
      let t4 = ''
      for await (const chunk of prepared4.stream(req4)) { if (chunk?.text) t4 += chunk.text; if (chunk?.delta?.text) t4 += chunk.delta.text }
      report.probes.P4_marked_stream = t4.includes('PONG') ? 'PASS' : 'FAILED'
    } catch (e) {
      report.probes.P2_P4_err = String(e).slice(0, 200)
    }

    await handle.dispose?.().catch(() => undefined)
    dispose?.()
    console.log('EXACT_REPORT', JSON.stringify(report))
  } finally {
    await web.close().catch(() => undefined)
  }
  expect(report.capture).toBeTruthy()
}, 300_000)
