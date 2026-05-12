import { useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { normalizeMedications } from '@/api/medications'
import { useSessionStore } from '@/store/sessionStore'

export function MedicationInput() {
  const [text, setText] = useState('')
  const [emergencyMsg, setEmergencyMsg] = useState<string | null>(null)

  const { setMedications, setStep, setLoading, isLoading, setWarnings } = useSessionStore()

  async function handleSubmit() {
    if (!text.trim()) return
    setLoading(true)
    setEmergencyMsg(null)
    try {
      const result = await normalizeMedications(text)
      if (result.blocked) {
        setEmergencyMsg(result.message)
        return
      }
      setMedications(result.medications)
      setWarnings(result.warnings)
      setStep('confirm')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-4">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">MedSafe</h1>
        <p className="text-slate-500">AI-powered drug interaction &amp; safety advisor</p>
      </div>

      {emergencyMsg && (
        <Alert className="mb-6 border-red-500 bg-red-50">
          <AlertTitle className="text-red-700 font-semibold">Emergency Notice</AlertTitle>
          <AlertDescription className="text-red-700">{emergencyMsg}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Enter Your Medications</CardTitle>
          <CardDescription>
            Include prescriptions, over-the-counter drugs, and supplements. One per line or
            comma-separated.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Lipitor 10mg, baby aspirin, turmeric, melatonin 5mg"
            rows={6}
            className="resize-none"
            disabled={isLoading}
          />
          <Button onClick={handleSubmit} disabled={isLoading || !text.trim()} className="w-full">
            {isLoading ? 'Looking up medications…' : 'Check Interactions'}
          </Button>
        </CardContent>
      </Card>

      <p className="mt-6 text-xs text-slate-400 text-center">
        MedSafe is for informational purposes only and does not constitute medical advice.
      </p>
    </div>
  )
}
