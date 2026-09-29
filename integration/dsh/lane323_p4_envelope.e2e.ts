/**
 * Phase 3.2.3 P4: AgentLoop envelope dimensions + inventory toggle.
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

const MODEL = 'deepseek-v4-flash'
const PROVIDER = 'deepseek-official'
const PROMPT = 'Reply with exactly PONG.'

function collectText(chunk: any, acc: { text: string }) {
  if (chunk?.text) acc.text += chunk.text
  if (chunk?.delta?.text) acc.text += chunk.delta.text
}

it('P4 envelope dimensions + inventory toggle', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const results: any = {}

  // ---- Inventory OFF: minimal Agent ----
  try {
    const webOff = await launchWebScaffold({
      extraOverlayPath: undefined,
      // test-only overlay disabling inventory
    })
    // We'll use agentPresets option to define minimal + disable inventory via a patch file
    await webOff.close().catch(() => undefined)
  } catch { /* ignore */ }

  // Run with inventory disabled overlay
  const overlayPath = process.env.INVENTORY_OFF_PATCH
  const web = await launchWebScaffold({
    ...(overlayPath ? { extraOverlayPath: overlayPath } : {}),
    profile: { packages: [] },
    agentPresets: {
      default: 'minimal',
      definitions: [],
    },
  })
  try {
    const ctx: any = web.ctx
    const llm: any = ctx.llm

    // P4a: PreparedCall + toolHistory
    try {
      const prepared = await llm.prepareCall({ provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 })
      let sessionId = 'p4-session-1'
      // try to get toolHistory from a session if available
      let toolHistory: any = undefined
      try {
        const sess = (web as any).persistenceRoot ? null : null
        // toolHistory from agent session API if present
        toolHistory = undefined
      } catch { /* */ }
      const acc = { text: '' }
      for await (const chunk of prepared.stream({
        ...prepared.config,
        tools: [],
        messages: [
          { role: 'system', content: [{ type: 'text', text: 'You are a coding agent.' }] },
          { role: 'user', content: [{ type: 'text', text: PROMPT }] },
        ],
        sessionId,
        ...(toolHistory ? { toolHistory } : {}),
      })) collectText(chunk, acc)
      results.P4a_toolHistory = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
    } catch (e) {
      results.P4a_toolHistory = 'FAILED'
      results.P4a_err = String(e).slice(0, 150)
    }

    // P4b: deep-freeze message shape
    try {
      const prepared = await llm.prepareCall({ provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 })
      const frozenMsgs = Object.freeze([
        Object.freeze({ role: 'system', content: Object.freeze([Object.freeze({ type: 'text', text: 'You are a coding agent.' })]) }),
        Object.freeze({ role: 'user', content: Object.freeze([Object.freeze({ type: 'text', text: PROMPT })]) }),
      ])
      const acc = { text: '' }
      for await (const chunk of prepared.stream({
        ...prepared.config,
        tools: [],
        messages: frozenMsgs,
      })) collectText(chunk, acc)
      results.P4b_frozen = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
    } catch (e) {
      results.P4b_frozen = 'FAILED'
      results.P4b_err = String(e).slice(0, 150)
    }

    // P4c: markAgentLoopRequest if available
    try {
      const prepared = await llm.prepareCall({ provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 })
      const req: any = {
        ...prepared.config,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
      }
      if (typeof llm.markAgentLoopRequest === 'function') {
        llm.markAgentLoopRequest(req)
        results.P4c_marked = true
      } else {
        results.P4c_marked = false
      }
      const acc = { text: '' }
      for await (const chunk of prepared.stream(req)) collectText(chunk, acc)
      results.P4c_loopMarker = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
    } catch (e) {
      results.P4c_loopMarker = 'FAILED'
      results.P4c_err = String(e).slice(0, 200)
    }

    // Real minimal Agent (the known FAIL case) for comparison
    try {
      const handle = await ctx.agents.create({
        sessionId: `p4-agent-${Date.now()}`,
        meta: { cwd: web.workspaceCwd, agentPreset: 'minimal' },
        agentOptions: { provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50 },
        setup: async (agentCtx: any) => { await ctx.agentPresets.mount(agentCtx, 'minimal') },
      })
      const llmMod = await import(join(DSH_SRC, 'node_modules/@deepseek-ai/dsh-llm/lib/index.js')).catch(() => ({} as any))
      const createUserMessage = (llmMod as any).createUserMessage ?? ((x: any) => x)
      handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: PROMPT }], source: { kind: 'user' } }))
      await handle.agent.whenIdle()
      const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
      const finals = events.filter((e: any) => String(e.type).includes('assistant'))
      let text = ''
      for (const ev of finals) {
        const c = ev.data?.content ?? []
        text = (Array.isArray(c) ? c : []).map((b: any) => (b.type === 'text' ? b.text : '')).join('') || text
      }
      results.minimalAgent = text.includes('PONG') ? 'PASS' : 'FAILED'
      results.minimalAgent_text = text.slice(0, 40)
      results.minimalAgent_retries = events.filter((e: any) => e.type === 'llm/retry').length
      await handle.dispose?.().catch(() => undefined)
    } catch (e) {
      results.minimalAgent = 'FAILED'
      results.minimalAgent_err = String(e).slice(0, 150)
    }

    console.log('P4_RESULTS', JSON.stringify(results))
  } finally {
    await web.close().catch(() => undefined)
  }
}, 300_000)
