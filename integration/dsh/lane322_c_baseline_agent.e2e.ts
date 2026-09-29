/**
 * Phase 3.2.2 Lane C: baseline minimal-preset Agent returns PONG.
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

it('lane C: minimal preset Agent returns PONG', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const web = await launchWebScaffold({})
  try {
    const ctx: any = web.ctx
    const llmSpy: any = { calls: [] }
    for (const methodName of ['stream', 'generate', 'request', 'complete', 'chat']) {
      const orig = (ctx.llm as any)[methodName]
      if (typeof orig === 'function') {
        ;(ctx.llm as any)[methodName] = (...args: any[]) => {
          llmSpy.calls.push({ method: methodName, argKeys: Object.keys(args[0] ?? {}), argPreview: JSON.stringify(args[0] ?? {}).slice(0, 200) })
          return orig.apply(ctx.llm, args)
        }
      }
    }
    const origStream = ctx.llm.stream.bind(ctx.llm)
    ctx.llm.stream = (opts: any) => {
      llmSpy.calls.push(JSON.parse(JSON.stringify({
        provider: opts?.provider,
        model: opts?.model,
        reasoningEffort: opts?.reasoningEffort,
        maxTokens: opts?.maxTokens,
        toolCount: (opts?.tools ?? []).length,
        msgCount: (opts?.messages ?? []).length,
        msgRoles: (opts?.messages ?? []).map((m: any) => m.role),
        extraKeys: Object.keys(opts ?? {}).filter((k) => !['provider','model','reasoningEffort','maxTokens','tools','messages','signal'].includes(k)),
      })))
      return origStream(opts)
    }
    const fetchLog: any[] = []
    const origFetch = globalThis.fetch
    globalThis.fetch = async (input: any, init: any) => {
      const url = typeof input === 'string' ? input : (input?.url ?? '')
      const bodyPreview = typeof init?.body === 'string' ? init.body.slice(0, 300) : String(init?.body?.slice?.(0, 300) ?? '')
      fetchLog.push({ url: String(url).slice(0, 120), method: init?.method, bodyLen: typeof init?.body === 'string' ? init.body.length : -1, bodyPreview })
      try {
        const resp = await origFetch(input, init)
        fetchLog.push({ status: resp.status, ok: resp.ok })
        return resp
      } catch (e) {
        fetchLog.push({ fetchError: String(e).slice(0, 200) })
        throw e
      }
    }
    const handle = await ctx.agents.create({
      sessionId: `lane-c-${Date.now()}`,
      meta: { cwd: web.workspaceCwd, agentPreset: 'minimal' },
      agentOptions: {
        provider: 'deepseek-official',
        model: 'deepseek-v4-flash',
        reasoningEffort: 'off',
        maxTokens: 50,
      },
      setup: async (agentCtx: any) => {
        await ctx.agentPresets.mount(agentCtx, 'minimal')
      },
    })
    // createUserMessage from dsh-llm
    // Spy on agent-scoped llm
    const agentLlm: any = handle.agent.ctx?.llm
    if (agentLlm) {
      for (const methodName of ['stream', 'generate', 'request', 'complete']) {
        const orig = agentLlm[methodName]
        if (typeof orig === 'function') {
          agentLlm[methodName] = (...args: any[]) => {
            llmSpy.calls.push({ method: 'agent.' + methodName, argKeys: Object.keys(args[0] ?? {}), preview: JSON.stringify(args[0] ?? {}).slice(0, 250) })
            return orig.apply(agentLlm, args)
          }
        }
      }
    }
    // Direct stream from agent scope
    try {
      let directText = ''
      const agentLlm2: any = handle.agent.ctx?.llm ?? ctx.llm
      for await (const chunk of agentLlm2.stream({
        provider: 'deepseek-official',
        model: 'deepseek-v4-flash',
        reasoningEffort: 'off',
        maxTokens: 50,
        tools: [],
        messages: [{ role: 'user', content: [{ type: 'text', text: 'Reply with exactly PONG.' }] }],
      })) {
        if (chunk?.text) directText += chunk.text
      }
      console.log('LANE_C_DIRECT', JSON.stringify({ directText: directText.slice(0, 40) }))
    } catch (de) {
      console.log('LANE_C_DIRECT_ERR', String(de).slice(0, 200))
    }
    const llmMod = await import(join(DSH_SRC, 'node_modules/@deepseek-ai/dsh-llm/lib/index.js')).catch(() => ({} as any))
    const createUserMessage = (llmMod as any).createUserMessage ?? ((x: any) => x)
    handle.agent.followup(createUserMessage({
      content: [{ type: 'text', text: 'Reply with exactly PONG.' }],
      source: { kind: 'user' },
    }))
    await handle.agent.whenIdle()
    const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
    const finals = events.filter((e: any) => String(e.type).includes('assistant'))
    let text = ''
    for (const ev of finals) {
      const c = ev.data?.content ?? []
      const t = (Array.isArray(c) ? c : []).map((b: any) => (b.type === 'text' ? b.text : '')).join('')
      if (t.trim()) text = t
    }
    console.log('LANE_C_RESULT', JSON.stringify({
      text: text.slice(0, 100),
      eventTypes: [...new Set(events.map((e: any) => e.type))].slice(0, 25),
      finalCount: finals.length,
    }))
    const req = events.find((e: any) => e.type === 'request/header')
    console.log('LANE_C_REQ_KEYS', JSON.stringify(Object.keys(req?.data?.header?.config ?? {})))
    console.log('LANE_C_REQ_CONFIG', JSON.stringify(req?.data?.header?.config ?? {}))
    console.log('LANE_C_REQ_META', JSON.stringify({ ...req?.data, header: undefined }).slice(0, 500))
    console.log('LANE_C_TOOL_COUNT', (req?.data?.header?.tools ?? []).length)
    const hdr = req?.data?.header ?? {}
    console.log('LANE_C_SPY', JSON.stringify(llmSpy.calls).slice(0, 400))
    console.log('LANE_C_FETCH', JSON.stringify(fetchLog).slice(0, 1000))
    console.log('LANE_C_HDR_KEYS', JSON.stringify(Object.keys(hdr)))
    const msgs = hdr.messages ?? []
    console.log('LANE_C_MSGS', msgs.length, JSON.stringify(msgs.map((m: any) => ({ role: m.role, blocks: (m.content ?? []).map((b: any) => b.type) }))).slice(0, 400))
    console.log('LANE_C_HDR_FULL_NO_MSG', JSON.stringify({ ...hdr, messages: undefined, tools: undefined }).slice(0, 600))
    const attempts = events.filter((e: any) => e.type === 'assistant/attempt')
    console.log('LANE_C_ATTEMPT0', JSON.stringify(attempts[0]?.data ?? {}).slice(0, 500))
    const retries = events.filter((e: any) => String(e.type).includes('llm/retry'))
    console.log('LANE_C_RETRY', JSON.stringify(retries[0]?.data ?? {}).slice(0, 600))
    const fail = retries[0]?.data?.failure
    if (fail) {
      console.log('LANE_C_FAIL_MSG', fail.message, 'CODE', fail.code, 'CAUSE', String(fail.cause ?? fail.detail ?? '').slice(0, 300))
    }
    // also dump assistant attempt stream chunks
    const attemptStream = attempts[0]?.data?.stream
    if (attemptStream) {
      console.log('LANE_C_STREAM', JSON.stringify(attemptStream).slice(0, 600))
    }
    expect(text).toContain('PONG')
    await handle.dispose?.().catch(() => undefined)
  } finally {
    await web.close().catch(() => undefined)
  }
}, 180_000)
