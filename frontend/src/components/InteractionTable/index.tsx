import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useSessionStore } from '@/store/sessionStore'
import type { AnalysisResult, Interaction } from '@/types'

const SEVERITY_STYLES: Record<Interaction['severity'], string> = {
  major:   'bg-red-100 text-red-800 border-red-200',
  moderate:'bg-orange-100 text-orange-800 border-orange-200',
  minor:   'bg-yellow-100 text-yellow-800 border-yellow-200',
  unknown: 'bg-slate-100 text-slate-600 border-slate-200',
}

const EVIDENCE_LABEL: Record<string, string> = {
  'well-documented': 'Well-documented',
  'theoretical':     'Theoretical',
  'case-reports':    'Case reports',
  'unknown':         'Unknown',
}

function SeverityBadge({ severity }: { severity: Interaction['severity'] }) {
  return (
    <Badge className={`${SEVERITY_STYLES[severity]} border font-medium capitalize`}>
      {severity}
    </Badge>
  )
}

function InteractionRow({ interaction }: { interaction: Interaction }) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <TableRow className="cursor-pointer hover:bg-slate-50 transition-colors">
          <TableCell className="font-medium">{interaction.drug_a.name}</TableCell>
          <TableCell className="font-medium">{interaction.drug_b.name}</TableCell>
          <TableCell><SeverityBadge severity={interaction.severity} /></TableCell>
          <TableCell className="text-slate-500 text-sm">
            {interaction.evidence_level ? EVIDENCE_LABEL[interaction.evidence_level] : '—'}
          </TableCell>
          <TableCell>
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
          </TableCell>
        </TableRow>
      </CollapsibleTrigger>
      <CollapsibleContent asChild>
        <TableRow>
          <TableCell colSpan={5} className="bg-slate-50 border-t-0 pt-0">
            <div className="py-3 px-2 space-y-3">
              {interaction.mechanism_plain && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                    What this means
                  </p>
                  <p className="text-sm text-slate-700">{interaction.mechanism_plain}</p>
                </div>
              )}
              {interaction.clinical_effect && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                    Clinical effect
                  </p>
                  <p className="text-sm text-slate-600">{interaction.clinical_effect}</p>
                </div>
              )}
              {interaction.mechanism && interaction.mechanism !== interaction.mechanism_plain && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                    Mechanism
                  </p>
                  <p className="text-sm text-slate-500 italic">{interaction.mechanism}</p>
                </div>
              )}
              {interaction.source && (
                <div className="pt-1 border-t border-slate-200">
                  <p className="text-xs text-slate-400">
                    Source: {interaction.source.type === 'drugbank' ? 'DrugBank' : 'FDA Drug Label'}
                    {interaction.source.section ? ` · ${interaction.source.section}` : ''}
                    {interaction.source.id ? ` · ID: ${interaction.source.id}` : ''}
                  </p>
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface Props {
  result: AnalysisResult
}

export function InteractionTable({ result }: Props) {
  const { setStep } = useSessionStore()
  const { interactions, medications } = result

  const pairCount = (medications.length * (medications.length - 1)) / 2
  const flaggedCount = interactions.filter(i => i.severity !== 'unknown').length

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <Alert className="mb-6 border-amber-400 bg-amber-50">
        <AlertDescription className="text-amber-800 text-sm">
          MedSafe provides information only. Always consult your healthcare provider before making
          any medication changes. Absence of a listed interaction does not confirm safety.
        </AlertDescription>
      </Alert>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Interaction Analysis</h2>
          <p className="text-sm text-slate-500 mt-1">
            {medications.length} medications · {pairCount} pair{pairCount !== 1 ? 's' : ''} checked
            {flaggedCount > 0 && (
              <span className="ml-2 text-orange-600 font-medium">
                · {flaggedCount} interaction{flaggedCount !== 1 ? 's' : ''} flagged
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => setStep('confirm')}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back
        </button>
      </div>

      {interactions.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-slate-600 font-medium">No interactions found</p>
          <p className="text-sm text-slate-400 mt-2">
            No known interactions were identified between these medications.
            Absence of data does not confirm safety — discuss with your healthcare provider.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border bg-white overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Drug A</TableHead>
                <TableHead>Drug B</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Evidence</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {interactions.map((interaction, i) => (
                <InteractionRow key={i} interaction={interaction} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <p className="mt-6 text-xs text-slate-400 text-center">
        Data sourced from FDA drug labels and DrugBank open data. Always verify with a licensed pharmacist.
      </p>
    </div>
  )
}
