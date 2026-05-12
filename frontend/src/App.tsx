import { useSessionStore } from '@/store/sessionStore'
import { MedicationInput } from '@/components/MedicationInput'
import { ConfirmMedications } from '@/components/ConfirmMedications'
import { InteractionTable } from '@/components/InteractionTable'
import { SafetyBriefingView } from '@/components/SafetyBriefing'

export default function App() {
  const { currentStep, analysisResult, briefing } = useSessionStore()

  return (
    <div className="min-h-screen bg-gray-50">
      {currentStep === 'input' && <MedicationInput />}
      {currentStep === 'confirm' && <ConfirmMedications />}
      {currentStep === 'analysis' && analysisResult && (
        <InteractionTable result={analysisResult} />
      )}
      {currentStep === 'briefing' && briefing && (
        <SafetyBriefingView briefing={briefing} />
      )}
    </div>
  )
}
