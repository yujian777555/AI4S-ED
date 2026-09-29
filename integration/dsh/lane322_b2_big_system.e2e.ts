/**
 * Lane B2: direct llm.stream with large system message (mimic Agent prompt size).
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

it('lane B2: llm.stream with large system message', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const web = await launchWebScaffold({})
  try {
    const llm: any = (web.ctx as any).llm
    const bigSystem = 'You are an AI agent. '.repeat(200) + ' Reply with exactly PONG.'
    let text = ''
    const kinds: string[] = []
    for await (const chunk of llm.stream({
      provider: 'deepseek-official',
      model: 'deepseek-v4-flash',
      reasoningEffort: 'off',
      maxTokens: 50,
      tools: [],
      messages: [
        { role: 'system', content: [{ type: 'text', text: bigSystem }] },
        { role: 'user', content: [{ type: 'text', text: 'Reply with exactly PONG.' }] },
      ],
    })) {
      kinds.push(chunk?.type ?? '?')
      if (chunk?.text) text += chunk.text
    }
    console.log('LANE_B2', JSON.stringify({ text: text.slice(0, 60), kinds: kinds.slice(0, 15), sysLen: bigSystem.length }))
    expect(text).toContain('PONG')
  } finally {
    await web.close().catch(() => undefined)
  }
}, 120_000)
