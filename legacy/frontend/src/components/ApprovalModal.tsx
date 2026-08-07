import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

interface ApprovalModalProps {
  isOpen: boolean
  onClose: () => void
  onApprove: () => void
  onRegenerate: (guidance: string) => void
  content: string
  title: string
  isLoading?: boolean
}

export default function ApprovalModal({
  isOpen,
  onClose,
  onApprove,
  onRegenerate,
  content,
  title,
  isLoading,
}: ApprovalModalProps) {
  const [showGuidance, setShowGuidance] = useState(false)
  const [guidance, setGuidance] = useState('')

  if (!isOpen) return null

  const handleRegenerate = () => {
    if (guidance.trim()) {
      onRegenerate(guidance)
      setGuidance('')
      setShowGuidance(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            disabled={isLoading}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-4 overflow-y-auto max-h-[60vh]">
          <div className="prose">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>

        {showGuidance && (
          <div className="px-6 py-4 border-t">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Guidance for regeneration
            </label>
            <textarea
              value={guidance}
              onChange={(e) => setGuidance(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={3}
              placeholder="Provide specific feedback for improvement..."
            />
          </div>
        )}

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t bg-gray-50">
          {showGuidance ? (
            <>
              <button
                onClick={() => setShowGuidance(false)}
                className="px-4 py-2 text-gray-700 hover:text-gray-900"
                disabled={isLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleRegenerate}
                disabled={isLoading || !guidance.trim()}
                className="px-4 py-2 bg-yellow-500 text-white rounded-md hover:bg-yellow-600 disabled:opacity-50"
              >
                {isLoading ? 'Regenerating...' : 'Regenerate'}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setShowGuidance(true)}
                className="px-4 py-2 text-yellow-600 hover:text-yellow-700"
                disabled={isLoading}
              >
                Regenerate with feedback
              </button>
              <button
                onClick={onApprove}
                disabled={isLoading}
                className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:opacity-50"
              >
                {isLoading ? 'Approving...' : 'Approve'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
