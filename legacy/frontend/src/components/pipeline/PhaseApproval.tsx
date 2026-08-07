/**
 * Phase Approval component - modal for reviewing and approving phase outputs.
 */

import React, { useState } from 'react'

interface PhaseApprovalProps {
  phase: string
  phaseName: string
  outputPreview: Record<string, unknown>
  onApprove: () => void
  onReject: (reason: string) => void
  onClose: () => void
}

export const PhaseApproval: React.FC<PhaseApprovalProps> = ({
  phase,
  phaseName,
  outputPreview,
  onApprove,
  onReject,
  onClose
}) => {
  const [rejectionReason, setRejectionReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  const handleReject = () => {
    if (rejectionReason.trim()) {
      onReject(rejectionReason)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-semibold text-gray-800">
            Review: {phaseName}
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Review the output and approve to continue or reject to regenerate.
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-4">
            {Object.entries(outputPreview).map(([key, value]) => (
              <div key={key} className="border-b pb-4">
                <h3 className="font-medium text-gray-700 capitalize mb-2">
                  {key.replace(/_/g, ' ')}
                </h3>
                <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                  {typeof value === 'string' ? (
                    <p className="whitespace-pre-wrap">{value}</p>
                  ) : Array.isArray(value) ? (
                    <ul className="list-disc pl-4">
                      {value.slice(0, 5).map((item, i) => (
                        <li key={i}>{String(item)}</li>
                      ))}
                      {value.length > 5 && (
                        <li className="text-gray-400">
                          ...and {value.length - 5} more
                        </li>
                      )}
                    </ul>
                  ) : (
                    <pre className="text-xs overflow-x-auto">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Rejection form */}
          {showRejectForm && (
            <div className="mt-4 p-4 bg-red-50 rounded-lg">
              <label className="block text-sm font-medium text-red-700 mb-2">
                Rejection Reason
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                className="w-full border border-red-300 rounded-md p-2 text-sm"
                rows={3}
                placeholder="Explain what should be changed..."
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>

          {!showRejectForm ? (
            <>
              <button
                onClick={() => setShowRejectForm(true)}
                className="px-4 py-2 bg-red-100 text-red-700 rounded-md hover:bg-red-200"
              >
                Reject
              </button>
              <button
                onClick={onApprove}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                Approve
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setShowRejectForm(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Back
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectionReason.trim()}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default PhaseApproval
