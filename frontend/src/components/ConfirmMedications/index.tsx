import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { confirmMedications, normalizeMedications } from '@/api/medications'
import { runFullAnalysis } from '@/api/analysis'
import { useSessionStore } from '@/store/sessionStore'
import type { Medication } from '@/types'

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  if (value >= 0.9) return <Badge className="bg-green-100 text-green-800">{pct}%</Badge>
  if (value >= 0.7) return <Badge className="bg-yellow-100 text-yellow-800">{pct}%</Badge>
  return <Badge className="bg-red-100 text-red-800">{pct}%</Badge>
}

function TypeBadge({ type }: { type: Medication['type'] }) {
  const styles: Record<Medication['type'], string> = {
    prescription: 'bg-blue-100 text-blue-800',
    otc: 'bg-slate-100 text-slate-700',
    supplement: 'bg-purple-100 text-purple-800',
  }
  return <Badge className={styles[type]}>{type}</Badge>
}

export function ConfirmMedications() {
  const {
    medications, setMedications, setStep, setSessionId,
    isLoading, setLoading, warnings, setAnalysisResult,
  } = useSessionStore()

  const [editValues, setEditValues] = useState<Record<number, string>>({})

  async function handleNameBlur(index: number) {
    const newName = editValues[index]
    if (!newName || newName === medications[index].input_text) return

    const result = await normalizeMedications(newName)
    if (!result.blocked && result.medications[0]) {
      const updated = [...medications]
      updated[index] = result.medications[0]
      setMedications(updated)
      setEditValues((prev) => {
        const next = { ...prev }
        delete next[index]
        return next
      })
    }
  }

  async function handleConfirm() {
    setLoading(true)
    try {
      const confirmed = await confirmMedications(medications)
      setSessionId(confirmed.session_id)
      const analysis = await runFullAnalysis(confirmed.medications, confirmed.session_id)
      setAnalysisResult(analysis)
      setStep('analysis')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <Alert className="mb-6 border-amber-400 bg-amber-50">
        <AlertDescription className="text-amber-800 text-sm">
          MedSafe provides information only. Always consult your healthcare provider before making
          medication changes.
        </AlertDescription>
      </Alert>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Confirm Your Medications</h2>
          <p className="text-sm text-slate-500 mt-1">
            Review the resolved names. Edit any that look wrong, then confirm.
          </p>
        </div>
        <button
          onClick={() => setStep('input')}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="mb-4 space-y-2">
          {warnings.map((w, i) => (
            <Alert key={i} className="border-yellow-400 bg-yellow-50">
              <AlertDescription className="text-yellow-800 text-sm">{w}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      <div className="rounded-lg border bg-white overflow-hidden mb-6">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead>Your Input</TableHead>
              <TableHead>Resolved Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>RXCUI</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {medications.map((med, i) => (
              <TableRow key={i}>
                <TableCell className="text-slate-500 text-sm">{med.input_text}</TableCell>
                <TableCell>
                  <Input
                    value={editValues[i] ?? med.name}
                    onChange={(e) => setEditValues((prev) => ({ ...prev, [i]: e.target.value }))}
                    onBlur={() => handleNameBlur(i)}
                    className="h-8 text-sm"
                  />
                </TableCell>
                <TableCell>
                  <TypeBadge type={med.type} />
                </TableCell>
                <TableCell>
                  <ConfidenceBadge value={med.confidence} />
                </TableCell>
                <TableCell className="text-slate-400 text-xs font-mono">
                  {med.rxcui ?? '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Button onClick={handleConfirm} disabled={isLoading} className="w-full sm:w-auto">
        {isLoading
          ? 'Analysing interactions…'
          : `Confirm & Check Interactions`}
      </Button>
    </div>
  )
}
