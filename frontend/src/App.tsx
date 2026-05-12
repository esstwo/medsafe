import { useSessionStore } from '@/store/sessionStore'
import { MedicationInput } from '@/components/MedicationInput'
import { ConfirmMedications } from '@/components/ConfirmMedications'
import { InteractionTable } from '@/components/InteractionTable'

export default function App() {
  const { currentStep, analysisResult } = useSessionStore()

  return (
    <div className="min-h-screen bg-gray-50">
      {currentStep === 'input' && <MedicationInput />}
      {currentStep === 'confirm' && <ConfirmMedications />}
      {currentStep === 'analysis' && analysisResult && (
        <InteractionTable result={analysisResult} />
      )}
    </div>
  )
}
