import { useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { attributeSymptoms } from '@/api/analysis'
import { useSessionStore } from '@/store/sessionStore'
import type { Attribution, FAERSResult, Interaction, SafetyBriefing } from '@/types'

const SEVERITY_STYLES: Record<Interaction['severity'], string> = {
  major:   'bg-red-100 text-red-800 border-red-200',
  moderate:'bg-orange-100 text-orange-800 border-orange-200',
  minor:   'bg-yellow-100 text-yellow-800 border-yellow-200',
  unknown: 'bg-slate-100 text-slate-600 border-slate-200',
}

const LIKELIHOOD_STYLES: Record<Attribution['likelihood'], string> = {
  probable: 'bg-orange-100 text-orange-800',
  possible: 'bg-yellow-100 text-yellow-800',
  unlikely: 'bg-slate-100 text-slate-600',
  unknown:  'bg-slate-100 text-slate-400',
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

function FAERSPanel({ results }: { results: FAERSResult[] }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Adverse Event Reports (FDA FAERS)</CardTitle>
      </CardHeader>
      <CardContent>
        <Alert className="mb-4 border-slate-300 bg-slate-50 py-2">
          <AlertDescription className="text-slate-600 text-xs">
            These counts reflect voluntary adverse event reports submitted to the FDA — not confirmed
            drug causation. Large report counts often reflect high usage, not higher risk.
          </AlertDescription>
        </Alert>
        <div className="space-y-3">
          {results.map((r, i) => (
            <div key={i} className="text-sm">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium capitalize">{r.drug_name}</span>
                {r.data_sparse && (
                  <Badge className="bg-slate-100 text-slate-500 text-xs">sparse data</Badge>
                )}
              </div>
              {r.data_sparse ? (
                <p className="text-slate-400 text-xs">Fewer than 10 reports found — insufficient data to summarise.</p>
              ) : (
                <>
                  <p className="text-slate-500 text-xs">
                    {r.total_reports.toLocaleString()} total reports · {r.serious_outcomes.toLocaleString()} serious
                  </p>
                  {r.top_reactions.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {r.top_reactions.slice(0, 5).map((rx, j) => (
                        <Badge key={j} variant="outline" className="text-xs py-0">{rx}</Badge>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function SymptomResults({ attributions }: { attributions: Attribution[] }) {
  const visible = attributions.filter(a => a.likelihood !== 'unknown' || a.drug_name !== 'unknown')
  if (visible.length === 0) return null
  return (
    <div className="space-y-3 mt-4">
      {visible.map((a, i) => (
        <div key={i} className="border rounded-lg p-3 bg-white">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">{a.symptom}</span>
            <span className="text-slate-400 text-xs">→</span>
            <span className="text-sm">{a.drug_name === 'unknown' ? 'No attribution found' : a.drug_name}</span>
            <Badge className={`${LIKELIHOOD_STYLES[a.likelihood]} text-xs capitalize`}>{a.likelihood}</Badge>
          </div>
          <p className="text-xs text-slate-600">{a.evidence_summary}</p>
          {a.source && (
            <p className="text-xs text-slate-400 mt-1">Source: {a.source.title || a.source.source_type}</p>
          )}
        </div>
      ))}
    </div>
  )
}

interface Props {
  briefing: SafetyBriefing
}

export function SafetyBriefingView({ briefing }: Props) {
  const { setStep, sessionId, medications, symptoms, setSymptoms, symptomAttributions, setSymptomAttributions } = useSessionStore()
  const [symptomLoading, setSymptomLoading] = useState(false)

  const flagged = briefing.interactions.filter(ix => ix.severity !== 'unknown')

  async function handleCheckSymptoms() {
    const symptomList = symptoms.split(/[,\n]+/).map(s => s.trim()).filter(Boolean)
    if (!symptomList.length) return
    setSymptomLoading(true)
    try {
      const attributions = await attributeSymptoms(symptomList, medications, sessionId || '')
      setSymptomAttributions(attributions)
    } finally {
      setSymptomLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <Alert className="border-amber-400 bg-amber-50">
        <AlertDescription className="text-amber-800 text-sm">
          {briefing.disclaimer}
        </AlertDescription>
      </Alert>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Safety Briefing</h1>
          <p className="text-sm text-slate-500 mt-1">
            Generated {formatDate(briefing.generated_at)} · {briefing.medications.length} medications
          </p>
        </div>
        <button onClick={() => setStep('analysis')} className="text-sm text-slate-500 hover:text-slate-700">
          ← Back to interactions
        </button>
      </div>

      {/* Medications */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Your Medications</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1">
            {briefing.medications.map((med, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className="capitalize text-xs">{med.type}</Badge>
                <span className="font-medium">{med.name}</span>
                {med.active_compounds.length > 0 && (
                  <span className="text-slate-400">· {med.active_compounds.join(', ')}</span>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Flagged Interactions */}
      {flagged.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Flagged Interactions
              <span className="ml-2 text-sm font-normal text-slate-500">
                ({flagged.length} of {briefing.interactions.length} pairs)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {flagged.map((ix, i) => (
              <div key={i}>
                {i > 0 && <Separator className="mb-4" />}
                <div className="flex items-start gap-3">
                  <Badge className={`${SEVERITY_STYLES[ix.severity]} border mt-0.5 capitalize shrink-0`}>
                    {ix.severity}
                  </Badge>
                  <div>
                    <p className="font-medium text-sm">{ix.drug_a.name} + {ix.drug_b.name}</p>
                    {ix.mechanism_plain && (
                      <p className="text-sm text-slate-600 mt-1">{ix.mechanism_plain}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* FAERS Adverse Events */}
      {briefing.adverse_events && briefing.adverse_events.length > 0 && (
        <FAERSPanel results={briefing.adverse_events} />
      )}

      {/* Provider Questions */}
      {briefing.provider_questions.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Questions to Ask Your Provider</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3 list-decimal list-inside">
              {briefing.provider_questions.map((q, i) => (
                <li key={i} className="text-sm text-slate-700">{q}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Symptom Checker */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Are you experiencing any symptoms?</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-slate-500 mb-3">
            Enter symptoms to see if they may be associated with your medications.
            Results are hypotheses only — not a diagnosis.
          </p>
          <Textarea
            value={symptoms}
            onChange={e => setSymptoms(e.target.value)}
            placeholder="e.g. nausea, muscle pain, dizziness, headache"
            rows={2}
            className="resize-none mb-3"
          />
          <Button
            onClick={handleCheckSymptoms}
            disabled={symptomLoading || !symptoms.trim()}
            variant="outline"
          >
            {symptomLoading ? 'Analysing…' : 'Check symptoms'}
          </Button>
          {symptomAttributions && <SymptomResults attributions={symptomAttributions} />}
        </CardContent>
      </Card>

      {/* Sources */}
      {briefing.sources.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {briefing.sources.map((src, i) => (
                <li key={i} className="text-xs text-slate-500">
                  {src.title || src.source_type}
                  {src.source_id && ` · ${src.source_id}`}
                  {src.section && ` · ${src.section}`}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-slate-400 text-center">
        Data sourced from FDA drug labels, DrugBank, and FDA FAERS. Always verify with a licensed pharmacist.
      </p>
    </div>
  )
}
