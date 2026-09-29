/**
 * Phase 3.2.3 C0/P1/P2/P3 probes for PreparedCall / session-aware isolation.
 * No body previews. Sanitized facts only.
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

it('C0/P1/P2/P3 binary isolation', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const web = await launchWebScaffold({})
  const results: any = {}
  try {
    const ctx: any = web.ctx
    const llm: any = ctx.llm

    // ---- C0: direct ctx.llm.stream, no session, no tools ----
    try {
      const acc = { text: '' }
      for await (const chunk of llm.stream({
        provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50,
        tools: [], messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
      })) collectText(chunk, acc)
      results.C0 = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
      results.C0_text = acc.text.slice(0, 40)
    } catch (e) {
      results.C0 = 'FAILED'
      results.C0_err = String(e).slice(0, 150)
    }

    // ---- P1: PreparedCall.stream without session ----
    try {
      const prepared = await llm.prepareCall({
        provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50,
      })
      const acc = { text: '' }
      for await (const chunk of prepared.stream({
        ...prepared.config,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
      })) collectText(chunk, acc)
      results.P1 = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
      results.P1_text = acc.text.slice(0, 40)
      results.P1_preparedKeys = Object.keys(prepared).slice(0, 12)
    } catch (e) {
      results.P1 = 'FAILED'
      results.P1_err = String(e).slice(0, 200)
    }

    // ---- P2: direct stream + real sessionId ----
    let sessionId: any = null
    try {
      const sess = await web.ctx.session?.create?.() ?? await web.ctx.sessions?.create?.()
      sessionId = sess?.id ?? sess?.sessionId ?? String(sess)
      results.P2_session = String(sessionId).slice(0, 40)
    } catch (e) {
      results.P2_session_err = String(e).slice(0, 100)
    }
    try {
      const acc = { text: '' }
      for await (const chunk of llm.stream({
        provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50,
        tools: [], messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
        sessionId,
      })) collectText(chunk, acc)
      results.P2 = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
      results.P2_text = acc.text.slice(0, 40)
    } catch (e) {
      results.P2 = 'FAILED'
      results.P2_err = String(e).slice(0, 200)
    }

    // ---- P3: PreparedCall.stream + sessionId ----
    try {
      const prepared = await llm.prepareCall({
        provider: PROVIDER, model: MODEL, reasoningEffort: 'off', maxTokens: 50,
      })
      const acc = { text: '' }
      for await (const chunk of prepared.stream({
        ...prepared.config,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: PROMPT }] }],
        sessionId,
      })) collectText(chunk, acc)
      results.P3 = acc.text.includes('PONG') ? 'PASS' : 'FAILED'
      results.P3_text = acc.text.slice(0, 40)
    } catch (e) {
      results.P3 = 'FAILED'
      results.P3_err = String(e).slice(0, 200)
    }

    console.log('PROBE_RESULTS', JSON.stringify(results))
    // C0 must pass; others report status
    expect(results.C0).toBe('PASS')
  } finally {
    await web.close().catch(() => undefined)
  }
}, 300_000)
