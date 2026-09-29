/**
 * Phase 3.2.2 Lane B: Web scaffold direct ctx.llm.stream (no Agent, no preset).
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')

it('lane B: scaffold direct llm.stream returns PONG', async () => {
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const web = await launchWebScaffold({})
  try {
    const llm: any = (web.ctx as any).llm
    let text = ''
    const kinds: string[] = []
    let lastChunk: any = null
    try {
      for await (const chunk of llm.stream({
        provider: 'deepseek-official',
        model: 'deepseek-v4-flash',
        reasoningEffort: 'off',
        maxTokens: 50,
        tools: [],
        messages: [
          { role: 'user', content: [{ type: 'text', text: 'Reply with exactly PONG.' }] },
        ],
      })) {
        kinds.push(chunk?.type ?? '?')
        lastChunk = chunk
        if (chunk?.text) text += chunk.text
        if (chunk?.delta?.text) text += chunk.delta.text
        if (chunk?.content && typeof chunk.content === 'string') text += chunk.content
      }
    } catch (streamErr) {
      console.log('LANE_B_STREAM_ERR', String(streamErr).slice(0, 400))
      throw streamErr
    }
    console.log('LANE_B_RESULT', JSON.stringify({
      text: text.slice(0, 120),
      kinds: kinds.slice(0, 20),
      kindCount: kinds.length,
      lastType: lastChunk?.type,
      lastKeys: lastChunk ? Object.keys(lastChunk).slice(0, 15) : [],
    }))
    expect(text).toContain('PONG')
  } finally {
    await web.close().catch(() => undefined)
  }
}, 120_000)
