/**
 * Phase 3.2.2 Lane C variant: Agent with empty preset (no tools) PONG.
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

it('lane C2: empty-preset Agent (no tools) returns PONG', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const web = await launchWebScaffold({
    agentPresets: {
      default: 'bare',
      definitions: [{ id: 'bare', name: 'bare', plugins: [] }],
    },
  })
  try {
    const ctx: any = web.ctx
    const handle = await ctx.agents.create({
      sessionId: `lane-c2-${Date.now()}`,
      meta: { cwd: web.workspaceCwd, agentPreset: 'bare' },
      agentOptions: {
        provider: 'deepseek-official',
        model: 'deepseek-v4-flash',
        reasoningEffort: 'off',
        maxTokens: 50,
      },
      setup: async (agentCtx: any) => {
        await ctx.agentPresets.mount(agentCtx, 'bare')
      },
    })
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
    const req = events.find((e: any) => e.type === 'request/header')
    const tools = req?.data?.header?.tools ?? []
    console.log('LANE_C2', JSON.stringify({
      text: text.slice(0, 80),
      toolCount: tools.length,
      toolNames: tools.map((t: any) => t.name),
      retryCount: events.filter((e: any) => e.type === 'llm/retry').length,
    }))
    expect(text).toContain('PONG')
    await handle.dispose?.().catch(() => undefined)
  } finally {
    await web.close().catch(() => undefined)
  }
}, 180_000)
