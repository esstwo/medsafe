import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useSessionStore } from '@/store/sessionStore'
import type { Interaction, SafetyBriefing } from '@/types'

const SEVERITY_STYLES: Record<Interaction['severity'], string> = {
  major:   'bg-red-100 text-red-800 border-red-200',
  moderate:'bg-orange-100 text-orange-800 border-orange-200',
  minor:   'bg-yellow-100 text-yellow-800 border-yellow-200',
  unknown: 'bg-slate-100 text-slate-600 border-slate-200',
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

interface Props {
  briefing: SafetyBriefing
}

export function SafetyBriefingView({ briefing }: Props) {
  const { setStep } = useSessionStore()
  const flagged = briefing.interactions.filter(ix => ix.severity !== 'unknown')

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
        <button
          onClick={() => setStep('analysis')}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
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
                    <p className="font-medium text-sm">
                      {ix.drug_a.name} + {ix.drug_b.name}
                    </p>
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
        Data sourced from FDA drug labels and DrugBank. Always verify with a licensed pharmacist or physician.
      </p>
    </div>
  )
}
