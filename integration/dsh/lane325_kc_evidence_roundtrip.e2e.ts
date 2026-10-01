/**
 * Phase 4.3.2: strict mounted Agent evidence live acceptance.
 *
 * - No soft-pass: live prerequisites present + zero tool/call => Vitest FAILED.
 * - Separate markers, each only after its own assertion.
 * - Direct-vs-DSH comparison for retrieve + validate (via Python direct ref).
 * - Strict tool/call <-> tool/result linking by seq/callId.
 * - Up to 3 live attempts with diagnostics.
 *
 * Markers (printed only after the matching assertion passes):
 *   LANE325_DISCOVERY_OK=1
 *   LANE325_RETRIEVE_TOOLCALL_OK=1
 *   LANE325_RETRIEVE_RESULT_OK=1
 *   LANE325_RETRIEVE_IDENTITY_MATCH=1
 *   LANE325_VALIDATE_TOOLCALL_OK=1
 *   LANE325_VALIDATE_RESULT_OK=1
 *   LANE325_VALIDATE_POLICY_MATCH=1
 *   LANE325_LIVE_COMPLETE=1
 */
import { it, expect } from 'vitest'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'

const DSH_SRC = process.env.DSH_SRC
if (!DSH_SRC) throw new Error('DSH_SRC env var is required')
const AI4S_ED_ROOT = process.env.AI4S_ED_ROOT
if (!AI4S_ED_ROOT) throw new Error('AI4S_ED_ROOT env var is required')

const MODEL = process.env.DSH_MODEL || 'deepseek-v4-flash'
const PROVIDER = process.env.DSH_PROVIDER || 'deepseek-official'
const PRESET_ID = 'knowledge-curator'
const TOOL_CURATE = 'mcp__knowledge_curator__curate_assertion_set'
const TOOL_RETRIEVE = 'mcp__knowledge_curator__retrieve_evidence'
const TOOL_VALIDATE = 'mcp__knowledge_curator__validate_retrieved_claims'
const FIXTURE_QUERY = '双极膜电渗析 能耗'
const MAX_ATTEMPTS = 3

function marker(name: string) {
  console.log(name)
}

function redact(s: string): string {
  let out = s
  const key = process.env.DEEPSSEEK_API_KEY || process.env.DEEPSEEK_API_KEY
  if (key) out = out.split(key).join('***')
  return out
}

/** Strict tool/call -> linked tool/result by seq/callId. */
function linkToolResult(events: any[], toolName: string): {
  calls: any[]
  results: any[]
  payload: any | null
} {
  const calls = events.filter(
    (e: any) => e.type === 'tool/call' && e.data?.name === toolName,
  )
  const callSeqs = new Set(calls.map((e: any) => String(e.seq)))
  const callIds = new Set(calls.map((e: any) => e.data?.callId).filter(Boolean))
  const results = events.filter((e: any) => {
    if (e.type !== 'tool/result') return false
    const src = e.sourceEventSeqs ?? e.data?.sourceEventSeqs ?? []
    const seqs = Array.isArray(src) ? src.map(String) : [String(src)]
    const cid = e.data?.message?.source?.callId ?? e.data?.callId
    return seqs.some((s: string) => callSeqs.has(s)) || (cid && callIds.has(cid))
  })
  if (!results.length) return { calls, results: [], payload: null }

  const content = results[0].data?.message?.content ?? []
  const texts: string[] = []
  for (const block of content) {
    if (block?.content) for (const sub of block.content) if (sub?.text) texts.push(sub.text)
    else if (block?.text) texts.push(block.text)
  }
  const joined = texts.join('')
  let payload: any = null
  try {
    payload = JSON.parse(joined)
  } catch {
    try {
      const outer = content[0]?.content ?? []
      const inner = (Array.isArray(outer) ? outer : []).map((b: any) => b.text ?? '').join('')
      payload = JSON.parse(inner)
    } catch {
      try {
        const arr = JSON.parse(joined)
        const inner = (Array.isArray(arr) ? arr : []).map((b: any) => b.text ?? '').join('')
        payload = JSON.parse(inner)
      } catch {
        payload = null
      }
    }
  }
  return { calls, results, payload }
}

function directRef(mode: 'retrieve' | 'validate'): any {
  const py = process.env.AI4S_KC_PYTHON || 'python'
  const out = execFileSync(
    py,
    ['-m', 'integration.dsh.direct_evidence_ref', mode],
    {
      cwd: AI4S_ED_ROOT,
      encoding: 'utf-8',
      env: {
        ...process.env,
        KC_EVIDENCE_INTEGRATION_FIXTURE: '1',
        PYTHONPATH: AI4S_ED_ROOT,
      },
      maxBuffer: 8 * 1024 * 1024,
    },
  )
  return JSON.parse(out)
}

function sameSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort().join('|')
  const sb = [...b].sort().join('|')
  return sa === sb
}

it('strict mounted Agent evidence live acceptance', async () => {
  const hasCredential = Boolean(process.env.DEEPSSEEK_API_KEY || process.env.DEEPSEEK_API_KEY)
  const { launchWebScaffold } = await import(join(DSH_SRC, 'apps/web/tests/scaffold.ts'))
  const llm = await import('@deepseek-ai/dsh-llm')
  const createUserMessage = (llm as any).createUserMessage

  const web = await launchWebScaffold({
    profile: {
      packages: [{ dir: join(AI4S_ED_ROOT, 'dsh', 'knowledge-curator'), enabled: true }],
    },
  })

  try {
    const ctx: any = web.ctx
    process.env.AI4S_KC_PYTHON = process.env.AI4S_KC_PYTHON || 'python'
    process.env.AI4S_KC_WORKSPACE = process.env.AI4S_KC_WORKSPACE || AI4S_ED_ROOT
    // SI-1.5-R1: production bootstrap uses AI4S_SYSTEM_ADAPTER_FACTORY
    process.env.AI4S_SYSTEM_ADAPTER_FACTORY =
      'integration.system.fixtures.dsh_provider:create_provider_bundle'

    const handle = await ctx.agents.create({
      sessionId: `kc-evidence-strict-${Date.now()}`,
      meta: { cwd: web.workspaceCwd, agentPreset: PRESET_ID },
      agentOptions: { provider: PROVIDER, model: MODEL, maxTokens: 1500 },
      setup: async (agentCtx: any) => {
        await ctx.agentPresets.mount(agentCtx, PRESET_ID)
      },
    })

    const composed = ctx.agentPresets.composedPreset(handle.agent.ctx)
    expect(composed).toBe(PRESET_ID)
    const schemas = ctx.tools.schemas(handle.agent) ?? []
    const names = schemas.map((s: any) => s.name)
    expect(names).toContain(TOOL_CURATE)
    expect(names).toContain(TOOL_RETRIEVE)
    expect(names).toContain(TOOL_VALIDATE)
    marker('LANE325_DISCOVERY_OK=1')

    // ---- live phase ----
    if (!hasCredential) {
      console.log('LANE325_NO_CREDENTIAL=1')
      console.log('LANE325_LIVE_NOT_RUN_ENV=1')
      return
    }

    // ---------- retrieve_evidence (up to 3 attempts) ----------
    let retrieveLinked: ReturnType<typeof linkToolResult> | null = null
    let lastTypes: string[] = []
    let attempts = 0
    for (let i = 1; i <= MAX_ATTEMPTS; i++) {
      attempts = i
      handle.agent.followup(
        createUserMessage({
          content: [
            {
              type: 'text',
              text:
                `You MUST call the tool named exactly ${TOOL_RETRIEVE} right now. ` +
                `Arguments JSON: {"request":{"query":"${FIXTURE_QUERY}","top_k":5,"coverage_keys":["sq1"],"required_coverage_keys":["sq1"]}}. ` +
                `Do not answer from memory. Call the tool first.`,
            },
          ],
          source: { kind: 'user' },
        }),
      )
      await handle.agent.whenIdle()
      const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
      lastTypes = [...new Set(events.map((e: any) => e.type))]
      const linked = linkToolResult(events, TOOL_RETRIEVE)
      console.log(
        redact(
          `LANE325_RETRIEVE_ATTEMPT=${i} calls=${linked.calls.length} results=${linked.results.length} types=${JSON.stringify(lastTypes)}`,
        ),
      )
      if (linked.calls.length >= 1) {
        marker('LANE325_RETRIEVE_TOOLCALL_OK=1')
        if (linked.results.length >= 1 && linked.payload) {
          marker('LANE325_RETRIEVE_RESULT_OK=1')
          retrieveLinked = linked
          break
        }
      }
    }
    if (!retrieveLinked) {
      console.log(redact(`LANE325_RETRIEVE_FAILED attempts=${attempts} types=${JSON.stringify(lastTypes)}`))
      throw new Error('retrieve_evidence: no linked structured tool result after bounded attempts')
    }

    // Direct vs DSH identity (SI-1.5-R2: fixture marker boundary, not equality)
    const directR = directRef('retrieve')
    const obsBundle = retrieveLinked.payload?.evidence_bundle
    const obsIds = (obsBundle?.evidence_records ?? []).map((r: any) => r.chunk_id)
    // R2-01: direct legacy reference is integration fixture; mounted DSH is not.
    const directFixture = Boolean(directR?.identity?.integration_fixture)
    const dshFixture = Boolean(retrieveLinked.payload?.integration_fixture)
    if (!directFixture) {
      throw new Error('direct reference must report integration_fixture=true')
    }
    if (dshFixture) {
      throw new Error('mounted DSH production path must report integration_fixture=false')
    }
    const identityOk =
      directR?.identity?.chunk_ids &&
      sameSet(directR.identity.chunk_ids, obsIds) &&
      JSON.stringify(directR.identity.coverage_keys) ===
        JSON.stringify(obsBundle?.coverage_keys ?? []) &&
      Boolean(directR.identity.abstain) === Boolean(obsBundle?.abstain?.abstain)
    if (!identityOk) {
      console.log(
        redact(
          `LANE325_IDENTITY_DIFF direct=${JSON.stringify(directR.identity)} observed_chunk_ids=${JSON.stringify(obsIds)}`,
        ),
      )
      throw new Error('direct vs DSH retrieve identity mismatch')
    }
    marker('LANE325_RETRIEVE_IDENTITY_MATCH=1')

    // ---------- validate_retrieved_claims ----------
    const anchor = (obsIds[0] as string) || 'R1-F1'
    let validateLinked: ReturnType<typeof linkToolResult> | null = null
    let vAttempts = 0
    for (let i = 1; i <= MAX_ATTEMPTS; i++) {
      vAttempts = i
      handle.agent.followup(
        createUserMessage({
          content: [
            {
              type: 'text',
              text:
                `You MUST call the tool named exactly ${TOOL_VALIDATE} right now. ` +
                `Arguments JSON: {"payload":{"query":"${FIXTURE_QUERY}","claims":[` +
                `{"claim_id":"C1","text":"BPM energy about 1.4 kWh/m3","anchor_chunk_ids":["${anchor}"]},` +
                `{"claim_id":"C2","text":"fabricated","anchor_chunk_ids":["NO-SUCH-CHUNK"]}` +
                `]}}. Do not answer from memory. Call the tool first.`,
            },
          ],
          source: { kind: 'user' },
        }),
      )
      await handle.agent.whenIdle()
      const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
      const linked = linkToolResult(events, TOOL_VALIDATE)
      console.log(
        redact(
          `LANE325_VALIDATE_ATTEMPT=${i} calls=${linked.calls.length} results=${linked.results.length}`,
        ),
      )
      if (linked.calls.length >= 1) {
        marker('LANE325_VALIDATE_TOOLCALL_OK=1')
        if (linked.results.length >= 1 && linked.payload) {
          marker('LANE325_VALIDATE_RESULT_OK=1')
          validateLinked = linked
          break
        }
      }
    }
    if (!validateLinked) {
      console.log(`LANE325_VALIDATE_FAILED attempts=${vAttempts}`)
      throw new Error('validate_retrieved_claims: no linked structured tool result')
    }

    const directV = directRef('validate')
    // R2-01: same fixture-marker boundary on the validate path.
    if (Boolean(validateLinked.payload?.integration_fixture)) {
      throw new Error('mounted DSH validate must report integration_fixture=false')
    }
    const byId = Object.fromEntries(
      (validateLinked.payload?.claim_results ?? []).map((c: any) => [c.claim_id, c]),
    )
    const d1 = directV.identity?.C1
    const d2 = directV.identity?.C2
    const policyOk =
      d1 &&
      byId.C1?.policy?.policy === d1.policy &&
      Boolean(byId.C1?.abstain?.abstain) === Boolean(d1.abstain) &&
      d2 &&
      sameSet(byId.C2?.unresolved_anchor_chunk_ids ?? [], d2.unresolved ?? []) &&
      byId.C2?.policy?.policy === d2.policy &&
      Boolean(byId.C2?.abstain?.abstain) === Boolean(d2.abstain) &&
      Array.isArray(d2.h1_types) &&
      (d2.h1_types.length > 0) === ((byId.C2?.h1?.findings ?? []).length > 0) &&
      (d2.h1_types.length === 0 ||
        d2.h1_types.every((t: string) =>
          (byId.C2?.h1?.findings ?? []).some((f: any) => f.type === t),
        ))
    if (!policyOk) {
      console.log(
        redact(
          `LANE325_POLICY_DIFF direct=${JSON.stringify(directV.identity)} observed=${JSON.stringify({ C1: byId.C1, C2: byId.C2 })}`,
        ),
      )
      throw new Error('direct vs DSH validate policy mismatch')
    }
    marker('LANE325_VALIDATE_POLICY_MATCH=1')
    marker('LANE325_LIVE_COMPLETE=1')
    console.log(`LANE325_ATTEMPTS retrieve=${attempts} validate=${vAttempts}`)
  } finally {
    try {
      await web.dispose?.()
    } catch {
      /* ignore */
    }
  }
})
