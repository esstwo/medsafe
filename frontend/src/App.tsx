import { useSessionStore } from '@/store/sessionStore'
import { MedicationInput } from '@/components/MedicationInput'
import { ConfirmMedications } from '@/components/ConfirmMedications'

function AnalysisPlaceholder() {
  const { sessionId, medications } = useSessionStore()
  return (
    <div className="max-w-2xl mx-auto py-12 px-4 text-center">
      <h2 className="text-xl font-semibold mb-2">Medications Confirmed</h2>
      <p className="text-slate-500 mb-4">
        Session:{' '}
        <code className="font-mono text-xs bg-slate-100 px-2 py-1 rounded">{sessionId}</code>
      </p>
      <p className="text-slate-500">
        {medications.length} medications confirmed — interaction analysis coming in Week 3.
      </p>
    </div>
  )
}

export default function App() {
  const { currentStep } = useSessionStore()

  return (
    <div className="min-h-screen bg-gray-50">
      {currentStep === 'input' && <MedicationInput />}
      {currentStep === 'confirm' && <ConfirmMedications />}
      {currentStep === 'analysis' && <AnalysisPlaceholder />}
    </div>
  )
}
